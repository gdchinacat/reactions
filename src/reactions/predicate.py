# Copyright (C) 2025 Anthony (Lonnie) Hutchinson <chinacat@chinacat.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR PredicateArgument PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

'''
Predicates implement comparison checks.
'''
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial
from typing import TypeVar, overload, Any, cast
import logging

from .error import InvalidPredicateExpression, ReactionMustNotBeCalled
from .field_descriptor import (FieldDescriptor, Evaluator, FieldChange,
                               BoundReaction, Reaction)
from .logging_config import VERBOSE


__all__ = ['Constant']


logger = logging.getLogger("reactions.predicate")


Tp = TypeVar('Tp')
'''the predicate type, composed of field types it is created from'''


@dataclass
class CustomFieldReactionConfiguration[Tw, Ti, Tf]:
    '''
    CustomFieldReactionConfiguration indicates to Predicate.__call__ that
    field reactions should not be handled by the Predicate decorator. The
    decorator will still return a _Reaction that references the reaction that
    can be used to do this configuration.

    FieldWatcher (typically) subclass reactions are decorated with this class
    so that the predicates that decorate them do not register field reactions.
    Instead, the CustomFieldReactionConfiguration.reaction is added as a
    reaction on the fields or the reactions of the subclass bound to the
    instance.
    '''
    reaction: BoundReaction[Tw, Ti, Tf] | None  # todo typing reaction


@dataclass(eq=True, frozen=True)
class _Reaction[Tw, Ti, Tf](ReactionMustNotBeCalled):
    '''
    The result of decorating a reaction function.
    '''
    predicate: Predicate[Tf]
    func: Reaction[Ti, Tf] | BoundReaction[Tw, Ti, Tf]


type Decorated[Tw, Ti, Tf] = ( Reaction[Ti, Tf]
                              |CustomFieldReactionConfiguration[Tw, Ti, Tf])
'''
Decorated is the type of things that Predicate can decorate or arguments
to the predicate decorator (Predicate.__call__).
'''


class Predicate[Tf](Evaluator[Any, bool, Tf], ABC):
    
    '''
    Predicate decorates reactions to be called when field changes cause the
    predicate to become true.
    Predicates evaluate to boolean values that indicate the truth of the
    predicate against an instance (.evaluate()). They do not have an instance
    # type because predicates can be composed of fields from any type.

    Predicates are typically created through Field and Predicate comparison
    methods:
        field = Field(None)
        field == 'value'  # creates a predicate

    Predicates objects are immutable and hashable.
    It is an Evaluator for any type of instance since Predicates may be
    composed of fields from different instance types.
    '''

    def react[Ti](self,
              change: FieldChange[Ti, Tf],
              *,
              reaction: Reaction[Ti, Tf]) -> None:
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
            #      isn't great. It's complicated by Executors being able to
            #      be provided on creation of watchers. This should not require
            #      instances have executors nor that watchers should have
            #      executors. The semantics are that either one or the other
            #      must have executor, which doesn't seem possible to express
            #      with static type hints.
            #      For now, this code just gets it and will error out
            #      if neither do. Unfortunately any errors from mistrust will
            #      not occur until the reaction executes. PredicateArgument similar issue
            #      exists with FieldWatcher executor assignment.
            executor_provider = getattr(  # get executor from:
                reaction, '__self__',  # the instance reaction is bound to
                change.instance)       # or the instance the field changed on
            executor = executor_provider.executor  # type: ignore
            executor.react(reaction, change)

    def __call__[Tw, Ti](self,
                         decorated: Decorated[Tw, Ti, Tf]
                        ) -> _Reaction[Tw, Ti, Tf]:
        '''
        Predicates are decorators that arrange for the decorated method to be
        called when the predicate becomes True.

        For example:
            @ State.a != State.b  # State.a, .b are Field, != creates predicate
            async def ...
            
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator, but rather
        the predicate when a field change causes it to become true. PredicateArgument dummy
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
        reaction: Reaction[Ti, Tf] | BoundReaction[Tw, Ti, Tf]
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

    def configure_reaction[Tw, Ti](self,
                                   reaction:Reaction[Ti, Tf],
                                   instance: Ti|None = None) -> None:
        '''configure the reaction on the fields'''
        # Add a reaction on all the fields to call self.react() with
        # func as the reaction function.
        for field in set(self.fields):
            field_ = (field.bound_field(instance)
                      if instance is not None else field)
            logger.info('changes to %s will call %s', field, reaction)
            field_.reaction(partial(self.react, reaction=reaction))


@dataclass
class Constant[Tf](Evaluator[Any, Tf, Tf]):
    '''An Evaluator that always evaluates to it's value.'''
    value: Tf

    def __eq__(self, other: object) -> bool:
        return self.value == other

    def __str__(self) -> str:
        return str(self.value)

    def evaluate[Ti](self, _: Ti) -> Tf:
        return self.value

    @InvalidPredicateExpression
    def __bool__(self) -> None: ...

    @property
    def fields(self) -> Iterator[FieldDescriptor[Any, Tf]]:
        return iter(())


class OperatorPredicate[Tf](Predicate[Tf], ABC):
    '''
    Predicate that uses an operator for its logic.
    '''

    operator: Callable[..., bool]

    @property
    @abstractmethod
    def token(self) -> str:
        '''the operator token (i.e. '==') to use for logging the predicate'''


type Pe[Tf] = Evaluator[Any, bool, Tf]  # predicate evaluator
type Fe[Tf] = Evaluator[Any, Tf, Tf]    # field evaluator
type PredicateOperand[Tf] = Pe[Tf] | Fe[Tf]            # Operand
type PredicateArgument[Tf] = PredicateOperand[Tf] | Tf                 # Argument


class UnaryPredicate[Tf](OperatorPredicate[Tf], ABC):
    '''Predicate that has a single operand.'''
    operand: PredicateOperand[Tf]

    # For some unknown reason, not having these overloads causes mypy to expect
    # never if isinstance(operand, Evaluator). Starting to doubt mypy is worth
    # the effort. No change required to the implementation, just tell it that
    # sometimes it is called with evaluators and sometimes TF and it suddenly
    # realizes that TF isn't a Never in Evaluator generic.
    @overload
    def __init__(self, operand: PredicateOperand[Tf]) -> None: ...
    
    @overload
    def __init__(self, operand: Tf) -> None: ...
    
    def __init__(self, operand: PredicateArgument[Tf]) -> None:
        if not isinstance(operand, Evaluator):
            operand = Constant(operand)
        self.operand = operand

    @property
    def fields(self) -> Iterator[FieldDescriptor[Any, Tf]]:
        yield from self.operand.fields

    def evaluate[Ti](self, instance: Ti) -> bool:
        return self.operator(self.operand.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.token} {self.operand})"


class BinaryPredicate[Tfl, Tfr](OperatorPredicate[Tfl|Tfr], ABC):
    '''Predicate that has two operands.'''
    left: PredicateOperand[Tfl]
    right: PredicateOperand[Tfr]

    @overload
    def __init__(self,
                 left: PredicateOperand[Tfl],
                 right: PredicateOperand[Tfr]) -> None: ...

    @overload
    def __init__(self, left: Tfl, right: Tfr) -> None: ...
    
    @overload
    def __init__(self, left: PredicateOperand[Tfl], right: Tfr) -> None: ...
    
    @overload
    def __init__(self, left: Tfl, right: PredicateOperand[Tfr]) -> None: ...

    def __init__(self, left: PredicateOperand[Tfl]|Tfl, right: PredicateOperand[Tfr]|Tfr) -> None:
        # Everything that isn't an Evaluator is treated as a constant.
        # This may need to be reevaluated, but it helps with the fields()
        # logic for now.
        super(BinaryPredicate, self).__init__()
        self.left = (left if isinstance(left, Evaluator)
                          else Constant(left))
        self.right = (right if isinstance(right, Evaluator)
                            else Constant(right))

    @property
    def fields(self) -> Iterator[FieldDescriptor[Any, Tfl|Tfr]]:
        # widening cast to allow [.., Tfl] to be used in for a [../, Tfl|Tfr]
        yield from cast(Iterator[FieldDescriptor[Any, Tfl|Tfr]],
                        self.left.fields)
        yield from cast(Iterator[FieldDescriptor[Any, Tfl|Tfr]],
                        self.right.fields)

    def evaluate[Ti](self, instance: Ti) -> bool:
        return self.operator(self.left.evaluate(instance),
                             self.right.evaluate(instance))

    def __str__(self) -> str:
        return f"({self.left} {self.token} {self.right})"

    # Disallow evaluation of predicate truthiness as doing so is more likely to
    # cause predicates to not work as expected than there are use cases for it.
    __bool__ = InvalidPredicateExpression( None,
        "bool(Predicate) (or 'Predicate and ...') not supported, use "
        "'And(Predicate, Predicate)' instead")
