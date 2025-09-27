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

from abc import ABC, abstractmethod
from asyncio import Future, create_task, Task
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial, wraps
import logging
from typing import Callable, Any, Coroutine, Optional, Type

from chinacat.whenstate.error import StateNotStarted

from .error import MustNotBeCalled
from .field import BoundField
from .predicate import Predicate, BoundReaction


__all__ = ['ReactionMustNotBeCalled', "State"]


config_logger = logging.getLogger('whenstate.state.config')
execute_logger = logging.getLogger('whenstate.state.execute')


class ReactionMustNotBeCalled(MustNotBeCalled):
    '''
    Exception raised if a @when decorated function is called directly. These
    functions should only be called by the predicate.

    The removal of the method from a class definition is very intentional.
        - readers may reasonably but incorrectly think the @when() is a guard
          that skips calls if the predicate is false. Avoiding confusion is a
          good thing.
        - it would be possible to return a function that does that. Calls that
          are ignored in this way are likely to hurt performance and suggest
          the state model is not well , designed, or understood. Encouraging
          good design and understanding is a good thing.
        - there is a trivial workaround...invoke the decorator manually on a
          function definition that will be included and is very explicit about
          what the function semantics are:
              def react(self: C, bound_field: BoundField[C, T], old, new): ...
              State.when(foo==1)(react)
    '''
    def __init__(self, func: BoundReaction, *args, **kwargs):
        super().__init__(None, f"{func.__qualname__} is a State reaction method and "
                         "can not be called directly.", *args, **kwargs)

    def __call__(self, *args, **kwargs):
        '''raises self to indicate method was in fact called'''
        raise self


type _Coroutine[R] = Coroutine[Any, Any, R]
type AsyncCallable[**A, R] = Callable[A, _Coroutine[R]]
type AsyncBoundReaction[C] = AsyncCallable[
    [C, BoundField[Type[C], Any], Any, Any],
    None]

@dataclass
class State(ABC):
    '''
    State implements an event driven state machine.

    Each State has its own asyncio event loop that is used for processing the
    state events.
    '''
    # TODO - This could be the basis for a tool for debugging otraffic_light_test.pyr
    #        for understanding how existing complex state machines
    #        actually work. Just extend StateAnalyzer(State) and
    #        have it dump the state machine your existing code
    #        creates. Not really a goal for now, but hmm....dev
    #        tools that help understand existing complex code are
    #        quite valuable ($$$).

    _complete: Optional[Future[None]] = None

    def start(self) -> Future[None]:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state.
         '''
        complete = self._complete = Future()
        self._start()
        return complete

    @abstractmethod
    def _start(self) -> None:
        '''
        Subclasses must implement this to start the state machine execution.
        '''

    def stop(self) -> None:
        if self._complete is None:
            raise StateNotStarted()
        self._complete.set_result(None)

    def error(self, exc:Exception) -> None:
        if self._complete is None:
            raise StateNotStarted()
        self._complete.set_exception(exc)

    def cancel(self, *args) -> None:
        if self._complete is None:
            raise StateNotStarted()
        self._complete.cancel(*args)

    @asynccontextmanager
    async def async_exception_handler(self):
        '''
        async context manager to catch exceptions and route them to error()
        '''
        try:
            yield
        except Exception as exc:
            self.error(exc)

    @classmethod
    def when[C](cls, predicate: Predicate) \
        -> Callable[[AsyncBoundReaction[State]],
                    MustNotBeCalled]:
        '''
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The fields the predicate uses are reaction()ed to react() the predicate
        on field changes. 
        '''
        def dec(func: AsyncBoundReaction[State]) \
                -> ReactionMustNotBeCalled:

            config_logger.info(f'will call {func.__qualname__} when {predicate}')
            def reaction(self: State,
                         bound_field: BoundField[Type[State], Any],
                         old: Any, new: Any) -> Optional[Task]:
                '''Invoke the reaction asynchrounously.'''
                # TODO - this is suboptimal since each true predicate gets its
                #        own task rather than a sngle task for all the state
                #        reactions. Consider batching by returning tasks rather
                #        than executing them inlne.
                assert self._complete is not None
                execute_logger.info(
                    f'received notification for {predicate} that '
                    f'{bound_field} changed from {old} to {new}')
                if not self._complete.done():
                    execute_logger.debug(
                        f'scheduling {func.__qualname__} because {predicate} '
                        f'== True after {bound_field} changed from {old} to '
                        f'{new}')
                    async def safe_func():
                        async with self.async_exception_handler():
                            return func(self, bound_field, old, new)
                    return create_task(safe_func())
                return None

            for field in set(predicate.fields):
                assert not isinstance(field, BoundField)
                field.reaction(partial(predicate.react, target=reaction))
            return ReactionMustNotBeCalled(func)
        return dec
