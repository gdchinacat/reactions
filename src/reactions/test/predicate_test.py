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
from unittest import TestCase, main

from ..executor import Executor
from ..field import Field, FieldManager, FieldManagerMeta
from ..field_descriptor import FieldChange
from .async_helpers import asynctest


class PredicateTest(TestCase):

    @asynctest
    async def test_decorator_returns__reaction(self)->None:
        '''test the object returned by decorating a reaction is correct'''
        class State:
            field = Field['State', bool](False)
        async def reaction(*_: object) -> None: ...
        predicate = State.field == True
        reaction = predicate(reaction)  # todo predicate typing
        self.assertEqual(predicate, reaction.predicate)

    def test_predicate_decorator_non_self(self) -> None:
        '''
        Test that the predicate decorator works for plain functions not on the
        state instance or a watcher class.
        '''
        start = 5
        class State(FieldManager):
            field = Field['State', int](-1)
            @ field > 0
            async def decrement(self, *_: object) -> None:
                self.field -= 1
                if self.field == 0:
                    self.stop()
            def _start(self) -> None: self.field = start
        state = State()

        change_events: list[tuple[State, Field[State, int], int, int]] = []
        @ State.field[state] != None
        async def watch(state: State, change: FieldChange[State, int]) -> None:
            change_events.append((change.instance, change.field,
                                  change.old, change.new))

        state.run()

        expected = ([(state, State.field, -1, start)] + # for _start
                    [(state, State.field, x, x - 1)
                     for x in range(start, 0, -1)])

        self.assertEqual(change_events, expected)

    @asynctest
    async def test_bare_instance(self) -> None:
        '''
        Test that predicate decorations work on bare instances as long
        as they provide an executor.
        '''
        class State:
            field = Field['State', bool](False)
            @ field == True
            async def _true(self, change: FieldChange[State, bool]) -> None:
                self.called = True
            def __init__(self) -> None:
                self.executor = Executor[State, bool]()
                self.called = False

        state = State()
        async with state.executor:
            state.field = True
            state.executor.stop()
        self.assertTrue(state.called)


if __name__ == "__main__":
    main()
