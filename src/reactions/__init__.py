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
    count = Field(-1)

    @ count >= 0
    async def _count(self, field, old, new):
        self.count += 1

    def _start(self):
        self.count = 0

'''

from . import base_field
from . import error
from . import executor
from . import field
from . import predicate
from . import predicate_types
from .base_field import *
from .error import *
from .executor import *
from .field import *
from .predicate import *
from .predicate_types import *


__all__ = (
           base_field.__all__ +
           error.__all__ +
           executor.__all__ +
           field.__all__ +
           predicate.__all__ +
           predicate_types.__all__ +
          [])
