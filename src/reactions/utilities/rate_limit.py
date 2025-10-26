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
A RateLimit mixin utility that provides a coroutine to delay to limit how
often it is called. Provides FPS like characteristics.
'''

from asyncio import sleep
from collections.abc import Coroutine
from time import time


class RateLimit:
    '''
    Rate limit class that provides a coroutine to await to restrict delay()
    call rate.
    rate_limit = RateLimit(60)  # 60 FPS
    ...
    await rate_limit()
    '''

    _next_tick_time: float = 0
    '''
    the time the next tick should happen, used to keep a regular tick rather
    than a regular space between ticks.
    '''

    tick = 0
    '''tick is incremented each time delay is called'''

    time_per_tick: float = 0
    '''the time in seconds per tick'''

    def __init__(self, rate: int = 60) -> None:
        '''create a RateLimit at the given rate per second'''
        self.time_per_tick = 1 / rate if rate > 0 else 0

    def rate_falling_behind(self, overrun: float) -> None:
        '''
        Called when the rate is not maintained. Subclasses can override to
        customize how this event is handled.
        overrun: the time in seconds the next cycle was missed by.
        '''

    def delay(self) -> Coroutine[None, None, None]:
        '''delay until the next tick should happen'''
        self.tick += 1
        if self._next_tick_time == 0:
            delay: float = 0
            self._next_tick_time = time() + self.time_per_tick
        else:
            delay = self._next_tick_time - time()
            if delay >= 0:
                self._next_tick_time += self.time_per_tick
            else:
                # Missed time at which to tick.
                self.rate_falling_behind(abs(delay))
                delay = 0
                if self.time_per_tick > 0:
                    self._next_tick_time += 2 * self.time_per_tick
                else:
                    self._next_tick_time = time()
        # delay can be greater than time_per_tick if a tick was missed
        # causing it to be advanced two tick works and processing the
        # delay=0 tick took less than time_per_tick, leaving more than
        # a tick worth. In that case undo the skip...
        if delay > self.time_per_tick:
            print(f'todo - why is delay={delay*1000:.2f} > time_per_tick={self.time_per_tick*1000:.2f}')
        return sleep(delay)  # returns coroutine, doesn't actually sleep
    __call__ = delay

