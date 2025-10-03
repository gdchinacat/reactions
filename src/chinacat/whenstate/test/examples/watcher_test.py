'''
An example showing how a class can watch a state for changes.
'''
from __future__ import annotations

import asyncio
from typing import List
from unittest import TestCase, main

from ... import Field, State, ReactorBase
from dataclasses import dataclass, field


@dataclass
class Watched(State):  # todo - don't require state here
    last_tick: Field[Watched, int] = Field(5)
    ticks: Field[Watched, int] = Field(-1)

    @ ticks == 5
    async def done(self, field, old: int, new: int):
        self.ticks = -1
        self.stop()

    @ ticks != -1
    async def tick(self, field, old: int, new: int):
        if new != self.ticks:
            # something else changed it before we reacted, skip
            return
        self.ticks += 1

    def _start(self):
        self.ticks = 0


@dataclass
class Watcher(ReactorBase):
    watched: Watched
    ticks_seen: List[int] = field(default_factory=list)

    @property
    def _reaction_executor(self):
        return self.watched._reaction_executor

    @_reaction_executor.setter
    def _reaction_executor(self, _):
        # ignore whatever is being set since we always use the one on watched
        pass

    #@(Watched.ticks != -1)
    async def watcher(self,
                watched: Watched,
                field: Field[Watched, int],
                old: int, new: int):
        self.ticks_seen.append(new)


class Test(TestCase):

    def test_watch_count(self):
        watched = Watched()
        watcher = Watcher(watched)
        asyncio.run(watched.run())

        self.assertEqual(watcher.ticks_seen, list(range(watched.last_tick + 1)))


if __name__ == "__main__":
    main()
