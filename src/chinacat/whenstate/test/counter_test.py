from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from unittest import TestCase, main

from ..field import Field, BoundField
from ..predicate import And
from ..state import State


logger = logging.getLogger('counter_test')

@dataclass
class Counter(State):
    '''
    Simple model that implements a counter. It has a loop() that increments
    a count and a done() that completes execution when the count reaches a
    specified value.
    '''

    count: Field[Counter, int] = \
        Field["Counter", int]("Counter", 'count', -1)
    '''count: the count'''
    
    def _start(self) -> None:
        self.count = 0

    @State.when(count == 5)
    def done(self,
             bound_field: BoundField[Counter, int],
             old: int, new:int) -> None:  # @UnusedVariable
        assert self._complete is not None
        self._complete.set_result(None)
        
    @State.when(And(0 <= count,
                    count < 5))
    def loop(self,
             bound_field: BoundField[Counter, int],
             old: int, new:int) -> None:  # @UnusedVariable
        self.count += 1
        

class CounterTest(TestCase):

    def test_counter(self):
        counter = Counter()
        asyncio.run(counter.run())
        
        self.assertEqual(counter.count, 5)


if __name__ == "__main__":
    main()
