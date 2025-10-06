'''
Predicates implement comparison checks.
'''
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
import logging
import operator
from typing import Any, Callable, Type, Iterable

from chinacat.whenstate.annotations import _Evaluatable, HasNoFields

from .annotations import PredicateReaction, _Field, _Predicate, _Reactant
from .error import InvalidPredicateExpression, ReactionMustNotBeCalled
from .logging_config import VERBOSE


__all__ = ['Predicate', 'Not', 'And', 'Or', 'Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge',
           'Contains', 'BinaryAnd', 'BinaryOr', 'Constant']


logger = logging.getLogger("whenstate.predicate")


@dataclass
class Predicate(_Predicate, ABC):
    '''
    Predicate evaluates expressions.
    TODO - give Predicate a type for the fields they use. Complicated by the
           fact that a predicate can use fields of different type:
               And(str_field == 'foo',
                   int_field == 1))
            This predicate has two types of fields, what should the predicate
            type be? str | int? Does this help anything?

    Created through Field and Predicate comparison methods:
        field = Field(None)
        field == 'value'  # creates a predicate

    Predicates can be used to decorate a function to schedule it to be run
    when the Predicate becomes True.
    '''

    #####################
    # Abstract methods defined on HasFields and _Evaluatable. Not sure why
    # they need to be redeclared here since this derives from them.
    # todo - figure out why they are required and remove them?
    #####################
    @property
    @abstractmethod
    def fields(self) -> Iterable[_Field]:
        raise NotImplementedError()

    @abstractmethod
    def evaluate(self, instance: Any) -> bool:
        '''evaluate the predicate against the given model'''
        raise NotImplementedError()
    #####################
    # End abstract protocol field redeclarations.
    #####################

    def react(self,
              instance: _Reactant,
              field: _Field,
              old: Any,
              new: Any,
              *,
              reaction: PredicateReaction) -> None:
        '''
        React to a field value changing. If the result of evaluating this
        predicate is True the reaction will be scheduled for execution by
        the fields reaction executor. TODO - update comment once predicates
        have a Reactant to schedule reaction with.
        '''
        logger.log(VERBOSE, 
                   '%s notified that %s %s -> %s',
                   self, field, old, new)

        if self.evaluate(instance):
            logger.debug('%s TRUE for %s %s -> %s',
                         self, field, old, new)
            # todo - don't (below too)
            #        bound field will likely start tracking reactant and
            #        instane independently. Soon.
            reaction_executor = instance._reaction_executor
            reaction_executor.react(reaction,
                                    instance,
                                    field,
                                    old, new)

    def __call__(self, func: PredicateReaction) -> ReactionMustNotBeCalled:
        '''
        Predicates are decorators that arrange for the decorated method to be
        called when the predicate becomes True.

        For example:
            @ State.a != State.b  # State.a, .b are Field, != creates predicate
            async def ...
            
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator, but rather
        the predicate when a field change causes it to become true. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The set of fields the predicate uses are reaction()ed to have the
        predicate react() by scheduling the reaction method to be executed
        asynchronously by the reaction executor (semantics TBD).

        The reaction is executed by the reaction executor in order of
        submission. Reactions are synchronous with respect to the other
        reactions submitted to the reaction executor. The synchronous execution
        model provides atomic semantics between the reactions in the executor.

        Reaction execution start order is undefined (but consistent). It is too
        premature to define it well. It is currently determined by the order
        of the reactions on the field which is the order the predicate
        decorator was applied to the fields in the predicate. It is therefore
        sensitive to which side a field is placed in a predicate, the method
        definition order, and the import order. This should be better defined,
        but at this time it is not. TODO

        TODO - remove ReactionMustNotBeCalled to allow stacking predicate
               decorators?

        TODO - And() is ugly...but if we could do it by stacking predicate
               decorators it's a lot less ugly.
               @ field1 == 1
               @ field2 == 2
               Attempting this currently raises ReactionMustNotBeCalled.
        '''
        # Add a reaction on all the fields to call self.react() with
        # func as the reaction function.
        for field in set(self.fields):
            field.reaction(partial(self.react, reaction=func))
        return ReactionMustNotBeCalled(func)


@dataclass
class Constant[T](_Evaluatable[T], HasNoFields):
    '''An _Evaluatable that always evaluates to it's value.'''
    value: T

    def __eq__(self, other) -> bool:
        return self.value == other

    def __str__(self) -> str:
        return str(self.value)

    def evaluate(self, _) -> T:
        return self.value

    @InvalidPredicateExpression
    def __bool__(self): ...


class OperatorPredicate(Predicate, ABC):
    '''
    Predicate that uses an operator for its logic.
    '''

    operator: Callable[..., bool]

    @property
    @abstractmethod
    def token(self) -> str: ...  # field from subclass

    @classmethod
    def factory[T](cls: Type[T],
                   name: str,
                   token: str,
                   op: Callable[..., bool]
                  ) -> Type[T]:
        '''
        Create a Predicate class using the given op. token is for str/repr
        and has no other use.
        The generated class is exported from the module through __all__.
        '''

        ret = type(name,
                   (cls, ),
                   {'token': token,
                    'operator': op})
        __all__.append(name)
        return ret


@dataclass
class UnaryPredicate(OperatorPredicate, ABC):
    '''Predicate that has a single operand.'''
    expression: _Evaluatable

    def __init__(self, expression: _Evaluatable | Any):
        if not isinstance(expression, _Evaluatable):
            expression = Constant(expression)
        self.expression = expression

    @property
    def fields(self) -> Iterable[_Field]:
        yield from self.expression.fields

    def evaluate(self, instance):
        return self.operator(self.expression.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.token} {self.expression})"


class BinaryPredicate(OperatorPredicate, ABC):
    '''Predicate that has two operands.'''
    left: _Evaluatable
    right: _Evaluatable

    def __init__(self,
                 left: _Evaluatable | Any,
                 right: _Evaluatable | Any):
        # Everything that isn't an _Evaluatable is treated as a constant.
        # This may need to be reevaluated, but it helps with the fields()
        # logic for now.
        super().__init__()
        self.left = left if isinstance(left, _Evaluatable) else Constant(left)
        self.right = right if isinstance(right, _Evaluatable) else Constant(right)


    @property
    def fields(self) -> Iterable[_Field]:
        yield from self.left.fields
        yield from self.right.fields

    def evaluate(self, instance):
        return self.operator(self.left.evaluate(instance),
                             self.right.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"

    __bool__ = InvalidPredicateExpression(
        None, 
        "'Predicate and Predicate' not supported, use "
        "'And(Predicate, Predicate)' instead")


Not = UnaryPredicate.factory('Not', '!not!', operator.not_)
And = BinaryPredicate.factory('And', '!and!', lambda _, a, b: a and b)
Or = BinaryPredicate.factory('Or', 'or', lambda _, a, b: a or b)
Eq: Type[BinaryPredicate] = BinaryPredicate.factory('Eq', '==', operator.eq)
Ne = BinaryPredicate.factory('Ne', '!=', operator.ne)
Lt = BinaryPredicate.factory('Lt', '<', operator.lt)
Le = BinaryPredicate.factory('Le', '<=', operator.le)
Gt = BinaryPredicate.factory('Gt', '>', operator.gt)
Ge = BinaryPredicate.factory('Ge', '>=', operator.ge)
Contains = BinaryPredicate.factory('Contains','contains', operator.contains)

# BinaryAnd and BinaryOr aren't strictly predicates since they don't evaluate
# to a bool. Still useful, so included.
BinaryAnd = BinaryPredicate.factory('BinaryAnd', '&', operator.and_)
BinaryOr = BinaryPredicate.factory('BinaryOr', '|', operator.or_)

