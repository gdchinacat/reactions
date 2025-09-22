'''
Predicates implement comparison checks.

todo - I'm not sure this is the best name. A lot of what is here are actually
       expressions, not predicates. Ultimately though they have to be a
       predicate that evaluates to True or False. I think the name is ok since
       they are all composed of comparisons which are predicates. The
       question I have is should callables be allowed, and if so, how to feed
       their arguments to them (zero-arity functons don't seem very useful).
'''
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .field import Field


EMPTY_ITERATOR = () # singleton iterator that contains nothing


@dataclass
class Predicate(ABC):
    '''
    '''

    @abstractmethod
    def __bool__(self):
        pass

    @property
    @abstractmethod
    def fields(self):
        '''
        yield all fields that are part of the predicate
        '''

    def _fields(self, condition: Predicate | Field):
        '''helper for subclasses to yield predicate fields or field'''
        if isinstance(condition, Predicate):
            yield from condition.fields
        elif isinstance(condition, Field):
            yield condition


@dataclass
class Constant(Predicate):
    value: Any = None

    def __bool__(self):
        return bool(self.value)

    @property
    def fields(self):
        return EMPTY_ITERATOR

    def __eq__(self, other):
        return self.value == other
    
    def __req__(self, other):
        return self.value == other


@dataclass
class UnaryPredicate(Predicate):
    condition: Predicate | Field | Constant

    def __bool__(self):
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
        yield from self._fields(self.left)
        yield from self._fields(self.right)

    @abstractmethod
    def __bool__(self): ...


class Eq(BinaryPredicate):

    def __bool__(self):
        return (self.left == self.right)
