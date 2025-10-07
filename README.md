# State Reactions
This package provides a way to implement state machines by specifying how to
react to changes of the state model. Functions that react to changes are called
**reactions**. They are called by **predicates** when the predicate becomes
true. Predicates are created through comparison function on **fields**.

## Usage
A state model class defines the fields of the state machine and decorates
reaction methods with predicates specifying the condition for execution of the
method.

This example shows how to set a counter that increments forever:
`
class Counter:
    count = Field(0)

    @ count >= 0
    def increment(self, bound_field, old, new):
        self.count += 1
`
The salient points:
  - Counter: is the class implementing the state machine.
  - count: a field of the state machine.
  - increment: the reaction when count changes and is greater than or equal
    to zero. While '@ count >= 0' is an unusual statement in python, it applies
    the predicate (@) created by the field comparisong (count >= 0).
  - old: the value the field contained before it was changed.
  - new: the value of the field that caused the predicate to become true.

There is more to it (initial state, starting) but this illustrates the basic
usage.

See the examples in the sr/test/examples directory for working examples.

## Design
There are three high level components, field instrumentation to detect changes,
predicates to detect when conditions on the state become true, and an asyncio
executor to execute the reactions asynchronously.
### Field Instrumentation
The *field* module provides a *Field* descriptor that intercepts changes to
fields it implements. Consumers can register reactions with fields in order to
receive a callback when the fields value changes.
Field reactions are invoked synchronously and execute as part of setting the
new value on the field.
Fields are used to create predicates using rich comparison functions (i.e
'field == 1' will create a Predicate for this condition.
### Predicates
The *predicate* module provides predicates for evaluating whether conditions
on fields are true. The predicates are typically created through the Field
rich comparison functions invoked using the associated operators.
Predicates are registered as reactions on the fields they are dependent on in order to call reactions registered on themselves.

Predicates are decorators that can be used to specify the conditions when a
decorated reaction method should be called. The predicate reaction evaluates
the predicate and when true asynchronously calls the decorated reaction method
using the associate executor.
### Executors
The *executor* module provides a *ReactionExecutor* class that is used to
execute the predicate reactions. Reactions are executed sequentially in the
order they are submitted. They are executed in the asyncio event loop for the
context they are started in.
## Why?
Expressing when code should be executed aligns with well defined state
machines. Reading the code in this way makes it easy to see how the state
works and transitions from one state to another.

#### Personal motivation
Also, I wanted to develop more in depth experience with several aspects of
Python. This project started as my way to do that. The features of Python that
are leveraged by this project are:
  - descriptors: Field implements the descriptor protocol to know when class
   	members value change.
  - rich comparison functions: Field implements these in order to create
    predicates.
  - asyncio: Predicate execution must be asynchronous in order to support
    reactions that change the fields they react to. By serializing the reaction
    execution a form of consistency is provided since field changes queue
    reactions to execute after the current reaction is complete so reactions
    only see state left by completed reactions.
  - type annotations: the meta programming aspects of this project require
    a good understanding of the typing system. (still a work in process).

## What can it be used for
Pretty much any state machine. It is envisioned that complex behaviors, such
as for game characters, can be implemented in a way that is easy to understand
and, more importantly, maintain. The existing examples are pretty much toys at
this point and need to be extended.

## Limitations
These are the current limitations. Also check the github bugs.

### Annotations
While type annotations are used throughout they are not as complete as they
should be. Specifically, the type checking for reactions does not function as
desired. The predicate decorator should, but currently does not, check that
the reaction function accepts a Field of the proper generic type and the old
and new arguments match the Field type. These types should be derived from the
Fields used to create the predicate. See code comments for gory details of what
needs to be done to make this work.

### Reaction instances
As implemented it only really works for reactions on the instances that contain
the fields. This is a pretty significant limitation and is the current focus as
it is considered a requirement for other objects to react to changes in the
state machine. While several hacks to work around this limitation exist, they
are not performant or easy to use since they need to associate (map) the
instance that changed to the instance that cares about its changes. This needs
to be made a supported aspect of the framework.

### Performance
Performance is not bad considering what it does. Is this an efficient way to
count? No...it certainly is not. Incrementing a field by using a descriptor to
detect changes, call a function that schedules a coroutine for asynchronous
execution, and then executing that coroutine is significantly more overhead
than simply incrementing the field and calling a notification function
explicitly. That said, performance is pretty good (microbenchmark shows it is
"only" 100x slower at counting than x += 1 in a tight loop). The reactions are
statically defined at class definition and the framework doesn't do much more
than call the reactions, evaluate fields and predicates. Object creation in
the reaction path is kept to a minimum, no asyncio.Tasks are created, only
coroutines and the object (tuple) to pass them to the executor.

That said, this is probably not the best way to implement performance critical
logic. Complex state machines with infrequent updates, yes. A way to count to
10,000,000 as quickly as possible, no. Those examples exist to show basic
functionality.

## Misc
The fact that Python uses '@' to decorate functions is fortuitous. It allows
reading the predicate decorator as 'at count greater than or equal to zero call
function increment'. Any other operator wouldn't read as nicely. Unfortunately,
'and', 'or', and 'not' operators are not implemented through dunders and there
is not a natural way to write predicates for them. Consideration was given to
hijacking the bitwise and (&) and bitwise or (|) operators for this purpose,
but doing so would mean predicate operators behave differently than everywhere
else and was deemed a bad idea. 'And(field_a == 1, field_b == 2)' will have to
do. (I believe python doesn't provide these operators as dunders for
performance reasons, which is valid).
