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


class StateNotStarted(StateError):
    '''
    Error indicating an action was taken that requires the state event loop
    to have been started yet wasn't.
    '''

class StateAlreadyStarted(StateError):
    '''
    Error indicating the state has already been started.

    The State may have already terminated, which, as the name implies, is
    terminal and can't be restarted. This error does not imply the state is
    running, only that the request to start it failed.
    '''

class StateAlreadyComplete(StateError):
    '''
    Error indicating the state has already been completed when an attempt
    to complete it was made.
    '''

class StateHasPendingReactions(StateError):
    '''
    StateHasPendingReactions is raised when a state is stop()'ed while it has
    reactions that have not yet executed.
    TODO - provide guidance on how to implement things so you *don't* have
    pending reactions. The problem is best illustrated by a state field that
    counts by incrementing the same field it uses as a predicate. In this case
    the reaction will always be both executing and pending since the executing
    calls task will be pending and will enqueue another execution. There is
    never a time when there isn't one pending reaction. States that are self
    driven must always have at least one pending reaction or they will cease to
    be self driven.
    '''
    

class PredicateError(RuntimeError): ...
class InvalidPredicateExpression(PredicateError): ...
