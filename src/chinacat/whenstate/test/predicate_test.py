from unittest import TestCase

from ..predicate import Eq


class TestPredicateTest(TestCase):

    def test_eq_constant_constant(self):
        self.assertTrue(Eq(1, 1))
        self.assertFalse(Eq(1, 2))

    def test_eq_constant_expression(self):
        self.assertTrue(Eq(1, lambda: 1))
        self.assertFalse(Eq(1, lambda: 2))

    def test_eq_expression_constant(self):
        self.assertTrue(Eq(lambda: 1, 1))
        self.assertFalse(Eq(lambda: 1, 2))
