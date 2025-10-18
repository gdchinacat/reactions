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
Error definitions.
'''
from collections.abc import Callable
from typing import NoReturn


__all__ = ['MustNotBeCalled', 'ReactionMustNotBeCalled',
           'ExecutorError', 'ExecutorNotStarted', 'ExecutorAlreadyStarted',
           'PredicateError', 'InvalidPredicateExpression']


class MustNotBeCalled(RuntimeError):
    '''
    Raised by methods that are easy to call when they really aren't what should
    be called.
    '''
    def __init__(self, func: Callable[..., object]|None,
                 *args: object, **kwargs: object) -> None:
        if func:
            # subclasses don't have to pass func if they already handled it.
            super().__init__(f'{func} must not be called', *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

    def __call__(self, *args: object, **kwargs: object) -> NoReturn:
        '''raises self to indicate a MustNotBeCalled was in fact called'''
        raise self


class ReactionMustNotBeCalled(MustNotBeCalled):
    '''
    Exception raised if a function decorated with a predicate is called
    directly, they should only be called from the Executor.

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
              async def reaction(self, change: FieldChange): ...
              (foo==1)(reaction)
    '''
    def __init__(self,
                 func: Callable[..., object],
                 *args: object,
                 **kwargs: object) -> None:
        super().__init__(None, f"{func.__qualname__} is a reaction method and "
                         "can not be called directly.", *args, **kwargs)


class ExecutorError(RuntimeError):
    '''base class for executor errors'''


class ExecutorNotStarted(ExecutorError):
    '''
    Error indicating an action was taken that requires the state event loop
    to have been started yet wasn't.
    '''

class ExecutorAlreadyStarted(ExecutorError):
    '''
    Error indicating the state has already been started.

    The Executor may have already terminated, which, as the name implies, is
    terminal and can't be restarted. This error does not imply the state is
    running, only that the request to start it failed.
    '''

class FieldConfigurationError(RuntimeError):
    '''Error indicating a field definition or management is improper.'''

class FieldAlreadyBound(FieldConfigurationError):
    '''
    Internal error indicating an instance already has a binding for a Field.
    Users aren't responsible and shouldn't need to bind fields directly. It
    indicates the FieldBinder has a fault.
    '''


class PredicateError(RuntimeError): ...
class InvalidPredicateExpression(PredicateError, MustNotBeCalled): ...
