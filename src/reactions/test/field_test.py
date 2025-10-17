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
from dataclasses import dataclass
from types import NoneType
from unittest import TestCase, main

from ..error import (MustNotBeCalled, FieldAlreadyBound,
                     InvalidPredicateExpression, FieldConfigurationError)
from ..field import (Field, BoundField, FieldManager, FieldWatcher,
                     FieldManagerMeta)
from ..field_descriptor import FieldDescriptor, FieldChange
from ..predicate import Predicate, _Reaction
from ..predicate_types import Contains, Not, Or, And


class TestField(TestCase):

    def test_class_field_eq_creates_predicate(self) -> None:
        class C:
            field = Field['C', bool](False, 'C', 'field')

        predicate = C.field == True
        self.assertIsInstance(predicate, Predicate)
        self.assertEqual(list(predicate.fields), [C.field])

    def test_del_field_not_allowed(self) -> None:
        class C:
            field = Field['C', bool](False, 'C', 'field')
        c = C()
        with self.assertRaises(MustNotBeCalled):
            del c.field
            self.assertFalse(c.field)

    def test_instance_field_equality(self) -> None:
        class C(FieldManager):
            field = Field['C', bool](True, 'C', 'field')
            def _start(self) -> None: ...
        c = C()
        self.assertTrue(c.field == True)

        # set a notification on c.field_a to call print
        reaction_called = False
        def reaction(change: FieldChange[Field[C, bool], C, bool]) -> None:
            nonlocal reaction_called
            reaction_called = True  # @UnusedVariable - it really is used
            self.assertEqual(
                (change.instance, change.field, change.old, change.new),
                (c, C.field, True, False))
        C.field.reaction(reaction)

        # verify updated value is properly set and comparison works
        c.field = False
        self.assertTrue(c.field == False)
        self.assertTrue(c.field != True)
        self.assertTrue(reaction_called)

    def test_edge_triggered_notify(self) -> None:
        class C(FieldManager):
            field = Field['C', bool|None](None, 'C', 'field')
            def _start(self) -> None: ...

        changes = list[tuple[bool|None, bool|None]]()
        def collect(change: FieldChange[Field[C, bool], C, bool|None]) -> None:
            changes.append((change.old, change.new))

        c = C()
        C.field.reaction(collect)

        for value in (True, False, False, True, True):
            c.field = value
        c.field = None
        self.assertEqual([(None, True),
                          (True, False),
                          (False, True),
                          (True, None)],
                         changes)

    def test_predicate_operators(self) -> None:
        @dataclass
        class C(FieldManager):
            field_a: Field[C, bool|None] = Field(None, 'C', 'field_a')
            field_b: Field[C, int|tuple[bool]|None] = Field(None, 'C', 'field_b')
            def _start(self) -> None: ...
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

    def test_field_already_bound(self) -> None:
        class C(FieldManager):
            field = Field['C', int](0, 'C', 'field')
            def _start(self) -> None: ...
        with self.assertRaises(FieldAlreadyBound):
            C.field._bind(C())  # pylint: disable=protected-access

    def test_field_manager_binds_fields(self) -> None:
        class C(FieldManager):
            field = Field['C', int](0, 'C', 'field')
            def _start(self) -> None: ...
        c1 = C()
        c2 = C()
        self.assertIsInstance(C.field[c1], BoundField)
        self.assertIsNot(C.field[c1], C.field)
        self.assertIsNot(C.field[c1], C.field[c2])
        with self.assertRaises(InvalidPredicateExpression):
            # The above assertIsNot are because comparing two fields creates
            # a predicate which is then evaluated for truthiness which is not
            # allowed because it is rarely what is intended. This demonstrates
            # why not to use assertNotEqaul to verify that the bound fields
            # are not the same.
            self.assertNotEqual(C.field[c1], C.field[c2])

    def test_bound_field_predicate(self) -> None:
        class C(FieldManager):
            field = Field['C', int](0, 'C', 'field')
            def _start(self) -> None: ...
        c = C()
        c_field = C.field[c]
        self.assertIsInstance(c_field == 1, Predicate)
        self.assertIsInstance(1 == c_field, Predicate)

    def test_bound_field_reaction(self) -> None:
        called = False
        def reaction(*_: object) -> None:
            nonlocal called
            called = True  # @UnusedVariable

        class C(FieldManager):
            field = Field['C', bool|int|None](None, 'C', 'field')
            def _start(self) -> None: ...

        # add an instance reaction and verify it is called
        c = C()
        C.field[c].reaction(reaction)
        self.assertFalse(called)
        c.field = 1
        self.assertTrue(called)

        # make sure another instance doesn't get called as well
        called = False
        c = C()
        self.assertFalse(called)
        c.field = 1
        self.assertFalse(called)

    def test_watcher__reactions_is_cached(self) -> None:
        class Watched(FieldManager):
            field = Field['Watched', bool](False)
            def _start(self) -> None: ...
        class Watcher(FieldWatcher[Watched]):
            _false: object
            @ Watched.field == True
            async def _true(self,
                            change: FieldChange[Field[Watched, bool],
                                                Watched, bool]) -> None:
                pass

        watched = Watched()

        # at this point there is only a single reaction on Watcher
        watcher = Watcher(watched)
        reactions = watcher._reactions  # pylint: disable=protected-access
        self.assertEqual(1, len(reactions))

        # add another reaction to Watcher.
        @ Watched.field == False
        async def _false(*_: object) -> None: ...
        self.assertIsInstance(_false, _Reaction)
        Watcher._false = _false  # unsupported, don't do this outside tests

        # verify Watcher reactions hasn't changed (indicating it was cached)
        watcher = Watcher(watched)
        reactions = watcher._reactions  # pylint: disable=protected-access
        self.assertEqual(1, len(reactions))

        # If the class is reinitialized the new reaction does appear.
        Watcher.__init_subclass__()  # don't do this outside tests.
        reactions = watcher._reactions  # pylint: disable=protected-access
        self.assertEqual(2, len(reactions))

    def test___set_name___prevents_field_name_collisions(self) -> None:
        '''
        '''
        with self.assertRaises(FieldConfigurationError):
            class _:
                field = Field['_', bool](False, '_', 'field')
                @field == False
                async def _field(self, *_: object) -> None: ...

    def test_field_manager_meta_prevents_field_name_collisions(self) -> None:
        '''
        FieldDescriptor adds attributes to the class it is managing fields on.
        When a class derives from FieldManager the definition of the class
        should fail if the Fields will use attributes that are already used.
        '''
        with self.assertRaises(FieldConfigurationError):
            class _(metaclass=FieldManagerMeta):
                field = Field['_', bool](False)
                @field == False
                async def _field(self, *_: object) -> None: ...


if __name__ == '__main__':
    main()
