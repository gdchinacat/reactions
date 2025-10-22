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
The predicate implementation types.
'''

from typing import overload
import operator

from .field_descriptor import Evaluator
from .predicate import (UnaryPredicate, BinaryPredicate, Predicate,
                        PredicateArgument, PredicateOperand, Decorated,
                        _Reaction)


__all__ = ['Boolean', 'Not', 'And', 'Or', 'Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge',
           'Contains', 'BitwiseAnd', 'BitwiseOr', 'BitwiseNot',
           'ComparisonPredicates']


class Not[Tf](UnaryPredicate[Tf]):
    token = '!not!'
    operator = operator.not_

class Boolean[Tf](UnaryPredicate[Tf]):
    token = 'bool'
    operator = bool

class And[Tf](BinaryPredicate[Tf]):
    # todo? Allow And to take more than two operands? Since it can't be written
    #       as 'foo and bar and baz' and requires And(foo, And(bar, baz)) it
    #       is preptty clunky...And(foo, bar, baz) would be a big improvement.
    token = '!and!'
    operator = lambda _, a, b: a and b

class Or[Tf](BinaryPredicate[Tf]):
    token = '!or!'
    operator = lambda _, a, b: a or b

class Eq[Tf](BinaryPredicate[Tf]):
    token = '=='
    operator = operator.eq

class Ne[Tf](BinaryPredicate[Tf]):
    token = '!='
    operator = operator.ne

class Lt[Tf](BinaryPredicate[Tf]):
    token = '<'
    operator = operator.lt

class Le[Tf](BinaryPredicate[Tf]):
    token = '<='
    operator = operator.le

class Gt[Tf](BinaryPredicate[Tf]):
    token = '>'
    operator = operator.gt

class Ge[Tf](BinaryPredicate[Tf]):
    token = '>='
    operator = operator.ge

class Contains[Tf](BinaryPredicate[Tf]):
    token = 'contains'
    operator = operator.contains

# BitwiseAnd and BitwiseOr aren't strictly predicates since they don't evaluate
# to a bool. Still useful, so included.
class BitwiseAnd[Tf](BinaryPredicate[Tf]):
    token = '&'
    operator = operator.and_

class BitwiseOr[Tf](BinaryPredicate[Tf]):
    token = '|'
    operator = operator.or_

class BitwiseNot[Tf](UnaryPredicate[Tf]):
    token = '~'
    operator = operator.__not__


class ComparisonPredicates[Ti, Tf](Evaluator[Ti, Tf, Tf]):
    '''Mixin to create predicates for the rich compparison function'''
    # Evaluates to the value of the field type, since this provides Field and
    # BoundField with comparison predicates for the specific field on a
    # specific type.
    ##########################################################################
    # Predicate creation operators
    #
    # _type: ignore[override]
    #       suppress override errors on on __eq__ and __ne__ because the
    #       builtin being overridden returns bool and these do not, so the
    #       error is valid. However, this is what the implementation needs to
    #       so so silence the error.
    ###########################################################################
    def __contains__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]: # todo NoReturn
        '''not implemented'''
        raise NotImplementedError('use Contains(self, other) instead')

    @overload
    def __and__(self, other: PredicateOperand[Tf]) -> Predicate[Tf]: ...

    @overload
    def __and__(self, other: Tf) -> Predicate[Tf]: ...

    def __and__(self, other: PredicateOperand[Tf]|Tf) -> Predicate[Tf]:
        '''create a BitwiseAnd (&) predicate for the field'''
        return BitwiseAnd(self, other)

    def __or__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:
        '''create a BitwiseOr (|) predicate for the field'''
        return BitwiseOr(self, other)

    def __invert__(self) -> Predicate[Tf]:
        '''create a BitwiseNot (~) predicate for the field'''
        return BitwiseNot(self)

    def __eq__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:  # type: ignore[override]
        '''create an Eq (==) predicate for the field'''
        return Eq(self, other)

    def __ne__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:  # type: ignore[override]
        '''create an Ne predicate for the field'''
        return Ne(self, other)

    def __lt__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:
        '''create an Lt (<) predicate for the field'''
        return Lt(self, other)

    def __le__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:
        '''create an Le (<=) predicate for the field'''
        return Le(self, other)

    def __gt__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:
        '''create an Gt (>) predicate for the field'''
        return Gt(self, other)

    def __ge__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:
        '''create an Ge (>=) predicate for the field'''
        return Ge(self, other)

    def __call__[Tw](self, decorated: Decorated[Tw, Ti, Tf]
                    ) -> _Reaction[Tw, Ti, Tf]:
        '''Can be used as a decorator to create a predicate Boolean'''
        return Boolean(self)(decorated)
