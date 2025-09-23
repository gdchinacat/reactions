from unittest import TestCase

from ..predicate import Eq, Ne, Lt, Le, Gt, Ge, Contains, Constant


class TestPredicate(TestCase):

    def test_eq_constant_constant(self):
        self.assertTrue(Eq(1, 1).evaluate(None))
        self.assertFalse(Eq(1, 2).evaluate(None))

    def test_eq_constant_expression(self):
        self.assertTrue(Eq(1,  Constant(1)).evaluate(None))
        self.assertFalse(Eq(1, Constant(2)).evaluate(None))

    def test_eq_expression_constant(self):
        self.assertTrue(Eq(Constant(1), 1).evaluate(None))
        self.assertFalse(Eq(Constant(1), 2).evaluate(None))
        
    def test_eq_constant_predicate(self):
        self.assertTrue(Eq(Constant(1), 1).evaluate(None))

    def test_ne_constant_predicate(self):
        self.assertFalse(Ne(Constant(1), 1).evaluate(None))
        self.assertTrue(Ne(Constant(1), 0).evaluate(None))

    def test_lt_constant_predicate(self):
        self.assertFalse(Lt(Constant(1), 1).evaluate(None))
        self.assertTrue(Lt(Constant(0), 1).evaluate(None))
        
    def test_le_constant_predicate(self):
        self.assertTrue(Le(Constant(1), 1).evaluate(None))
        self.assertFalse(Le(Constant(1), 0).evaluate(None))

    def test_gt_constant_predicate(self):
        self.assertFalse(Gt(Constant(1), 1).evaluate(None))
        self.assertTrue(Gt(Constant(2), 1).evaluate(None))
        
    def test_ge_constant_predicate(self):
        self.assertTrue(Ge(Constant(1), 1).evaluate(None))
        self.assertFalse(Ge(Constant(0), 1).evaluate(None))
        
    def test_contains_constant_predicate(self):
        self.assertTrue(Contains(Constant((1, )), 1).evaluate(None))
        self.assertFalse(Contains(Constant((1, )), 2).evaluate(None))

    # todo - predicates of predicates
