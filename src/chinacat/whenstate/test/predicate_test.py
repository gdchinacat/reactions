from unittest import TestCase

from ..predicate import Eq, Constant


class TestPredicate(TestCase):

    def test_eq_constant_constant(self):
        self.assertTrue(Eq(1, 1))
        self.assertFalse(Eq(1, 2))

    def test_eq_constant_expression(self):
        self.assertTrue(Eq(1,  Constant(1)))
        self.assertFalse(Eq(1, Constant(2)))

    def test_eq_expression_constant(self):
        self.assertTrue(Eq(Constant(1), 1))
        self.assertFalse(Eq(Constant(1), 2))
        
    def test_eq_constant_predicate(self):
        self.assertTrue(Eq(Constant(1), 1))

    # todo - a whole bunch of more predicates
    # todo - predicates of predicates
