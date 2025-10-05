'''
Asynchronous reaction executor.
'''
from __future__ import annotations

from abc import abstractmethod
from asyncio import (Queue, Task, create_task, QueueShutDown, sleep,
                     get_event_loop)
from dataclasses import dataclass, field
from itertools import count
from logging import Logger, getLogger
from typing import Callable, Any, Optional, Coroutine, Tuple, Awaitable

from .error import (ExecutorAlreadyStarted, ExecutorNotStarted,
                    ExecutorAlreadyComplete)
from .field import BoundField, Field, FieldManagerMeta
from .logging_config import VERBOSE
from asyncio.exceptions import CancelledError


__all__ = ['Reactant']


logger: Logger = getLogger('whenstate.executor')


type AsyncReaction[C, T] = Callable[[C, Field[C, T], T, T],
                                    Coroutine[None, None, None]]
'''
AsyncReaction is the type for functions that implement reactions.
'''


# TODO - ReactionExecutor and Reactant are very tightly coupled and should be
#        better encapsulated. The done-ness of the Reactant is entirely
#        controlled by ReactionExecutor.complete, which shadows the task
#        future and may be able to be cleaned up. This may remove the need for
#        the task done callbacks. Executor and Reactant are separate entities
#        to allow reactants to share executors to provide concurrency control.
class ReactionExecutor[C: "Reactant", T]():
    '''
    ReactionExecutor executes reactions submitted by Reactants. It is separate
    from Reactant to allow multiple reactants to share the same executor to
    allow the executor to act as a means of providing other reactions
    consistent views of the fields managed by the executor.
    todo - figure out exactly how this management happens). 
    todo - move start/stop from Reactant? Force users to manage
           ReactionExecutors? Part of cleaning up the tight coupling.

    ReactionExecutor has a queue and a task. The queue contains the coroutines
    for the reactions to execute, while the task drains the queue and executes
    the coroutines sequentially.

    It provides concurrency control. The executor processes the reactions in
    the order they are submitted sequentially. The reactions are run
    asynchronously with respect to what is being reacted to, but synchronously
    with respect to the other reactions in the queue.

    Reactions that need to run concurrently with other reactions may create
    Tasks or callbacks to perform their work asynchronously with
    respect to this executor. While possible, it is recommended to not submit
    reactions to the executor directly, but rather incorporate this into the
    Field state and use the predicate facility to create reactions. No
    management of tasks created by reactions is provided.
    '''

    task: Optional[Task] = None
    '''the task that is processing the queue to execute reactions'''

    queue: Queue[Tuple[int, C, Coroutine[None, None, T], Any]]
    '''
    The queue of reactions to execute.
    TODO - The Tuple has grown to the point an actual class makes sense.
           Initially the queue only contained the coroutine and was 'fast' in
           that scheduling and executing a reaction didn't require creation of
           a wrapper object. But, that is no longer the case...the tuple has to
           be created, so it might as well just be a custom object that is
           readable.
    Tuple elements are:
        [0] - the id of the reaction (for logging)
        [1] - the instance the reaction is called on
              (todo - is actually the instance of the field that changed)
              stop() is called on this if the reaction raises an exception
        [2] - the coroutine that implements the reaction (*not* the coroutine
              function, but the coroutine the function returns)
        [3] - the args (used only for logging)
    '''

    _ids: count = count()
    '''
    _ids assigns a unique id to each reaction handled by the executor. It is
    used only for informational purposes, but this may change if there is a
    need. It is a class member, not instance, so reaction ids are unique within
    a process. Log messages should include the assigned id to aid in log
    analysis.
    '''
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    @staticmethod
    def react(reaction: AsyncReaction[C, T],
              instance: C,
              # TODO - should be the instance of the class that defined the reaction, not the instance of the class that field change triggered reaction
              bound_field: BoundField[C, T],
              old: T, new: T) -> None:
        '''reaction that asynchronously executes the reaction'''
        # The weirdness of this being a @staticmethod that gets its self from
        # the instance is so this method can be used as a @partial wrapped
        # predicate reaction rather than having an extra method do this before
        # calling # this method. While a @partial wraps this to pass the
        # reaction arg, it is created from a @classmethod that doesn't have the
        # actual state to get the _reaction_executor from.
        # Microbenchmarking on stock Mac OS build of python 3.13.7 shows
        # partial is significantly faster (22%) than an intermediate function:
        #     def foo(a): ...
        #     def foo_func(): return foo(1)  # 43.3 ns
        #     foo_partial = partial(foo, 1)  # 33.8 ns

        # Get self and assert state is acceptable.
        self = instance._reaction_executor
        assert self.task, "ReactionExecutor not start()'ed"

        id_ = next(self._ids)

        try:
            coro = reaction(instance, bound_field.field, old, new)
            self.queue.put_nowait((id_,
                                   bound_field.instance,
                                   coro,
                                   (bound_field, old, new)))
            instance._logger.log(VERBOSE,
                '%d scheduled %s(..., %s,  %s)',
                id_, reaction.__qualname__, old, new)
        except Exception:
            instance._logger.exception(
                '%d failed to schedule %s (..., %s,  %s)',
                id_, reaction.__qualname__, old, new)
            raise

    ###########################################################################
    # Task life cycle:
    #
    # Task completion is asynchronous to allow scheduled reactions to execute.
    # A clean shutdown is performed by stop() calling the shutdown() method on
    # the queue to stop accepting reactions. When the queue is empty the
    # reaction_executor() loop receives a QueueShutDown error and returns. The
    # task is the awaitable provided for awaiting completion so tasks waiting
    # will unblock.
    # However, to ensure a timely shutdown stop() has a default timeout= kwarg
    # that specifies the amount of time to wait for a clean shutdown. If the
    # task has not completed after that timeout a callback created by stop()
    # executes to call cancel() on the task, causing the coroutine being
    # executed by the task to receive a CancelledError. This error is raised
    # to the task and will be presented to waiters.
    # For completeness, all other error raised by a reaction are also raised
    # to the task and raised to waiters.
    ###########################################################################

    def start(self) -> Awaitable:
        if self.task is not None:
            raise ExecutorAlreadyStarted()
        self.task = create_task(self.execute_reactions())
        return self.task


    def stop(self, timeout: Optional[float]):
        '''stop the reaction queue with timeout (defaults to 2 seconds)'''
        self.queue.shutdown()

        # Create a callback to cancel the task if a timeout is specified.
        if timeout is not None:
            loop = get_event_loop()
            if timeout is not None:
                def _cancel_task():
                    if not self.task.done():
                        logger.error(f'{self} cancelled after shutdown '
                                     f'took more than {timeout}s')
                        self.task.cancel()
                loop.call_later(timeout, _cancel_task)

    async def execute_reactions(self) -> None:
        '''
        Queue worker that gets pending tasks from the queue and executes
        them.

        The pending tasks are processed synchronously.
        '''
        while True:
            try:
                # TODO - get rid of everything but the coro:
                #        id_ and args are only for "calling" log
                #            replace with fmt string that the various logs for
                #            a specific reaction pass around and things fill
                #            in the action pertaining to the reaction:
                #        instance only used to get the logger
                #    Maybe the solution is to enable a debug mode that passes
                #    the details for logging and when not in debug it passes
                #    the coro instead of everything. Maye have different
                #    executor classes that can be chosen (i.e. "give me speed"
                #    vs "give me insight").
                (id_, instance, coro, args) = await self.queue.get()
            except QueueShutDown:
                logger.info(f'{self} stopped')
                break

            try:
                instance._logger.debug(f'%s calling %s(%s)',
                    id_, coro.__qualname__, str(args))
                await coro
                await sleep(0)
            except CancelledError as ce:
                logger.exception(f'{self} stopped with error.', exc_info=ce)
                raise  # CancelledError needs to be propagated
            except Exception as exc:
                # A failure in a reaction means the state is inconsistent.
                # Log the executor is stopped and raise the error to allow
                # waiters to see it.
                logger.exception(f'{self} stopped with error.', exc_info=exc)
                raise
            finally:
                self.queue.task_done()

@dataclass
class Reactant(metaclass=FieldManagerMeta):
    '''
    Base class that allows classes to react asynchronously to predicates that
    become true.

    Usage:
    class Counter(Reactant):
        """A counter that spins until stopped"""
        count: Field[Counter, int] = Field(-1)

        @ count != -1
        async defcounter(self, bound_field: BoundField[Counter, int],
                 old: int, new: int) -> None:
            self.count += 1

        def _start(self):
            'transition from initial state, called during start()'
            self.count = 0

    async def run_counter_for_awhile():
        counter = Counter()
        counter_task = asyncio.create_task(counter.start())
        ....
        counter.stop()
        await counter_task

    Reactions are called asynchronously in the Reactant's reaction executor.
    '''
    # todo - a reaction_executor for instances introduces an ambiguity of
    #        which instances executor predicate reactions will be executed
    #        in, meaning it actually *is* possible for reactions to do dirty
    #        reads if a predicate contains multiple reaction executors.
    #        Fix this by defining a better executor management strategy.
    #          - global - yuck,  this would have the effect of serializaiong
    #                     all reactions. This isn't good because two
    #                     independent state instances should be able to execute
    #                     reinvent a GIL. Unrelated states should be able to
    #                     execute asynchronously.
    #          - specify it for every instance created - yuck...a goal is to
    #            make it so users don't have to think about how to schedule
    #            reactions.
    #          - Specify on the predicate, with a lambda? that is called when
    #            the predicate is true with itself (for fields) that provides
    #            an executor that the predicate should execute in.
    #          - don't allow ambiguous predicates...if the instances the
    #            predicates are using have different reaction executors raise
    #            an error
    #          - unfortunately the mechanism to get instances other than bound
    #            field isn't complete yet and sorting it out will likely
    #            provide structure (ie watcher = Watcher(watched)) to associate
    #            instances with each other (1:1 seems a bit restrictuve, need
    #            a mapping for each end that isn't 1 to or to 1. Performance?
    #            Ramble Ramble Ramble: using metaclasses to hook into instance
    #            creation/initialization seems like the most promising route.
    #            The problem is the instance a reaction is called on is
    #            currently acquired from the BoundField that had a field
    #            change. This works fine for reactions that listen on their
    #            own classes fields (including base class fields). But
    #            reactions on other classes will invoke the reaction with the
    #            other class as 'self', or at least the only instance
    #            available.
    #                - @(Foo.foo == 1) on Bar.foo_eq_one(): The method on Bar
    #                  will not get a reference to an Bar instance.A
    #                  ??? create Foo: Watched with reference to Bar: yuck, it
    #                      is totally backwards and there are multiple
    #                      for different Fields.
    #                  ??? give predicate a resolver to push back to user
    #                  ??? Factory method to create a new Watcher from a 
    #                      Watched.
    #                  ??? asyncio Context? 
    _reaction_executor: ReactionExecutor = field(
        default_factory=ReactionExecutor, kw_only=True)

    _logger: Logger = field(default=logger, kw_only=True)

    '''
    Each state can have its own logger, for example to identify instance
    that logged. Defaults to execute_logger.
    '''

    @abstractmethod
    def _start(self) -> None:
        '''
        Subclasses must implement this to start the state machine execution.
        '''

    def start(self) -> Awaitable:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state. If an exception
         caused termination of the state it is available as the futures
         exception.
         '''
        if self._reaction_executor.task is not None:
            raise ExecutorAlreadyStarted()
        get_event_loop()

        awaitable = self._reaction_executor.start()
        self._start()
        return awaitable

    async def run(self) -> None:
        '''Run the Reactant and wait for completion.'''
        # TODO - start and run responsibilities and how and when to use which
        #        is not clear and not documented. Add a way to start a Reactant
        #        with or without an event loop, and a way to start and wait.
        #        start() should work in and outside an async context, and run
        #        should wait for completion, again from either context.
        await self.start()

    def stop(self, timeout: Optional[float]=2) -> None:
        '''
        stop the state processing.
        Args:
            timeout - time in seconds to wait for the shutdown to complete
                      normally before canceling the task.
        '''
        if not self._reaction_executor.task:
            raise ExecutorNotStarted()
        if self._reaction_executor.task.done():
            raise ExecutorAlreadyComplete()

        self._reaction_executor.stop(timeout)
        self._logger.debug(f'{self} stopping.')

    async def astop(self, *args) -> None:
        '''
        Async stop:
        (done == True)(Reactant.astop)
        '''
        self.stop()

    def cancel(self) -> None:
        self.stop(0)
