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
Predicate test
'''

from __future__ import annotations

from unittest import TestCase, main

from .. import Field
from .async_helpers import asynctest


class PredicateTest(TestCase):

    @asynctest
    async def test_predicate_decorator_returns__reaction(self):
        '''test the object returned by decorating a reaction is correct'''
        class State:
            field: Field[bool] = Field(False)
        predicate = State.field == True
        reaction = predicate(lambda *_: ...)
        self.assertEqual(predicate, reaction.predicate)

if __name__ == "__main__":
    main()
