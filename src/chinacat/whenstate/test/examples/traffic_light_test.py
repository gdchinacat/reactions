from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
from time import time
from typing import List, Coroutine
from unittest import TestCase, main

from ... import Field, And, State


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


@dataclass
class TrafficLight(State):
    '''
    simple model that implements a traffic light:
    '''

    color: Field[TrafficLight, Color] = Field(Color.RED)
    '''color: the current color of the light'''

    ticks: Field[TrafficLight, int] = Field(-1)
    '''tick: the number of ticks for the current color'''

    cycles: Field[TrafficLight, int] = Field(0)
    ''' cycles: the number of times the light has gone through a full cycle '''

    _next_tick_time: float = 0
    '''
    the time the next tick should happen, used to keep a regular tick rather
    than a regular space between ticks.
    '''

    sequence: List[Color] = field(default_factory=list)

    def _start(self) -> None:
        self.ticks = 0

    @And(color == Color.RED,
         ticks == TICKS_PER_LIGHT)
    async def red_to_green(self,
                     field: Field[TrafficLight, int | Color],
                     old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.GREEN)

    @And(color == Color.GREEN,
         ticks == TICKS_PER_LIGHT)
    async def green_to_yellow(self,
                        field: Field[TrafficLight, int | Color],
                        old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.YELLOW)

    @And(color == Color.YELLOW,
         ticks == TICKS_PER_LIGHT)
    async def yellow_to_red(self,
                      field: Field[TrafficLight, int | Color],
                      old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.cycles += 1
        self.change(Color.RED)

    def change(self, color: Color) -> None:
        self.ticks = 0
        self.color = color
        self.sequence.append(color)
        logger.debug('%s %s', self, color.name)

    @ ticks != -1
    async def tick(self, 
             field: Field[TrafficLight, int],
             old: int, new: int) -> None:  # @UnusedVariable
        
        if self.ticks != new:
            # TODO - reactions can be called when their predicate is not true
            #        if another reaction modifies the field between scheduling
            #        and execution of this reaction. Specifically the reactions
            #        to change the color reset ticks to zero in reaction to a
            #        tick change and execute before this reaction since they
            #        are defined before this one. When ticks changes both the
            #        color changing reaction and this reaction are scheduled,
            #        the color changing reaction resets ticks, then this
            #        reaction executes. It isn't an error per se, but can be
            #        unintuitive. The reaction was scheduled for *asynchronous*
            #        execution, and the predicate was changed during that
            #        asynchronous execution.
            # Don't increment the tick...the other reaction already handled it.
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
                # TODO - move constant rate into State mixin.
                # TODO - make missed tick behavior customizable.
                # TODO - metric on delay time?
                logger.error(f'{self} delayed tick')
                delay = 0
                self._next_tick_time += 2 * TIME_PER_TICK
        return asyncio.sleep(delay)

    def __str__(self):
        return f'{self.__class__.__qualname__}({id(self)})'

class TrafficLightTest(TestCase):

    def test_traffic_light(self):
        expected = [Color.GREEN, Color.YELLOW, Color.RED] * CYCLES
        async def _run():
            logger.info(f'Creating {NUMBER_OF_TRAFFIC_LIGHTS} traffic lights')
            traffic_lights = [TrafficLight()
                              for _ in range(NUMBER_OF_TRAFFIC_LIGHTS)]
            logger.info(f'starting {len(traffic_lights)} traffic lights')
            futures = [(traffic_light, traffic_light.start())
                       for traffic_light in traffic_lights]
            logger.info(f'awaiting {len(futures)} traffic lights')
            for traffic_light, future in futures:
                self.assertIsNone(await future)
                self.assertEqual(expected, traffic_light.sequence)
                self.assertEqual(traffic_light.cycles, CYCLES)
            logger.info(f'done')
        asyncio.run(_run())
        


if __name__ == "__main__":
    main()