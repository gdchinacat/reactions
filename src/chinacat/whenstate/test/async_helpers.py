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
            async with asyncio.timeout(None): # todo for testing 1):
                await func(*args, **kwargs)
        asyncio.run(async_test_runner())
    return _asynctest


