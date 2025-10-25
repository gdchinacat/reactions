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
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest import TestCase, main

from ..error import InvalidPredicateExpression
from ..field import Field
from ..field_descriptor import FieldDescriptor, FieldChange
from ..predicate import Constant
from ..predicate_types import (Eq, Ne, Lt, Le, Gt, Ge, Contains, Not, Or,
                And, BitwiseAnd, BitwiseOr, BitwiseNot, Boolean,
                ComparisonPredicates)


class TestPredicate(TestCase):

    @contextmanager
    def assertReactionAdded(self, field: FieldDescriptor[Any, Any]
                       ) -> Iterator[None]:
        '''assert that a reaction is added to the field'''
        count = len(field.reactions)
        yield None
        self.assertEqual(len(field.reactions), count + 1)

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

    def test_and_predicate_evaluate(self) -> None:
        class C:
            field = Field['C', bool](False, 'C', 'field')

        c = C()
        self.assertFalse(And(Boolean(C.field), Boolean(C.field)).evaluate(c))

        c.field = True
        self.assertTrue(And(Boolean(C.field), Boolean(C.field)).evaluate(c))

    def test_and_predicate_decorate_creates_reaction(self) -> None:
        class C:
            field_a = Field['C', bool](False, 'C', 'field_a')
            field_b = Field['C', bool](False, 'C', 'field_b')

        with self.assertReactionAdded(C.field_a):
            # The predicates don't matter since it is never evaluated.
            @ And(C.field_a == True, C.field_a == False)
            async def _(c: C, change: FieldChange[C, bool]) -> None: ...

    def test_not_predicate(self) -> None:
        class C:
            field = Field['C',bool](True, 'C', 'field')
        c = C()
        true_predicate = C.field == True
        false_predicate = C.field == False
        self.assertTrue(Not(false_predicate).evaluate(c))
        self.assertFalse(Not(true_predicate).evaluate(c))

    def test_binary_or_predicate(self) -> None:
        self.assertEqual(0b11, BitwiseOr(0b01, 0b10).evaluate(None))

    def test_binary_and_predicate(self) -> None:
        self.assertEqual(0b010, BitwiseAnd(0b111, 0b010).evaluate(None))

    def test_and_invalid_predicate(self) -> None:
        class C:
            field = Field['C', bool](False, 'C', 'field')
        with self.assertRaises(InvalidPredicateExpression):
            Constant(1) and Constant(1)
        with self.assertRaises(InvalidPredicateExpression):
            p = C.field == True
            And(p, p) and And(p, p)

    def test_boolean_predicate(self) -> None:
        self.assertTrue(Boolean(True).evaluate(None))
        self.assertFalse(Boolean(False).evaluate(None))
        self.assertTrue(Boolean(object()).evaluate(None))
        self.assertFalse(Boolean(None).evaluate(None))

    def test_comparison_creates_predicate(self) -> None:
        class C: ...
        class Creator(ComparisonPredicates[C, int]):
            def evaluate(self, instance: C)->bool:
                raise NotImplementedError()
            @property
            def fields(self)->Iterator[FieldDescriptor[C, int]]:
                raise NotImplementedError()

        creator = Creator()

        self.assertIsInstance(creator == 0, Eq)
        self.assertIsInstance(creator != 0, Ne)
        self.assertIsInstance(creator < 0, Lt)
        self.assertIsInstance(creator <= 0, Le)
        self.assertIsInstance(creator > 0, Gt)
        self.assertIsInstance(creator >= 0, Ge)
        self.assertIsInstance(creator & 0, BitwiseAnd)
        self.assertIsInstance(creator | 0, BitwiseOr)
        self.assertIsInstance(~creator, BitwiseNot)
