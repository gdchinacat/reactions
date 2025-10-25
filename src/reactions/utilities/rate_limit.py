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

from abc import ABC, abstractmethod
from asyncio import sleep
from collections.abc import Coroutine
from logging import Logger
from time import time


class RateLimit(ABC):
    '''
    Mixin to allow state models to react at a constant rate.

    Usage:
    class State(Reactor, RateLimit):
        time_per_tick = 1/60  # 60 FPS

        async def  _loop(...):
            # do your per loop stuff
            await self.delay()
    '''

    _next_tick_time: float = 0
    '''
    the time the next tick should happen, used to keep a regular tick rather
    than a regular space between ticks.
    '''

    @property
    @abstractmethod
    def time_per_tick(self) -> float:
        '''
        The time per update, in seconds
        '''

    @abstractmethod
    def rate_falling_behind(self, overrun: float) -> None:
        '''
        Called when the rate is not maintained.
        overrun: the time in seconds the next cycle was missed by.
        '''

    def delay(self) -> Coroutine[None, None, None]:
        '''delay until the next tick should happen'''
        if self._next_tick_time == 0:
            delay: float = 0
            self._next_tick_time = time() + self.time_per_tick
        else:
            delay = self._next_tick_time - time()
            if delay > 0:
                self._next_tick_time += self.time_per_tick
            else:
                # Missed time at which to tick.
                self.rate_falling_behind(abs(delay))
                delay = 0
                self._next_tick_time += 2 * self.time_per_tick
        return sleep(delay)  # returns coroutine, doesn't actually sleep
