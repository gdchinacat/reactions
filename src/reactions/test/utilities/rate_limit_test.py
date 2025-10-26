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

from time import time
from unittest import TestCase

from reactions.field_descriptor import FieldChange

from ...field import FieldManager, Field
from ...predicate_types import And, Not
from ...utilities import RateLimit


class RateLimited(FieldManager, RateLimit):
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

    (stop_predicate := tick == stop_at)(FieldManager.astop)

    def _start(self) -> None:
        self.tick = 0

    def rate_falling_behind(self, overrun: float) -> None:
        self.overruns.append(overrun)
        
    @ And(tick != -1,
          Not(stop_predicate))
    async def _(self, _: FieldChange[RateLimited, int]) -> None:
        await self.delay()
        # no need to increment tick since delay() does that.


class Test(TestCase):
    def test_rate_limit_pretty_accurate(self) -> None:
        rate_limited = RateLimited(1000, 500)
    
        start = time()
        rate_limited.run()
        stop = time()
        self.assertAlmostEqual(.5, stop - start, places=2)
        self.assertEqual([], rate_limited.overruns)

    def test_rate_limit_tracks_overruns(self) -> None:
        rate_limited = RateLimited(0, 5)
    
        rate_limited.run()
        self.assertEqual(4, len(rate_limited.overruns))
