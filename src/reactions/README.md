# State Reactions
This package provides a way to implement state machines by specifying how to
react to changes to the state model. Functions that react to changes are called
**reactions**.
## Design
There are three high level components, field instrumentation to detect changes,
predicates to detect when conditions on the state become true, and a state
machine to react to predicates that become true.
### Field Instrumentation
The *field* module provides a *Field* descriptor that intercepts changes to
fields it implements. Consumers can register reactions with fields in order to
receive a callback when the fields value changes.
Field reactions are invoked synchronously and execute before the statement that
caused the change returns.
Predicate reactions are processed synchronously.
### Predicates
The *predicate* module provides predicates for evaluating whether conditions
on fields are true. The predicates are typically created through evaluation
operations on Fields. Predicates are registered as reactions on the fields
they are dependent on in order to call reactions registered on themselves.
### States
The *state* module provides a *State* class that is used to create Fields,
specify predicates on those fields, and register methods when those predicates
are true.
The **State.when()** decorator is used to specify the conditions when a
decorated reaction method should be called. The predicate reaction evaluates
the predicate and when true asynchronously calls the decorated reaction method.

## Usage
A state model is defined by subclassing **state.State**. The subclass decorates
reaction methods with State.when specifying the condition for execution of the
method.

This example shows how to set a counter that increments forever:
`
class Counter(State):
    count = Field(0)

    @State.when(count >= 0)
    def increment(self, bound_field, old, new):
        self.count += 1
`

There is more to it (initial state, starting) but this illustrates the basic
usage.

The arguments to increment() are:
  - bound_field: an instance of the count field specific to self. It can be
    used to determine which field in the predicate changed to cause the
    predicate to become true.
  - old: the value the field contained before it was changed.
  - new: the value of the field that caused the predicate to become true.

See the examples in the test/examples directory for working examples.