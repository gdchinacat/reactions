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
An example showing how a class can watch a state for changes.
'''
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, NoReturn
from unittest import TestCase, main

from ... import Field, FieldManager, FieldWatcher, And
from ...executor import ReactionExecutor
from ..async_helpers import asynctest


@dataclass
class Watched(FieldManager):

    last_tick: Field[int] = Field(1)
    ticks = Field(-1)

    def _start(self):
        self.ticks = 0

    @ And(ticks != -1,
          ticks != last_tick)
    async def tick(self, *_):
        self.ticks += 1

    @ ticks == last_tick
    # todo - Field[..., bool] is wrong...predicate decorator typing isn't
    #        working because it expects to pass a BaseField to reaction and
    #        reaction accepts more specific Field. Even then, the field type
    #        isn't validating properly. Needs a fair bit of work.
    async def done(self, field: Field[bool], old: int, new:int):
        self.ticks = -1
        self.stop()

    def __repr__(self):
        return f'{type(self).__qualname__}({id(self)})'

class Test(TestCase):

    def test_manual_predicate(self):
        watched = Watched()
        change_events = []

        @ Watched.ticks[watched] != None
        async def watch(*args):
            change_events.append(args)

        watched.run()

        # last_tick + 2 for changing ticks to -1
        expected = [(watched, Watched.ticks, x - 1,
                     x if x != watched.last_tick + 1 else -1)
                    for x in range(watched.last_tick + 2)]

        self.assertEqual(change_events, expected)

    def test_automatic_predicate(self):

        class Watcher[T: type](FieldWatcher):
            def __init__(self, watched:Watched, *args, **kwargs):
                super().__init__(watched, *args, **kwargs)
                self.change_events: List[Tuple] = list()

            @ Watched.ticks != None
            async def _watch(self, watched: T, field, old, new):
                assert isinstance(self, Watcher), f'got {type(self)=}'
                assert isinstance(watched, Watched), f'got {type(watched)=}'
                self.change_events.append((watched, field, old, new))

        watched = Watched()
        watcher = Watcher(watched=watched,
                          _reaction_executor=watched._reaction_executor)

        watched.run()

        # last_tick + 2 for changing ticks to -1
        expected = [(watched, Watched.ticks, x - 1,
                     x if x != watched.last_tick + 1 else -1)
                    for x in range(watched.last_tick + 2)]

        self.assertEqual(watcher.change_events, expected)

    @asynctest
    async def test_automatic_dispatches_to_correct_watcher(self)->None:
        class Watched(FieldManager):
            field = Field(False)
            def _start(self): ...

        class Watcher(FieldWatcher[Watched]):
            reacted: bool = False
            @ Watched.field == True
            async def _true(
                self, watched: Watched, field: Field[bool], old:bool, new:bool):
                assert self.watched is watched
                self.reacted = True

        executor = ReactionExecutor()

        watched1 = Watched(_reaction_executor=executor)
        watcher1 = Watcher(watched=watched1, _reaction_executor=executor)

        watched2 = Watched(_reaction_executor=executor)
        watcher2 = Watcher(watched=watched2, _reaction_executor=executor)

        async with executor:
            watched1.field = True

        self.assertTrue(watcher1.reacted)
        self.assertFalse(watcher2.reacted)

if __name__ == "__main__":
    main()
