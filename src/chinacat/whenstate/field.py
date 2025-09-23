'''
Where most of the 'magic' happens.
'''
from __future__ import annotations
from typing import Callable, List

from .predicate import Eq, _Field


class Field[C, T](_Field):
    '''
    An instrumented field of a State.
    - C: is the type of the object the field is a member of
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

    Calling the field with an instance will return a bound field specific to
    that instance. # TODO - update this once it's fleshed out.
    '''
    def __init__(self,
                 attr: str,  # name of the field, value stored as ._{attr}
                 initial_value: T | None = None):
        self.attr: str = f"_{attr}"
        self.initial_value: T | None = initial_value

    def __hash__(self):
        '''
        Make Field 'immutable' so that they can be used in dataclasses. The
        todo - Field isn't ever mutated so this *should* be ok....right?
        '''
        return id(self)

    def __call__(self, instance: C):
        '''
        Get or create the BoundField for this field on the given instance.
        todo - for thread safety it is probably better to create the BoundField
               when the instance is created rather than doing it here lazily.

        This is not expected to be a frequent operation so the attr name is
        built when executed. If this assumption proves to be incorrect cache
        the name.
        todo - @memoize this?
        '''
        attr = f"{self.attr}_field"
        bound_field = getattr(instance, attr, None)
        if bound_field is None:
            bound_field = BoundField[C, T](instance, self)
            setattr(instance, attr, bound_field)
        return bound_field

    def _get_with_initialize(self, instance: C) -> T | None:
        try:
            return getattr(instance, self.attr)
        except AttributeError:
            setattr(instance, self.attr, self.initial_value)
            return self.initial_value

    def __get__(self, instance, owner=None):
        '''
        Get the value of the field.

        For instances (instance is not None) this returns the actual value of
        the field.
        For classes (instance is None) the Field is returned so it can be used
        to create predicates.
        '''
        if instance is not None:
            return self._get_with_initialize(instance)

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

    def __set__(self, instance: C, value: T):
        # See comment in __get__ for handling field access. Ignore this call
        # if value is self.
        if value is self:
            return
        old: T | None = self._get_with_initialize(instance)
        if value != old:
            self(instance).notify(old , value)
            setattr(instance, self.attr, value)

    def __eq__(self, other):
        '''create an Eq predicate for the field'''
        return Eq(self, other)

    # todo implement these comparison methods.
    def _NotImplementedError(self, *args: object):
        return NotImplementedError(*args)
    __ne__ = __lt__ = __le__ = __gt__ = __ge__ = _NotImplementedError

    @property
    def fields(self):
        yield self


type Listener[C, T] = Callable[["BoundField[C, T]", T, T], None]
'''Listener for field value change notifications'''


class BoundField[C, T]:
    '''
    A field on a specific instance.

    ALL field state relating to the instance should be on this object so that
    it is collected along with the instance. The Field should have no
    references to any instance specific information.
    '''
    def __init__(self,
                 instance: C,
                 field: Field[C, T]):
        super().__init__()
        self.field: Field[C, T] = field
        self.instance: C = instance
        self.listeners: List[Listener[C, T]] = []  # todo - use weakrefs

    def listen(self, func: Listener[C, T]):
        '''
        Decorator to indicate func(field=, instance=) should be called when
        this fields value changes.
        '''
        # todo - defer call until "after" the current execution is "done"
        #        allow transaction-like semantics?
        #        remove spurious calls for intermediate value changes
        self.listeners.append(func)

    def notify(self, old: T, new: T):
        '''
        Notify listeeners that the value changed from old to new.
        '''
        # todo - defer?
        # todo - async await?
        for listener in self.listeners:
            listener(self, old, new)
