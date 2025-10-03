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

    @(ticks != -1) 
    def tick(self, field, old: int, new: int):
        assert self is field.instance
        self.ticks += 1

    @(ticks == 5)
    def reset(self, field, old: int, new: int):
        assert self is field.instance
        self.ticks = -1

    def _start(self):
        self.ticks = 0


@dataclass
class Watcher(ReactorBase):
    watched: Watched
    ticks_seen: List[int] = field(default_factory=list)

    def __init__(self, watched: Watched, *args, **kwargs):
        super().__init__(_reaction_executor=watched._reaction_executor,
                         *args, **kwargs)
        self.watched=watched

    @(Watched.ticks != -1)
    def watcher(self,
                watched: Watched,
                field: Field[Watched, int],
                old: int, new: int):
        self.ticks_seen.append(new)


class Test(TestCase):

    def test_watch_count(self):
        watched = Watched()
        watcher = Watcher(watched)
        asyncio.run(watched.run())

        self.assertEqual(watcher.ticks, list(range(watched.last_tick + 1)))


if __name__ == "__main__":
    main()
