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


EMPTY_ITERATOR = () # singleton iterator that contains nothing


class _Field: ...


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
    condition: Predicate | _Field

    def __bool__(self):
        return self.condition()

    @property
    def fields(self):
        yield from self.condition


@dataclass
class BinaryPredicate(Predicate, ABC):
    '''
    '''
    left: Predicate | _Field
    right: Predicate | _Field

    def __post_init__(self):
        # Everything that isn't a Predicate or a _Field is treated as a
        # constant. This may need to be reevaluated, but it helps with the
        # fields() logic for now.
        if not isinstance(self.left, (Predicate, _Field)):
            self.left = Constant(self.left)
        if not isinstance(self.right, (Predicate, _Field)):
            self.right = Constant(self.right)

    @property
    def fields(self):
            yield from self.left.fields
            yield from self.right.fields

    @abstractmethod
    def __bool__(self): ...


class Eq(BinaryPredicate):

    def __bool__(self):
        return (self.left == self.right)
