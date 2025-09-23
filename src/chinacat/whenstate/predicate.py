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
import operator
from typing import Any, Callable, Generator, Sequence, Type, TypeAlias

from .error import MustNotBeCalled


__all__ = []


logger = logging.getLogger("whenstate.predicate")
EMPTY_ITERATOR = () # singleton iterator that contains nothing
type BoundField[C, T] = TypeAlias

type Reaction[C, T] = Callable[[BoundField[C, T], T, T], None]
''' Reaction for field value change notifications.'''


class _Field[C, T](ABC):
    '''ABC for field behavior Predicate uses'''

    @property
    @abstractmethod
    def fields(self) -> Generator[_Field[C, T], None, None]: ...

    @abstractmethod
    def reaction(self, reaction: Reaction[C, T]) -> None: ...

    @abstractmethod
    def evaluate(self, instance: C ) -> T: ...

@dataclass
class Predicate[C](ABC):
    '''
    Predicate evaluates expressions.

    Created through Field and Predicate comparison methods:
        State.field == 'value'
    They are e
    '''

    @property
    @abstractmethod
    def fields(self) -> Generator[_Field[C, Any], None, None] | \
                        Sequence[_Field[C, Any]]:
        '''
        yield all fields that are part of the predicate
        '''

    def __and__(self, other):
        return And(self, other)  # pylint: disable=abstract-class-instantiated

    @abstractmethod
    def evaluate(self, instance: C) -> Any:
        '''evaluate the predicate against the given model'''

    def react(self,
              bound_field: BoundField,
              old: Any,
              new: Any,
              *,
              target: Reaction):
        logger.debug('%s notified that %s %s -> %s', self, bound_field,
                     old, new)

        if self.evaluate(bound_field.instance):
            target(bound_field, old, new)
        # todo call the target if predicate(bound_field.instance)


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

    def evaluate(self, instance: C) -> T | None: \
        # @UnusedVariable pylint: disable=unused-argument
        return self.value


@dataclass
class BinaryPredicate[C](Predicate[C], ABC):
    '''
    Predicate that has two operands.
    '''
    left: Predicate[C] | _Field[C, Any]
    right: Predicate[C] | _Field[C, Any]

    @property
    @abstractmethod
    def token(self) -> str: ...  # field from subclass

    @property
    @abstractmethod
    def operator(self) -> Callable[[Any, Any], bool]: ...

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

    def evaluate(self, instance: C):
        return self.operator(self.left.evaluate(instance),
                             self.right.evaluate(instance))

    @MustNotBeCalled
    def __bool__(self): ...

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"

    @classmethod
    def factory(cls,
                name: str,
                token: str,
                op: Callable[[Any, Any], bool]
               ) -> Type[BinaryPredicate[C]]:
        '''
        Create a binary operator using the given function. token is for str/repr
        and has no other use. The class is exported from the module through
        __all__.
        '''

        ret: Type[BinaryPredicate[C]] = type(name,
                                             (BinaryPredicate, ),
                                             {'token': token,
                                              'operator': op}) 
        __all__.append(name)
        return ret

Eq: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('Eq', '==', operator.eq)
Ne: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('Ne', '!=', operator.ne)
And: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('And', '&', operator.and_)
Lt: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('Lt', '<', operator.lt)
Le: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('Le', '<=', operator.le)
Gt: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('Gt', '>', operator.gt)
Ge: Type[BinaryPredicate[Any]] = BinaryPredicate.factory('Ge', '>=', operator.ge)

class Contains[C](BinaryPredicate):
    token: str = 'in'
    operator: Callable[[Any, Any], bool] = operator.contains

    def __init__(self,  # pylint: disable=useless-parent-delegation
                 left: Predicate[C] | _Field[C, Any],
                 right: Predicate[C] | _Field[C, Any]):
        # contains() args are reversed the other binary operations, so swap
        # left and right.
        super().__init__(left, right)
