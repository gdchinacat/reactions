from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from unittest import TestCase, main

from ... import Field, BoundField, And, State


TICKS_PER_LIGHT = 2
CYCLES = 5


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
            self.ticks += 1


class TrafficLightTest(TestCase):

    def test_traffic_light(self):
        traffic_light = TrafficLight()
        asyncio.run(traffic_light.run())
        
        self.assertEqual(traffic_light.cycles, CYCLES)


if __name__ == "__main__":
    main()