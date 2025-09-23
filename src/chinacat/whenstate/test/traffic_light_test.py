from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from unittest import TestCase

from ..field import Field, BoundField
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

    ticks: Field[TrafficLight, int | None] = \
        Field["TrafficLight", int | None]("TrafficLight", 'ticks', None)
    '''tick: the number of ticks for the current color'''

    cycles: Field[TrafficLight, int] = \
        Field["TrafficLight", int]("TrafficLight", 'cycles', 0)
    ''' cycles: the number of times the light has gone through a full cycle '''

    @State.when(cycles == 5)
    def stop(self,
             bound_field: BoundField[TrafficLight, int],
             # the field types depend on the predicates
             old: int,
             new: int) -> None:
        self.ticks = None

    @State.when(ticks != None)
    def loop(self,
             bound_field: BoundField[TrafficLight, int],
             # the field types depend on the predicates
             old: int,
             new:int) -> None:
        self.ticks += 1

    @State.when((color == Color.RED) &
                (ticks == 4))
    def red_to_green(self,
                     bound_field: BoundField[TrafficLight, int | Color],
                     # the field types depend on the predicates
                     old: int | Color,
                     new:int | Color) -> None:
        self.ticks = 0
        self.color = Color.GREEN
        print("GREEN")

    @State.when((color == Color.GREEN) &
                (ticks == 4))
    def green_to_yellow(self,
                        bound_field: BoundField[TrafficLight, int | Color],
                        # the field types depend on the predicates
                        old: int | Color,
                        new:int | Color) -> None:
        self.ticks = 0
        self.color = Color.YELLOW
        print("YELLOW")

    @State.when((color == Color.YELLOW) &
                (ticks == 4))
    def yellow_to_red(self,
                      bound_field: BoundField[TrafficLight, int | Color],
                      # the field types depend on the predicates
                      old: int | Color,
                      new:int | Color) -> None:
        self.ticks = 0
        self.color = Color.RED
        print("RED")


class TrafficLightTest(TestCase):
    def test_traffic_light(self):
        traffic_light = TrafficLight()

        async def run():
            # there isn't a formal way to start the model...just nudge the
            # state to get it going. It should run to completion.
            traffic_light.ticks = 0
        
        asyncio.run(run())
        self.assertEqual(traffic_light.cycles, 5)
