'''
A state machine:
    - instrumentable fields to schedule callable when predicate using
      the fields become true.
    - async loop to execute schduled callables.
'''
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from functools import partial
import logging
from typing import Callable, Any, Type

from .field import BoundField, Reaction
from .predicate import Predicate
from .error import MustNotBeCalled

__all__ = ['ReactionMustNotBeCalled', "State"]

logger = logging.getLogger('whenstate.state')
logging.basicConfig(level=logging.DEBUG, force=True)  # todo remove


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
    def __init__(self, func: Reaction, *args, **kwargs):
        super().__init__(None, f"{func.__qualname__} is a State reaction method and "
                         "can not be called directly.", *args, **kwargs)

    def __call__(self, *args, **kwargs):
        '''raises self to indicate method was in fact called'''
        raise self

@dataclass
class State(ABC):
    
    @classmethod
    def when(cls: Type[State], predicate: Predicate) \
        -> Callable[[Reaction[State, Any]], Callable[..., None]]:
        '''
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The fields the predicate uses are listen()ed to react() the predicate
        on field changes. 
        '''
        def dec(func) -> Callable[[State, BoundField, Any, Any], None]:
            for field in predicate.fields:
                assert not isinstance(field, BoundField)
                field.reaction(partial(predicate.react, target=func))
            return ReactionMustNotBeCalled(func)
        return dec
