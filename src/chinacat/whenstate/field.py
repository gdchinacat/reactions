'''
Weird sick can't sleep thoughts after seeing:
https://www.reddit.com/r/Python/comments/1nmta0f/i_built_a_full_programming_language_interpreter/
Right before going to bed and trying to sleep I thought...I bet a bunch of that
can be done with standard python using descriptors and ....

Then the dogs barked and woke me up early while still sick. Here goes nothing.

The basic language idea is that you specify conditions when code should
execute based on a state model. But, rather than adding events to your model
explicitly you write code that appears procedural, but it just sets up
listeners for model change events. Under the covers the model has a complex
graph of dependent conditions that are evaluated when the condition changes.

TODO - example
'''
from .predicate import Eq


class Field[T]:
    '''
    An instrumented field of a State.

    This is a descriptor that:
        - manages and tracks updates to the field value
        - provides predicates for comparisons of the field value
    '''
    def __init__(self,
                 initial_value: T = None):
        self.initial_value = initial_value

    def __getattr__(self, attr):
        # delegate to T
        print(f"__getattr__({self=}, {attr=})")
        return getattr(T, attr)

    def __get__(self, instance, owner=None):
        if owner is not None:
            # todo - return a proxy with instrumented evaluation dunders
            print(f"accessing field on {owner=} with generic {T}")
        else:
            # todo - actually return the field value
            print(f"accessing field on {instance=} with generic {T}")
        return None

    def __set__(self, instance, value):
        # todo - set the value
        print(f"set field on {instance=} with generic {T} to {value=}")

    def __eq__(self, other):
        '''create an Eq predicate for the field'''
        return Eq(self, other)
