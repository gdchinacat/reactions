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

from typing import overload, override, Never, Sequence, Any
import operator

from .field_descriptor import Evaluator, Reaction
from .predicate import (UnaryPredicate, BinaryPredicate, Predicate,
                        PredicateArgument, PredicateOperand, _Reaction)


__all__ = ['Boolean', 'Not', 'And', 'Or', 'Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge',
           'Contains', 'BitwiseAnd', 'BitwiseOr', 'BitwiseNot',
           'ComparisonPredicates', 'TruePredicate', 'Mod']


class TruePredicate[Tf](UnaryPredicate[Tf]):
    '''
    Predicate that is always true.
    '''

    @property
    def token(self) -> str: return 'True'

    def evaluate(self, instance: object)->bool:
        return True


class Boolean[Tf](UnaryPredicate[Tf]):
    @property
    def token(self) -> str: return 'bool'
    operator = bool

class Not[Tf](UnaryPredicate[Tf]):
    @property
    def token(self) -> str: return '!not!'
    operator = operator.not_

    @override
    def __init__(self, operand: Predicate[Tf]) -> None:
        return super().__init__(operand)

class _And[Tfl, Tfr](BinaryPredicate[Tfl, Tfr]):
    '''_And is a BinaryPredicate implementation used by variadic And'''
    @property
    def token(self) -> str: return '!and!'
    operator = lambda _, a, b: a and b

    @override
    def __init__(self, left: Predicate[Tfl], right: Predicate[Tfr]) -> None:
        super().__init__(left, right)

# And overloads are to allow correct typing for small number of variadic
# arguments. Python typing does not provide a way to accurately type this for
# an unbounded number of arguments. This is a compromise solution.
@overload
def And[Tf](p1: Predicate[Tf], /) -> Predicate[Tf]: ...

@overload
def And[Tf1, Tf2](p1: Predicate[Tf1],
                  p2: Predicate[Tf2], /) -> Predicate[Tf1|Tf2]: ...

@overload
def And[Tf1, Tf2, Tf3](p1: Predicate[Tf1],
                       p2: Predicate[Tf2],
                       p3: Predicate[Tf3], /) -> Predicate[Tf1|Tf2|Tf3]: ...

@overload
def And[Tf1, Tf2, Tf3,  Tf4](p1: Predicate[Tf1],
                             p2: Predicate[Tf2],
                             p3: Predicate[Tf3],
                             p4: Predicate[Tf4],
                             /) -> Predicate[Tf1|Tf2|Tf3|Tf4]: ...

def And[Tf](p1: Predicate[Tf],
            *predicates: Predicate[Any]) -> Predicate[Any]:
    '''
    Predicate that is true IFF all of it's argument predicates are true.

    @ And(C.a == 'aar',
          C.b == 'bar',
          C.c != 'car',
          ...
          )
    '''
    _predicates: Sequence[Predicate[Any]] = predicates
    ret = p1
    while _predicates:
        b, *_predicates = _predicates
        ret = _And(ret, b)
    return ret

class Or[Tfl,Tfr](BinaryPredicate[Tfl, Tfr]):
    @property
    def token(self) -> str: return '!or!'
    operator = lambda _, a, b: a or b

    @override
    def __init__(self, left: Predicate[Tfl], right: Predicate[Tfr]) -> None:
        super().__init__(left, right)

class Eq[Tf](BinaryPredicate[Tf, Tf]):
    operator = operator.eq
    @property
    def token(self) -> str: return '=='

class Ne[Tf](BinaryPredicate[Tf, Tf]):
    operator = operator.ne
    @property
    def token(self) -> str: return '!='

class Lt[Tf](BinaryPredicate[Tf, Tf]):
    operator = operator.lt
    @property
    def token(self) -> str: return '<'

class Le[Tf](BinaryPredicate[Tf, Tf]):
    operator = operator.le
    @property
    def token(self) -> str: return '<='

class Gt[Tf](BinaryPredicate[Tf, Tf]):
    operator = operator.gt
    @property
    def token(self) -> str: return '>'

class Ge[Tf](BinaryPredicate[Tf, Tf]):
    @property
    def token(self) -> str: return '>='
    operator = operator.ge

class Contains[Tf](BinaryPredicate[Tf, Tf]):
    @property
    def token(self) -> str: return 'contains'
    operator = operator.contains


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
    def __contains__(self, other: object) -> Never:
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

    def __call__[Tw](self, reaction: Reaction[Ti, Tf]
                    ) -> _Reaction[Tw, Ti, Tf]:
        '''Can be used as a decorator to create a predicate Boolean'''
        return TruePredicate(self)(reaction)

    def __mod__(self, other: PredicateArgument[Tf]) -> Predicate[Tf]:
        '''Can be used as a decorator to create a predicate Boolean'''
        return Mod(self, other)


# These aren't strictly predicate since they don't return bool, but are useful
# in predicate expressions. Unlike the other Predicates they are also
# ComparisonPredicates so they can be evaluated and compared (@ field % 2 == 1)
class BitwiseAnd[Ti, Tf](BinaryPredicate[Tf, Tf],
                         ComparisonPredicates[Ti, Tf]):
    @property
    def token(self) -> str: return '&'
    operator = operator.and_

class BitwiseOr[Ti, Tf](BinaryPredicate[Tf, Tf],
                        ComparisonPredicates[Ti, Tf]):
    @property
    def token(self) -> str: return '|'
    operator = operator.or_

class BitwiseNot[Ti, Tf](UnaryPredicate[Tf],
                         ComparisonPredicates[Ti, Tf]):
    @property
    def token(self) -> str: return '~'
    operator = operator.__not__

class Mod[Ti, Tf](BinaryPredicate[Tf, Tf],
                  ComparisonPredicates[Ti, Tf]):
    @property
    def token(self) -> str: return '%'
    operator = operator.mod
