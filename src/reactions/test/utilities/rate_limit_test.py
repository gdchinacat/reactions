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

from asyncio import sleep
from time import time
from unittest import TestCase, main

from ...field import ExecutorFieldManager, Field
from ...field_descriptor import FieldChange
from ...predicate_types import And, Not
from ...test.async_helpers import asynctest
from ...utilities import RateLimit, ScheduledUpdate


class RateLimited(ExecutorFieldManager, RateLimit):
    tick: Field[RateLimited, int] = Field(-1)  # replace RateLimit.tick
    stop_at: Field[RateLimited, int] = Field(0)
    time_per_tick: float = 0

    def __init__(self, rate: int, stop_at: int) -> None:
        '''
        rate: number of ticks per second
        stop_at: stop ticking when the tick count reaches stop_at
        '''
        super().__init__(rate)
        self.overruns: list[float] = []

        self.stop_at = stop_at

    (stop_predicate := tick == stop_at)(ExecutorFieldManager.astop)

    def _start(self) -> None:
        self.tick = 0

    def skipped_tick(self, overrun: float) -> None:
        self.overruns.append(overrun)
        
    @ And(tick != -1,
          Not(stop_predicate))
    async def _(self, _: FieldChange[RateLimited, int]) -> None:
        await self.delay()
        # no need to increment tick since delay() does that.


class TestRateLimit(TestCase):
    def test_rate_limit_pretty_accurate(self) -> None:
        rate_limited = RateLimited(100, 50 + 1)
    
        start = time()
        rate_limited.run()
        stop = time()
        self.assertAlmostEqual(0.5, stop - start, 2,
                               'test that rate limit time is pretty accurate, '
                               'but will occasionally fail if system is busy')
        self.assertEqual([], rate_limited.overruns)

    def test_rate_limit_tracks_overruns(self) -> None:
        rate_limited = RateLimited(0, 5)
    
        rate_limited.run()
        self.assertEqual(4, len(rate_limited.overruns))

class TestScheduledUpdate(TestCase):
    @asynctest
    async def test_scheduled_update(self) -> None:
        class Updated(ScheduledUpdate):
            deltas: list[float]
            _last_update = 0.0
            def __init__(self, rate: int):
                super().__init__(rate)
                self.deltas = []
            async def update(self) -> None:
                if self._last_update != 0:
                    _time = time()
                    self.deltas.append(_time - self._last_update)
                    self._last_update = _time
        class _Exception(Exception): ...

        with self.assertRaises(_Exception):
            async with Updated(10) as updater:
                await sleep(0.51)  # let updater run for 5 complete updates
                raise _Exception()
        for delta in updater.deltas:
            self.assertAlmostEqual(.1,  delta)


if __name__ == '__main__':
    main()