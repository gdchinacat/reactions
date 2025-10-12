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
Predicate test
'''
from __future__ import annotations

from unittest import TestCase, main

from .. import Field, ReactionMustNotBeCalled, FieldManager, FieldWatcher
from ..predicate import _Reaction
from .async_helpers import asynctest


class PredicateTest(TestCase):

    @asynctest
    async def test_decorator_returns__reaction(self):
        '''test the object returned by decorating a reaction is correct'''
        class State:
            field: Field[bool] = Field(False)
        predicate = State.field == True
        reaction = predicate(lambda *_: ...)
        self.assertEqual(predicate, reaction.predicate)

    @asynctest
    async def test_decorator_bound_reactions(self):
        '''test that bound reactions are handled properly'''
        class State(FieldManager):
            field = Field(False)
        class Watcher(FieldWatcher):
            called = False
            @State.field == True
            async def _true(self,
                            state: State,
                            field: Field,
                            old: bool, new:bool):
                self.called = True

        self.assertIsInstance(Watcher._true, _Reaction)
        self.assertRaises(ReactionMustNotBeCalled, Watcher._true)

        # reactions that look like they are bound aren't added to the class
        # field reactions.
        self.assertEqual([], State.field.reactions)

        state = State()
        watcher = Watcher(state)

        self.assertEqual([], State.field.reactions)
        async with state:
            state.field = True
        self.assertTrue(watcher.called)

        self.assertEqual([], State.field.reactions)

if __name__ == "__main__":
    main()
