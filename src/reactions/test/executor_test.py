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
Executor test.
'''
from unittest import TestCase, main

from ..error import ExecutorAlreadyStarted
from ..executor import Executor
from .async_helpers import asynctest


class ExecutorTest(TestCase):

    @asynctest
    async def test_executor_context_manager(self) -> None:
        executor = Executor()
        async with executor:
            with self.assertRaises(ExecutorAlreadyStarted):
                executor.start()
        assert executor.task
        self.assertTrue(executor.task.done())


if __name__ == "__main__":
    main()
