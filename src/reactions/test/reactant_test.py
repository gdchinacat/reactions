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
State machine test.
'''

from __future__ import annotations

from asyncio import Future, CancelledError, sleep, Barrier
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import NoneType
from typing import NoReturn
from unittest import TestCase, main

from .. import (ReactionMustNotBeCalled, ExecutorAlreadyStarted, Field,
                ReactionExecutor, FieldManager, FieldChange)
from .async_helpers import asynctest


class State(FieldManager):
    '''
    Kitchen sink state machine for testing various aspects of State.
    '''

    exception = Field[Exception|None](None)
    infinite_loop = Field(False)

    infinite_loop_running: Future[None]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.infinite_loop_running = Future()

    def _start(self) -> None:
        pass

    @ exception != None
    async def exception_(self, change: FieldChange[State, Exception]) -> None:
        '''raise an exception'''
        if change.new is not None:
            raise change.new

    @ infinite_loop == True
    async def _infinite_interuptable_loop(self,
                                          change: FieldChange[State, int]
                                          ) -> NoReturn:
        '''enter an infinite loop. Currently no way to exit it.'''
        assert self.infinite_loop_running is not None
        self.infinite_loop_running.set_result(None)
        while True:
            await sleep(1)


@asynccontextmanager
async def running_state(skip_stop: bool = False,
                        skip_await: bool = False,
                        ) -> AsyncIterator[tuple[State, ReactionExecutor]]:
    '''
    Async contexst manager to run the state before managed block and wait
    for it after the block. Context is (state, state_done_awaitable).
    async with running_state() as state:
    '''
    executor = ReactionExecutor()
    state = State(executor=executor)
    executor.start()
    try:
        yield state, executor
    finally:
        if not skip_stop:
            executor.stop()
        if not skip_await:
            await executor


class ReactantTest(TestCase):

    @asynctest
    async def test_reaction_exception_terminates_reactor(self) -> None:
        class _Exception(Exception): ...
        async with running_state(skip_await=True) as (state, executor):
            state.exception = _Exception()
            with self.assertRaises(_Exception):
                await executor

    @asynctest
    async def test_already_started(self) -> None:
        async with running_state() as (_, executor):
            # trying to start it a second time raises error
            with self.assertRaises(ExecutorAlreadyStarted):
                executor.start()

    @asynctest
    async def test_stop(self) -> None:
        '''test that stop can be called multiple times in various states'''
        async with running_state(skip_stop=True,
                                 skip_await=True) as (_, executor):
            executor.stop()
            executor.stop()  # a second is fine since it hasn't stopped yet

            # Wait for the future to actually complete.
            await executor

            # It is still ok to call stop()
            executor.stop()

    @asynctest
    async def test_calling_reaction_not_allowed(self) -> None:
        async with running_state() as (state, _):
            with self.assertRaises(ReactionMustNotBeCalled):
                state.exception_()

    @asynctest
    async def test_reaction_infinite_interruptable_loop(self) -> None:
        async with running_state(skip_stop=True,
                                 skip_await=True) as (state, executor):
            state.infinite_loop = True
            await sleep(0)
            await state.infinite_loop_running
            executor.stop(.1)
            with self.assertRaises(CancelledError):
                await executor

    def test_defined_state_fields_are_named(self) -> None:
        self.assertEqual('State', State.exception.classname)
        self.assertEqual('exception', State.exception.attr)

    @asynctest  # not really necessary but for State.inifinite_loop needing it
    async def test_added_fields_are_named(self) -> None:
        '''fields added to a Reactant subclass after definition are named'''
        obj = object()
        class _State(State):
            foo: Field[object]
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

    @asynctest
    async def test_private_executors(self) -> None:
        '''test that each Reactant has its own executor'''

        # Have reactions on state instances with different reaction executors
        # wait on a barrier
        barrier = Barrier(2)
        class State(FieldManager):
            field = Field(False)
            @ field  == True
            async def field_(self, *_: object) -> None:
                await barrier.wait()
            def _start(self) -> None: ...

        state1, state2 = State(), State()

        async with (state1 as executor1,
                    state2 as executor2):
            self.assertIsNot(executor1, executor2)
            # Since both states are waiting on the barrier, that will only
            # happen if they execute in separate executors.
            state1.field = True
            state2.field = True
        self.assertEqual(0, barrier.n_waiting)


if __name__ == "__main__":
    main()
