'''
An event driven state machine.

Implementation is done by specifying reaction functions that react to state
changes based on predicates. When a state field changes the predicates that
use the changed field are reevaluated and the reaction is scheduled for
asynchronous execution.

Execution of the reaction is delayed from when the predicate for the reaction
is evaluated. This means intervening reactions may change state such that the
predicate is no longer true when the reaction is eventually executed. State
implementations are expected to take this into account. TODO - mark fields
for predicates with pending reactions so that updates to them raise exception?
This would guarantee predicates don't become false before their reactions
are done executing, but would preclude reactions that change their predicate
field...implementing a counter would become convoluted (change to count_1
increments count_2 which has a reaction to change count_1...yuck..but may be
worth it).

The asynchronous execution of reactions means ordering is not well defined.
Implementations are expected to take this into account by modeling it in
sufficient detail to ensure the required semantics.

Implementations are strongly discouraged from using locks or other
synchronization primitives. Model the state those would manage.

TODO - come up with guidelines for how to safely implement state
'''
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from asyncio import Future, Queue, Task, create_task, QueueShutDown
from dataclasses import dataclass, field
from functools import partial, wraps
from logging import Logger, getLogger
from typing import Callable, Any, Optional, Coroutine

from .error import (ReactionMustNotBeCalled, StateNotStarted, StateError,
                    StateAlreadyComplete, StateHasPendingReactions,
                    StateAlreadyStarted)
from .field import BoundField, Field
from .predicate import Predicate


__all__ = ['State', 'ReactionMustNotBeCalled', ]


config_logger: Logger = getLogger('whenstate.state.config')
execute_logger: Logger = getLogger('whenstate.state.execute')


type ShouldBeState = Any  # TODO - use correct incantation rather than Any
type Decorator[**A, R] = Callable[A, R]
# TODO - change Reaction args to be [State, Field, T, T] so reactions don't
#        have to be aware of BoundField or get instance in multiple ways.
type Reaction[C, T] = Callable[[Any, Field[ShouldBeState, T], T, T], None]
type AsyncReaction[C, T] = Callable[[Any, Field[ShouldBeState, T], T, T],
                                    Coroutine[None, None, None]]
type StateReaction = Reaction[ShouldBeState, Any]
type AsyncStateReaction = AsyncReaction[ShouldBeState, Any]


TRACE_ENABLED = True


def trace(func: Callable[..., Any]) -> Callable[..., Any]:
    if not TRACE_ENABLED:
        return func
    @wraps(func)
    def _trace(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
            execute_logger.debug(
                f'{func}({args=}, {kwargs=}) = {ret=}')
        except BaseException as exc:
            execute_logger.debug(
                f'!!{func}({args=}, {kwargs=}) raised {exc=}')
            raise
    return _trace
            

@dataclass
class PendingReaction[C, T]:
    '''
    A reaction that is scheduled for asynchronous execution.
    '''
    reaction: AsyncReaction[C, T]
    bound_field: BoundField[C, Any]
    old: T
    new: T

    @property
    def instance(self):
        return self.bound_field.instance

    async def execute(self):
        '''
        Call the reaction.
        TODO - support async reactions?
        '''
        instance = self.bound_field.instance
        await self.reaction(instance,
                            self.bound_field,
                            self.old, self.new)

    def __str__(self):
        return f'{self.reaction.__qualname__}(..., {self.old}, {self.new})'


class ReactionExecutor[C: "State", T](Queue[PendingReaction[C, T]],
                                    Task):
    '''
    ReactionExecutor is created by State.start() to execute the states
    reactions asynchronously.

    It is an asyncio.Queue with a coroutine that executes elements of the queue
    as it is drained.
    '''

    task: Optional[Task] = None
    '''the task that is processing the queue to execute reactions'''

    @staticmethod
    def react(reaction: AsyncReaction[C, T],
              state: C,
              bound_field: BoundField[C, T],
              old: T, new: T) -> None:
        '''reaction that asynchronously executes the reaction'''
        # The weirdness of this being a @staticmethod that gets its self from
        # the state is so this method can be used as a @partial wrapped
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
        self = state._reaction_executor
        assert self.task, "ReactionExecutor not start()'ed"
        
        state.logger.debug(
            f'schedule {reaction.__qualname__}(..., {old},  {new})')
        pending = PendingReaction(reaction, bound_field, old, new)
        try:
            self.put_nowait(pending)
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
                             f'after {state} completed.')


    def start(self):
        self.task = create_task(self.execute_reactions())

    def stop(self):
        '''stop the reaction queue'''
        if not self.empty():
            raise StateHasPendingReactions()
        self.shutdown()
        self.task.cancel()  # stop processing reactions

    async def execute_reactions(self):
        while True:
            try:
                pending = await self.get()
            except QueueShutDown:
                break
            pending.instance.logger.debug(f'calling {pending}')
            try:
                await pending.execute()
            except Exception as exc:
                pending.bound_field.instance.error(exc)
            finally:
                self.task_done()


class FieldNamingDict(dict[str, Any]):
    '''
    A dict that is used by StateMeta for State class creation to provide
    members that are instances of Field with the class and attribute name.
    '''

    def __init__(self, classname: str):
        self.classname = classname

    def __setitem__(self, attr: str, value: Any)->None:
        if isinstance(value, Field):
            # Populate Field classname and attr fields.
            value.set_names(self.classname, attr)
        super().__setitem__(attr, value)


class StateMeta(ABCMeta, type):
    '''
    Metaclass for State objects.
    Modifies State class definition to set the classname and attr on Field
    members.
    '''
    @classmethod
    def __prepare__(cls, name, bases):
        return FieldNamingDict(name)

    def __setattr__(self, attr: str, value: Any):
        '''
        Intercept calls to set attributes on instances to name Field members.
        '''
        if isinstance(value, Field):
            value.set_names(self.__qualname__, attr)
        super().__setattr__(attr, value)


@dataclass
class State(metaclass=StateMeta):
    '''
    State implements an event driven state machine.

    Usage:
    class Counter(State):
        """A counter that spins until stopped"""
        count: Field[Counter, int] = Field(-1)

        @State.when(count != -1)
        def counter(self, bound_field: BoundField[Counter, int],
                    old: int, new: int) -> None:
            self.count += 1

        def _start(self):
            self.count = 0

    async def run_counter_for_awhile():
        counter = Counter()
        counter_task = asyncio.create_task(counter.start())
        ....
        counter.stop()
        await counter_task

    State reaction callbacks are asynchronous in contrast to Field and
    Predicate callbacks. The reactions are not themselves async def's, but
    support for that may be added to enable asyncio.sleep() to allow reactions
    to introduce delays.
    '''

    _complete: Optional[Future[None]] = field(init=False, default=None)
    _reaction_executor: ReactionExecutor = field(
        init=False, default_factory=ReactionExecutor)
    logger: Logger = field(default=execute_logger, kw_only=True)
    '''
    Each state can have its own logger, for example to identify instance
    that logged. Defaults to execute_logger.
    '''

    def start(self) -> Future[None]:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state. If an exception
         caused termination of the state it is available as the futures
         exception.
         '''
        if self._complete is not None:
            raise StateAlreadyStarted()
        complete = self._complete = Future()
        self._reaction_executor.start()
        self._start()
        return complete

    async def run(self) -> None:
        '''
        Run the state and wait for its completion.
        If execution was terminated with an exception it is raised.
        '''
        self._complete = self.start()
        await self._complete
        if (exc := self._complete.exception()):
            raise exc

    @abstractmethod
    def _start(self) -> None:
        '''
        Subclasses must implement this to start the state machine execution.
        '''

    def stop(self) -> None:
        '''
        stop the state processing.
        '''
        if self._complete is None:
            raise StateNotStarted()
        elif self._complete.done():
            raise StateAlreadyComplete()
        self._reaction_executor.stop()
        self._complete.set_result(None)
        self.logger.debug(f'{self} stopped.')
    
    def error(self, exc_info: Exception) -> None:
        if self._complete is None:
            raise StateNotStarted()
        elif self._complete.done():
            # future is already done so nothing to do but log it.
            self.logger.exception('exception encountered processing '
                                  'reaction for closed state',
                                  exc_info=exc_info)
        self._reaction_executor.stop()
        self._complete.set_exception(exc_info)

    def cancel(self, *args) -> None:
        if self._complete is None:
            raise StateNotStarted()
        self._reaction_executor.stop()
        self._complete.cancel(*args)

    @classmethod
    def when(cls, predicate: Predicate) \
        -> Decorator[[AsyncStateReaction], ReactionMustNotBeCalled]:
        '''
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The set of fields the predicate uses are reaction()ed to have the
        predicate react() by asynchronously calling the method being decorated.

        TODO - remove ReactionMustNotBeCalled to allow stacking @when()'s?
               not sure exactly what the semantics would be...And() the
               predicates together?
        TODO - allow async methods to be decorated with @when()?
        '''
        def dec(func: AsyncStateReaction) -> ReactionMustNotBeCalled:
            config_logger.info(
                f'{func.__qualname__} will be called when {predicate}')
            # Register predicate reactions that call our reaction with the
            # fields the predicate uses.
            for field in set(predicate.fields):
                reaction = partial(ReactionExecutor.react, func)
                field.reaction(partial(predicate.react,
                                       reaction=reaction))

            return ReactionMustNotBeCalled(func)
        return dec
