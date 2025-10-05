from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, List, Any, Optional, NoReturn
from unittest import TestCase, main


from ..error import (MustNotBeCalled , FieldAlreadyBound,
                     FieldConfigurationError)
from ..field import Field, BoundField, FieldManagerMeta
from ..predicate import Predicate, Contains, Not, Or, And


class Base(metaclass=FieldManagerMeta):
    '''
    exists solely to give create_class() a base class for type annotations
    '''
    field_a: Optional[Field[Any, Optional[bool | int]]] = None
    field_b: Optional[Field[Any, Optional[bool | int]]] = None
    def __init__(self,
                 a: Optional[bool | int] = None,
                 b: Optional[bool | int] = None) -> NoReturn:
        raise Exception()

def create_class() -> type[Base]:
    @dataclass
    class C(Base):
        field_a: Field[C, Optional[bool | int]] = Field(None, 'C', 'field_a')
        field_b: Field[C, Optional[bool | int]] = Field(None, 'C', 'field_b')
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
        def reaction(field: BoundField[C, bool],
                     old: bool, new: bool):
            nonlocal reaction_called
            reaction_called = True  # @UnusedVariable - it really is used
            self.assertEqual((field.instance, field.field, old, new),
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
        def collect(_: BoundField[Any, bool], old: bool, new: bool):
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
        c: type[Base] = C(True, 0)
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
            assert C.field_a
            C.field_a._bind(C())

    def test_bound_field_specific_reactions_not_permitted(self) -> None:
        C = create_class()
        with self.assertRaises(FieldConfigurationError):
            async def reaction(*args): ...
            C()._field_a_bound.reaction(reaction)


if __name__ == '__main__':
    main()
