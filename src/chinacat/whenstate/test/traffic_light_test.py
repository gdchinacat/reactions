from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from unittest import TestCase, main

from ..field import Field, BoundField
from ..predicate import And
from ..state import State


TICKS_PER_LIGHT = 1
CYCLES = 1


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

    ticks: Field[TrafficLight, int] = \
        Field["TrafficLight", int]("TrafficLight", 'ticks', -1)
    '''tick: the number of ticks for the current color'''

    cycles: Field[TrafficLight, int] = \
        Field["TrafficLight", int]("TrafficLight", 'cycles', 0)
    ''' cycles: the number of times the light has gone through a full cycle '''

    def _start(self) -> None:
        self.ticks = 0

    @State.when(And(color == Color.RED,
                    ticks == TICKS_PER_LIGHT))
    def red_to_green(self,
                     bound_field: BoundField[TrafficLight, int | Color],
                     old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.GREEN)

    @State.when(And(color == Color.GREEN,
                    ticks == TICKS_PER_LIGHT))
    def green_to_yellow(self,
                        bound_field: BoundField[TrafficLight, int | Color],
                        old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.change(Color.YELLOW)

    @State.when(And(color == Color.YELLOW,
                    ticks == TICKS_PER_LIGHT))
    def yellow_to_red(self,
                      bound_field: BoundField[TrafficLight, int | Color],
                      old: int | Color, new:int | Color) -> None:  # @UnusedVariable
        self.cycles += 1
        self.change(Color.RED)

    def change(self, color: Color) -> None:
        self.ticks = 0
        self.color = color
        print(color.name)

    @State.when(ticks != -1)
    def tick(self,
             bound_field: BoundField[TrafficLight, int],
             old: int, new: int) -> None:  # @UnusedVariable
        if self.ticks != new:
            return  # TODO - shouldn't have to check our predicates to know
                    # it has been invalidated by another reaction.
        assert self.ticks != TICKS_PER_LIGHT

        if self.cycles == CYCLES:
            self._stop()
        else:
            self.ticks += 1


class TrafficLightTest(TestCase):

    def test_traffic_light(self):
        traffic_light = TrafficLight()
        asyncio.run(traffic_light.run())
        
        self.assertEqual(traffic_light.cycles, CYCLES)


if __name__ == "__main__":
    main()