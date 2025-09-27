from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Optional, Type
from unittest import TestCase, main

from ..field import Field, BoundField
from ..predicate import And
from ..state import State


logger = logging.getLogger('traffic_light_test')

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

    # todo metaclass to wrap attributes with Field
    color: Field[TrafficLight, Color] = \
        Field["TrafficLight", Color]("TrafficLight", 'color', Color.RED)
    '''color: the current color of the light'''

    ticks: Field[TrafficLight, Optional[int]] = \
        Field["TrafficLight", Optional[int]]("TrafficLight", 'ticks', None)
    '''tick: the number of ticks for the current color'''

    cycles: Field[TrafficLight, int] = \
        Field["TrafficLight", int]("TrafficLight", 'cycles', 0)
    ''' cycles: the number of times the light has gone through a full cycle '''

    def _start(self) -> None:
        self.ticks = 0

    def error(self, exc:Exception)->None:
        assert self._complete is not None
        self._complete.set_exception(exc)

    @State.when(cycles == 5)
    def done(self,
             bound_field: BoundField[Type[TrafficLight], int],
             old: int, new: int) -> None:  # @UnusedVariable
        assert self.cycles == 5
        assert self._complete is not None
        self._complete.set_result(None)
        self.ticks = -1  # todo - shouldn't be necessary...but stops looping

    @State.when(And(color == Color.RED,
                    ticks == 4))
    def red_to_green(self,
                     bound_field: BoundField[Type[TrafficLight], int | Color],
                     old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        assert self.ticks == 4, f"resetting from {self.ticks=}"
        self.ticks = 0
        self.color = Color.GREEN
        print("GREEN")

    @State.when(And(color == Color.GREEN,
                    ticks == 4))
    def green_to_yellow(self,
                        bound_field: BoundField[Type[TrafficLight], int | Color],
                        old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        logger.debug(f"green_to_yellow called: {bound_field=} {old=} {new=}")
        assert self.ticks == 4, f"resetting from {self.ticks=}"
        self.ticks = 0
        self.color = Color.YELLOW
        print("YELLOW")

    @State.when(And(color == Color.YELLOW,
                    ticks == 4))
    def yellow_to_red(self,
                      bound_field: BoundField[Type[TrafficLight], int | Color],
                      old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        assert self.ticks == 4, f"resetting from {self.ticks=}"
        self.ticks = 0
        self.cycles += 1
        self.color = Color.RED
        print("RED")

    @State.when(ticks != -1)
    def loop(self,
             bound_field: BoundField[Type[TrafficLight], int],
             old: int, new: int) -> None:  # @UnusedVariable
        logger.debug(f'loop() called: {self.ticks}+=1 => {self.ticks + 1}')
        self.ticks += 1


class TrafficLightTest(TestCase):

    def test_traffic_light(self):
        traffic_light = TrafficLight()

        async def run():
            await traffic_light.start()
        asyncio.run(run())
        
        self.assertEqual(traffic_light.cycles, 5)


if __name__ == "__main__":
    main()