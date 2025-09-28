'''
Where most of the 'magic' happens.
'''
from __future__ import annotations

from abc import ABC
from typing import List, Any, Dict, Optional

from .error import MustNotBeCalled
from .predicate import (_Field, Reaction, BinaryPredicate,
                         Eq, Ne, Lt, Le, Gt, Ge, And, Or)


__all__ = ['Field', 'BoundField', ]

class ReactionMixin[C, T](ABC):
    '''
    Implements the Reaction members and methods for Field and BoundField.
    '''

    def __init__(self, *args: List[Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        self.reactions: List[Reaction[C, T]] = []

    def reaction(self, reaction: Reaction[C, T]):
        '''
        Decorator to indicate the reaction should be called when the field's
        value changes.
        '''
        # todo - allow transaction-like semantics?
        #        - remove spurious calls for intermediate value changes
        self.reactions.append(reaction)

    def react(self, old: T, new: T):
        '''
        Notify the reactions that the value changed from old to new.
        '''
        for reaction in self.reactions:
            reaction(self, old, new)


class Field[C, T](ReactionMixin, _Field):
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
    '''

    instance: None = None

    def __init__(self,
                 classname: str,  # for str/repr
                 attr: str,  # name of the field, value stored as ._{attr}
                 initial_value: Optional[T] = None,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.classname: str = classname
        self.attr: str = attr                           # public
        self._attr: str = '_' + attr                    # private
        self._attr_bound: str = self._attr + '_bound'   # bound field
        self.initial_value: Optional[T] = initial_value

    def __hash__(self):
        '''
        Make Field 'immutable' so that they can be used in sets. The id() of
        the field is its hash.
        '''
        return id(self)

    def bound_field(self, instance: C) -> BoundField[C, T]:
        '''
        Get or create the BoundField for this field on the given instance.
        todo - (metaclass) for thread safety it is probably better to create
               the BoundField when the instance is created rather than doing it
               here lazily.
        '''
        bound_field = getattr(instance, self._attr_bound, None)
        if bound_field is None:
            bound_field = BoundField[C, T](instance, self)
            setattr(instance, self._attr_bound, bound_field)
        return bound_field

    def evaluate(self, instance: C) -> Optional[T]:
        return getattr(instance, self.attr)

    def _get_with_initialize(self, instance: C) -> Optional[T]:
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
        old: Optional[T] = self._get_with_initialize(instance)
        if value != old:
            setattr(instance, self._attr, value)
            bound_field: BoundField[C, T] =  self.bound_field(instance)
            bound_field.react(old , value)

    __delete__ = MustNotBeCalled(
        None, "removal of state attributes is not permitted")
    # end Descriptor protocol.
    ###########################################################################

    ###########################################################################
    # Predicate creation operators
    ###########################################################################
    def __contains__(self, other) -> None:
        '''not implemented'''
        raise NotImplementedError('use Contains(self, other) instead')

    def __and__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an And (&) predicate for the field'''
        return And(self, other)  # pylint: disable=abstract-class-instantiated

    def __or__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Or (|) predicate for the field'''
        return Or(self, other)  # pylint: disable=abstract-class-instantiated

    def __eq__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Eq (==) predicate for the field'''
        return Eq(self, other)  # pylint: disable=abstract-class-instantiated

    def __ne__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Eq predicate for the field'''
        return Ne(self, other)  # pylint: disable=abstract-class-instantiated

    def __lt__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Lt (<) predicate for the field'''
        return Lt(self, other)  # pylint: disable=abstract-class-instantiated

    def __le__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Le (<=) predicate for the field'''
        return Le(self, other)  # pylint: disable=abstract-class-instantiated

    def __gt__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Gt (>) predicate for the field'''
        return Gt(self, other)  # pylint: disable=abstract-class-instantiated

    def __ge__(self, other) -> BinaryPredicate[C]:  # type: ignore[override]
        '''create an Ge (>=) predicate for the field'''
        return Ge(self, other)  # pylint: disable=abstract-class-instantiated

    # end Predicate creation operators
    ###########################################################################

    @property
    def fields(self):
        yield self

    def __str__(self):
        return f"{self.classname}.{self.attr}"
    __repr__ = __str__


class BoundField[C, T](ReactionMixin):
    '''
    A field bound to a specific instance.

    ALL field state relating to the instance should be on this object so that
    it is collected along with the instance. The Field should have no
    references to any instance specific information.

    The reactions for BoundFields are the *same* as for the unbound Field.
    TODO - if there is a need for instance specific reactions this can be made
           more complex, but for now, simple is better.
    '''

    def __init__(self,
                 instance: C,
                 field: Field[C, T], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.field: Field[C, T] = field
        self.instance: C = instance
        # TODO - should the reactions be async generators that the bound field
        #        and values are sent to? Reduce load by avoiding task creation?
        #        are async generators less expensive than tasks?
        self.reactions = field.reactions

    def __str__(self):
        return f"{self.field.classname}({id(self.instance)}).{self.field.attr}"
    __repr__ = __str__
