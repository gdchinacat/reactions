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
from .predicate import ReactionCoroutine, PredicateReaction


__all__ = ['ReactionExecutor']


logger: Logger = getLogger('reactions.executor')

# TODO - ReactionExecutor and Reactant are very tightly coupled and should be
#        better encapsulated. The done-ness of the Reactant is entirely
#        controlled by ReactionExecutor.complete, which shadows the task
#        future and may be able to be cleaned up. This may remove the need for
#        the task done callbacks. Executor and Reactant are separate entities
#        to allow reactants to share executors to provide concurrency control.
class ReactionExecutor:
    '''
    ReactionExecutor executes reactions submitted by Reactants. It is separate
    from Reactant to allow multiple reactants to share the same executor to
    allow the executor to act as a means of providing other reactions
    consistent views of the fields managed by the executor.
    todo - figure out exactly how this management happens). 
    todo - move start/stop from Reactant? Force users to manage
           ReactionExecutors? Part of cleaning up the tight coupling.

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

    queue: Queue[Tuple[int, Any, ReactionCoroutine, Any]]
    '''
    The queue of reactions to execute.
    TODO - The Tuple has grown to the point an actual class makes sense.
           Initially the queue only contained the coroutine and was 'fast' in
           that scheduling and executing a reaction didn't require creation of
           a wrapper object. But, that is no longer the case...the tuple has to
           be created, so it might as well just be a custom object that is
           readable.
    Tuple elements are:
        [0] - the id of the reaction (for logging)
        [1] - the instance the reaction is called on
              (todo - is actually the instance of the field that changed)
              stop() is called on this if the reaction raises an exception
        [2] - the coroutine that implements the reaction (*not* the coroutine
              function, but the coroutine the function returns)
        [3] - the args (used only for logging)
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
                 reaction: PredicateReaction,
                 instance,
                 # TODO - should be the instance of the class that defined the reaction, not the instance of the class that field change triggered reaction
                 field: FieldDescriptor[T],
                 old: T, new: T) -> None:
        '''reaction that asynchronously executes the reaction'''

        assert self.task, "ReactionExecutor not start()'ed"

        id_ = next(self._ids)

        try:
            coro = reaction(instance, field, old, new)
            self.queue.put_nowait((id_,
                                   instance,
                                   coro,
                                   (field, old, new)))
            logger.log(VERBOSE,
                '%d scheduled %s(..., %s,  %s)',
                id_, reaction.__qualname__, old, new)
        except Exception:
            logger.exception(
                '%d failed to schedule %s (..., %s,  %s)',
                id_, reaction.__qualname__, old, new)
            raise

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
        ## todo major hack till reaction executors are plumbed where they needed
        from . import predicate
        predicate.reaction_executor = self
        ##
        if self.task is not None:
            raise ExecutorAlreadyStarted()
        self.task = create_task(self.execute_reactions())
        return self.task

    def stop(self, timeout: Optional[float] = 2):
        '''stop the reaction queue with timeout (defaults to 2 seconds)'''
        if not self.task:
            raise ExecutorNotStarted()

        logger.debug(f'{self} stopping.')

        ## todo major hack till reaction executors are plumbed where they needed
        from . import predicate
        predicate.reaction_executor = None
        ##

        self.queue.shutdown()

        # Create a callback to cancel the task if a timeout is specified.
        if timeout is not None:
            loop = get_event_loop()
            if timeout is not None:
                def _cancel_task():
                    if not self.task.done():
                        logger.error(f'{self} cancelled after shutdown '
                                     f'took more than {timeout}s')
                        self.task.cancel()
                loop.call_later(timeout, _cancel_task)

    async def execute_reactions(self) -> None:
        '''
        Queue worker that gets pending tasks from the queue and executes
        them.

        The pending tasks are processed synchronously.
        '''
        while True:
            try:
                # TODO - get rid of everything but the coro:
                #        id_ and args are only for "calling" log
                #            replace with fmt string that the various logs for
                #            a specific reaction pass around and things fill
                #            in the action pertaining to the reaction:
                #        instance only used to get the logger
                #    Maybe the solution is to enable a debug mode that passes
                #    the details for logging and when not in debug it passes
                #    the coro instead of everything. Maye have different
                #    executor classes that can be chosen (i.e. "give me speed"
                #    vs "give me insight").
                (id_, instance, coro, args) = await self.queue.get()
            except QueueShutDown:
                logger.info(f'{self} stopped')
                break

            try:
                logger.debug(f'%s calling %s(%s)',
                    id_, coro.__qualname__, str(args))
                await coro
                await sleep(0)
            except CancelledError as ce:
                logger.exception(f'{self} stopped with error.', exc_info=ce)
                raise  # CancelledError needs to be propagated
            except Exception as exc:
                # A failure in a reaction means the state is inconsistent.
                # Log the executor is stopped and raise the error to allow
                # waiters to see it.
                logger.exception(f'{self} stopped with error.', exc_info=exc)
                raise
            finally:
                self.queue.task_done()

    def __await__(self):
        '''wait for the task kto complete'''
        if not self.task:
            raise ExecutorNotStarted()
        yield from self.task
