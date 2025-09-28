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
from typing import (Any, Callable, Generator, Sequence, Type, TypeAlias,
                    Optional)

from .error import MustNotBeCalled, InvalidPredicateExpression


__all__ = ['Predicate', 'Not', 'And', 'Or', 'Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge',
           'Contains', 'BinaryAnd', 'BinaryOr', ]


logger = logging.getLogger("whenstate.predicate")
EMPTY_ITERATOR = () # singleton iterator that contains nothing
type BoundField[C, T] = TypeAlias
type Reaction[C, T] = Callable[[BoundField[C, T], T, T], None]
type BoundReaction[C, R] = Callable[[C,                   # cls
                                  BoundField[C, Any],     # bound_field
                                  Any,                    # old
                                  Any],                   # new
                                 R]                       # return None


class _Field[C, T](ABC):
    '''ABC for field behavior Predicate uses'''

    @property
    @abstractmethod
    def fields(self) -> Generator[_Field[C, T], None, None]: ...

    @abstractmethod
    def reaction(self, reaction: Reaction[C, T]) -> None: ...

    @abstractmethod
    def evaluate(self, instance: C) -> Optional[T]: ...

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

    def __or__(self, other):
        return Or(self, other)  # pylint: disable=abstract-class-instantiated

    @abstractmethod
    def evaluate(self, instance: C) -> Any:
        '''evaluate the predicate against the given model'''

    def react(self,
              bound_field: BoundField,
              old: Any,
              new: Any,
              *,
              target: BoundReaction) -> None:
        logger.debug('%s notified that %s %s -> %s', self, bound_field,
                     old, new)

        if self.evaluate(bound_field.instance):
            target(bound_field.instance, bound_field, old, new)


@dataclass
class Constant[C, T](Predicate[C]):
    value: Optional[T] = None

    @property
    def fields(self) -> Sequence[_Field[C, T]]:
        return EMPTY_ITERATOR

    def __eq__(self, other) -> bool:
        return self.value == other

    def __str__(self) -> str:
        return str(self.value)

    def evaluate(self, instance: C) -> Optional[T]: \
        # @UnusedVariable pylint: disable=unused-argument
        return self.value

    @MustNotBeCalled
    def __bool__(self): ...


class OperatorPredicate[P, C](Predicate[C], ABC):
    '''predicate that uses an operator for its logic'''

    operator: Callable[..., bool]

    @property
    @abstractmethod
    def token(self) -> str: ...  # field from subclass

    @abstractmethod
    def evaluate(self, instance: C): ...

    @classmethod
    def factory(cls,
                name: str,
                token: str,
                op: Callable[..., bool]
               ) -> Type[P]:
        '''
        Create a Predicate class using the given op. token is for str/repr
        and has no other use. The class is exported from the module through
        __all__.
        '''

        ret: Type[P] = type(name,
                            (cls, ),
                            {'token': token,
                             'operator': op}) 
        __all__.append(name)
        return ret


@dataclass
class UnaryPredicate[C](OperatorPredicate["UnaryPredicate", C], ABC):
    '''Predicate that has a single operand.'''
    expression: Predicate[C] | _Field[C, Any]

    def __init__(self, expression:Predicate[C] | _Field[C, Any] | Any,
                 *args, **kwargs):
        if not isinstance(expression, (Predicate, _Field)):
            expression = Constant(expression)
        self.expression = expression

    @property
    def fields(self) -> Generator[_Field[C, Any], None, None]:
        yield from self.expression.fields

    def evaluate(self, instance: C):
        return self.operator(self.expression.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.token} {self.expression})"


@dataclass
class BinaryPredicate[C](OperatorPredicate["BinaryPredicate", C], ABC):
    '''Predicate that has two operands.'''
    left: Predicate[C] | _Field[C, Any]
    right: Predicate[C] | _Field[C, Any]

    def __init__(self,
                 left: Predicate[C] | _Field[C, Any] | Any,
                 right: Predicate[C] | _Field[C, Any] | Any,
                 *args, **kwargs):
        # Everything that isn't a Predicate or a _Field is treated as a
        # constant. This may need to be reevaluated, but it helps with the
        # fields() logic for now.
        super().__init__(*args, **kwargs)
        if not isinstance(left, (Predicate, _Field)):
            left = Constant(left)
        self.left = left

        if not isinstance(right, (Predicate, _Field)):
            right = Constant(right)
        self.right = right

    @property
    def fields(self) -> Generator[_Field[C, Any], None, None]:
        yield from self.left.fields
        yield from self.right.fields

    def evaluate(self, instance: C):
        return self.operator(self.left.evaluate(instance),
                             self.right.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"

    def __bool__(self) -> bool | Predicate:
        # TODO - add unit test for this.
        raise InvalidPredicateExpression(f'{self}.__bool__() call indicates '
                                         'predicate was improperly created. '
                                         f' This most likely results from '
                                         'using it in a logical and '
                                         'expression ("? < P < ?", '
                                         '"P and P", etc.')

Not: Type[UnaryPredicate[Any]] = UnaryPredicate.factory(
    'Not', 'not', operator.not_)
And: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'And', 'and', lambda _, a, b: a and b)
Or: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Or', 'or', lambda _, a, b: a or b)
Eq: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Eq', '==', operator.eq)
Ne: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Ne', '!=', operator.ne)
Lt: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Lt', '<', operator.lt)
Le: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Le', '<=', operator.le)
Gt: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Gt', '>', operator.gt)
Ge: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Ge', '>=', operator.ge)
Contains: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'Contains','contains', operator.contains)

# BinaryAnd and BinaryOr aren't strictly predicates since they don't evaluate
# to a bool. Still useful, so included.
BinaryAnd: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'BinaryAnd', '&', operator.and_)
BinaryOr: Type[BinaryPredicate[Any]] = BinaryPredicate.factory(
    'BinaryOr', '|', operator.or_)

