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

from abc import ABCMeta, abstractmethod, ABC
from asyncio import run
from collections.abc import Awaitable, Iterator, MutableMapping
from logging import getLogger
from types import MethodType, TracebackType, MappingProxyType, NoneType
from typing import overload, NoReturn, cast, Self, Any, Iterable

from .error import FieldAlreadyBound, FieldConfigurationError
from .executor import Executor
from .field_descriptor import (FieldDescriptor, FieldReaction, FieldChange,
                               _BoundField, BoundReaction)
from .predicate import _Reaction, CustomFieldReactionConfiguration
from .predicate_types import ComparisonPredicates
from .predicate_types import Not


__all__ = ['Field', 'FieldManager', 'FieldWatcher']

logger = getLogger()


class BoundField[Ti, Tf](_BoundField[Ti, Tf],
                         ComparisonPredicates[Ti, Tf]):
    '''
    A field bound to a specific instance.

    ALL field state relating to the instance should be on this object so that
    it is collected along with the instance. The Field should have no
    references to any instance specific information.
    '''

    def __init__(self,
                 nascent_instance: Ti,
                 field: Field[Ti, Tf],
                 *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.field = field
        self.instance = nascent_instance

        # reactions is the list of reactions to call. Initialixe as a reference
        # to the Field creactions. A copy is made when any instance reactions
        # are configured.
        self.reactions = field.reactions

    def reaction(self, reaction: FieldReaction[Ti, Tf]) -> None:
        '''Add a reaction for when this bound field changes value.'''
        # ensure the bound field is using a private reactions list
        if self.reactions is self.field.reactions:
            self.reactions = list(self.field.reactions)

        self.reactions.append(reaction)

    def react(self, change: FieldChange[Ti, Tf]) -> None:

        """React to field change events by dispatching them to the reactions"""
        for reaction in self.reactions:
            reaction(change)

    def __str__(self) -> str:
        return (f'{self.field.classname}({id(self.instance)})'
                f'.{self.field.attr}')
    __repr__ = __str__

    @property
    def fields(self) -> Iterator[Field[Ti, Tf]]:
        yield self.field

    def evaluate(self, instance: Ti) -> Tf:
        return self.field.evaluate(instance)

class Field[Ti, Tf](FieldDescriptor[Ti, Tf],
                    ComparisonPredicates[Ti, Tf]):
    '''
    Field provides attribute change notification and predicates to configure
    asynchronous callbacks when the condition becomes true.

    class State:
        field = Field(0)

        @ field >= 0
        async def count(self, *_) -> None:
        self.field += 1

    An attribute may need to be a Field to use it in predicates even if the
    value is never changed after instances are initialized. This is necessary
    because the predicates are defined when the class is defined and whatever
    value it has at that point will be used as a constant by the predicate. In
    order to evaluate the instance value it should be made a Field.
    '''

    def set_names(self, classname:str, attr:str) -> None:
        super().set_names(classname, attr)
        self._attr_bound: str = self._attr + '_bound'   # bound field

    def __hash__(self) -> int:
        '''make Field hashable/immutable'''
        return id(self)

    def bound_field(self, instance: Ti) -> BoundField[Ti, Tf]:
        '''
        Get/create/set a Field specific to the instance.

        This allows reactions specific to the instance. For example:
        (Watched.field[state] >= 5)(watcher.watch_field)
        '''
        bound_field = getattr(instance, self._attr_bound)
        assert isinstance(bound_field, BoundField)
        return bound_field
    __getitem__ = bound_field

    def _bind(self, nascent_instance: Ti) -> BoundField[Ti, Tf]:
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

            Note: nascent_instance is not guaranteed to be nascent since the
            fields for bare classes are bound on access rather than
            instance initialization.
        '''
        if (hasattr(nascent_instance, self._attr_bound)):
            raise FieldAlreadyBound(
                f'{self} already bound to object '
                f'id(instance)={id(nascent_instance)}')
        bound_field = BoundField[Ti, Tf](nascent_instance, self)
        setattr(nascent_instance, self._attr_bound, bound_field)
        return bound_field

    @classmethod
    def validate_fields_against_members(
            cls, namespace: dict[str, object]|MappingProxyType[str, object]
            ) -> None:
        '''
        Check that none of the fields will clobber attributes with their
        implementation attributes.
        Raises FieldConfigurationError if there is a conflict.
        '''
        try:
            fields = namespace['_fields']
        except KeyError:
            # bare class, find fields by iterating contents of class dict
            fields  = [x for x in namespace.values() if isinstance(x, Field)]

        assert isinstance(fields, Iterable), f'fields is a {type(fields)=}'
        attr_field_names = {
            name for field in fields
                 for name in (field._attr, field._attr_bound)}  # pylint: disable=protected-access
        conflicts = attr_field_names & namespace.keys()
        if conflicts:
            raise FieldConfigurationError(
                f'conflicting members: {", ".join(conflicts)}')


class FieldManagerMetaDict(dict[str, object]):
    '''
    A dict that is used by FieldManagerMeta for class creation. It names Field
    members and tracks them in a list of the class.

    A _fields member is added to the class. It is a tuple of Field attributes
    the class has. It is used to track which fields need to be bound on
    instance creation. It is a tuple to discourage modification.
    '''

    def __init__(self, classname: str) -> None:
        self.classname = classname
        self['_fields'] = tuple[tuple[Field[Self, object]]]()

    def __setitem__(self, attr: str, value: object)->None:
        if isinstance(value, Field):
            value.set_names(self.classname, attr)
            self['_fields'] = self['_fields'] + (value,)  # type: ignore 
        super().__setitem__(attr, value)


class FieldManagerMeta[Ti](ABCMeta, type):
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
    _fields: tuple[Field[Ti, object], ...] = tuple()

    @classmethod
    def __prepare__(metacls, name: str, bases: tuple[type, ...], \
                    # pylint: disable=unused-argument
                    /, **kwargs: object
                    ) -> MutableMapping[str, object]:
        return FieldManagerMetaDict(name)

    def __setattr__(self, attr: str, value: object) -> None:
        '''
        call set_names() on Field attributes
        '''
        if isinstance(value, Field):
            value.set_names(self.__qualname__, attr)
            self._fields = self._fields + (value,)
        super().__setattr__(attr, value)

    def __new__[T: type](cls: T,
                         name: str,
                         bases: tuple[type, ...],
                         namespace: dict[str, object]) -> T:
        '''Create a new instance of a class managed by FieldManagerMeta.'''
        Field.validate_fields_against_members(namespace)
        if BoundFieldCreatorMixin not in bases:
            bases = bases + (BoundFieldCreatorMixin,)
        ret: T = super().__new__(cls, name, bases, namespace)
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
    _fields: Iterator[Field[BoundFieldCreatorMixin, object]]  # todo should be the subclass of BFCM

    def __new__(cls, *_: object, **__: object) -> BoundFieldCreatorMixin:
        nascent = super().__new__(cls)
        for field_ in nascent._fields:
            field_._bind(nascent)
        return nascent


class Reactant():
    '''
    Mixin to give a class a reaction executor and methods to manage its
    lifecycle.

    Not intended for direct use by client code, FieldManager and
    FieldWatcher should be used instead.

    Reactants are asynchronous context managers that start on enter and stop
    on exit.
    '''

    executor: Executor
    '''The Executor that predicates will use to execute reactions.'''

    @overload
    def __init__(self,
                 *args: object,
                 executor: Executor|None = None,
                 **kwargs: object): ...
                 
    @overload
    def __init__(self,
                 *args: object,
                 **kwargs: object): ...

    def __init__(self,
                 *args: object,
                 **kwargs: object) -> None:
        executor = kwargs.pop('executor', None)
        assert executor is None or isinstance(executor, Executor)
        self.executor = executor or Executor()
        super().__init__(*args, **kwargs)

    @abstractmethod
    def _start(self) -> None:
        '''
        Subclasses must implement this to start the state machine execution.
        '''

    async def start(self) -> Awaitable[None]:
        '''
         Start processing the state machine. Returns a future that indicates
         when the state machine has entered a terminal state. If an exception
         caused termination of the state it is available as the futures
         exception.
         '''
        self.executor.start()
        self._start()
        return self.executor

    def run(self)->None:
        '''run and wait until complete'''
        async def _run() -> None:
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
        self.executor.stop(timeout)

    async def astop(self, *_: object) -> None:
        '''
        Async stop:
        (done == True)(Reactant.astop)
        '''
        self.stop()

    def cancel(self) -> None:
        self.stop(0)

    async def __aenter__(self)->Awaitable[None]:
        return await self.start()

    async def __aexit__(self,
                        exc_type: type[BaseException]|None,
                        exc_val: BaseException|None,
                        exc_tb: TracebackType|None) -> bool:
        self.stop()
        await self.executor
        return False



class FieldManager(Reactant, ABC, metaclass=FieldManagerMeta):
    '''
    Base class for classes with Field attributes.

    Provides management of fields (naming, bound field creation).
    '''


class FieldWatcher[Ti](Reactant,
                       CustomFieldReactionConfiguration['FieldWatcher[Ti]',
                                                        Ti, Any],
                        ABC):
    '''
    Base class to allow subclasses to watch Fields on other classes.

    This associates specific instances of other classes with this class so that
    the reactions are routed to the proper instance.

    Usage:
        class Watcher(FieldWatcher):
            @ Watched.field == True
            @ FieldWatcher
            async def reaction(...

    This class has an unusual dual purpose. It acts as a base class for classes
    that watch fields on other classes as well as being a decorator for that
    classes reactions. While complex, this is done to tightly bind the field
    management the predicate decorator defers when it receives a
    CustomFieldReactionConfiguration to the implementation of that provided
    by this class.
    # todo Is it possible to make this class acting in its
           CustomFieldReactionConfiguration able to look like a callable?
           Need to have the static type of __call__ be the Reaction that is
           passed to the initializer. Should this complexity be scrapped and
           just use a static method decorator?  Could then just tag the
           reaction and return it rather than acting as a proxy. Probably
           simplify things a bit.
    '''

    watched: Ti
    '''The instance being watched. Only defined when created as a FieldWatcher
    rather than a CustomFieldReactionConfiguration.
    '''

    _reactions: set[_Reaction[Ti, object, object]]
    '''
    The reactions FieldWatcher needs to register bound reactions for when
    instances are initialized.
    '''

    @overload
    def __init__(self,
                 reaction_or_watched: BoundReaction[FieldWatcher[Ti],
                                                    Ti, Any]) -> None:
        '''
        Reaction decorator to indicate the reaction referred to by
        reaction_or_watched is managed by FieldWatcher.
        '''

    @overload
    def __init__(self,
                 reaction_or_watched: Ti,
                 *args: object,
                 **kwargs: object) -> None:
        '''
        Create a FieldWatcher that watches the instance referred to by
        reaction_or_watched and executes the reaction using the executor used
        by watched.
        '''

    def __init__(self,
                 reaction_or_watched: Ti | BoundReaction[FieldWatcher[Ti],
                                                         Ti, Any],
                 *args: object,
                 **kwargs: object) -> None:
        '''
        Create a FieldWatcher or decorate a BoundReaction managed by
        FieldWatcher.
        '''
        if callable(reaction_or_watched):
            # Wrap the reaction so that it will not have instance field
            # reactions configured for it. It will be tracked as a reaction in
            # _reactions so that __init_subclass__ can configure the for the
            # specific instance. Strictly speaking
            # CustomFieldReactionConfiguration could be used instead of this,
            # but doing so is not nearly as understandable as this.
            reaction = reaction_or_watched  # for clarity
            super().__init__(reaction)
        else:
            # actually creating the FieldWatcher
            self.watched = reaction_or_watched
            executor = kwargs.pop('executor', None)
            assert isinstance(executor, (Executor, NoneType))
            if not executor:
                # Watcher will use the executor of watched if an executor is
                # not provided. Ti is not limited to things that have an
                # executor since it doesn't need to have an instance if only
                # bound reactions are used (ie classes that provide fields
                # for others to what but don't themselves have any reactions).
                # Typing for either this or that is non-obvious and skipped.
                # It is taken on blind faith that callers will provide an
                # executor if the type they are watching don't have an
                # executor. The exception that results if this blind faith is
                # misplaced occurs at definition time and will be trivially
                # noticed on first execution. It's not great, but the risk of
                # horrible things happening is minimal.
                # A similar issue exists with predicate reactions.
                executor = self.watched.executor  # type: ignore # blind faith
            super().__init__(None, # CustomFieldReactionConfiguration.reaction
                             *args,
                             executor=executor,
                             **kwargs)

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

    def _start(self) -> None:
        '''
        FieldWatcher implementations typically don't have a start action since
        they use the watched reaction executor. This is implemented as a no op
        so subclasses don't have to implement this method.
        '''

    def __replace__(self, *args: object, **kwargs: object) -> NoReturn:
        # Base classes both implement __replace__, Until there is an actual
        # need for this functionality it is not implemented.
        raise NotImplementedError()
