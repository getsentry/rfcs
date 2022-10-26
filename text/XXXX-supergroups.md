* Start Date: 2022-06-22
* RFC Type: feature / decision / informational
* RFC PR: https://github.com/getsentry/rfcs/pull/29

# Summary

This RFC describes the motivation for supergroups.

## Motivation

When an error or exception is reported, it's desireable to fingerprint them so that the
frequency of their ocurrence can be determined.  However what makes an error "the same"
as another error?  Sentry has always run an algorithm to calculate the unique fingerprint
of the error.  Any further error with the same fingerprint is fed into the same group and
tallied up.  However no error is quite the same so the fingerprinting algorithm intentionally
removed quite a bit of information or cleaned it up, to increase the chance of getting the
same fingerprint.

In doing so, there is a direct relationship to the creation of a Sentry issue to the
calculation of the fingerprint.  This proposal wants to break this process up into two
independent steps.

It's evident from empiric evidence at Sentry that creating a overly precise fingerprint is
problematic if each individual fingerprint creates a new issue in Sentry.  Because of this
coupling the grouping algorithms have learned a few tricks over the years to disregard
certain patterns that are known to be unstable between errors.  However there are a few
fundamental issues that the grouping algorithm cannot address today.

### Non Stack Fingerprints

The primary way of creating fingerprints for errors are components of the stack trace.  There
are however situations where a stack trace is unavailable or the stack trace does not have
enough useful information (ie: the entire stack is discarded).  In that case Sentry needs to
fall back to alternative grouping information which is often a string supplied with the error
(the error or log message).  These typically contain formatted strings which are different
between error instances.  The classical example is an error such as `"Worker process crashed (PID=23)"`.

Here even multiple years of investment into the grouping algorithm has not resulted in good
fingerprints.  We generally undergroup compared to what a human would expect, however the
approach taken today is limited as it needs to generate a unique fingerprint.

### Caller vs Callee Stacks

One challenge with grouping based on stacks is that bugs might be happening in functions which
are invoked from different places in the codebase.  Imagine a function that returns the currently
authenticated user (`get_current_user`).  If this function is used all across the code base
in different places, then a newly introduced regression can cause a range of different stack
traces to be generated which in turn results in independent fingerprints.  To make this more
concrete imagine the function fails with an `AttributeError` and is invoked in the following
ways:

```
Traceback (most recent call last):
  File "demo.py" in login
  File "demo.py" in validate_access
  File "demo.py" in get_current_user
AttributeError: 'NoneType' object has no attribute 'username'
```

vs

```
Traceback (most recent call last):
  File "demo.py" in checkout
  File "demo.py" in process_transaction
  File "demo.py" in get_current_user
AttributeError: 'NoneType' object has no attribute 'username'
```

Here it seems obvious in a way that these are the same error beacuse the issue
is clearly in the `get_current_user` function.  Yet the two stack traces are
different (`login | validate_access | get_current_user` and
`checkout | process_transaction | get_current_user`).  In this case we would say that the error
is in the callee and would expect them to be grouped the same.

On the other hand there can be exactly the same type of stack trace situation, but instead the
error is in fact in the caller due to bad input.  Take for instance a function which parses a
UUID (`parse_uuid`).  As part of the contract of this function we expect that the function will
raise an error on bad input (`InvalidUuid`).  Now this function ends up being called in two
different places:

```
Traceback (most recent call last):
  File "demo.py" in load_images
  File "demo.py" in parse_uuid
InvalidUuid
```

vs

```
Traceback (most recent call last):
  File "demo.py" in parse_request
  File "demo.py" in parse_uuid
InvalidUuid
```

Here the error is in fact not in `parse_uuid`.  The function operates as expected, but the
calling functions are failing to catch down the invalid input error.  We at this point do not
even know yet if the `parse_request` or `load_images` function are supposed to catch down the
error or if someone higher up in the stack is supposed to, but we do know that it somewhere made
it to a point where a Sentry error was created.  In this case we would not want this to group
together under `parse_uuid`.

### Environmental Failures

Another class of errors that causes challenges today are what we call "environmental failures".  These
are failures that happen because something in the environment degraded and is starting to fail
unexpectedly.  A class of these environmental failures are network problems.  If for instance your database
becomes unavailable, then a range of functions all over the product will start to fail in yet unseen
ways.  This will create a lot of new fingerprints and as a result will create a number of new Sentry
errors.  Particularly during incidents it's very common that a Sentry project will generate a huge
number of issues that are unlikely to happen a second time and your only solution is to mass resolve
these.

Some of these environmental failures could be clustered from a fingerprinting point of view at the
level of just the exception.  For instance one could make a relatively drastic call and decide that
any `SocketError` shares the same fingerprint.  This however is unscalable for large software bases
where different parts of the code base connect to different endpoints and as a user you want to be
able to distinguish between these.

### Snapshot or Sampled Stack Traces

When a error is reported to Sentry in many cases the stack trace is coming directly from the exception
object.  This means that when the error is created, it also carries at least an approximation of the
call stack.  There are however situations where errors are reported to Sentry and the stack trace is
fabricated.  Many of these are from situations where an error was not actually happening, but the
SDK decided to report one anyways from a watchdog.  The most common example is something like a
deadlock or hang detection.  If a certain task is not making progress for an extended period of time
SDKs will often monitor what is happening from a background thread and issue a hang warning as Sentry
error.  In that case the SDK goes in and creates a stack trace for another thread which might actually
be busy doing something instead of hanging on a lock.  In that case the stack is highly unstable.

This is a common issue with ANR (Application Not Responding) reports on mobile for instance where we
already have to opt to a different grouping algorithm altogether as it creates too much noise otherwise.

### Runtime Unstable Stacks

The fingerprinting algorithm currently replies heavily on the fact that the same error produces the
same fingerprint.  Unfortunatley there are limitations in runtimes that makes this impossible at times.
For instance when working with browser javascript engines, the stack traces between different browsers
are never quite the same.

Take for instance this little JavaScript example:

```javascript
function failingFunction() {
  throw new Error("broken");
}

const result = [1, 2, 3].map((item) => {
  if (item % 2 == 1) {
    failingFunction();
  }
  return item;
});
```

In Firefox the stack trace looks roughly like this:

```
failingFunction
result<
(anonymous)
(anonymous)
```

Compare this to Chrome:

```
failingFunction
(anonymous)
Array.map
(anonymous)
```

Or Safari:

```
failingFunction
(anonymous)
map@[native code]
(global code)
```

Or node:

```
failingFunction
(anonymous)
Array.map
Object.<anonymous>
Module._compile
Object.Module._extensions..js
Module.load
Function.Module._load
Function.executeUserEntryPoint
```

There is little agreement on what the stack should look like and it cannot even be properly
normalized.  Sure there is something that can be detected or cleaned up, but fundamentally the
stack traces are differences are big enough that generating the complete same fingerprint is
close to impossible and definitely impossible in the general case.

### Compiler Unstable Stacks

Similar to the situation where the runtime creates difference stack traces, there are also
issues where compilers or transpilers are involved.  The tricky case here are largely compiler
optimizations.  The most trivial example are inlines.  If the compiler choses to inline a frame
the stack traces in the trivial case changes.  This would not appear to be much of an issue as
the debug information carries enough information to know where a function was inlined and that
can be used to correct the stack trace.  However unfortunately limitations in the debug information
format often cause inline frames to look slightly different than regular frames.

The reason for this issue is that for instance in C++ and many other languages there are really
two different ways to describe a function.  One is the mangled format and one is the demangled
format.  Neither of these formats are particularly stable and there are no agreed upon standards.
In PDB for instance for mangled functions there is no general way to retrieve either format for
functions.  Many inline functions do not carry the same amount of information as a non inlined one.
For instance take this function:

```
template <class T> const T &min(const T &a, const T &b)
{
    return !(b < a) ? a : b;
}
```

When invoked with an `int` the function when not inlined is typically recoded as
`module::min<int>(const int &, const int &)` or `min(const int &, const int &)`
in the stack trace.  However when inlined the function on Windows platforms
might only be called `min`.  However that's not true in the general case either.
Many functions do retain their types, some do not.

This problem becomes even larger when dealing with compiler generated code.  For instance C++
knows a lot of different destructors and they can all look very different and they will look
different depending on if they are inlined or not.

As such from one release to another the fingerprint generated for a stack might change entirely.

### Platform Unstable Stacks

Related to the former case another complication arises from platform provided primitives that might
end up in the stack trace.  Imagine for instance an application written in Rust that runs on macOS,
Windows and Linux and has a trivial user introduced panic in a function invoked from an event loop.
The event loop part of the stack will look different on every platform, yet the user code on top
will look the very same.  On Linux it might use some epoll abstraction, in Windows IOCP or kqueue on
mac.  Similar problems happy with mutexes, thread spawning code or more.

None of the platform differences are relevant to the user bug, yet the same issue will create three
different fingerprints, one per platform.

We can also not universally exclude platform specific code because there might very well be a bug
in this threading code.  For instance you would not want to have all the event handling code be
excluded from stack traces for the case that the bug is in fact in the platform specific event
handling code.

## Proposed Changes

The relationship of event to issue is very strong in Sentry.  There are directly workflows associated
with it and there are quite significant technical hurdles to this.  The proposal is to not touch this
association but instead augment it on a higher level.  The idea is to actually create these Sentry
issues still based on the unique fingerprint but to lower the consequences of such a group being
created.  Related fingerprints could then at regular intervals be sweeped up in to larger super
groups.

This means that from a user's point of view the individual groups still exist, but the main way to
interact with them would be larger groups that group around the already existing smaller groups.
Since the events stay associated with their fingerprint created group the event itself is immutable
and stays that way, but the merge just becomes an association of that group with the supergroup.

The way the individual fingerprints are associated with the supergroup is not defined by this
proposal.  The idea is to create the possibility and to then experiment with ways in which this
can happen.

