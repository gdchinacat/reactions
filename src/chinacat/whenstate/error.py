'''
Error definitions.
'''
from typing import Any, Callable, Optional


__all__ = ['MustNotBeCalled']


class MustNotBeCalled(RuntimeError):
    '''
    Raised by methods that are easy to call when they really aren't what should
    be called.
    '''
    def __init__(self, func: Optional[Callable[[Any], Any]], *args, **kwargs):
        if func:
            # subclasses don't have to pass func if they already handled it.
            super().__init__(f'{func.__qualname__} must not be called',
                             *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        '''raises self to indicate a MustNotBeCalled was in fact called'''
        raise self


class StateError(RuntimeError):
    '''base class for state errors'''


class StateAlreadyStarted(StateError):
    '''
    Error indicating the state has already been started.

    The State may have already terminated, which, as the name implies, is
    terminal and can't be restarted. This error does not imply the state is
    running, only that the request to start it failed.
    '''

class StateNotStarted(StateError):
    '''
    Error indicating an action was taken that requires the state event loop
    to have been started yet wasn't.
    '''
