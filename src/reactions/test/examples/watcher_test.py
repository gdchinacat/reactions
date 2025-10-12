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
from typing import List, Tuple
from unittest import TestCase, main

from ... import Field, FieldManager, FieldWatcher, And


@dataclass
class Watched(FieldManager):

    last_tick: Field[int] = Field[int](0)
    ticks = Field[int](-1)

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

@dataclass
class Watcher[T: type](FieldWatcher):
    change_events: List[Tuple] = field(default_factory=list)

    @ Watched.ticks != None
    async def _watch(self, watched: T, field, old, new):
        assert isinstance(self, Watcher), f'got {type(self)=}'
        assert isinstance(watched, Watched), f'got {type(watched)=}'
        self.change_events.append((watched, field, old, new))


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
        watched = Watched()
        watcher = Watcher(watched=watched,
                          _reaction_executor=watched._reaction_executor)

        watched.run()

        # last_tick + 2 for changing ticks to -1
        expected = [(watched, Watched.ticks, x - 1,
                     x if x != watched.last_tick + 1 else -1)
                    for x in range(watched.last_tick + 2)]

        self.assertEqual(watcher.change_events, expected)


if __name__ == "__main__":
    main()
