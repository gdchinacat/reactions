'''
The predicate implementation types.
'''
from __future__ import annotations

import operator

from .predicate import UnaryPredicate, BinaryPredicate


__all__ = ['Not', 'And', 'Or', 'Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge',
           'Contains', 'BinaryAnd', 'BinaryOr']


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

