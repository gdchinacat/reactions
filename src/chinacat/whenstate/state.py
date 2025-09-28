'''
An event driven state machine.

Implementation is done by specifying reaction functions that react to state
changes based on predicates. When a state field changes the predicates that
use the changed field are reevaluated and the reaction is scheduled for
asynchronous execution.

Execution of the reaction is delayed from when the predicate for the reaction
is evaluated. This means intervening reactions may change state such that the
predicate is no longer true when the reaction is eventually executed. State
implementations are expected to take this into account. TODO - mark fields
for predicates with pending reactions so that updates to them raise exception?
This would guarantee predicates don't become false before their reactions
are done executing, but would preclude reactions that change their predicate
field...implementing a counter would become convoluted (change to count_1
increments count_2 which has a reaction to change count_1...yuck..but may be
worth it).

The asynchronous execution of reactions means ordering is not well defined.
Implementations are expected to take this into account by modeling it in
sufficient detail to ensure the required semantics.

Implementations are strongly discouraged from using locks or other
synchronization primitives. Model the state those would manage.

TODO - come up with guidelines for how to safely implement state
'''
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from asyncio import Future, create_task, Task, current_task
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial, wraps
import logging
from typing import Callable, Any, Optional, Type, Set

from .error import (ReactionMustNotBeCalled, StateNotStarted, StateError,
                    StateAlreadyComplete, StateHasPendingReactions)
from .field import BoundField
from .predicate import Predicate


__all__ = ['State', 'ReactionMustNotBeCalled', ]


config_logger = logging.getLogger('whenstate.state.config')
execute_logger = logging.getLogger('whenstate.state.execute')


type ShouldBeState = Any 
type Decorator[**A, R] = Callable[A, R]
type Reaction[C] = Callable[[C, BoundField[C, Any], Any, Any], None]
type StateReaction = Reaction[ShouldBeState]


TRACE_ENABLED = True


def trace(func: Callable[..., Any]) -> Callable[..., Any]:
    if not TRACE_ENABLED:
        return func
    @wraps(func)
    def _trace(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
            execute_logger.debug(
                f'{func}({args=}, {kwargs=}) = {ret=}')
        except BaseException as exc:
            execute_logger.debug(
                f'!!{func}({args=}, {kwargs=}) raised {exc=}')
            raise
    return _trace
            

@dataclass(frozen=True)
class PendingTask:
    '''
    Elements of State._pending_tasks.
    Immutable.
    To enable set removal by either PendingTask or Task the hash is the same
    as the task has and equality uses only task identity.
    '''
    task: Task
    state: State
    reaction: str
    
    def __hash__(self):
        return hash(self.task)

    def __eq__(self, other):
        return self.task is other


@dataclass
class State(ABC):
    '''
    State implements an event driven state machine.

    Each State has its own asyncio event loop that is used for processing the
    state events.
    '''
    _complete: Optional[Future[None]] = field(init=False, default=None)
    _pending_tasks: Set[PendingTask] = field(init=False, default_factory=set)
    '''
    The set of pending tasks.
    Used to maintain strong reference as well as to implement cancellation.
    (reaction.__qualname__, Task)
    '''

    def start(self) -> Future[None]:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state.
         '''
        complete = self._complete = Future()
        self._start()
        return complete

    async def run(self) -> None:
        self._complete = self.start()
        await self._complete
        if (exc := self._complete.exception()):
            raise exc

    @abstractmethod
    def _start(self) -> None:
        '''
        Subclasses must implement this to start the state machine execution.
        '''

    def stop(self) -> None:
        '''
        Stop processing the state.
        Calling from a reaction will raise StateHasPendingReactions since the
        reaction is pending while executing. Use _stop() instead.
        '''
        self._stop(pending=0)
        
    def _stop(self, pending=1) -> None:
        '''
        stop the state processing.
        
        pending - the number of pending tasks that are allowed (exact number,
                  not a max number)
        '''
        if self._complete is None:
            raise StateNotStarted()
        elif self._complete.done():
            raise StateAlreadyComplete()
        if len(self._pending_tasks) > pending:
            pending_tasks = list(self._pending_tasks)
            task = current_task()
            msg = "\n\t".join(f'{"* " if pending.task is task else "  "}'
                              f'{pending.reaction}'
                              for pending in pending_tasks)
            raise StateHasPendingReactions(f'{len(pending_tasks)} pending '
                                           f' reactions:\n\t{msg}')
        self._cancel_pending_tasks()
        self._complete.set_result(None)
    
    def _cancel_pending_tasks(self):
        for pending_task in self._pending_tasks:
            pending_task.task.cancel()

    def error(self, exc_info: BaseException) -> None:
        if self._complete is None:
            raise StateNotStarted()
        elif self._complete.done():
            # future is already done so nothing to do but log it.
            execute_logger.exception('exception encountered processing '
                                     'reaction for closed state',
                                     exc_info=exc_info)
        self._cancel_pending_tasks()
        self._complete.set_exception(exc_info)

    def cancel(self, *args) -> None:
        if self._complete is None:
            raise StateNotStarted()
        self._cancel_pending_tasks()
        self._complete.cancel(*args)

    @asynccontextmanager
    async def async_exception_handler(self):
        '''
        async context manager to catch exceptions and route them to error()
        '''
        try:
            yield
        except Exception as exc:
            self.error(exc)

    async def call_reaction(self,
                            bound_field: BoundField[Type[State], Any],
                            predicate: Predicate,
                            reaction: StateReaction,
                            old: Any, new: Any):
        '''method to asynchronously call the reaction in a 'safe' way'''
        execute_logger.info(
            f' calling {reaction.__qualname__}(..., {old},  {new}) '
            f'for {predicate}')
        async with self.async_exception_handler():
            # yield control to the event loop to allow already 
            # scheduled reactions and task callbacks to run.
            # TODO - almost certainly need more robust
            #        synchronization/task control to guarantee
            #        execution semantics. This works for now.
            await asyncio.sleep(0)
            reaction(bound_field.instance, bound_field, old, new)

    @classmethod
    def when(cls, predicate: Predicate) \
        -> Decorator[[StateReaction], ReactionMustNotBeCalled]:
        '''
        Decorate a function to register it for execution when the predicate
        becomes true. The function is *not* called by the decorator. A dummy
        function is returned so that directly calling it on instances will
        raise ReactionMustNotBeCalled.

        The set of fields the predicate uses are reaction()ed to have the
        predicate react() by asynchronously calling the method being decorated.

        TODO - remove ReactionMustNotBeCalled to allow stacking @when()'s?
               not sure exactly what the semantics would be...And() the
               predicates together?
        TODO - allow async methods to be decorated with @when()?
        '''
        def dec(func: StateReaction) -> ReactionMustNotBeCalled:
            config_logger.info(
                f'{func.__qualname__} will be called when {predicate}')
            def reaction(self: State,
                         bound_field: BoundField[Type[State], Any],
                         old: Any, new: Any) -> Optional[Task]:
                '''Invoke the reaction asynchrounously.'''
                # TODO - this is suboptimal since each true predicate gets its
                #        own task rather than a single task for all the state
                #        reactions. Consider batching by returning tasks rather
                #        than executing them inlne.
                execute_logger.debug(
                    f'received notification for {predicate} that '
                    f'{bound_field} changed from {old} to {new}')
                assert self._complete is not None
                if not self._complete.done():
                    execute_logger.info(
                        f'schedule {func.__qualname__}(..., {old},  {new}) '
                        f'for {predicate}')
                    task = create_task(self.call_reaction(bound_field,
                                                          predicate,
                                                          func,
                                                          old, new))
                    pending = PendingTask(task, self, func.__qualname__)
                    self._pending_tasks.add(pending)
                    task.add_done_callback(
                        partial(self._pending_tasks.remove))
                    return task
                else:
                    # TODO - this can happen for a bunch of reasons that need
                    #        to be locked down. Once that has stabilized it may
                    #        still be possible, so this may need to be removed.
                    #        For now, I want to know when state updates are
                    #        happening after the state has entered terminal
                    #        state.
                    #        1) are queued tasks generating these? Why do we
                    #           have queued tasks for terminal state? (yes)
                    #        2) is the state continuing to execute after
                    #           completing its future? (only without sleep(0))
                    #        3) does state completion need to be moved into a
                    #           task? (don't think so)
                    #        4) are tasks waiting unexpectedly causing out of
                    #           order execution? (don't think so)
                    raise StateError(f'reaction {func.__qualname__} called '
                                     f'after {self} completed.')
                return None

            # Register predicate reactions that call our reaction with the
            # fields the predicate uses.
            for field in set(predicate.fields):
                assert not isinstance(field, BoundField)
                field.reaction(partial(predicate.react, target=reaction))

            return ReactionMustNotBeCalled(func)
        return dec


