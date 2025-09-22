'''
Weird sick can't sleep thoughts after seeing:
https://www.reddit.com/r/Python/comments/1nmta0f/i_built_a_full_programming_language_interpreter/
Right before going to bed and trying to sleep I thought...I bet a bunch of that
can be done with standard python using descriptors and ....

Then the dogs barked and woke me up early while still sick. Here goes nothing.

The basic language idea is that you specify conditions when code should
execute based on a state model. But, rather than adding events to your model
explicitly you write code that appears procedural, but it just sets up
listeners for model change events. Under the covers the model has a complex
graph of dependent conditions that are evaluated when the condition changes.

TODO - example
'''
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import typing


Field = typing.TypeAlias


@dataclass
class Constant:
    value: Any = None


@dataclass
class Predicate(ABC):
    '''
    '''

    @abstractmethod
    def __call__(self):
        '''
        Evaluate the predicate.
        '''

    @property
    @abstractmethod
    def fields(self):
        '''
        yield all fields that are part of the predicate
        '''

    def _fields(self, condition: "Predicate" | Field):
        '''helper for subclasses to yield predicate fields or field'''
        if isinstance(condition, Predicate):
            yield from condition.fields
        else:
            yield condition


@dataclass
class UnaryPredicate(Predicate):
    condition: "Predicate" | Field | Constant

    def __call__(self):
        return self.condition()

    @property
    def fields(self):
        yield super()._fields(self.condition)


@dataclass
class BinaryPredicate(Predicate, ABC):
    '''
    '''
    left: Predicate | Field
    right: Predicate | Field

    @property
    def fields(self):
        yield from super()._fields(self.left)
        yield from super()._fields(self.right)


class Eq(BinaryPredicate):

    def __call__(self):
        return ((self.left() if callable(self.left) else self.left)
                ==
                (self.right() if callable(self.right) else self.right))
    __bool__ = __call__
