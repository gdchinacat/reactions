'''
The public facing Field implementation.
'''
from __future__ import annotations

from .base_field import BaseField
from .predicate import Predicate
from .predicate_types import And, Or, Eq, Ne, Lt, Le, Gt, Ge
from typing import NoReturn

__all__ = ['Field']


class Field[T](BaseField[T]):
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
