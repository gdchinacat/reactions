from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest import TestCase, main

from ... import BoundField, Field, State


@dataclass
class Counter(State):
    '''
    Simple model that implements a counter. It has a loop() that increments
    a count and a done() that completes execution when the count reaches a
    specified value.
    '''

    count_to: Field[Counter, int] = Field(0)
    count: Field[Counter, int] = Field(-1)
    
    def _start(self) -> None:
        self.count = 0

    @State.when(0 <= count)
    async def loop(self,
                   bound_field: BoundField[Counter, int],
                   old: int, new:int) -> None:  # @UnusedVariable
        assert old + 1 == new, f"count error {old} + 1 != {new}"
        if self.count == self.count_to:
            self.stop()
        else:
            self.count += 1


class CounterTest(TestCase):

    def test_count(self):
        counter = Counter(5)
        asyncio.run(counter.run(), debug=False)

        self.assertEqual(counter.count, counter.count_to)


if __name__ == "__main__":
    main()
