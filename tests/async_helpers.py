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
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import ParamSpec
import asyncio


TestParams = ParamSpec("TestParams")
TestMethod = Callable[TestParams, None]
AsyncTestMethod = Callable[TestParams, Coroutine[None, None, None]]
TestMethodDecorator = Callable[[AsyncTestMethod[TestParams]],
                               TestMethod[TestParams]]

def asynctest(func: AsyncTestMethod[TestParams]|None = None,
              *,
              timeout:float|None=1
              ) -> TestMethod[TestParams]|TestMethodDecorator[TestParams]:
    '''
    Decorator to execute async test functions.
    func - function to decorate
    timeout - timeout to apply
    May be used as a plain decorator:
    @asynctest
    def test_foo(..): ...

    or with arguments:
    @asynctest(timeout=2)
    async def test_foo(...): ...
    '''
    def dec(func: AsyncTestMethod[TestParams]) -> TestMethod[TestParams]:
        @wraps(func)
        def _asynctest(*args: TestParams.args, **kwargs: TestParams.kwargs
                       ) -> None:
            @wraps(func)
            async def async_test_runner() -> None:
                async with asyncio.timeout(timeout):
                    await func(*args, **kwargs)
            asyncio.run(async_test_runner())
        return _asynctest
    if func is not None:
        return dec(func)
    return dec
