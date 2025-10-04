'''
Weird sick can't sleep thoughts after seeing:
https://www.reddit.com/r/Python/comments/1nmta0f/i_built_a_full_programming_language_interpreter/
Right before going to bed and trying to sleep I thought...I bet a bunch of that
can be done with standard python using descriptors and ....
Then the dogs barked and woke me up early while still sick. Here goes nothing.
This package is *not* the same thing as that post and does not aspire to be. It
is only inspired by it.

The basic idea is that you implement reaction methods that are called when
predicates become true. For example, this class counts upwards forever.

class Counter(Reactant):
    count: Field[Counter, int] = Field(-1)

    @ count >= 0
    async def _count(self, field, old, new):
        self.count += 1

    def _start(self):
        self.count = 0

'''

from . import error
from . import executor
from . import field
from . import logging_config  # todo - libraries shouldn't configure logging.
from . import predicate
from .error import *
from .executor import *
from .field import *
from .predicate import *


__all__ = (error.__all__ +
           executor.__all__ +
           field.__all__ +
           predicate.__all__)
