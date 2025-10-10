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

from ... import Field, FieldManager, FieldWatcher

@dataclass
class Watched(FieldManager):
    last_tick = Field[int](5)
    ticks = Field[int](-1)

    @ ticks == 5
    # todo - Field[..., bool] is wrong...predicate decorator typing isn't
    #        working because it expects to pass a BaseField to reaction and
    #        reaction accepts more specific Field. Even then, the field type
    #        isn't validating properly. Needs a fair bit of work.
    async def done(self, field_: Field[bool], old: int, new:int):
        assert field_
        assert old != new
        self.ticks = -1
        self.stop()

    @ ticks != -1
    async def tick(self, *_):
        if self.ticks is not None:
            self.ticks += 1

    def _start(self):
        self.ticks = 0

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
        def watch(*args):
            change_events.append(args)

        # todo - fix failing unit test by making BoundField create predicates
        # todo - refactor FieldDispatcher to separate descriptor from else.
        (Watched.ticks[watched] != None)(watch)
        
        watched.run()

        self.assertEqual(change_events,
                         [(watched, Watched.ticks, x - 1, x)
                          for x in range(watched.last_tick + 1)])
        print(change_events)


if __name__ == "__main__":
    main()
