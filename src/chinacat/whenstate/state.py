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
from asyncio import Future
from dataclasses import dataclass, field
from functools import partial
import logging
from typing import Callable, Any, Coroutine

from .error import MustNotBeCalled
from .field import BoundField
from .predicate import Predicate, BoundReaction


__all__ = ['ReactionMustNotBeCalled', "State"]


logger = logging.getLogger('whenstate.state')


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


type _Coroutine[R] = Coroutine[None, None, R]
type AsyncCallable[**A, R] = Callable[A, _Coroutine[R]]
type AsyncBoundReaction[C] = AsyncCallable[
    [C, BoundField[C, Any], Any, Any],
    None]

@dataclass
class State[C](ABC):
    '''
    State implements an event driven state machine.

    Each State has its own asyncio event loop that is used for processing the
    state events.
    '''

    @abstractmethod
    def start(self) -> Future:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state.
         '''

    # TODO - implement a cancellation mechanism.

    @classmethod
    def when(cls, predicate: Predicate) \
        -> Callable[[AsyncBoundReaction[C]],
                    MustNotBeCalled]:
        '''
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The fields the predicate uses are reaction()ed to react() the predicate
        on field changes. 
        '''
        
        def dec(func: AsyncBoundReaction[C]) \
                -> ReactionMustNotBeCalled:
            def _async(self: C, bound_field: BoundField[C, Any],
                       old: Any, new: Any)->None:
                '''Invoke the reaction asynchrounously.'''
                raise NotImplementedError(
                    f'NOT calling {func} asynchronously {old=} {new=}')

            for field in predicate.fields:
                assert not isinstance(field, BoundField)
                field.reaction(partial(predicate.react, target=_async))
            return ReactionMustNotBeCalled(func)
        return dec
