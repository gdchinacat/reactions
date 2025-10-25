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
from collections.abc import Coroutine
from enum import Enum
from time import time
from unittest import TestCase, main
import asyncio
import logging

from ... import Field, And, FieldManager, FieldChange


NUMBER_OF_TRAFFIC_LIGHTS = 1_000
TIME_PER_TICK = 1/3
TICKS_PER_LIGHT = 1
CYCLES = 2


logger = logging.getLogger("traffic_light")


class Color(Enum):
    '''the color of a traffic light'''
    RED = 1
    GREEN = 2
    YELLOW = 3


type TlFc[Tf] = FieldChange[TrafficLight, Tf]
type IntOrColorFieldChange = TlFc[int|Color]

class TrafficLight(FieldManager):
    '''
    simple model that implements a traffic light:
    '''

    color = Field['TrafficLight', Color](Color.RED)
    '''color: the current color of the light'''

    ticks = Field['TrafficLight', int](-1)
    '''tick: the number of ticks for the current color'''

    cycles = Field['TrafficLight', int](0)
    ''' cycles: the number of times the light has gone through a full cycle '''

    _next_tick_time: float = 0
    '''
    the time the next tick should happen, used to keep a regular tick rather
    than a regular space between ticks.
    '''

    sequence: list[Color]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # todo executor kwarg
        self.sequence = []

    def _start(self) -> None:
        self.ticks = 0

    @And(color == Color.RED,
         ticks == TICKS_PER_LIGHT)
    async def red_to_green(self, change: IntOrColorFieldChange) -> None:
        self.change(Color.GREEN)

    @And(color == Color.GREEN,
         ticks == TICKS_PER_LIGHT)
    async def green_to_yellow(self, change: IntOrColorFieldChange) -> None:
        self.change(Color.YELLOW)

    @And(color == Color.YELLOW,
         ticks == TICKS_PER_LIGHT)
    async def yellow_to_red(self, change: IntOrColorFieldChange) -> None:
        self.cycles += 1
        self.change(Color.RED)

    def change(self, color: Color) -> None:
        self.ticks = 0
        self.color = color
        self.sequence.append(color)
        logger.debug('%s %s', self, color.name)

    @ ticks != -1
    async def tick(self, change: FieldChange[TrafficLight, int]) -> None:
        if self.ticks != change.new:
            # change reset ticks, don't react
            return
        assert self.ticks != TICKS_PER_LIGHT

        if self.cycles == CYCLES:
            self.stop()
        else:
            await self._delay()
            self.ticks += 1

    def _delay(self) -> Coroutine[None, None, None]:
        '''delay until the next tick should happen'''
        if self._next_tick_time == 0:
            delay: float = 0
            self._next_tick_time = time() + TIME_PER_TICK
        else:
            delay = self._next_tick_time - time()
            if delay > 0:
                self._next_tick_time += TIME_PER_TICK
            else:
                # Missed time at which to tick.
                # TODO - move constant rate into mixin?
                # TODO - make missed tick behavior customizable.
                # TODO - metric on delay time?
                logger.error(f'{self} delayed tick')
                delay = 0
                self._next_tick_time += 2 * TIME_PER_TICK
        return asyncio.sleep(delay)

    def __str__(self) -> str:
        return f'{self.__class__.__qualname__}({id(self)})'
    __repr__ = __str__

class TrafficLightTest(TestCase):

    def test_traffic_light(self) -> None:
        expected = [Color.GREEN, Color.YELLOW, Color.RED] * CYCLES
        async def _run() -> None:
            logger.info(f'Creating {NUMBER_OF_TRAFFIC_LIGHTS} traffic lights')
            traffic_lights = [TrafficLight()
                              for _ in range(NUMBER_OF_TRAFFIC_LIGHTS)]

            logger.info(f'starting {len(traffic_lights)} traffic lights')
            awaitables = [(traffic_light, await traffic_light.start())
                          for traffic_light in traffic_lights]

            logger.info(f'awaiting {len(awaitables)} traffic lights')
            for traffic_light, awaitable in awaitables:
                await awaitable
                self.assertEqual(expected, traffic_light.sequence)
                self.assertEqual(traffic_light.cycles, CYCLES)
            logger.info(f'done')
        asyncio.run(_run())


if __name__ == "__main__":
    main()