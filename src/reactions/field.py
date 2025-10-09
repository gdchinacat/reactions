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
The public facing Field implementation.
'''

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from asyncio import run
from dataclasses import dataclass, field
from logging import getLogger
from typing import NoReturn, Any, Tuple, Awaitable

from .executor import ReactionExecutor
from .field_descriptor import FieldDescriptor
from .predicate import Predicate
from .predicate_types import And, Or, Eq, Ne, Lt, Le, Gt, Ge


__all__ = ['Field', 'FieldManager', 'FieldWatcher']


logger = getLogger('reactions.field')

class Field[T](FieldDescriptor[T]):
    '''
    Field subclass that creates predicates from rich comparison methods.
    '''

    def __hash__(self):
        '''make Field hashable/immutable'''
        return id(self)

    ###########################################################################
    # Predicate creation operators
    #
    # todo - pylint too-many-function-args is disabled because it doesn't seem
    #        to understand that they are classes.
    # type: ignore[override]
    #       suppress override errors on on __eq__ and __ne__ because the
    #       builtin being overridden returns bool and these do not, so the
    #       error is valid. However, this is what the implementation needs to
    #       so so silence the error.
    ###########################################################################
    # TODO - the returned predicates need to have the type of the field that
    #        created them in their type so that when they are called the type
    #        of field the PredicateReaction accepts will match.
    def __contains__(self, other) -> NoReturn:
        '''not implemented'''
        raise NotImplementedError('use Contains(self, other) instead')

    def __and__(self, other) -> Predicate:  # todo should be And (below too)
        '''create an And (&) predicate for the field'''
        return And(self, other)  # pylint: disable=too-many-function-args

    def __or__(self, other) -> Predicate:
        '''create an Or (|) predicate for the field'''
        return Or(self, other)  # pylint: disable=too-many-function-args

    def __eq__(self, other) -> Predicate:  # type: ignore[override]
        '''create an Eq (==) predicate for the field'''
        return Eq(self, other)  # pylint: disable=too-many-function-args

    def __ne__(self, other) -> Predicate:  # type: ignore[override]
        '''create an Eq predicate for the field'''
        return Ne(self, other)  # pylint: disable=too-many-function-args

    def __lt__(self, other) -> Predicate:
        '''create an Lt (<) predicate for the field'''
        return Lt(self, other)  # pylint: disable=too-many-function-args

    def __le__(self, other) -> Predicate:
        '''create an Le (<=) predicate for the field'''
        return Le(self, other)  # pylint: disable=too-many-function-args

    def __gt__(self, other) -> Predicate:
        '''create an Gt (>) predicate for the field'''
        return Gt(self, other)  # pylint: disable=too-many-function-args

    def __ge__(self, other) -> Predicate:
        '''create an Ge (>=) predicate for the field'''
        return Ge(self, other)  # pylint: disable=too-many-function-args

    def __getitem__(self, instance):
        '''
        Get/create/set a Field specific to the instance.

        This allows reations specific to the instance. For example:
        (Watched.field[state] >= 5)(watcher.watch_field)
        '''
        # How this works:
        # When an instance is created it does not have instance specific Field
        # attributes, rather they are inherited from the class. There is no
        # reason to have them until an instance specific field is requested by
        # indexing the class Field with the instance as the index (this method)
        # is invoked. When that happens, if the instance does not already have
        # an instance specific field, one is created and set on the instance.
        # This instance field has a reference to the class fields reactions.
        # At this point this __getitem__ method is complete.
        # Later, when the instance field is used to create a predicate the
        # reaction is configured with the field.  When reactions are configured
        # on instance fields if the reactions is the class reactions the list
        # is copied and the reaction appended. This places the instance
        # specific reaction on an attribute of the instance rather than a class
        # field so the reaction will apply only to that instance and does not
        # need cleanup or have an impact on the performance of the class level
        # fields used by other instances.
        
        
        return Field(
            self, self.initial_value, self.attr, self.classname, instance)


class FieldManagerMetaDict(dict[str, Any]):
    '''
    A dict that is used by FieldManagerMeta for class creation. It names Field
    members and tracks them in a list of the class.

    A _fields member is added to the class. It is a tuple of Field attributes
    the class has. It is used to track which fields need to be bound on
    instance creation. It is a tuple to discourage modification.
    '''

    def __init__(self, classname: str):
        self.classname = classname
        self['_fields'] = tuple[FieldDescriptor]()

    def __setitem__(self, attr: str, value: Any)->None:
        if isinstance(value, FieldDescriptor):
            value.set_names(self.classname, attr)
            self['_fields'] = self['_fields'] + (value,)
        super().__setitem__(attr, value)


class FieldManagerMeta(ABCMeta, type):
    '''
    Metaclass to manage the Field members of classes.

    Field naming:
    Class members that are Fields will be named during class definition. This
    makes the Field definition much more concise as it doesn't need to take the
    class and attr names. (__prepare__)
    When a Field attribute is set on the class after definition it will be
    named. (__setattr__)

    Class creation:
    BoundFields will be created for Fields during class creation. (__new__)
    '''

    # _fields is initialized by FieldManagerMetaDict.__init__() since it needs
    # to be present during the nascent stages before __init__ is called to
    # initialize the instance.
    _fields: Tuple[FieldDescriptor, ...]

    @classmethod
    def __prepare__(cls, name, bases):
        return FieldManagerMetaDict(name)

    def __setattr__(self, attr: str, value: Any):
        '''
        Intercept calls to name Field attributes that are set on the class.
        '''
        if isinstance(value, FieldDescriptor):
            value.set_names(self.__qualname__, attr)
            self._fields = self._fields + (value,)
        super().__setattr__(attr, value)

    def __new__(cls, name, bases, namespace):
        '''Create a new instance of a class managed by FieldManagerMeta.'''
        if BoundFieldCreatorMixin not in bases:
            bases = bases + (BoundFieldCreatorMixin,)
        ret = super().__new__(cls, name, bases, namespace)
        return ret

class BoundFieldCreatorMixin:
    '''
    Mixin to create bound fields during class initialization.

    Not intended to be used directly. Classes should use the FieldManagerMeta
    which will insert this into the bases if needed.
    '''
    def __new__(cls, *_):
        nascent = super().__new__(cls)
        for field in nascent._fields:
            field._bind(nascent)
        return nascent

@dataclass
class Reactant(): # todo metaclass=FieldManagerMeta):
    '''
    Base class that allows classes to react asynchronously to predicates that
    become true. Not intended for direct use by client code, FieldManager and
    FieldWatcher should be used instead.

    Usage:
    class Counter(Reactant):
        """A counter that spins until stopped"""
        count: Field[Counter, int] = Field(-1)

        @ count != -1
        async defcounter(self, bound_field: BoundField[Counter, int],
                 old: int, new: int) -> None:
            self.count += 1

        def _start(self):
            'transition from initial state, called during start()'
            self.count = 0

    async def run_counter_for_awhile():
        counter = Counter()
        counter_task = asyncio.create_task(counter.start())
        ....
        counter.stop()
        await counter_task

    Reactions are called asynchronously in the Reactant's reaction executor.
    '''
    # todo - a reaction_executor for instances introduces an ambiguity of
    #        which instances executor predicate reactions will be executed
    #        in, meaning it actually *is* possible for reactions to do dirty
    #        reads if a predicate contains multiple reaction executors.
    #        Fix this by defining a better executor management strategy.
    #          - global - yuck,  this would have the effect of serializaiong
    #                     all reactions. This isn't good because two
    #                     independent state instances should be able to execute
    #                     reinvent a GIL. Unrelated states should be able to
    #                     execute asynchronously.
    #          - specify it for every instance created - yuck...a goal is to
    #            make it so users don't have to think about how to schedule
    #            reactions.
    #          - Specify on the predicate, with a lambda? that is called when
    #            the predicate is true with itself (for fields) that provides
    #            an executor that the predicate should execute in.
    #          - don't allow ambiguous predicates...if the instances the
    #            predicates are using have different reaction executors raise
    #            an error
    #          - unfortunately the mechanism to get instances other than bound
    #            field isn't complete yet and sorting it out will likely
    #            provide structure (ie watcher = Watcher(watched)) to associate
    #            instances with each other (1:1 seems a bit restrictuve, need
    #            a mapping for each end that isn't 1 to or to 1. Performance?
    #            Ramble Ramble Ramble: using metaclasses to hook into instance
    #            creation/initialization seems like the most promising route.
    #            The problem is the instance a reaction is called on is
    #            currently acquired from the BoundField that had a field
    #            change. This works fine for reactions that listen on their
    #            own classes fields (including base class fields). But
    #            reactions on other classes will invoke the reaction with the
    #            other class as 'self', or at least the only instance
    #            available.
    #                - @(Foo.foo == 1) on Bar.foo_eq_one(): The method on Bar
    #                  will not get a reference to an Bar instance.A
    #                  ??? create Foo: Watched with reference to Bar: yuck, it
    #                      is totally backwards and there are multiple
    #                      for different Fields.
    #                  ??? give predicate a resolver to push back to user
    #                  ??? Factory method to create a new Watcher from a 
    #                      Watched.
    #                  ??? asyncio Context? 
    _reaction_executor: ReactionExecutor = field(
        default_factory=ReactionExecutor, kw_only=True,
        doc=
        '''
        The ReactionExecutor that predicates will use to execute reactions.
        ''')

    @abstractmethod
    def _start(self) -> None:
        '''
        Subclasses must implement this to start the state machine execution.
        '''

    async def start(self) -> Awaitable:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state. If an exception
         caused termination of the state it is available as the futures
         exception.
         '''
        self._reaction_executor.start()
        self._start()
        return self._reaction_executor

    def run(self)->None:
        '''run and wait until complete'''
        async def _run():
            awaitable = await self.start()
            await awaitable
        run(_run())

    def stop(self, timeout: float|None=2) -> None:
        '''
        stop the state processing.
        Args:
            timeout - time in seconds to wait for the shutdown to complete
                      normally before canceling the task.
        '''
        self._reaction_executor.stop(timeout)

    async def astop(self, *_) -> None:
        '''
        Async stop:
        (done == True)(Reactant.astop)
        '''
        self.stop()

    def cancel(self) -> None:
        self.stop(0)


class FieldManager(Reactant, metaclass=FieldManagerMeta):
    '''
    Base class for classes with Field attributes.

    Provides management of fields (naming, bound field creation).
    '''


@dataclass
class FieldWatcher(Reactant):
    '''
    Base class to allow subclasses to watch Fields on other classes.

    This associates specific instances of other classes with this class so that
    the reactions are routed to the proper instance.
    '''
    
    watch: Tuple[Any]
    '''The set of instances being watched.'''

    def __post_init__(self):
        logger.error(f'todo - add bound predicates on {self.watch} for {self}')