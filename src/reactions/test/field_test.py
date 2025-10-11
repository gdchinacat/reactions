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
Test field functionality.
'''
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, List, NoReturn
from unittest import TestCase, main

from ..error import (MustNotBeCalled, FieldAlreadyBound,
                     InvalidPredicateExpression)
from ..field import Field, BoundField, FieldManager
from ..predicate import Predicate
from ..predicate_types import Contains, Not, Or, And


class Base(FieldManager):
    field_a: Field[bool|int|None]
    field_b: Field[bool|int|None]

    def __init__(self,
                 a: bool|int|None = None,
                 b: bool|int|None = None) -> NoReturn:
        raise Exception()

    def _start(self)->None:
        pass

def create_class()->type[Base]:
    @dataclass
    class C(Base):
        field_a: Field[bool|int|None] = Field(None, 'C', 'field_a')
        field_b: Field[bool|int|None] = Field(None, 'C', 'field_b')
    return C

class TestField(TestCase):

    def test_class_field_eq_creates_predicate(self):
        C = create_class()
        predicate = C.field_a == True
        self.assertIsInstance(predicate, Predicate)
        self.assertEqual(list(predicate.fields), [C.field_a])

    def test_del_field_not_allowed(self):
        C = create_class()
        c = C(True, False)
        with self.assertRaises(MustNotBeCalled):
            del c.field_a
            c.field_a

    def test_instance_field_equality(self):
        C = create_class()
        c = C(True, False)
        self.assertTrue(c.field_a == True)

        # set a notification on c.field_a to call print
        reaction_called = False
        def reaction(instance: C, field: BoundField[C, bool],
                     old: bool, new: bool):
            nonlocal reaction_called
            reaction_called = True  # @UnusedVariable - it really is used
            self.assertEqual((instance, field, old, new),
                             (c, C.field_a, True, False))
            pass
        C.field_a.reaction(reaction)

        # verify updated value is properly set and comparison works
        c.field_a = False
        self.assertTrue(c.field_a == False)
        self.assertTrue(c.field_a != True)
        self.assertTrue(reaction_called)

    def test_edge_triggered_notify(self) -> None:
        C = create_class()
        changes: List[Tuple[bool, bool]] = list[Tuple[bool, bool]]()
        def collect(instance, field: Field[bool], old: bool, new: bool):
            changes.append((old, new))

        c: type[Base] = C()
        C.field_a.reaction(collect)

        for value in (True, False, False, True, True):
            c.field_a = value
        c.field_a = None
        self.assertEqual([(None, True),
                          (True, False),
                          (False, True),
                          (True, None)],
                         changes)

    def test_predicate_operators(self) -> None:
        C = create_class()
        c: Base = C(True, 0)
        self.assertTrue((C.field_a == True).evaluate(c))
        self.assertFalse((C.field_a != True).evaluate(c))
        self.assertTrue((C.field_b < 1).evaluate(c))
        self.assertTrue((C.field_b <= 0).evaluate(c))
        self.assertTrue((C.field_b > -1).evaluate(c))
        self.assertTrue((C.field_b >= 0).evaluate(c))

        # bitwise and and or, not logical (not strictly predicates)
        self.assertEqual(1, (C.field_b | 1).evaluate(c))
        self.assertEqual(0, (C.field_b & 1).evaluate(c))

        # No operators for these predicates
        self.assertFalse((Not(C.field_a)).evaluate(c))
        self.assertTrue(Or(C.field_b, True).evaluate(c))
        self.assertFalse(And(C.field_b, True).evaluate(c))

        # __contains__ doesn't seem to work with non-bool returns (explains why
        # sqlalchemy uses in_() rather than 'foo in bar' I've wondered about
        # previously).
        c.field_b = (True, )
        with self.assertRaises(NotImplementedError):
            # while X in Y creates a Contains() predicate, returning it from
            # __contains__() does not return it to here..rather it is evaluated
            # as True since it is not None. An exception is raised suggesting
            # how the predicate can be used directly.
            _ = C.field_a in C.field_b
        self.assertTrue(Contains(C.field_b, C.field_a).evaluate(c))

    def test_field_already_bound(self) -> None:
        C = create_class()
        with self.assertRaises(FieldAlreadyBound):
            C.field_a._bind(C())

    def test_bound_field(self) -> None:
        C = create_class()
        c1: Base = C()
        c2: Base = C()
        self.assertIsInstance(C.field_a[c1], BoundField)
        self.assertIsNot(C.field_a[c1], C.field_a)
        self.assertIsNot(C.field_a[c1], C.field_a[c2])
        with self.assertRaises(InvalidPredicateExpression):
            # The above assertIsNot are because comparing two fields creates
            # a predicate which is then evaluated for truthiness which is not
            # allowed because it is rarely what is intended. This demonstrates
            # why not to use assertNotEqaul to verify that the bound fields
            # are not the same.
            self.assertNotEqual(C.field_a[c1], C.field_a[c2])

    def test_bound_field_predicate(self) -> None:
        C = create_class()
        c: Base = C()
        c_field_a = C.field_a[c]
        self.assertIsInstance(c_field_a == 1, Predicate)
        self.assertIsInstance(1 == c_field_a, Predicate)

    def test_bound_field_reaction(self) -> None:
        called = False
        def reaction(*args):
            nonlocal called
            called = True
            
        C = create_class()
        
        # add an instance reaction and verify it is called
        c: Base = C()  # todo why does c need to be told what it is, and why not C
        C.field_a[c].reaction(reaction)
        self.assertFalse(called)
        c.field_a = 1
        self.assertTrue(called)

        # make sure another instance doesn't get called as well
        called = False
        c = C()
        self.assertFalse(called)
        c.field_a = 1
        self.assertFalse(called)

if __name__ == '__main__':
    main()
