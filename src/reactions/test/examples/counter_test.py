# Copyright (C) 2025 Anthony (Lonnie) Hutchinson <chinacat@chinacat.org>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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
