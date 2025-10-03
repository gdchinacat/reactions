'''
Asynchronous reaction executor.
'''
from __future__ import annotations

from asyncio import Queue, Task, create_task, QueueShutDown
from dataclasses import dataclass, field
from logging import Logger, getLogger
from typing import Callable, Any, Optional, Coroutine, Tuple

from .error import (StateError, StateHasPendingReactions)
from .field import BoundField, Field


__all__ = ['ReactorBase']


logger: Logger = getLogger('whenstate.executer')


type Reaction[C, T] = Callable[[Any, Field[C, T], T, T], None]
type AsyncReaction[C, T] = Callable[[C, Field[C, T], T, T],
                                    Coroutine[None, None, None]]


class ReactionExecutor[C: "ReactorBase", T](
        Queue[Tuple[C, Coroutine[None, None, T]]]
        ):
    '''
    ReactionExecutor executes reactions for sublcasses of ReactorBase.

    It is an asyncio.Queue with a coroutine that executes elements of the queue
    as it is drained.
    It provides concurrency control. The executor processes the reactions in
    the order they are submitted, one after the next. The reactions are run
    asynchronously with respect to what is being reacted to, but synchronously
    with respect to the other reactions in the queue.
    There is no need to extend this in the future to run the tasks
    asynchronously with respect to each other. If that is desirable a reaction
    is able to create a Task or callbackk to execute asynchronously on the
    event loop. This is more explicit about when the state is being updated
    asynchronously and also makes the simple synchronous use case the default.
    '''

    task: Optional[Task] = None
    '''the task that is processing the queue to execute reactions'''

    @staticmethod
    def react(reaction: AsyncReaction[C, T],
              instance: C,
              bound_field: BoundField[C, T],
              old: T, new: T) -> None:
        '''reaction that asynchronously executes the reaction'''
        # The weirdness of this being a @staticmethod that gets its self from
        # the instance is so this method can be used as a @partial wrapped
        # predicate reaction rather than having an extra method do this before
        # calling # this method. While a @partial wraps this to pass the
        # reaction arg, it is created from a @classmethod that doesn't have the
        # actual state to get the _reaction_executor from.
        # Microbenchmarking on stock Mac OS build of python 3.13.7 shows
        # partial is significantly faster (22%) than an intermediate function:
        #     def foo(a): ...
        #     def foo_func(): return foo(1)  # 43.3 ns
        #     foo_partial = partial(foo, 1)  # 33.8 ns

        # Get self and assert state is acceptable.
        self = instance._reaction_executor
        assert self.task, "ReactionExecutor not start()'ed"
        
        instance.logger.debug(f'schedule %s (..., %s,  %s)',
                           reaction.__qualname__, old, new)
        coro = reaction(bound_field.instance, bound_field.field, old, new)
        try:
            self.put_nowait((bound_field.instance, coro))
        except QueueShutDown:
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
            raise StateError(f'reaction {reaction.__qualname__} called '
                             f'after {self} completed.')


    def start(self):
        self.task = create_task(self.execute_reactions())

    def stop(self):
        '''stop the reaction queue'''
        if not self.empty():
            # todo - haven't seen this, write a unit test to make sure it
            #        actually works.
            raise StateHasPendingReactions()
        self.shutdown()
        self.task.cancel()  # stop processing reactions

    async def execute_reactions(self):
        '''
        Queue worker that gets pending tasks from the queue and executes
        them.

        The pending tasks are processed synchronously.
        '''
        while True:
            try:
                (instance, coro) = await self.get()
            except QueueShutDown:
                break
            try:
                instance.logger.debug(f'calling {coro}')
                await coro
            except Exception as exc:
                instance.error(exc)
            finally:
                self.task_done()

@dataclass
class ReactorBase:
    '''base class for classes that have reactions'''
    _reaction_executor: ReactionExecutor = field(
        default_factory=ReactionExecutor, kw_only=True)
    logger: Logger = field(default=logger, kw_only=True)
