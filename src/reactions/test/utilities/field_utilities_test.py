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

from unittest import TestCase, main

from asyncio import sleep

from ...field import Field, ExecutorFieldManager, FieldWatcher
from ...test.async_helpers import asynctest
from ...utilities import adjust_while


class Adjusted:
    adjusted = 0


class _C(Adjusted, ExecutorFieldManager):
    field: Field['_C', bool]

    def _start(self) -> None: ...


class Test(TestCase):

    async def _test_adjust_while(self, c: _C,
                                 watcher: Adjusted) -> None:
        async with c.executor:
            c.field = True
            await sleep(0)  # yield so the reaction can execute
            self.assertEqual(1, watcher.adjusted)

            c.field = False
            await sleep(0)  # yield so the reaction can execute
            self.assertEqual(0, watcher.adjusted)

    @asynctest
    async def test_adjust_while_watcher(self) -> None:
        class C(_C):
            field = Field['C', bool](False)
        class Watcher(Adjusted, FieldWatcher[C]):
            adjust_while(C.field, 'adjusted', 1, locals(), watcher=True)
        c = C()
        watcher = Watcher(c)

        await self._test_adjust_while(c, watcher)

    @asynctest
    async def test_adjust_while_instance(self) -> None:
        class C(_C):
            field = Field['C', bool](False)
            adjust_while(field, 'adjusted', 1, locals())
        c = C()
        await self._test_adjust_while(c, c)


if __name__ == '__main__':
    main()
