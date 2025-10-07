from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest import TestCase, main

from ... import Field, Reactant


@dataclass
class Counter(Reactant):
    '''
    Simple model that implements a counter.

    It has a loop() that increments a count and a done() that completes
    execution when the count reaches a specified value.

    It derives from Reactant in order to start and stop execution of the state
    machine.
    '''

    count_to: Field[int] = Field(0)
    count: Field[int] = Field(-1)
    
    def _start(self) -> None:
        '''
        Implementation of the abstract method to transition from the initial
        state to the running state. when the Counter is start()ed.
        '''
        self.count = 0

    @ count >= 0
    async def loop(self,
                   field: Field[int],
                   old: int,
                   new: int) -> None:
        assert old + 1 == new, f"count error {old} + 1 != {new}"
        if self.count == self.count_to:
            # Stop the state machine when the terminal count is reached
            # This can also be done as a reaction, but it is not as simple (see
            # external_stop_test) for an example of that.
            self.stop()
        else:
            self.count += 1


class CounterTest(TestCase):

    def test_count(self):
        counter = Counter(5)
        asyncio.run(counter.run())

        self.assertEqual(counter.count, counter.count_to)


if __name__ == "__main__":
    main()
