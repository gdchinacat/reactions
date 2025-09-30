from __future__ import annotations

from asyncio import Future
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from threading import Event, Thread
from time import sleep
from typing import Optional, AsyncIterator, Tuple
from unittest import TestCase, main

from chinacat.whenstate.error import ReactionMustNotBeCalled, \
    StateAlreadyComplete, StateAlreadyStarted

from .. import BoundField, Field, State


@dataclass
class _State(State):
    '''
    Kitchen sink state machine for testing various aspects of State.
    '''

    exception: Field[_State, Optional[Exception]] = Field()
    infinite_loop: Field[_State, bool] = Field(False)
    infinite_loop_running: Event = Event()
    
    def _start(self) -> None:
        pass

    @State.when(exception != None)
    def _exception(self,
             bound_field: BoundField[_State, int],
             old: int, new:int) -> None:  # @UnusedVariable
        '''raise an exception'''
        raise self.exception

    @State.when(infinite_loop == True)
    def _infinite_loop(self,
             bound_field: BoundField[_State, int],
             old: int, new:int) -> None:  # @UnusedVariable
        '''enter an infinite loop. Currently no way to exit it.'''
        assert self.infinite_loop_running is not None
        self.infinite_loop_running.set()
        while True:
            sleep(1)

def asynctest(func):
    '''decorator to execute async test functions'''
    @wraps(func)
    def _asynctest(*args, **kwargs):
        @wraps(func)
        async def async_test_runner():
            async with asyncio.timeout(1):
                await func(*args, **kwargs)
        asyncio.run(async_test_runner())
    return _asynctest


@asynccontextmanager
async def running_state(skip_stop=False,
                        skip_await=False,
                        *args, **kwargs
                        ) -> AsyncIterator[Tuple[_State, Future]]:
    '''
    Async contexst manager to run the state before managed block and wait
    for it after the block. Context is the state.
    async with running_state() as state:
    '''
    state = _State()
    future = state.start()
    try:
        yield state, future
    finally:
        if not skip_stop:
            state.stop()
        if not skip_await:
            await future


class StateTest(TestCase):

    @asynctest
    async def test_reaction_exception_terminates_state(self):
        class _Exception(Exception): ...
        state = _State()
        future = state.start()

        state.exception = _Exception()
        with self.assertRaises(_Exception):
            await future

    @asynctest
    async def test_already_started(self):
        async with running_state() as (state, _):
            # trying to start it a second time raises error
            with self.assertRaises(StateAlreadyStarted):
                state.start()

    @asynctest
    async def test_stop(self):
        async with running_state(skip_stop=True,
                                 skip_await=True) as (state, future):
            state.stop()

            # trying to stop it a second time raises error
            with self.assertRaises(StateAlreadyComplete):
                state.stop()
            await future

    @asynctest
    async def test_calling_reaction_not_allowed(self):
        async with running_state() as (state, _):
            with self.assertRaises(ReactionMustNotBeCalled):
                state._exception()

    @asynctest
    async def _test_reaction_infinite_loop(self):
        # NOTE - there isn't really a way to interrupt a thread that isn't
        #        allowing itself to be interrupted so this test is disabled.
        async with running_state(skip_stop=True) as (state, _):
            def stop():
                state.infinite_loop_running.wait()
                state.stop()
            stop_thread = Thread(target=stop)
            stop_thread.start()

            state.infinite_loop = True
            await asyncio.sleep(0)  # yield so reaction can run

            stop_thread.join(1)


if __name__ == "__main__":
    main()
