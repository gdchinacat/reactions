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

from .state import State
from .field import Field  # todo - don't require models use this explicitly (metaclass to do it automatically?)

__all__ = ['State', 'Field']
