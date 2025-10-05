'''
An example showing how a class can watch a state for changes.
'''
from __future__ import annotations

import asyncio
from typing import List, Optional
from unittest import TestCase, main

from ... import Field, Reactant
from ...executor import ReactionExecutor
from ...logging_config import VERBOSE
from dataclasses import dataclass, field


@dataclass
class Watched(Reactant):
    last_tick: Field[Watched, int] = Field(5)
    ticks: Field[Watched, Optional[int]] = Field(None)

    @ ticks == 5
    async def done(self, *_):
        self.ticks = None
        self.stop()

    @ ticks != -1
    async def tick(self, *_):
        if self.ticks is not None:
            self.ticks += 1

    def _start(self):
        self.ticks = 0


# todo - should *not* be global, but until reaction instance is plumbed through
#        a global is used.
ticks_seen: List[int] = []


@dataclass
class Watcher(Reactant):
    watched: Watched
    ticks_seen: List[int] = field(default_factory=list[int])

    # TODO - property(_reaction_executor) needs to go away as part of work to
    #        properly define how reaction execution works (and maybe how to
    #        manage instances).
    @property
    def _reaction_executor(self) -> ReactionExecutor:
        return self.watched._reaction_executor

    @_reaction_executor.setter
    def _reaction_executor(self, _):
        # ignore whatever is being set since we always use the one on watched
        pass

    def _start(self): ...

    @ (Watched.ticks != None)
    @staticmethod
    async def watcher(watched: Watched,
                _: Field[Watched, int],
                old: int, new: int):
        # todo - use self.logger, once self is provided
        watched._logger.log(VERBOSE,
                           'static watcher got notice that '
                           f'{watched} changed {old} -> {new})')

        ticks_seen.append(new)  # move onto Watcher once self is provided


class Test(TestCase):

    def test_watch_count(self):
        watched = Watched()
        watcher = Watcher(watched)  # todo - associate watched with watched reactions
        asyncio.run(watched.run())

        # todo - use watcher.ticks_seen
        self.assertEqual(ticks_seen, list(range(watched.last_tick + 1)))


if __name__ == "__main__":
    main()
