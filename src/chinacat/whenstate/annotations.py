'''
Annotation types. Defines the interfaces for the entities.

Everything can import this.
'''
from __future__ import annotations

from abc import abstractmethod
from logging import Logger
from typing import (Any, Coroutine, Protocol, runtime_checkable,
                    Iterable, Optional)


__all__ = ['FieldReaction', 'PredicateReaction']


EMPTY_ITERATOR = () # singleton empty sequence
    
type ReactionCoroutine = Coroutine[None, None, None]


# todo - verify that all of these protocols are still needed now that things
#        have been cleaned up a bunch.
class FieldReaction[T](Protocol):
    '''A method that is called when a _Field value changes.'''
    def __call__(self,
                 instance: Any,       # the instance the field is on
                 field: "_Field[T]",  # the field whose value changed
                 old: T,              # the old value of the field
                 new: T               # the new value of the field
                ) -> None:
        pass

class _ReactionExecutor(Protocol):
    '''
    _ReactionExecutor is able to schedule PredicateReactions for asynchronous
    execution.
    '''
    _logger: Logger

    @abstractmethod
    def react[T](self,
                 reaction: PredicateReaction,
                 instance: _Reactant,
                 # TODO - should be the instance of the class that defined the
                 # reaction, not the instance of the class that field change
                 #triggered reaction
                 field: _Field[T],
                 old: T, new: T) -> None:
        raise NotImplementedError()

class PredicateReaction(Protocol):
    '''
    A _Reactant method that is called asynchronously when a _Predicate value
    changes.

    Predicate reactions are processed asynchronously and require the type that
    defines them be a _Reactant so the reaction can be scheduled with the
    _ReactionExecutor for the _Reactant.
    '''

    __qualname__: str

    # todo for some reason adding instance causes a an error with the instance
    #      not matching and the types in the error look right to me....
    #      work around for now.
    async def __call__(self, *args) -> None: pass
#    async def __call__[T](self,
#                 instance: Any,
#                 field: _Field[T],
#                 old: T,
#                 new: T
#            ) -> None:
#        pass


# TODO - rename _Reactant to FieldClass?
class _Reactant(Protocol):
    '''Reactant is able to schedule reactions.'''

    _reaction_executor: _ReactionExecutor
    _logger: Logger

    @abstractmethod
    def reaction[T](self, reaction: PredicateReaction) -> None:
        '''
        Schedule a reaction to be called back at some point in the future.
        The conditions for when it is called are determined by the type of
        _Reactant. For example, Field.reaction() calls the reaction when the
        field value changes, whereas Predicate.reaction() calls it when the
        predicate is True.
        '''
        raise NotImplementedError()

class HasFields(Protocol):
    '''A protocol for types that have fields.'''
    
    @property
    @abstractmethod
    def fields(self) -> Iterable[_Field]:
        '''Get the list of fields the type is composed of.'''
        raise NotImplementedError()

class HasNoFields(HasFields):
    '''A HasFields that has no fields.'''
    
    @property
    def fields(self) -> Iterable[_Field]:
        return EMPTY_ITERATOR

@runtime_checkable  # TODO perf - predicate constant wrapping uses isinstance
class _Evaluatable[T](HasFields, Protocol):
    
    @abstractmethod
    def evaluate(self, instance: Any) -> Optional[T]:  # todo should Optional be baked in?
        '''
        Get the value of the type on instance.
        Field returns the instance value of the field.
        Predicates evaluate their truth value for the instance.

        T is the type the evaluate() returns.
        '''
        raise NotImplementedError()

class _Field[T](_Evaluatable[T], HasFields, Protocol):
    '''Protocol for Field.'''

    @property
    def fields(self) -> Iterable[_Field[T]]:
        # a field has itself as its fields
        return [self]

    @abstractmethod
    def reaction(self, reaction: FieldReaction) -> None:
        '''Schedule reaction to be called when the field value changes.'''
        raise NotImplementedError()

class _Predicate(_Evaluatable[bool], Protocol):
    '''A predicate evaluates to a boolean based on its fields.'''
