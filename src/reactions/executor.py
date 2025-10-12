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
Asynchronous reaction executor.
'''
from __future__ import annotations

from asyncio import (Queue, Task, create_task, QueueShutDown, sleep,
                     get_event_loop, CancelledError)
from itertools import count
from logging import Logger, getLogger
from typing import Any, Optional, Tuple, Awaitable

from .error import ExecutorAlreadyStarted, ExecutorNotStarted
from .field_descriptor import FieldDescriptor
from .logging_config import VERBOSE
from .predicate import ReactionCoroutine, Reaction


__all__ = ['ReactionExecutor']


logger: Logger = getLogger('reactions.executor')

class ReactionExecutor:
    '''
    ReactionExecutor executes ReactionCoroutines sequentially but
    asynchronously (the submitter is not blocked). Submitters are typically
    Predicates.

    ReactionExecutor has a queue and a task. The queue contains the coroutines
    for the reactions to execute, while the task drains the queue and executes
    the coroutines sequentially.

    It provides concurrency control. The executor processes the reactions in
    the order they are submitted sequentially. The reactions are run
    asynchronously with respect to what is being reacted to, but synchronously
    with respect to the other reactions in the queue.

    Reactions that need to run concurrently with other reactions may create
    Tasks or callbacks to perform their work asynchronously with
    respect to this executor. While possible, it is recommended to not submit
    reactions to the executor directly, but rather incorporate this into the
    Field state and use the predicate facility to create reactions. No
    management of tasks created by reactions is provided.
    '''

    task: Optional[Task] = None
    '''the task that is processing the queue to execute reactions'''

    queue: Queue[Tuple[int, ReactionCoroutine, Any]]
    '''
    The queue of reactions to execute.
    Tuple elements are:
        [0] - the id of the reaction (for logging)
        [1] - the coroutine that implements the reaction (*not* the coroutine
              function, but the coroutine the function returns)
        [2] - the args (used only for logging)
    '''

    _ids: count = count()
    '''
    _ids assigns a unique id to each reaction handled by the executor. It is
    used only for informational purposes, but this may change if there is a
    need. It is a class member, not instance, so reaction ids are unique within
    a process. Log messages should include the assigned id to aid in log
    analysis.
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    def react[T](self,
                 reaction: Reaction,
                 instance,
                 field: FieldDescriptor[T],
                 old: T, new: T) -> None:
        '''reaction that asynchronously executes the reaction'''

        assert self.task, "ReactionExecutor not start()'ed"

        id_ = next(self._ids)

        reaction_coroutine = reaction(instance, field, old, new)
        self.queue.put_nowait((id_, reaction_coroutine, (field, old, new)))
        logger.log(VERBOSE, '%d scheduled %s(..., %s,  %s)',
                   id_, reaction.__qualname__, old, new)

    ###########################################################################
    # Task life cycle:
    #
    # Task completion is asynchronous to allow scheduled reactions to execute.
    # A clean shutdown is performed by stop() calling the shutdown() method on
    # the queue to stop accepting reactions. When the queue is empty the
    # reaction_executor() loop receives a QueueShutDown error and returns. The
    # task is the awaitable provided for awaiting completion so tasks waiting
    # will unblock.
    # However, to ensure a timely shutdown stop() has a default timeout= kwarg
    # that specifies the amount of time to wait for a clean shutdown. If the
    # task has not completed after that timeout a callback created by stop()
    # executes to call cancel() on the task, causing the coroutine being
    # executed by the task to receive a CancelledError. This error is raised
    # to the task and will be presented to waiters.
    # For completeness, all other error raised by a reaction are also raised
    # to the task and raised to waiters.
    ###########################################################################

    def start(self) -> Awaitable:
        '''start the task to execute the queued reactions'''
        if self.task is not None:
            raise ExecutorAlreadyStarted()
        self.task = create_task(self.execute_reactions())
        return self.task

    def stop(self, timeout: Optional[float] = 2):
        '''stop the reaction queue with timeout (defaults to 2 seconds)'''
        if not self.task:
            raise ExecutorNotStarted()

        logger.debug('%s stopping.', self)

        self.queue.shutdown()

        # Create a callback to cancel the task if a timeout is specified.
        if timeout is not None:
            def _cancel_task():
                if not self.task.done():
                    logger.error('%s cancelled after shutdown '
                                 'took more than %.2fs', self, timeout)
                    self.task.cancel()
            get_event_loop().call_later(timeout, _cancel_task)

    async def execute_reactions(self) -> None:
        '''
        Queue worker that gets pending tasks from the queue and executes
        them.

        The pending tasks are processed synchronously.
        '''
        while True:
            try:
                # todo - use template string for id, args, other logging only
                #        info.
                (id_, coroutine, args) = await self.queue.get()
            except QueueShutDown:
                logger.info('%s stopped', self)
                break

            try:
                logger.debug('%s %s calling %s(%s)',
                             self, id_, coroutine.__qualname__, str(args))
                await coroutine
                await sleep(0)
            except CancelledError as ce:
                logger.exception('%s cancelled.', self, exc_info=ce)
                raise  # CancelledError needs to be propagated
            except Exception as exc:
                # A failure in a reaction means the state is inconsistent.
                # Log the executor is stopped and raise the error to allow
                # waiters to see it.
                logger.exception('%s stopping on error.', self, exc_info=exc)
                raise
            finally:
                self.queue.task_done()

    def __await__(self):
        '''wait for the task to complete'''
        if not self.task:
            raise ExecutorNotStarted()
        yield from self.task
