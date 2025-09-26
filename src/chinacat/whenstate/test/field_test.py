from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, List
from unittest import TestCase, main

from chinacat.fixtures import default_fixture_name, fixture  # todo remove de[

from ..error import MustNotBeCalled
from ..field import Field, BoundField
from ..predicate import Predicate, Contains, Not, Or, And


@default_fixture_name('C')
def class_fixture(test: TestCase, a=None, b=None, **_) -> type:  # @UnusedVariable
    '''create new class with fields for testing'''
    @dataclass
    class C:
        field_a: Field[C, bool] = Field["C", bool]('C', 'field_a', a)
        field_b: Field[C, bool] = Field["C", bool]('C', 'field_b', b)
    return C

class TestField(TestCase):

    @fixture(class_fixture)
    def test_class_field_eq_creates_predicate(self, C):
        predicate = C.field_a == True
        self.assertIsInstance(predicate, Predicate)
        self.assertEqual(list(predicate.fields), [C.field_a])

    @fixture(class_fixture)
    def test_del_field_not_allowed(self, C):
        c = C(True, False)
        with self.assertRaises(MustNotBeCalled):
            del c.field_a
            c.field_a

    @fixture(class_fixture)
    def test_instance_field_equality(self, C):
        c = C(True, False)
        self.assertTrue(c.field_a == True)

        # set a notification on c.field_a to call print
        reaction_called = False
        def reaction(field: BoundField[C, bool],
                     old: bool, new: bool):
            nonlocal reaction_called
            reaction_called = True  # @UnusedVariable - it really is used
            self.assertEqual((field.instance, field.field, old, new),
                             (c, C.field_a, True, False))
        C.field_a.bound_field(c).reaction(reaction)  # todo reaction on the class

        # verify updated value is properly set and comparison works
        c.field_a = False
        self.assertTrue(c.field_a == False)
        self.assertTrue(c.field_a != True)
        self.assertTrue(reaction_called)

    @fixture(class_fixture)
    def test_edge_triggered_notify(self, C) -> None:
        changes: List[Tuple[bool, bool]] = list[Tuple[bool, bool]]()
        def collect(_: BoundField[C, bool], old: bool, new: bool):
            changes.append((old, new))

        c = C()
        C.field_a.bound_field(c).reaction(collect)

        for value in (True, False, False, True, True):
            c.field_a = value
        c.field_a = None
        self.assertEqual([(None, True),
                          (True, False),
                          (False, True),
                          (True, None)],
                         changes)

    @fixture(class_fixture)
    def test_predicate_operators(self, C) -> None:
        c = C(True, 0)
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


if __name__ == '__main__':
    main()
