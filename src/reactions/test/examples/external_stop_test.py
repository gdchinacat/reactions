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
'''
Example of how to cleanly stop a self driven state.

The Counter has a done field that is set to indicate it should stop. The _count
reaction predicate checks this flag and stops processing.
'''
from unittest import TestCase, main

from ... import Field, ExecutorFieldManager, FieldChange


class Counter(ExecutorFieldManager):
    done: Field[Counter, bool] = Field(False) # field to  indicate state should stop
    count: Field[Counter, int] = Field(-1)    # start in a quiescent state

    # Manual application of predicate decorator to stop the state machine when
    # done.
    (done == True)(ExecutorFieldManager.astop)

    @ count >= 0
    async def count_(self, *_: object) -> None:
        '''keep counting until done'''
        if not self.done:
            self.count += 1

    def _start(self) -> None:
        '''start the counter by transitioning from quiescent state'''
        self.count = 0

class ExternalStopTest(TestCase):

    def test_external_stop(self) -> None:
        count_to = 5
        counter = Counter()

        @ Counter.count[counter] == count_to
        async def stop(
            instance: Counter,
            change: FieldChange[Counter, int]
            ) -> None:
            # the Counter reaction to increment count has already executed by
            # the time this one executes, so instance.count is one greater than
            # the value that caused this reaction to execute.
            self.assertEqual(instance.count, change.new + 1)
            counter.done = True

        counter.run()

        assert counter.count == count_to + 1

if __name__ == '__main__':
    main()