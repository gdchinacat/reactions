from __future__ import annotations

import asyncio
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

    @State.when(And(color == Color.RED,
                    ticks == 4))
    def red_to_green(self,
                     bound_field: BoundField[TrafficLight, int | Color],
                     old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.GREEN)

    @State.when(And(color == Color.GREEN,
                    ticks == 4))
    def green_to_yellow(self,
                        bound_field: BoundField[TrafficLight, int | Color],
                        old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.YELLOW)

    @State.when(And(color == Color.YELLOW,
                    ticks == 4))
    def yellow_to_red(self,
                      bound_field: BoundField[TrafficLight, int | Color],
                      old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.RED)

    def change(self, color: Color) -> None:
        assert self.ticks == 4, f"resetting from {self.ticks=}"
        # order is very sensitive, changing color before ticks results in rapic
        # cycling through the colors as predicates evaluate to true since ticks
        # hasn't changed.
        self.cycles += 1
        self.ticks = 0
        self.color = color
        print(color)

    @State.when(ticks != -1)
    def loop(self,
             bound_field: BoundField[TrafficLight, int],
             old: int, new: int) -> None:  # @UnusedVariable
        assert self.ticks != 4

        if self.cycles == 5:
            self.stop()
        else:
            self.ticks += 1


class TrafficLightTest(TestCase):

    def test_traffic_light(self):
        traffic_light = TrafficLight()
        asyncio.run(traffic_light.run())
        
        self.assertEqual(traffic_light.cycles, 5)


if __name__ == "__main__":
    main()