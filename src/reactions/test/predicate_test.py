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
    async def test_decorator_returns__reaction(self)->None:
        '''test the object returned by decorating a reaction is correct'''
        class State:
            field = Field(False)
        def reaction(state, field, old, new): # pylint: disable=unused-argument
            pass
        predicate = State.field == True
        reaction = predicate(reaction)
        self.assertEqual(predicate, reaction.predicate)

    def test_predicate_decorator_non_self(self):
        '''
        Test that the predicate decorator works for plain functions not on the
        state instance or a watcher class.
        '''
        start = 5
        class State(FieldManager):
            field = Field(-1)
            @ field > 0
            async def decrement(self, *_):
                self.field -= 1
                if self.field == 0:
                    self.stop()
            def _start(self): self.field = start
        state = State()

        change_events = []
        @ State.field[state] != None
        async def watch(*args):
            change_events.append(args)

        state.run()

        expected = ([(state, State.field, -1, start)] + # for _start
                    [(state, State.field, x, x - 1)
                     for x in range(start, 0, -1)])

        self.assertEqual(change_events, expected)


if __name__ == "__main__":
    main()
