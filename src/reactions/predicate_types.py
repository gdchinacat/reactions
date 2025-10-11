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

from __future__ import annotations

from typing import NoReturn
import operator

from .predicate import UnaryPredicate, BinaryPredicate, Predicate


__all__ = ['Not', 'And', 'Or', 'Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge',
           'Contains', 'BinaryAnd', 'BinaryOr', 'ComparisonPredicates']


Not = UnaryPredicate.factory('Not', '!not!', operator.not_, __all__)
And = BinaryPredicate.factory('And', '!and!', lambda _, a, b: a and b, __all__)
Or = BinaryPredicate.factory('Or', 'or', lambda _, a, b: a or b, __all__)
Eq = BinaryPredicate.factory('Eq', '==', operator.eq, __all__)
Ne = BinaryPredicate.factory('Ne', '!=', operator.ne, __all__)
Lt = BinaryPredicate.factory('Lt', '<', operator.lt, __all__)
Le = BinaryPredicate.factory('Le', '<=', operator.le, __all__)
Gt = BinaryPredicate.factory('Gt', '>', operator.gt, __all__)
Ge = BinaryPredicate.factory('Ge', '>=', operator.ge, __all__)
Contains = BinaryPredicate.factory('Contains','contains', operator.contains, __all__)

# BinaryAnd and BinaryOr aren't strictly predicates since they don't evaluate
# to a bool. Still useful, so included.
BinaryAnd = BinaryPredicate.factory('BinaryAnd', '&', operator.and_, __all__)
BinaryOr = BinaryPredicate.factory('BinaryOr', '|', operator.or_, __all__)


class ComparisonPredicates:
    '''Mixin to create predicates for the rich compparison function'''
    ##########################################################################
    # Predicate creation operators
    #
    # todo - pylint too-many-function-args is disabled because it doesn't seem
    #        to understand that they are classes.
    # type: ignore[override]
    #       suppress override errors on on __eq__ and __ne__ because the
    #       builtin being overridden returns bool and these do not, so the
    #       error is valid. However, this is what the implementation needs to
    #       so so silence the error.
    ###########################################################################
    # TODO - the returned predicates need to have the type of the field that
    #        created them in their type so that when they are called the type
    #        of field the PredicateReaction accepts will match.
    def __contains__(self, other) -> NoReturn:
        '''not implemented'''
        raise NotImplementedError('use Contains(self, other) instead')

    def __and__(self, other) -> Predicate:
        '''create an And (&) predicate for the field'''
        return BinaryAnd(self, other)  # pylint: disable=too-many-function-args

    def __or__(self, other) -> Predicate:
        '''create an Or (|) predicate for the field'''
        return BinaryOr(self, other)  # pylint: disable=too-many-function-args

    def __eq__(self, other) -> Predicate:  # type: ignore[override]
        '''create an Eq (==) predicate for the field'''
        return Eq(self, other)  # pylint: disable=too-many-function-args

    def __ne__(self, other) -> Predicate:  # type: ignore[override]
        '''create an Eq predicate for the field'''
        return Ne(self, other)  # pylint: disable=too-many-function-args

    def __lt__(self, other) -> Predicate:
        '''create an Lt (<) predicate for the field'''
        return Lt(self, other)  # pylint: disable=too-many-function-args

    def __le__(self, other) -> Predicate:
        '''create an Le (<=) predicate for the field'''
        return Le(self, other)  # pylint: disable=too-many-function-args

    def __gt__(self, other) -> Predicate:
        '''create an Gt (>) predicate for the field'''
        return Gt(self, other)  # pylint: disable=too-many-function-args

    def __ge__(self, other) -> Predicate:
        '''create an Ge (>=) predicate for the field'''
        return Ge(self, other)  # pylint: disable=too-many-function-args
