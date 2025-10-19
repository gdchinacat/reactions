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
.field.FieldWatcher test
'''
from unittest import TestCase, main

from ..error import ReactionMustNotBeCalled
from ..executor import Executor
from ..field import Field, FieldManager, FieldWatcher
from ..field_descriptor import FieldChange
from ..predicate import _Reaction
from ..predicate_types import And
from .async_helpers import asynctest


class Watched(FieldManager):
    '''class with fields to be watched'''

    last_tick = Field['Watched', int](1)
    ticks = Field['Watched', int](-1)

    def __init__(self,
                 *args: object,
                 last_tick: int|None = None,
                 **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        if last_tick is not None:
            self.last_tick = last_tick

    def _start(self) -> None:
        self.ticks = 0

    @ And(ticks != -1,
          ticks != last_tick)
    async def tick(self, change: FieldChange['Watched', int]) -> None:
        self.ticks += 1

    @ ticks == last_tick
    # todo - Field[..., bool] is wrong...predicate decorator typing isn't
    #        working because it expects to pass a BaseField to reaction and
    #        reaction accepts more specific Field. Even then, the field type
    #        isn't validating properly. Needs a fair bit of work.
    # todo - create a predicate_test for reaction type checking
    async def done(self, change: FieldChange['Watched', int]) -> None:
        self.ticks = -1
        self.stop()

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}({id(self)})'

class FieldWatcherTest(TestCase):

    def test_automatic_predicate(self) -> None:

        class Watcher(FieldWatcher[Watched]):
            def __init__(self, watched: Watched,
                         *args: object,
                         **kwargs: object) -> None:
                super().__init__(watched, *args, **kwargs)
                self.change_events: list[tuple[int, int]] = []

            @ Watched.ticks != None
            @ FieldWatcher  # todo typing
            async def _watch(self,
                             watched: Watched,
                             change: FieldChange[Watched, int]) -> None:
                assert isinstance(self, Watcher), f'got {type(self)=}'
                assert isinstance(watched, Watched), f'got {type(watched)=}'
                self.change_events.append((change.old, change.new))

        watched = Watched()
        watcher = Watcher(watched=watched,
                          executor=watched.executor)

        watched.run()

        # last_tick + 2 for changing ticks to -1
        expected = [(x - 1, x if x != watched.last_tick + 1 else -1)
                    for x in range(watched.last_tick + 2)]

        self.assertEqual(watcher.change_events, expected)

    @asynctest
    async def test_automatic_dispatches_to_correct_watcher(self)->None:
        class Watched(FieldManager):
            field = Field['Watched', bool](False)
            def _start(self) -> None: ...

        class Watcher(FieldWatcher[Watched]):
            reacted: bool = False
            @ Watched.field == True
            @ FieldWatcher  # todo typing
            async def _true(self,
                            watched: Watched,
                            change: FieldChange[Watched, bool]) -> None:
                assert self.watched is watched
                self.reacted = True

        executor = Executor()

        watched1 = Watched(executor=executor)
        watcher1 = Watcher(watched1, executor=executor)

        watched2 = Watched(executor=executor)
        watcher2 = Watcher(watched2, executor=executor)

        async with executor:
            watched1.field = True

        self.assertTrue(watcher1.reacted)
        self.assertFalse(watcher2.reacted)

    @asynctest
    async def test_decorator_bound_reactions(self)->None:
        '''test that bound reactions are handled properly'''
        class State(FieldManager):
            field = Field['State', bool](False)
            def _start(self) -> None: ...
        class Watcher(FieldWatcher[State]):
            called = False
            @ State.field == True
            @ FieldWatcher  # todo typing
            async def _true(self,
                            state: State,
                            change: FieldChange[State, bool]) -> None:
                self.called = True

        self.assertIsInstance(Watcher._true, _Reaction)
        self.assertRaises(ReactionMustNotBeCalled, Watcher._true)

        # reactions that look like they are bound aren't added to the class
        # field reactions.
        self.assertEqual([], State.field.reactions)

        state = State()
        watcher = Watcher(state)  # todo typing

        self.assertEqual([], State.field.reactions)
        async with state:
            state.field = True
        self.assertTrue(watcher.called)

        self.assertEqual([], State.field.reactions)


if __name__ == "__main__":
    main()
