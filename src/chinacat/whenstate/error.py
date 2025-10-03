'''
Error definitions.
'''
from typing import Any, Callable, Optional, NoReturn


__all__ = ['MustNotBeCalled', 'ReactionMustNotBeCalled',
           'StateError', 'StateNotStarted', 'StateAlreadyStarted',
           'StateAlreadyComplete', 'StateHasPendingReactions',
           'PredicateError', 'InvalidPredicateExpression', ]


class MustNotBeCalled(RuntimeError):
    '''
    Raised by methods that are easy to call when they really aren't what should
    be called.
    '''
    def __init__(self, func: Optional[Callable[..., Any]], *args, **kwargs):
        if func:
            # subclasses don't have to pass func if they already handled it.
            super().__init__(f'{func} must not be called', *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs) -> NoReturn:
        '''raises self to indicate a MustNotBeCalled was in fact called'''
        raise self
 

class ReactionMustNotBeCalled(MustNotBeCalled):
    '''
    Exception raised if a function decorated with a predicate is called
    directly, they should only be called from the ReactionExecutor.

    The removal of the method from a class definition is very intentional.
        - readers may reasonably but incorrectly think the @Predicate decorator
          is a guard that skips calls if the predicate is false. Avoiding
          confusion is a good thing.
        - it would be possible to return a function that does that. Calls that
          are ignored in this way are likely to hurt performance and suggest
          the state model is not well designed, or understood. Encouraging
          good design and understanding is a good thing.
        - there is a trivial workaround...invoke the decorator manually on a
          function definition that will be included and is very explicit about
          what the function semantics are:
              def reaction(self: C, bound_field: BoundField[C, T], old, new): ...
              State.when(foo==1)(react)
    '''
    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__(None, f"{func.__qualname__} is a reaction method and "
                         "can not be called directly.", *args, **kwargs)


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
class InvalidPredicateExpression(PredicateError, MustNotBeCalled): ...
