from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest import TestCase, main

from ..field import Field, BoundField
from ..predicate import And
from ..state import State

@dataclass
class Counter(State):
    '''
    Simple model that implements a counter. It has a loop() that increments
    a count and a done() that completes execution when the count reaches a
    specified value.
    '''

    count_to: Field[Counter, int] = \
        Field["Counter", int]("Counter", 'count_to', 0)

    count: Field[Counter, int] = \
        Field["Counter", int]("Counter", 'count', -1)
    '''count: the count'''
    
    def _start(self) -> None:
        self.count = 0

    @State.when(0 <= count)
    def loop(self,
             bound_field: BoundField[Counter, int],
             old: int, new:int) -> None:  # @UnusedVariable
        assert old + 1 == new, f"count error {old} + 1 != {new}"
        if self.count == self.count_to:
            self._stop()
        else:
            self.count += 1


class CounterTest(TestCase):

    def test_count(self):
        counter = Counter(50)
        asyncio.run(counter.run(), debug=False)

        # TODO - this test currently fails because the state is completed on
        #        5000 but loop() was already scheduled by the call to it that
        #        incremented it to 5000, so it runs. I'd rather not have to
        #        have a counter reaction have to include the duplicate
        #        condition for done
        self.assertEqual(counter.count, counter.count_to)


if __name__ == "__main__":
    main()
