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
from typing import List
from unittest import TestCase, main

from ... import Field, FieldManager, FieldWatcher, And

@dataclass
class Watched(FieldManager):

    # While last_tick doesn't change, it is a Field so that its value will be
    # evaluated in the predicates. if it were a simple field whatever value
    # it had at class definition time would be used as a constant.
    # todo - document this as a reason for making a static attribute a Field.
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
class Watcher(FieldWatcher):
    ticks_seen: List[int] = field(default_factory=list[int])

    #@ Watched.ticks != None  # todo make this work
    async def _watch(self,
                     watched: Watched,
                     _: Field[int],
                     old: int, new: int):
        assert isinstance(self, Watcher), f'got {type(self)=}'
        assert isinstance(watched, Watcher), f'got {type(watched)=}'
        self.ticks_seen.append(new)


class Test(TestCase):

    def test_watch_manual_predicate(self):
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


if __name__ == "__main__":
    main()
