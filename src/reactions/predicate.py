# Copyright (C) 2025 Anthony (Lonnie) Hutchinson <chinacat@chinacat.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
Predicates implement comparison checks.
'''
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any, Callable, Type, Iterable, Coroutine

from .error import InvalidPredicateExpression, ReactionMustNotBeCalled
from .field_descriptor import FieldDescriptor, Evaluatable
from .logging_config import VERBOSE


__all__ = ['Constant']


logger = logging.getLogger("reactions.predicate")


type ReactionCoroutine = Coroutine[Any, Any, None]
# Callable arguments behavior is contravariant to ensure type safety.
# todo  - make FieldDescriptor[T] arg covariant so client code can declare
#         reactions as taking Field[T] rather than FieldDescriptor[T].
#         -- or --
#         Is there someway to make the predicates created by Field take a
#         PredicateReaction that takes Field? This is probably better from
#         a type safety perspective since it doesn't violate type safety :)
# TODO - this _T, B, etc makes errors go away, but specifying different types
#        for T on the reaction (Field[T], T, T) don't show as errors either,
#        is kinda the whole point. The reactions should be type checked against
#        the fields that generated the predicates. Probably need a whole lot
#        more plumbing to get that to work. For now, the errors on the
#        reaction decoration is preferable, so commented out to leave a trace
#        for maybe how to do this.
#type _T = Any
#type B = FieldDescriptor[_T]
#type PredicateReaction[_T, F: B] = Callable[[Any, F, _T, _T],
#                                     ReactionCoroutine]
type PredicateReaction[T] = Callable[[Any, FieldDescriptor[T], T, T],
                                     ReactionCoroutine]

'''
A _Reactant method that is called asynchronously when a _Predicate value
changes.

Predicate reactions are processed asynchronously and require the type that
defines them be a _Reactant so the reaction can be scheduled with the
_ReactionExecutor for the _Reactant.
'''


@dataclass
class Predicate(Evaluatable[bool], ABC):
    '''
    Predicate evaluates expressions.
    T - the type the predicate evaluates to
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

    def react(self,
              instance: Any,
              field: FieldDescriptor,
              old: Any,
              new: Any,
              *,
              reaction: PredicateReaction) -> None:
        '''
        React to a field value changing. If the result of evaluating this
        predicate is True the reaction will be scheduled for execution.
        The executor to use is determined by the object the reaction is being
        called on. For bound method reactions the object the reaction is bound
        to provides the executor, otherwise the instance.
        '''
        logger.log(VERBOSE,
                   '%s notified that %s %s -> %s',
                   self, field, old, new)

        if self.evaluate(instance):
            logger.debug('%s TRUE for %s %s -> %s',
                         self, field, old, new)
            
            # It is noticeably faster to just try to get __self__ than to check
            # inspect.ismethod(react). if reaction is a method the fastest is
            # to try/except AttributeError, but if it's not that is horrendous.
            executor_instance = getattr(reaction, '__self__', instance)

            # Objects that react must provide an executor. This is typically
            # done by deriving from FieldManager or FieldWatcher.
            reaction_executor = executor_instance._reaction_executor
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
        of the reactions on the field, which is the order the predicate
        decorator was applied to the fields in the predicate. It is therefore
        sensitive to which side a field is placed in a predicate, the method
        definition order, and the import order. This should be better defined,
        but at this time it is not. TODO

        Consistency is the hobgoblin....oh, wait, that's entirely different.
        Consistency is provided by the executors sequentially executing
        reactions. Each reaction within an executor can be thought of as a sort
        of transaction. Within an executor reactions will see consistent states
        created by other reactions in the executor. Inconsistent reads will
        occur when the fields being read are updated outside a reaction
        executing in the same executor.

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
            logger.info('changes to %s will call %s', field, func)
            field.reaction(partial(self.react, reaction=func))
        return ReactionMustNotBeCalled(func)


@dataclass
class Constant[T](Evaluatable[T]):
    '''An Evaluatable that always evaluates to it's value.'''
    value: T

    def __eq__(self, other) -> bool:
        return self.value == other

    def __str__(self) -> str:
        return str(self.value)

    def evaluate(self, _) -> T:
        return self.value

    @InvalidPredicateExpression
    def __bool__(self): ...

    @property
    def fields(self) -> Iterable[FieldDescriptor]:
        return ()


class OperatorPredicate(Predicate, ABC):
    '''
    Predicate that uses an operator for its logic.
    '''

    operator: Callable[..., bool]

    @property
    @abstractmethod
    def token(self) -> str:
        '''the operator token (i.e. '==') to use for logging the predicate'''


@dataclass
class UnaryPredicate(OperatorPredicate, ABC):
    '''Predicate that has a single operand.'''
    expression: Evaluatable

    def __init__(self, expression: Evaluatable | Any):
        if not isinstance(expression, Evaluatable):
            expression = Constant(expression)
        self.expression = expression

    @property
    def fields(self) -> Iterable[FieldDescriptor]:
        yield from self.expression.fields

    def evaluate(self, instance):
        return self.operator(self.expression.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.token} {self.expression})"


class BinaryPredicate(OperatorPredicate, ABC):
    '''Predicate that has two operands.'''
    left: Evaluatable
    right: Evaluatable

    def __init__(self,
                 left: Evaluatable | Any,
                 right: Evaluatable | Any):
        # Everything that isn't an Evaluatable is treated as a constant.
        # This may need to be reevaluated, but it helps with the fields()
        # logic for now.
        super().__init__()
        self.left = (left if isinstance(left, Evaluatable)
                          else Constant(left))
        self.right = (right if isinstance(right, Evaluatable)
                            else Constant(right))

    @property
    def fields(self) -> Iterable[FieldDescriptor]:
        yield from self.left.fields
        yield from self.right.fields

    def evaluate(self, instance):
        return self.operator(self.left.evaluate(instance),
                             self.right.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"

    # Disallow evaluation of predicate truthiness as doing so is more likely to
    # cause predicates to not work as expected than there are use cases for it.
    __bool__ = InvalidPredicateExpression( None,
        "bool(Predicate) (or 'Predicate and ...') not supported, use "
        "'And(Predicate, Predicate)' instead")
