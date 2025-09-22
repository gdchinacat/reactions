from __future__ import annotations
from dataclasses import dataclass
from unittest import TestCase

from ..field import Field, BoundField
from ..predicate import Predicate
from chinacat.fixtures import default_fixture_name, fixture

@default_fixture_name('C')
def class_fixture(test: TestCase, **_) -> type:
    @dataclass
    class C:
        true_field: Field[C, bool] = Field["C", bool]('true_field', True)
        false_field: Field[C, bool] = Field["C", bool]('false_field', False)
    return C

class TestField(TestCase):

    @fixture(class_fixture)
    def test_class_field_eq_creates_predicate(self, C):
        predicate = (C.true_field == True)
        self.assertIsInstance(predicate, Predicate)
        self.assertEqual(list(predicate.fields), [C.true_field])

    @fixture(class_fixture)
    def test_instance_field_equality(self, C):
        c = C()
        self.assertTrue(c.true_field == True)

        
        # set a notification on c.true_field to call print
        listener_called = False
        def listener(field: BoundField[C, bool],
                     old: bool, new: bool):
            nonlocal listener_called
            listener_called = True  # @UnusedVariable - it really is used
            self.assertEqual((field.instance, field.field, old, new),
                             (c, C.true_field, True, False))
        C.true_field(c).listen(listener)
        
        # verify updated value is properly set and comparison works
        c.true_field = False
        self.assertTrue(c.true_field == False)
        self.assertTrue(c.true_field != True)
        self.assertTrue(listener_called)
        