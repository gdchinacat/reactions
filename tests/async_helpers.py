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
Helpers for async testing.
'''
from collections.abc import Callable, Coroutine, AsyncGenerator
from contextlib import asynccontextmanager
from functools import wraps
from typing import ParamSpec
import asyncio


TestParams = ParamSpec("TestParams")
TestMethod = Callable[TestParams, None]
AsyncTestMethod = Callable[TestParams, Coroutine[None, None, None]]
TestMethodDecorator = Callable[[AsyncTestMethod[TestParams]],
                               TestMethod[TestParams]]
AsyncTestMethodDecorator = Callable[[AsyncTestMethod[TestParams]],
                                    AsyncTestMethod[TestParams]]

@asynccontextmanager
async def async_timeout(timeout: float|None = 1) -> AsyncGenerator[None]:
    """
    asynccontextmanager wrapper around asyncio.timeout.

    @async_timeout(2)
    async def foo():
        ...

    async def foo():
        async with async_timeout(2):
            ...
    """
    async with asyncio.timeout(timeout):
        yield
