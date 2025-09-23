'''
Error definitions.
'''
from typing import Any, Callable


__all__ = ['MustNotBeCalled']


class MustNotBeCalled(RuntimeError):
    '''
    Raised by methods that are easy to call when they really aren't what should
    be called.
    '''
    def __init__(self, func: Callable[[Any], Any] | None, *args, **kwargs):
        if func:
            # subclasses don't have to pass func if they already handled it.
            super().__init__(f'{func.__qualname__} must not be called',
                             *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        '''raises self to indicate a MustNotBeCalled was in fact called'''
        raise self
