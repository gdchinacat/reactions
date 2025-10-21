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
from unittest import TestCase, main

from .. import (Eq, Ne, Lt, Le, Gt, Ge, Contains, Constant, Not, Or,
                And, BinaryAnd, BinaryOr, Boolean, InvalidPredicateExpression)

class TestPredicate(TestCase):

    def test_eq_constant_constant(self) -> None:
        self.assertTrue(Eq(1, 1).evaluate(None))
        self.assertFalse(Eq(1, 2).evaluate(None))

    def test_eq_constant_expression(self) -> None:
        self.assertTrue(Eq(1,  Constant(1)).evaluate(None))
        self.assertFalse(Eq(1, Constant(2)).evaluate(None))

    def test_eq_expression_constant(self) -> None:
        self.assertTrue(Eq(Constant(1), 1).evaluate(None))
        self.assertFalse(Eq(Constant(1), 2).evaluate(None))

    def test_eq_constant_predicate(self) -> None:
        self.assertTrue(Eq(Constant(1), 1).evaluate(None))

    def test_ne_constant_predicate(self) -> None:
        self.assertFalse(Ne(Constant(1), 1).evaluate(None))
        self.assertTrue(Ne(Constant(1), 0).evaluate(None))

    def test_lt_constant_predicate(self) -> None:
        self.assertFalse(Lt(Constant(1), 1).evaluate(None))
        self.assertTrue(Lt(Constant(0), 1).evaluate(None))

    def test_le_constant_predicate(self) -> None:
        self.assertTrue(Le(Constant(1), 1).evaluate(None))
        self.assertFalse(Le(Constant(1), 0).evaluate(None))

    def test_gt_constant_predicate(self) -> None:
        self.assertFalse(Gt(Constant(1), 1).evaluate(None))
        self.assertTrue(Gt(Constant(2), 1).evaluate(None))

    def test_ge_constant_predicate(self) -> None:
        self.assertTrue(Ge(Constant(1), 1).evaluate(None))
        self.assertFalse(Ge(Constant(0), 1).evaluate(None))

    def test_contains_constant_predicate(self) -> None:
        self.assertTrue(Contains(Constant((1, )), 1).evaluate(None))
        self.assertFalse(Contains(Constant((1, )), 2).evaluate(None))

    def test_or_predicate(self) -> None:
        self.assertTrue(Or(True, False).evaluate(None))
        self.assertFalse(Or(False, False).evaluate(None))

    def test_and_predicate(self) -> None:
        self.assertFalse(And(True, False).evaluate(None))
        self.assertTrue(And(True, True).evaluate(None))

    def test_not_predicate(self) -> None:
        self.assertTrue(Not(False).evaluate(None))
        self.assertFalse(Not(True).evaluate(None))

    def test_binary_or_predicate(self) -> None:
        self.assertEqual(0b11, BinaryOr(0b01, 0b10).evaluate(None))

    def test_binary_and_predicate(self) -> None:
        self.assertEqual(0b010, BinaryAnd(0b111, 0b010).evaluate(None))

    def test_and_invalid_predicate(self) -> None:
        with self.assertRaises(InvalidPredicateExpression):
            Constant(1) and Constant(1)
        with self.assertRaises(InvalidPredicateExpression):
            And(True, True) and And(True, True)

    def test_boolean_predicate(self) -> None:
        self.assertTrue(Boolean(True).evaluate(None))
        self.assertFalse(Boolean(False).evaluate(None))
        self.assertTrue(Boolean(object()).evaluate(None))
        self.assertFalse(Boolean(None).evaluate(None))

if __name__ == '__main__':
    main()
