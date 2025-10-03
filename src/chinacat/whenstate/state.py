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
from asyncio import Future
from dataclasses import dataclass, field
from functools import partial, wraps
from logging import Logger, getLogger
from typing import Callable, Any, Optional, Coroutine

from .error import (ReactionMustNotBeCalled, StateNotStarted,
                    StateAlreadyComplete, StateAlreadyStarted)
from .executor import ReactionExecutor, ReactorBase
from .field import Field
from .predicate import Predicate


__all__ = ['State']


config_logger: Logger = getLogger('whenstate.state.config')
execute_logger: Logger = getLogger('whenstate.state.execute')


type ShouldBeState = Any #"State"  # TODO - use correct incantation rather than Any
type Decorator[**A, R] = Callable[A, R]
# TODO - change Reaction args to be [State, Field, T, T] so reactions don't
#        have to be aware of BoundField or get instance in multiple ways.
type Reaction[C, T] = Callable[[Any, Field[ShouldBeState, T], T, T], None]
type AsyncReaction[C, T] = Callable[[ShouldBeState,
                                     Field[C, T], T, T],
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
class State(ReactorBase, metaclass=StateMeta):
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
        becomes true. The function is *not* called by the decorator, but rather
        the predicate when a field change causes it to become true. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The set of fields the predicate uses are reaction()ed to have the
        predicate react() by calling the method being decorated.

        The reaction is called asynchronously in the event loop. It can rely on
        the semantics of coroutine cooperative scheduling to make atomic
        updates to the state by only yielding to the event loop when the state
        is consistent. Failure to yield for "long" periods of time will block
        execution of other asynchronous tasks, including reactions (don't
        time.sleep()).

        Reaction execution start order is implementation specific. It is too
        premature to define it well. It is currently determined by the order
        of the reactions on the field which is the order the @when() decorator
        was applied to the fields in the predicate. It is therefore sensitive
        to which side a field is placed in a predicate, the method definition
        order, and the import order. This should be better defined, but at this
        time it is not. TODO

        TODO - remove ReactionMustNotBeCalled to allow stacking @when()'s?
               not sure exactly what the semantics would be...And() the
               predicates together?
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
