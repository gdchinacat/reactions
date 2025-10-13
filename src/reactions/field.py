# Copyright (C) 2025 Anthony (Lonnie) Hutchinson <chinacat@chinacat.org>

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

from abc import ABCMeta, abstractmethod, ABC
from asyncio import run
from dataclasses import dataclass, field
from logging import getLogger
from types import MethodType
from typing import Any, Tuple, Awaitable, Set, overload, NoReturn

from .error import FieldAlreadyBound
from .executor import ReactionExecutor
from .field_descriptor import FieldDescriptor, FieldReaction, Evaluatable
from .predicate import (_Reaction, CustomFieldReactionConfiguration,
                        BoundReaction)
from .predicate_types import ComparisonPredicates


__all__ = ['Field', 'FieldManager', 'FieldWatcher']


logger = getLogger('reactions.field')


class BoundField[T](Evaluatable[T], ComparisonPredicates):
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

        # reactions is the list of reactions to call. Initialixe as a reference
        # to the Field creactions. A copy is made when any instance reactions
        # are configured.
        self.reactions = field.reactions

    def reaction(self, reaction: FieldReaction):
        '''Add a reaction for when this bound field changes value.'''
        # ensure the bound field is using a private reactions list
        if self.reactions is self.field.reactions:
            self.reactions = list(self.field.reactions)

        self.reactions.append(reaction)

    def react(self, instance:Any, field:FieldDescriptor[T],
              old:T, new:T):
        """React to field change events by dispatching them to the reactions"""
        for reaction in self.reactions:
            reaction(instance, field, old, new)

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
    Field provides attribute change notification and predicates to configure
    asynchronous callbacks when the condition becomes true.

    class State:
        field = Field(0)

        @ field >= 0
        async def count(self, *):
        self.field += 1

    An attribute may need to be a Field to use it in predicates even if the
    value is never changed after instances are initialized. This is necessary
    because the predicates are defined when the class is defined and whatever
    value it has at that point will be used as a constant by the predicate. In
    order to evaluate the instance value it should be made a Field.
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
    bound_field = __getitem__

    def _bind(self, nascent_instance)->None:
        '''
        Create a BoundField on instance.
        nascent_instance:
            the state instance that reactions are called on
            (reaction(self, ...))

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
        raise NotImplementedError('reactions should be on bound field')


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
        call set_names() on Field attributes
        '''
        if isinstance(value, Field):
            value.set_names(self.__qualname__, attr)
            self._fields = self._fields + (value,)  # pylint: disable=no-member
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
    def __new__(cls, *_, **__):
        nascent = super().__new__(cls)
        for field_ in nascent._fields:
            field_._bind(nascent)
        return nascent

@dataclass
class Reactant():
    '''
    Mixin to give a class a reaction executor and methods to manage its
    lifecycle.

    Not intended for direct use by client code, FieldManager and
    FieldWatcher should be used instead.

    Reactants are asynchronous context managers that start on enter and stop
    on exit.
    '''
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

    async def __aenter__(self)->Awaitable:
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        await self._reaction_executor



class FieldManager(Reactant, ABC, metaclass=FieldManagerMeta):
    '''
    Base class for classes with Field attributes.

    Provides management of fields (naming, bound field creation).
    '''


class FieldWatcher[T: FieldManager](Reactant,
                                    CustomFieldReactionConfiguration,
                                    ABC):
    '''
    Base class to allow subclasses to watch Fields on other classes.

    This associates specific instances of other classes with this class so that
    the reactions are routed to the proper instance.

    Usage:
            @ Watched.field == True
            @ FieldWatcher
            async def reaction(...
    '''

    watched: T
    '''The instance being watched.'''

    _reactions: Set[_Reaction]
    '''
    The reactions the class needs to register bound reactions for when
    instances are initialized.
    '''

    @overload
    def __init__(self, reaction_or_watched: BoundReaction): ...

    @overload
    def __init__(self,
                  reaction_or_watched: Any,
                  *args,
                 _reaction_executor=None,
                 **kwargs): ...

    def __init__(self,
                 reaction_or_watched: BoundReaction|Any,
                 *args,
                 _reaction_executor=None,
                 **kwargs):
        '''
        Create a FieldWatcher or decorate a BoundReaction managed by
        FieldWatcher.
        '''
        if callable(reaction_or_watched):
            '''
            Wrap the reaction so that it will not have instance field reactions
            configured for it. It will be tracked as a reaction in _reactions
            so that __init_subclass__ can configure the for the specific
            instance. Strictly speaking CustomFieldReactionConfiguration could
            be used instead of this, but doing so is not nearly as
            understandable as this.
            '''
            CustomFieldReactionConfiguration.__init__(
                self, reaction_or_watched, type(self).__init_subclass__)
        else:
            self.watched = reaction_or_watched
            executor = _reaction_executor or self.watched._reaction_executor
            Reactant.__init__(
                self, *args, _reaction_executor=executor, **kwargs)

            # Configure the bound reactions.
            for reaction in self._reactions:
                reaction.predicate.configure_reaction(
                    MethodType(reaction.func, self), self.watched)

    @classmethod
    def __init_subclass__(cls)->None:
        '''Initialize the reactions for the class.'''
        super().__init_subclass__()

        cls._reactions = set(value for value in cls.__dict__.values()
                             if isinstance(value, _Reaction))
        logger.info('%s has bound reactions: %s', cls, cls._reactions)

    def _start(self):
        '''
        FieldWatcher implementations typically don't have a start action since
        they use the watched reaction executor. This is implemented as a no op
        so subclasses don't have to implement this method.
        '''

    def __replace__(self, *args, **kwargs)->NoReturn:
        # Base classes both implement __replace__, Until there is an actual
        # need for this functionality it is not implemented.
        raise NotImplementedError()
