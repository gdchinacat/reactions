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

from unittest import TestCase, main

from ... import Field, FieldManager, And


class Counter(FieldManager):
    '''
    Simple model that implements a counter.

    It has a loop() that increments a count and a done() that completes
    execution when the count reaches a specified value.

    It derives from Reactant in order to start and stop execution of the state
    machine.
    '''

    # annotations are required for dataclass to include in __init__
    count_to: Field[int] = Field(0)
    count: Field[int] = Field(-1)

    def __init__(self, count_to: int = 0):
        super().__init__()
        self.count_to = count_to

    def _start(self) -> None:
        '''Start counting.'''
        self.count = 0

    # stop when the count reaches count_to
    (count == count_to)(FieldManager.astop)

    @ And(0 <= count,
          count < count_to)
    async def loop(self,
                   field: Field[int],
                   old: int,
                   new: int) -> None:
        self.count += 1


class CounterTest(TestCase):

    def test_count(self) -> None:
        counter = Counter(5)
        counter.run()

        self.assertEqual(counter.count, counter.count_to)


if __name__ == "__main__":
    main()
