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
from __future__ import annotations

import asyncio
from functools import wraps


def asynctest(func):
    '''decorator to execute async test functions'''
    @wraps(func)
    def _asynctest(*args, **kwargs):
        @wraps(func)
        async def async_test_runner():
            async with asyncio.timeout(1):
                await func(*args, **kwargs)
        asyncio.run(async_test_runner())
    return _asynctest


