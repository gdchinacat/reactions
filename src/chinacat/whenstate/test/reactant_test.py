'''
State machine test.
'''
from __future__ import annotations

from asyncio import Future, CancelledError, sleep
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator, Tuple, Awaitable, Callable
from unittest import TestCase, main

from .. import (ReactionMustNotBeCalled, ExecutorAlreadyComplete,
                 ExecutorAlreadyStarted, Field, Reactant)
from .async_helpers import asynctest


@dataclass
class State(Reactant):
    '''
    Kitchen sink state machine for testing various aspects of State.
    '''

    exception = Field[Optional[Exception]]()
    infinite_loop  = Field[bool](False)
    infinite_loop_running: Future[None] = field(default_factory=Future)
    
    def _start(self) -> None:
        pass

    @ exception != None
    async def _exception(self,
             field: Field[int],
             old: int, new:int) -> None:  # @UnusedVariable
        '''raise an exception'''
        raise self.exception

    @ infinite_loop == True
    async def _infinite_interuptable_loop(self,
             field: Field[int],
             old: int, new:int) -> None:  # @UnusedVariable
        '''enter an infinite loop. Currently no way to exit it.'''
        assert self.infinite_loop_running is not None
        self.infinite_loop_running.set_result(None)
        while True:
            await sleep(1)


@asynccontextmanager
async def running_state(skip_stop=False,
                        skip_await=False,
                        *args, **kwargs
                        ) -> AsyncIterator[Tuple[State, Awaitable]]:
    '''
    Async contexst manager to run the state before managed block and wait
    for it after the block. Context is (state, state_done_awaitable).
    async with running_state() as state:
    '''
    state = State()
    awaitable = state.start()
    try:
        yield state, awaitable
    finally:
        if not skip_stop:
            state.stop()
        if not skip_await:
            await awaitable


class ReactantTest(TestCase):

    @asynctest
    async def test_reaction_exception_terminates_reactor(self):
        class _Exception(Exception): ...
        state = State()
        awaitable = state.start()

        state.exception = _Exception()
        with self.assertRaises(_Exception):
            await awaitable

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
            state.stop()  # a second is fine since it hasn't stopped yet

            # Wait for the future to actually complete.
            await future

            # Stopping it now results in an already complete error.
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
        async with running_state(skip_stop=True,
                                 skip_await=True) as (state, complete):
            state.infinite_loop = True
            await sleep(0)
            await state.infinite_loop_running
            state.stop(.1)
            with self.assertRaises(CancelledError):
                await complete

    def test_defined_state_fields_are_named(self):
        self.assertEqual('State', State.exception.classname)
        self.assertEqual('exception', State.exception.attr)

    @asynctest  # not really necessary but for State.inifinite_loop needing it
    async def test_added_fields_are_named(self):
        '''fields added to a Reactant subclass after definition are named'''
        obj = object()
        class _State(State): ...
        _State.foo = Field(obj)

        # Verify that it got named and tracked properly.
        self.assertEqual(_State.__qualname__, _State.foo.classname)
        self.assertEqual("foo", _State.foo.attr)

        # assertIn() creates an In predicate and fails, check the new field
        # is in the classes list of fields.
        self.assertTrue(any(state is _State.foo
                            for state in  _State._fields))

        # And that it functions as a field.
        state = _State()
        self.assertIs(obj, state.foo)


if __name__ == "__main__":
    main()
