'''
A state machine:
    - instrumentable fields to schedule callable when predicate using
      the fields become true.
    - async loop to execute schduled callables.
'''
from abc import ABC
from dataclasses import dataclass
from functools import wraps

from .predicate import Predicate
from .field import Field


@dataclass
class State(ABC):
    count: int = Field(0)  # cycle counter

    @classmethod
    def when(cls, predicate: Predicate):
        '''
        Arrange for the decorated function to be called when the predicate
        becomes true.
        '''
        def dec(func):
            for field in predicate.fields:
                print(f"TODO when {field} changes call {func}")

            @wraps(func)
            def _when(*args, **kwargs):
                # this isn't at all correct:
                #    - invariably calls the decorated function
                #    - doesn't schedule change event on predicate
                #    - func must not return anything since it is meaningless
                return func(*args, **kwargs)
            return _when
        return dec

