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
           'Contains', 'BinaryAnd', 'BinaryOr', 'BinaryNot',
           'ComparisonPredicates']


class Not(UnaryPredicate):
    token = '!not!'
    operator = operator.not_

class And(BinaryPredicate):
    token = '!and!'
    operator = lambda _, a, b: a and b

class Or(BinaryPredicate):
    token = '!or!'
    operator = lambda _, a, b: a or b

class Eq(BinaryPredicate):
    token = '=='
    operator = operator.eq

class Ne(BinaryPredicate):
    token = '!='
    operator = operator.ne

class Lt(BinaryPredicate):
    token = '<'
    operator = operator.lt

class Le(BinaryPredicate):
    token = '<='
    operator = operator.le

class Gt(BinaryPredicate):
    token = '>'
    operator = operator.gt

class Ge(BinaryPredicate):
    token = '>='
    operator = operator.ge

class Contains(BinaryPredicate):
    token = 'contains'
    operator = operator.contains

# BinaryAnd and BinaryOr aren't strictly predicates since they don't evaluate
# to a bool. Still useful, so included.
class BinaryAnd(BinaryPredicate):
    token = '&'
    operator = operator.and_

class BinaryOr(BinaryPredicate):
    token = '|'
    operator = operator.or_

class BinaryNot(BinaryPredicate):
    token = '~'
    operator = operator.or_


class ComparisonPredicates:
    '''Mixin to create predicates for the rich compparison function'''
    ##########################################################################
    # Predicate creation operators
    #
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
        return BinaryAnd(self, other)

    def __or__(self, other) -> Predicate:
        '''create an Or (|) predicate for the field'''
        return BinaryOr(self, other)

    def __eq__(self, other) -> Predicate:  # type: ignore[override]
        '''create an Eq (==) predicate for the field'''
        return Eq(self, other)

    def __ne__(self, other) -> Predicate:  # type: ignore[override]
        '''create an Eq predicate for the field'''
        return Ne(self, other)

    def __lt__(self, other) -> Predicate:
        '''create an Lt (<) predicate for the field'''
        return Lt(self, other)

    def __le__(self, other) -> Predicate:
        '''create an Le (<=) predicate for the field'''
        return Le(self, other)

    def __gt__(self, other) -> Predicate:
        '''create an Gt (>) predicate for the field'''
        return Gt(self, other)

    def __ge__(self, other) -> Predicate:
        '''create an Ge (>=) predicate for the field'''
        return Ge(self, other)
