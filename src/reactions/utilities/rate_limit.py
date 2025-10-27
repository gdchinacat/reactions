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

# TODO - neither of these classes really have anything to do with reactions,
# at best RateLimit is handy for slowing down self-driving state machines,
# and Updatable uses RateLimit. Should they be reimplemented to use reactions?
# Moved to a different package?

from abc import ABC, abstractmethod
from asyncio import sleep, create_task, Task
from collections.abc import Coroutine, AsyncIterator
from contextlib import asynccontextmanager
from time import time
from typing import Self


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

    def skipped_tick(self, overrun: float) -> None:
        '''
        Called when the rate is not maintained. Subclasses can override to
        customize how this event is handled.
        overrun: the time in seconds the next cycle was missed by.
        '''

    def delay(self) -> Coroutine[None, None, None]:
        '''delay until the next tick should happen'''
        self.tick += 1
        _time = time()
        if self._next_tick_time == 0:
            delay: float = 0
            self._next_tick_time = _time + self.time_per_tick
        else:
            delay = self._next_tick_time - _time
            if delay >= 0:
                self._next_tick_time += self.time_per_tick
            else:
                # Missed time at which to tick.
                self.skipped_tick(abs(delay))
                delay = 0
                if self.time_per_tick > 0:
                    self._next_tick_time += 2 * self.time_per_tick
                else:
                    self._next_tick_time = _time
        if self.time_per_tick > 0:
            if delay > self.time_per_tick:
                # delay can be greater than time_per_tick if a tick was missed
                # causing it to be advanced two time_per_ticks and processing
                # the delay=0 tick completed before the skipped tick would have
                # been scheduled
                delay -= self.time_per_tick
            assert delay < self.time_per_tick
        self.last_delay = delay
        return sleep(delay)
    __call__ = delay


class Updatable(ABC):  # todo this is a horrible name
    '''
    Updatable provides periodic updates to subclasses.

    Usage:
    class Updater(Updtabable):
        async def update(self):
            ...

    ...
        with Updater(60).execute() as updater:
           # called 60 times per second
           ...

    Updatable.execute() is a context manager that yields itself. While entered
    it calls .update() at the fixed rate. It executes in a newly created
    asyncio task.
    '''

    __rate_limit: RateLimit
    __task: Task[None]|None = None
    __stop = False

    def __init__(self, rate: int, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.__rate_limit = RateLimit(rate)

    @abstractmethod
    async def update(self) -> None: ...

    async def __loop(self) -> None:
        while not self.__stop:
            await self.update()
            await self.__rate_limit()

    @asynccontextmanager
    async def execute(self) -> AsyncIterator[Self]:
        '''Context manager that runs a task to call update() at the rate.'''
        # todo - the class is not a context manager and this method is named
        #        execute() rather than run so it can be mixed in with
        #        FieldWatcher/Reactant that already has those methods.
        self.__task = create_task(self.__loop())
        try:
            yield self
        finally:
            self.__stop = True
            await self.__task
