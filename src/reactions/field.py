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
from typing import Any, Tuple, Awaitable

from .error import FieldAlreadyBound
from .executor import ReactionExecutor
from .field_descriptor import (FieldDescriptor, ReactionDispatcher,
                               FieldReaction, Evaluatable)
from .predicate_types import ComparisonPredicates


__all__ = ['Field', 'FieldManager', 'FieldWatcher']


logger = getLogger('reactions.field')


class BoundField[T](ReactionDispatcher[T], Evaluatable[T], ComparisonPredicates):
    '''
    A field bound to a specific instance.

    ALL field state relating to the instance should be on this object so that
    it is collected along with the instance. The Field should have no
    references to any instance specific information.
    '''

    def __init__(self,
                 nascent_instance: Any,
                 field: Field[T],
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field: Field[T] = field
        self.instance = nascent_instance

        # This class is per instance, so it doesn't hurt to store the instance
        # specific data on the bound field, so unlike the class field instance
        # data is stored on the bound field.

        # _reactions is the list of reactions to call when the field changes
        # value. It starts out as a reference to the class reactions. When an
        # instance reaction is configured a copy is made of the class reactions
        # and a private copy for this instance only is created.
        self._reactions = field._reactions

    def reaction(self, reaction: FieldReaction):
        '''Add a reaction for when this bound field changes value.'''
        # ensure the bound field is using a private reactions list
        if self._reactions is self.field._reactions:
            self._reactions = list(self.field._reactions)

        self._reactions.append(reaction)

    def __str__(self):
        return (f'{self.field.classname}({id(self.instance)})'
                f'.{self.field}')
    __repr__ = __str__

    @property
    def fields(self):
        yield self.field

    def evaluate(self, instance:Any)->T:
        return self.field.evaluate(instance)

class Field[T](FieldDescriptor[T], ComparisonPredicates):
    '''
    Field subclass that creates predicates from rich comparison methods.
    '''

    def set_names(self, classname:str, attr:str):
        super().set_names(classname, attr)
        self._attr_bound: str = self._attr + '_bound'   # bound field

    def __hash__(self):
        '''make Field hashable/immutable'''
        return id(self)

    def __getitem__(self, instance):
        '''
        Get/create/set a Field specific to the instance.

        This allows reations specific to the instance. For example:
        (Watched.field[state] >= 5)(watcher.watch_field)
        '''
        return getattr(instance, self._attr_bound)

    def _bind(self, nascent_instance)->None:
        '''
        Create a BoundField on instance.
        nascent_instance:
            the Reactant that reactions are called on (reaction(self, ...))
            todo - saying it this way makes me realize the instance I've
            been struggling with figuring out how to identify is an
            aspect of the field. Specifically, the bound field. It needs
            to associate (field, attribute, old, new) with what object
            is the self for reaction(self, (field, attr,. ..)).

            Beware: field._bind(nascent_instance) called during __new__()
            before it has been initialized (hence its name). While it goes
            without saying that instance attributes not managed by Field,
            FieldManagerMixin, etc should not be acessed since they may not
            exist and if they do the values have not been initialized, what
            isn't so obvious is *do not* call str() or repr() on instance
            as they are likely to fail before the object is initialized.
        '''
        if (hasattr(nascent_instance, self._attr_bound)):
            raise FieldAlreadyBound(
                f'{self} already bound to object '
                f'id(instance)={id(nascent_instance)}')
        bound_field = BoundField[T](nascent_instance, self)
        setattr(nascent_instance, self._attr_bound, bound_field)

    def react(self,
              instance: Any,
              field: FieldDescriptor[T],
              old: T,
              new: T):
        '''
        Notify the reactions that the value changed from old to new.
        Override ReactionDispatcher to dispatch using the bound field.
        '''
        # todo - get rid of the extra call in Field.__set__->Field.react()->BoundField.react()
        assert field is self
        self[instance].react(instance, field, old, new)


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
        self['_fields'] = tuple[Field]()

    def __setitem__(self, attr: str, value: Any)->None:
        if isinstance(value, Field):
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
    _fields: Tuple[Field, ...]

    @classmethod
    def __prepare__(cls, name, bases):
        return FieldManagerMetaDict(name)

    def __setattr__(self, attr: str, value: Any):
        '''
        Intercept calls to name Field attributes that are set on the class.
        '''
        if isinstance(value, Field):
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

    The purpose of this is to ensure that all instances have bound fields for
    all the class Field attributes. This allows reactions to invariably
    dispatch to the bound field rather than having to check if the Field or the 
    bound field should be called.
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
        async defcounter(self, field: Field[int],
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