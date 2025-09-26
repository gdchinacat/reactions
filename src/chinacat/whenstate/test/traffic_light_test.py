from __future__ import annotations

import asyncio
from asyncio import Future
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from unittest import TestCase, main

from ..field import Field, BoundField
from ..predicate import And
from ..state import State


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

    _complete: Optional[Future[None]] = None

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

    def start(self) -> Future[None]:
        self.ticks = 0
        future = self._complete = Future[None]()
        return future

    @State["TrafficLight"].when(cycles == 5)
    async def done(self,
             bound_field: BoundField[TrafficLight, int],
             # the field types depend on the predicates
             old: int, new: int) -> None:  # @UnusedVariable
        assert self._complete is not None
        self._complete.set_result(None)

    @State["TrafficLight"].when(ticks != None)
    async def loop(self,
             bound_field: BoundField[TrafficLight, int],
             # the field types depend on the predicates
             old: int, new:int) -> None:  # @UnusedVariable
        self.ticks += 1

    @State["TrafficLight"].when(And(color == Color.RED,
                    ticks == 4))
    async def red_to_green(self,
                     bound_field: BoundField[TrafficLight, int | Color],
                     # the field types depend on the predicates
                     old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.ticks = 0
        self.color = Color.GREEN
        print("GREEN")

    @State["TrafficLight"].when(And(color == Color.GREEN,
                    ticks == 4))
    async def green_to_yellow(self,
                        bound_field: BoundField[TrafficLight, int | Color],
                        # the field types depend on the predicates
                        old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.ticks = 0
        self.color = Color.YELLOW
        print("YELLOW")

    @State["TrafficLight"].when(And(color == Color.YELLOW,
                    ticks == 4))
    async def yellow_to_red(self,
                      bound_field: BoundField[TrafficLight, int | Color],
                      # the field types depend on the predicates
                      old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.ticks = 0
        self.color = Color.RED
        print("RED")


class TrafficLightTest(TestCase):

    def test_traffic_light(self):
        traffic_light = TrafficLight()

        async def run():
            await traffic_light.start()
        asyncio.run(run())
        
        self.assertEqual(traffic_light.cycles, 5)


if __name__ == "__main__":
    main()