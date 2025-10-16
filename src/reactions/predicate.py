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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from typing import TypeVar, overload
import logging

from .error import InvalidPredicateExpression, ReactionMustNotBeCalled
from .executor import HasExecutor, Reaction, BoundReaction
from .field_descriptor import FieldDescriptor, Evaluatable, FieldChange, Tf, Ti
from .logging_config import VERBOSE


__all__ = ['Constant']


logger = logging.getLogger("reactions.predicate")


Tp = TypeVar('Tp')
'''the predicate type, composed of field types it is created from'''


@dataclass
class CustomFieldReactionConfiguration[Tp]:
    '''
    Class to indicate to Predicate.__call__ that field reactions should not
    be handled by the Predicate decorator. The decorator will still return a
    _Reaction that references the reaction that can be used to do this
    configuration.
    '''
    reaction: BoundReaction[Tp]|None


@dataclass(eq=True, frozen=True)
class _Reaction[Tp](ReactionMustNotBeCalled):
    '''
    The result of decorating a reaction function.
    '''
    predicate: Predicate[Tp]
    func: Reaction[Tp]|BoundReaction[Tp]


type Decoratee[Tf, Tr, Tp] = Reaction[Tf, Tr]|CustomFieldReactionConfiguration[Tp]
'''
Decoratee is the type of things that Predicate can decorate or arguments
to the predicate decorator (Predicate.__call__).
'''

@dataclass(eq=True, frozen=True)
class Predicate[Tp](Evaluatable[bool], ABC):
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

    Predicates objects are immutable and hashable.
    '''

    def react(self, change: FieldChange[Ti, Tf], *, reaction: Reaction) -> None:
        '''
        React to a field value changing. If the result of evaluating this
        predicate is True the reaction will be scheduled for execution.
        The executor to use is determined by the object the reaction is being
        called on. For bound method reactions the object the reaction is bound
        to provides the executor, otherwise the instance.
        '''
        # todo - I forgot to make a reaction async, and it didn't work as
        # expected, but the behavior was pretty close to what I've been
        # considering adding. When the non-async reaction was called to get the
        # coroutine it executed the reaction synchronously. Of course things
        # didn't work right, but I think skipping the put_nowait() if
        # coroutine is None would be a trivial way to allow reactions to
        # execute inline with the field update. The *big* concern here is the
        # consistency guarantees that are based on coroutine execution would be
        # broken. Either support this mode of synchronous reaction or disallow
        # it. Also stack overflow is likely. Probably a bad idea in general,
        # but wanted to document it until I get around to formalizing whatever
        # I decide.
        logger.log(VERBOSE, '%s notified that %s', self, change)

        if self.evaluate(change.instance):
            logger.debug('%s TRUE for %s', self, change)

            # Objects that react must provide an executor. This is typically
            # done by deriving from FieldManager or FieldWatcher.
            # todo type safety for getting executor...just hoping it's there
            #      isn't great.
            executor_provider: HasExecutor = getattr(reaction, '__self__',
                                                     change.instance)
            reaction_executor = executor_provider.executor
            reaction_executor.react(reaction, change)

    @overload
    def __call__(self, decorated: Reaction) -> _Reaction: ...

    @overload
    def __call__(self, decorated: CustomFieldReactionConfiguration
                 ) -> _Reaction: ...

    def __call__(self, decorated: Decoratee) -> _Reaction:
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

        Field reactions are not configured if the decorated func is an instance
        of CustomFieldReactionConfiguration. This is used by FieldWatcher to
        not configure reactions that need to be bound to specific instances
        (rather than the classes that fields are on).
        '''
        reaction: Reaction|BoundReaction
        if isinstance(decorated, CustomFieldReactionConfiguration):
            assert decorated.reaction
            reaction = decorated.reaction
            logger.info('changes to %s will use %s to '
                        'create bound reactions for %s',
                        ', '.join(str(f) for f in self.fields),
                        decorated, self)
        else:
            reaction = decorated
            self.configure_reaction(reaction)
        return _Reaction(self, reaction)

    def configure_reaction(self, func: Reaction,
                           instance: Ti = None) -> None:
        '''configure the reaction on the fields'''
        # Add a reaction on all the fields to call self.react() with
        # func as the reaction function.
        for field in set(self.fields):
            field_ = (field.bound_field(instance)
                      if instance is not None else field)
            logger.info('changes to %s will call %s', field, func)
            field_.reaction(partial(self.react, reaction=func))

@dataclass
class Constant[T](Evaluatable[T]):
    '''An Evaluatable that always evaluates to it's value.'''
    value: T

    def __eq__(self, other: object) -> bool:
        return self.value == other

    def __str__(self) -> str:
        return str(self.value)

    def evaluate(self, _: object) -> T:
        return self.value

    @InvalidPredicateExpression
    def __bool__(self) -> None: ...

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


class UnaryPredicate(OperatorPredicate, ABC):
    '''Predicate that has a single operand.'''
    expression: Evaluatable

    def __init__(self, expression: Evaluatable[Tp] | object) -> None:
        if not isinstance(expression, Evaluatable):
            expression = Constant(expression)
        self.expression = expression

    @property
    def fields(self) -> Iterable[FieldDescriptor]:
        yield from self.expression.fields

    def evaluate(self, instance: Ti) -> bool:
        return self.operator(self.expression.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.token} {self.expression})"


class BinaryPredicate(OperatorPredicate, ABC):
    '''Predicate that has two operands.'''
    left: Evaluatable
    right: Evaluatable

    def __init__(self,
                 left: Evaluatable | object,
                 right: Evaluatable | object) -> None:
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

    def evaluate(self, instance: Ti) -> bool:
        return self.operator(self.left.evaluate(instance),
                             self.right.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"

    # Disallow evaluation of predicate truthiness as doing so is more likely to
    # cause predicates to not work as expected than there are use cases for it.
    __bool__ = InvalidPredicateExpression( None,
        "bool(Predicate) (or 'Predicate and ...') not supported, use "
        "'And(Predicate, Predicate)' instead")
