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
import logging
from typing import Any, Callable, Generator, Sequence


logger = logging.getLogger("whenstate.predicate")
EMPTY_ITERATOR = () # singleton iterator that contains nothing


type Reaction[C, T] = Callable[["BoundField[C, T]", T, T], None]
''' Reaction for field value change notifications.'''


class _Field[C, T](ABC):
    '''ABC for field behavior Predicate uses'''
    @property
    @abstractmethod
    def fields(self) -> Generator[_Field[C, T], None, None]: ...

    @abstractmethod
    def reaction(self, reaction: Reaction[C, T]) -> None: ...


@dataclass
class Predicate[C](ABC):
    '''
    '''

    @property
    @abstractmethod
    def fields(self) -> Generator[_Field[C, Any], None, None] | \
                        Sequence[_Field[C, Any]]:
        '''
        yield all fields that are part of the predicate
        '''

    def __and__(self, other):
        return And(self, other)

    def __call__(self, instance: C) -> bool:
        raise NotImplementedError('predicate evaluation not implemented')

    def react(self, bound_field, old, new,  # Reaction # todo annotations
               target: Reaction):
        logger.debug('%s notified that %s %s -> %s', self, bound_field,
                     old, new)
        if self(bound_field.instance):
            self.react(bound_field.instance, bound_field, old, new)
        # todo call the target if predicate(bound_field.instance)
        # 

@dataclass
class Constant[C, T](Predicate[C]):
    value: T | None = None

    @property
    def fields(self) -> Sequence[_Field[C, T]]:
        return EMPTY_ITERATOR

    def __eq__(self, other) -> bool:
        return self.value == other
    
    def __str__(self) -> str:
        return str(self.value)


@dataclass
class BinaryPredicate[C](Predicate[C], ABC):
    '''
    '''
    left: Predicate[C] | _Field[C, Any]
    right: Predicate[C] | _Field[C, Any]

    @property
    @abstractmethod
    def token(self) -> str: ...

    def __post_init__(self):
        # Everything that isn't a Predicate or a _Field is treated as a
        # constant. This may need to be reevaluated, but it helps with the
        # fields() logic for now.
        if not isinstance(self.left, (Predicate, _Field)):
            self.left = Constant(self.left)
        if not isinstance(self.right, (Predicate, _Field)):
            self.right = Constant(self.right)

    @property
    def fields(self) -> Generator[_Field[C, Any], None, None]:
            yield from self.left.fields
            yield from self.right.fields

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"


class Eq[C](BinaryPredicate[C]):
    token: str = "=="
    
    def __bool__(self) -> bool:
        return (self.left == self.right)

class Ne[C](BinaryPredicate[C]):
    token: str = "!="

    def __bool__(self) -> bool:
        return (self.left != self.right)

class And[C](BinaryPredicate[C]):
    token: str = "&"
    
    def __bool__(self) -> bool:
        return bool(self.left) and bool(self.right)
