'''
Asynchronous reaction executor.
'''
from __future__ import annotations

from asyncio import Queue, Task, create_task, QueueShutDown
from dataclasses import dataclass, field
from logging import Logger, getLogger
from typing import Callable, Any, Optional, Coroutine, Tuple

from .error import StateError
from .field import BoundField, Field

__all__ = ['ReactorBase']


logger: Logger = getLogger('whenstate.executor')


type Reaction[C, T] = Callable[[Any, Field[C, T], T, T], None]
type AsyncReaction[C, T] = Callable[[C, Field[C, T], T, T],
                                    Coroutine[None, None, None]]


class ReactionExecutor[C: "ReactorBase", T](
        Queue[Tuple[C, Coroutine[None, None, T]]]
        ):
    '''
    ReactionExecutor executes reactions for sublcasses of ReactorBase.

    It is an asyncio.Queue with a coroutine that executes elements of the queue
    as it is drained.
    It provides concurrency control. The executor processes the reactions in
    the order they are submitted, one after the next. The reactions are run
    asynchronously with respect to what is being reacted to, but synchronously
    with respect to the other reactions in the queue.
    There is no need to extend this in the future to run the tasks
    asynchronously with respect to each other. If that is desirable a reaction
    is able to create a Task or callbackk to execute asynchronously on the
    event loop. This is more explicit about when the state is being updated
    asynchronously and also makes the simple synchronous use case the default.
    '''

    task: Optional[Task] = None
    '''the task that is processing the queue to execute reactions'''

    @staticmethod
    def react(reaction: AsyncReaction[C, T],
              instance: C,
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
        
        instance.logger.debug(f'schedule %s (..., %s,  %s)',
                           reaction.__qualname__, old, new)
        print(f"{reaction=}")
        coro = reaction(instance, bound_field.field, old, new)
        try:
            self.put_nowait((bound_field.instance, coro))
        except QueueShutDown:
            # TODO - this can happen for a bunch of reasons that need
            #        to be locked down. Once that has stabilized it may
            #        still be possible, so this may need to be removed.
            #        For now, I want to know when state updates are
            #        happening after the state has entered terminal
            #        state.
            #        1) are queued tasks generating these? Why do we
            #           have queued tasks for terminal state? (yes)
            #        2) is the state continuing to execute after
            #           completing its future? (only without sleep(0))
            #        3) does state completion need to be moved into a
            #           task? (don't think so)
            #        4) are tasks waiting unexpectedly causing out of
            #           order execution? (don't think so)
            raise StateError(f'reaction {reaction.__qualname__} called '
                             f'after {self} completed.')


    def start(self):
        self.task = create_task(self.execute_reactions())

    def stop(self):
        '''stop the reaction queue'''
        if not self.empty():
            # todo - disabled for development, restore this
            # raise StateHasPendingReactions()
            pass
        self.shutdown()
        self.task.cancel()  # stop processing reactions

    async def execute_reactions(self):
        '''
        Queue worker that gets pending tasks from the queue and executes
        them.

        The pending tasks are processed synchronously.
        '''
        while True:
            try:
                (instance, coro) = await self.get()
            except QueueShutDown:
                break
            try:
                instance.logger.debug(f'calling {coro}')
                await coro
            except Exception as exc:
                instance.error(exc)
            finally:
                self.task_done()

@dataclass
class ReactorBase:
    '''base class for classes that have reactions'''
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

    logger: Logger = field(default=logger, kw_only=True)
