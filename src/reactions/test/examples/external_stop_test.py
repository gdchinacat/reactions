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
from __future__ import annotations

from unittest import TestCase, main

from ... import Reactant, Field
from ..async_helpers import asynctest


class Counter(Reactant):
    done = Field[bool](False) # field to  indicate state should stop
    count = Field[int](-1)    # start in a quiescent state

    # Manual application of predicate decorator to stop the state machine when
    # done.
    (done == True)(Reactant.astop)
    
    @ count >= 0
    async def _count(self, *_):
        '''keep counting until done'''
        if not self.done:
            self.count += 1

    def _start(self):
        '''start the counter by transitioning from quiescent state'''
        self.count = 0

class ExternalStopTest(TestCase):
    
    @asynctest
    async def test_external_stop(self):
        counter = Counter()
        
        count_to = 5

        # todo - Counter.count will apply the reaction any Counter instance
        #        that reaches count_to. Not a problem with just one Counter
        #        but if another Counter was being used concurrently (tests in
        #        parallel) it could confuse this. Essentially the same problem
        #        with globals because Couner.count is essentially a global.
        #        Need a way to apply it to only counter.
        #        @ Counter.count[counter] == count_to
        #            - create a bound predicate where Counter instance is
        #              the bound field and predicate is bound to counter?
        @ Counter.count == count_to
        @staticmethod
        async def stop(*_):
            counter.done = True
            
        await counter.start()

        counter._logger.info("Done waiting for count to complete, "
                            f"final count: {counter.count}")

        # TODO - the change that makes stop predicate true has two reactions
        #        on it, one to increment the count, one to set done=True. By
        #        the time stop() is called the count is already one greater
        #        than the value in the predicate. Account for this here. But,
        #        this is counterintuitive and is likely to cause bugs that are
        #        hard to track down. Is there a better way? Yes! Allow the
        #        (what should be) bound field reaction to run before the Field
        #        reactions. Instance reactions take precedence of class
        #        reactions?
        assert counter.count == count_to + 1

if __name__ == '__main__':
    main()