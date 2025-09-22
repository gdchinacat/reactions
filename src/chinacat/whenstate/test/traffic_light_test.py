from dataclasses import dataclass
from enum import Enum
from unittest import TestCase

from .. import State
from .. import Field


class Color(Enum):
    '''the color of a traffic light'''
    RED = 1
    GREEN = 2
    YELLOW = 3


@dataclass
class traffic_light(State):
    '''
    simple model that implements a traffic light:
    '''
    # todo metaclass to wrap attributes with Field
    color: Color = Field[Color](Color.RED)

    @State.when(color == Color.RED and State.count == 4)
    def red_to_green(self):
        self.color = Color.GREEN
        self.count = 0


class TrafficLightTest(TestCase):
    def test_traffic_light(self):
        pass