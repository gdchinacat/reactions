'''
State machine test.
'''
from __future__ import annotations

from asyncio import Future
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional, AsyncIterator, Tuple
from unittest import TestCase, main

from .. import (ReactionMustNotBeCalled, ExecutorAlreadyComplete,
                 ExecutorAlreadyStarted, Field, Reactant)
from .async_helpers import asynctest


@dataclass
class State(Reactant):
    '''
    Kitchen sink state machine for testing various aspects of State.
    '''

    exception: Field[State, Optional[Exception]] = Field()
    infinite_loop: Field[State, bool] = Field(False)
    infinite_loop_running: Optional[Future[None]] = None
    
    def _start(self) -> None:
        pass

    @ exception != None
    async def _exception(self,
             field: Field[State, int],
             old: int, new:int) -> None:  # @UnusedVariable
        '''raise an exception'''
        raise self.exception

    @ infinite_loop == True
    async def _infinite_interuptable_loop(self,
             field: Field[State, int],
             old: int, new:int) -> None:  # @UnusedVariable
        '''enter an infinite loop. Currently no way to exit it.'''
        assert self.infinite_loop_running is not None
        self.infinite_loop_running.set_result(None)
        while True:
            await asyncio.sleep(1)


@asynccontextmanager
async def running_state(skip_stop=False,
                        skip_await=False,
                        *args, **kwargs
                        ) -> AsyncIterator[Tuple[State, Future]]:
    '''
    Async contexst manager to run the state before managed block and wait
    for it after the block. Context is the state.
    async with running_state() as state:
    '''
    state = State()
    future = state.start()
    try:
        yield state, future
    finally:
        if not skip_stop:
            state.stop()
        if not skip_await:
            await future


class ReactorBaseTest(TestCase):

    @asynctest
    async def test_reaction_exception_terminates_reactor(self):
        class _Exception(Exception): ...
        state = State()
        future = state.start()

        state.exception = _Exception()
        with self.assertRaises(_Exception):
            await future

    @asynctest
    async def test_already_started(self):
        async with running_state() as (state, _):
            # trying to start it a second time raises error
            with self.assertRaises(ExecutorAlreadyStarted):
                state.start()

    @asynctest
    async def test_stop(self):
        async with running_state(skip_stop=True,
                                 skip_await=True) as (state, future):
            state.stop()

            # trying to stop it a second time raises error
            with self.assertRaises(ExecutorAlreadyComplete):
                state.stop()
            await future

    @asynctest
    async def test_calling_reaction_not_allowed(self):
        async with running_state() as (state, _):
            with self.assertRaises(ReactionMustNotBeCalled):
                state._exception()

    @asynctest
    async def test_reaction_infinite_interruptable_loop(self):
        async with running_state(skip_stop=True) as (state, complete):
            state.infinite_loop_running = Future()
            state.infinite_loop = True
            await asyncio.sleep(0)  # yield so reaction can run
            await state.infinite_loop_running
            state.stop()
            await complete

    def test_defined_state_fields_are_named(self):
        self.assertEqual('State', State.exception.classname)
        self.assertEqual('exception', State.exception.attr)

    def test_added_fields_are_named(self):
        '''fields added to a Reactant subclass after definition are named'''
        obj = object()
        State.foo = Field(obj)
        try:
            # test that it got named properly
            self.assertEqual("State", State.foo.classname)
            self.assertEqual("foo", State.foo.attr)

            # And that it functions as a field.
            state = State()
            self.assertIs(obj, state.foo)
        finally:
            del State.foo


if __name__ == "__main__":
    main()
