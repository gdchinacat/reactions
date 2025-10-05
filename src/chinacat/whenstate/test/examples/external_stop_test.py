'''
Example of how to cleanly stop a self driven state.

The Counter has a done field that is set to indicate it should stop. The _count
reaction predicate checks this flag and stops processing.
'''
from __future__ import annotations

from unittest import TestCase, main

from ... import Reactant, Field, And
from ..async_helpers import asynctest


class Counter(Reactant):
    done: Field[Counter, bool] = Field(False)
    count: Field[Counter, int] = Field(-1)

    (done == True)(Reactant.astop)  # stop the executor when done
    
    @ And(count >= 0,
          done == False)
    async def _count(self, field, old, new):
        if not self.done:
            self.count += 1

    def _start(self):
        self.count = 0

class ExternalStopTest(TestCase):
    
    @asynctest
    async def test_external_stop(self):
        counter = Counter()
        
        count_to = 5
        @ Counter.count == count_to  # todo - should be on counter.count BoundField
        async def stop(*args):
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