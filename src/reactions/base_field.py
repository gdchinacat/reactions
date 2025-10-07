'''
Where most of the 'magic' happens.
'''
from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from itertools import count
from typing import List, Any, Dict, Optional, Tuple, Callable, Iterable

from .error import (MustNotBeCalled, FieldAlreadyBound,
                    FieldConfigurationError)


__all__ = ['FieldManagerMeta']

type FieldReaction[T] = Callable[[Any, "BaseField[T]", T, T], None]
'''A method that is called when a field changes.'''


class HasFields(ABC):
    '''A class that has fields.'''

    @property
    def fields(self) -> Iterable[BaseField]:
        raise NotImplementedError()


class HasNoFields:
    '''A Mixin that has no fields'''

    @property
    def fields(self) -> Iterable[BaseField]:
        return ()


class Evaluatable[T](HasFields, ABC):
    '''base class for fields and predicates that can be evaluated'''

    @abstractmethod
    def evaluate(self, instance: Any) -> Optional[T]:
        '''
        Get the value of the type on instance.
        Field returns the instance value of the field.
        Predicates evaluate their truth value for the instance.

        T is the type the evaluate() returns.
        '''
        raise NotImplementedError()


class ReactionMixin(ABC):
    '''
    Implements the Reaction members and methods for Field and BoundField.
    '''
    _reactions: List[FieldReaction]

    def __init__(self, *args: List[Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        self._reactions = []

    def reaction(self, reaction: FieldReaction):
        '''
        Decorator to indicate the reaction should be called when the field's
        value changes.
        '''
        self._reactions.append(reaction)

    def react[T](self, instance: Any, field: "BaseField[T]", old: T, new: T):
        '''
        Notify the reactions that the value changed from old to new.
        '''
        for reaction in self._reactions:
            reaction(instance, field, old, new)


class BaseField[T](Evaluatable[T], ReactionMixin):
    '''
    An instrumented field.
    - T: is the type of object the field references

    This is a descriptor that:
        - manages and tracks updates to the field value
        - provides predicates for comparisons of the field value

    This works by intercepting field accesses on the class to return the
    descriptor itself so that dunder comparison methods on the descriptor can
    create predicates that are wired to instance methods that react to changes.
    The changes are detected by __set__ on instances (rather than their types).

    The general flow is a class with a Field is created. Comparisons are done
    on the class Field attribute to specify predicates with reactions. The
    class is instantiated and values set on the field inspect the predicates
    and call them when the Fields they are composed of change.
    '''

    _field_count = count()  # class member for assigning default attr names

    def __init__(self,
                 initial_value: Optional[T] = None,
                 classname: Optional[str] = None,
                 attr: Optional[str] = None,
                 *args, **kwargs) -> None:
        '''
        initial_value: The initial value for the field.
        classname: the name of the class this is a member of (display only)
        attr: the name of the attribute
        *args, **kwargs: play nice with super()

        classname and attr are optional and will have values provided. However,
        They will not be very meaningful so it is encouraged that they be set.
        They aren't required to keep field definitions simple and not repeat
        the class and name in the definition. The FieldManagerMeta populates
        these as part of class definition.
        '''
        super().__init__(*args, **kwargs)
        self.set_names(classname or '<no class associated>',
                       attr or f'field_{next(self._field_count)}')
        self.initial_value: Optional[T] = initial_value

    def set_names(self, classname: str, attr: str):
        '''Update the field with classname and attr.'''
        self.classname = classname
        self.attr = attr
        self._attr: str = '_' + self.attr               # private
        self._attr_bound: str = self._attr + '_bound'   # bound field

    def __hash__(self):
        '''
        Make Field 'immutable' so that they can be used in sets. The id() of
        the field is its hash.
        '''
        return id(self)

    def _bind(self, nascent_instance):
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

    def evaluate(self, instance) -> Optional[T]:
        try:
            return getattr(instance, self._attr)
        except AttributeError:
            setattr(instance, self._attr, self.initial_value)
            return self.initial_value

    ###########################################################################
    # Descriptor protocol for intercepting field updates
    ###########################################################################
    def __get__(self, instance, owner=None):
        '''
        Get the value of the field.

        For instances (instance is not None) this returns the actual value of
        the field.
        For classes (instance is None) the Field is returned so it can be used
        to create predicates.
        '''
        if instance is not None:
            return self.evaluate(instance)

        # Getting the field on the class. There are two cases that need to be
        # handled.
        #  1) Class.field for comparison
        #  2) dataclass initialization to set default value.
        # WTF did python conflate these two cases?
        # To handle this self is returned so case 1) uses the class field.
        # This means that instances of dataclass initialization receives this
        # Field as the 'default' value and it is set on the dataclass. This
        # case is handled in __set__ by detecting if "value is self" and
        # ignoring the call to __set__.
        assert owner is not None
        return self

    def __set__(self, instance, value: Optional[T]):
        # See comment in __get__ for handling field access. Ignore this call
        # if value is self.
        if value is self:
            return
        old: Optional[T] = self.evaluate(instance)
        if value != old:
            setattr(instance, self._attr, value)
            bound_field = getattr(instance, self._attr_bound)
            bound_field.react(instance, self, old, value)

    __delete__ = MustNotBeCalled(
        None, "removal of state attributes is not permitted")
    # end Descriptor protocol.
    ###########################################################################

    @property
    def fields(self):
        yield self

    def __str__(self):
        return f"{self.classname}.{self.attr}"
    __repr__ = __str__


class BoundField[T](ReactionMixin):
    '''
    A field bound to a specific instance.

    ALL field state relating to the instance should be on this object so that
    it is collected along with the instance. The Field should have no
    references to any instance specific information.

    The reactions for BoundFields is a reference to the unbound Field
    reactions. Adding class reactions through a bound field would be bad, so
    an exception is raised if reaction() is called.
    TODO - if there is a need for instance specific reactions this can be made
           more complex, but for now, simple is better.
    '''

    def __init__(self,
                 nascent_instance: Any,
                 field: BaseField[T], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.field: BaseField[T] = field
        self.instance = nascent_instance
        self._reactions = field._reactions

    def reaction(self, reaction: FieldReaction):
        raise FieldConfigurationError(
            'BoundField specific reactions are not supported, but could be.')

    def __str__(self):
        return (f'{self.field.classname}({id(self.instance)})'
                f'.{self.field}')
    __repr__ = __str__


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
        self['_fields'] = tuple[BaseField]()

    def __setitem__(self, attr: str, value: Any)->None:
        if isinstance(value, BaseField):
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
    _fields: Tuple[BaseField, ...]

    @classmethod
    def __prepare__(cls, name, bases):
        return FieldManagerMetaDict(name)

    def __setattr__(self, attr: str, value: Any):
        '''
        Intercept calls to name Field attributes that are set on the class.
        '''
        if isinstance(value, BaseField):
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
