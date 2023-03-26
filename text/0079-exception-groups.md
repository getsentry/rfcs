- Start Date: 2023-03-26
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/79
- RFC Status: draft

# Summary

This RFC is intended to capture the changes required to Sentry to handle *exception groups*,
including changes to SDKs, protocol schema, event processing, and UI.

# Motivation

Several programming languages have a concept of an unrelated group of multiple exception, aggregated into a single exception.

- Python [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#exception-groups) ([PEP 654](https://peps.python.org/pep-0654/))
- .NET [`AggregateException`](https://docs.microsoft.com/dotnet/api/system.aggregateexception)
- JavaScript [`AggregateError`](https://developer.mozilla.org/docs/Web/JavaScript/Reference/Global_Objects/AggregateError)
- Go [`Unwrap() []error`](https://pkg.go.dev/errors) ([see also](https://tip.golang.org/doc/go1.20#errors))
- Java [`Throwable.getSuppressed()`](https://docs.oracle.com/javase/7/docs/api/java/lang/Throwable.html#getSuppressed())

There may be others. We will use the term "exception group" throughout the design.
It applies to the concept, regardless of language.

Sentry needs a way to capture exception groups, and present them in a meaningful way.
Simply raising the exception group as a single issue is insufficient.

See also:
- [Python customer feedback](https://github.com/getsentry/sentry/issues/37716)
- [.NET customer feedback](https://github.com/getsentry/sentry-dotnet/issues/270)

# Background

## About Exception Groups

An exception group is an exception unto itself.  It is caused by the exceptions in the group,
but there is no implied causal relationship between those exceptions.

In other words, given the following:

- Group A
  - Exception 1
  - Exception 2
  
`Group A` is an exception group caused by both `Exception 1` and `Exception 2`.
However, it is generally _not_ true that `Exception 1` was caused by `Exception 2` or vice versa.

Furthermore:
- `Exception 1` and `Exception 2` might be of the same type, or they might be of different types.
- There can be `n` number of exceptions in an exception group (`n >= 1`).
- There can be a stack trace on each of the exceptions within an exception group, as well as on the group itself.
- Just like any other exception, each exception within an exception group can have a chain of inner exceptions.
- An inner exception can *also* be an exception group.
- Exception groups can be present at any level.  There is no requirement that the start of the chain is an exception group.

Thus, other valid examples that could occur in an application include the following:

- Group B
  - Exception 1
    - Exception 2
      - Exception 3

- Group C
  - Exception 1
    - Exception 1a
      - Exception 1b
  - Exception 2
    - Exception 2a
      - Exception 2b

- Group D
  - Exception 1
    - Exception 1a
      - Exception 1b
  - Group E
    - Exception 2
      - Exception 2a
        - Exception 2b
    - Exception 3
      - Exception 3a
        - Exception 3b

- Exception 1
  - Exception 1a
    - Group E
      - Exception 2
        - Exception 2a
          - Exception 2b
      - Exception 3
        - Exception 3a
          - Exception 3b

## Interpreting Exception Groups

The meaning of a _normal_ exception or is pretty straightforward:
- An exception is something that went wrong in the application, and thus represents an issue to resolve.
- If there is another exception that occurred to cause this one, that is assigned to the "inner exception" or "cause".
- The chain of exceptions thus is linear.

This changes with an exception group:
- The exception group _might_ represent the issue to resolve, or the issue might better be represented by one or more of the inner exceptions within the group.
- Depending on language, there might be a cause that is separate from the _any_ of the exceptions in the group.
- Thus, the chain of exceptions is more tree-like than linear.

Note that exception

## Exception Handling in Sentry

SDKs send exceptions to Sentry using the [Exception Interface](https://develop.sentry.dev/sdk/event-payloads/exception/)
on an event. One or more exceptions can be sent in the `values` array of the interface.  Multiple values represent
a chain of exceptions in a causal relationship, sorted from oldest to newest.  For example:

```json
{
  "exception": {
    "values": [
      {"type": "TypeError", "value": "Invalid Type!"},
      {"type": "ValueError", "value": "Invalid Value!"},
      {"type": "RuntimeError", "value": "Something went wrong!"}
    ]
  }
}
```

In the above example, an issue is created in Sentry for the `RuntimeError` exception.

```
Issue Title: "RuntimeError: Something went wrong!"

+==============================
+ RuntimeError: Something went wrong!
+------------------------------
+ (stack trace)
+==============================

+==============================
+ ValueError: Invalid Value!
+------------------------------
+ (stack trace)
+==============================

+==============================
+ TypeError: Invalid Type!
+------------------------------
+ (stack trace)
+==============================
```

This design is linear, and thus cannot support exception groups having more than one exception.
But even in that case, the exception presented in Sentry might be titled and grouped in an undesirable manner.

Consider:

```json
{
  "exception": {
    "values": [
      {"type": "TypeError", "value": "Invalid Type!"},
      {"type": "ValueError", "value": "Invalid Value!"},
      {"type": "RuntimeError", "value": "Something went wrong!"},
      {"type": "ExceptionGroup", "value": "Exception Group (1 sub-exception)"}
    ]
  }
}
```

Sending this to Sentry would result in an issue titled `"ExceptionGroup: Exception Group (1 sub-exception)"`.
In some contexts that may be desired, but in others the expectation is that the issue would be titled `"RuntimeError: Something went wrong!"`.

# Language Specifics

## .NET

The exception group type in .NET is [`AggregateException`](https://learn.microsoft.com/dotnet/api/system.aggregateexception).
- The exceptions of the group are stored in the `InnerExceptions` property.
- Like other exceptions, it also has an `InnerException` property, which is interpreted as the cause of this exception.
  - Its value is always the same as `InnerExceptions[0]`.

## Python

The exception group type in .Python is [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#exception-groups).
- The exceptions of the group are stored in the `exceptions` attribute.
- Like other exceptions, it can have a `__cause__` and/or a `__context__` attribute.
  - `__context__` is an indirect cause, assigned if another exception occurs while handling the exception.
  - `__cause__` is a direct cause, assigned if raised with the exception (using the `from` keyword).
    - Setting it suppresses any `__context__` value, when displayed in the stack trace.
  - There is no requirement that `exceptions[0]` be either of these.

## JavaScript

The exception group type in JavaScript is [`AggregateError`](https://developer.mozilla.org/docs/Web/JavaScript/Reference/Global_Objects/AggregateError).
- The errors of the group are stored in the `errors` property.
- Like other errors, it has a `cause` (singular) property.
  - There is no requirement that `errors[0]` be the same as `cause`.

# Proposed Solution

We will break down the problem into two phases, as described in the following sections.

## Phase 1

In this phase, we will focus on having the "primary issue" of the exception group surfaced in Sentry in a meaningful way.
Instead of representing every possible exception in the group, we will build an issue by walking only the first path through
the exception tree.  In other words, SDKs will follow the chain from the captured exception to its _first_ inner exception,
repeatedly until there are no more inner exceptions.  As with the current Sentry design, these exceptions will be sent in the
[`exception`](https://develop.sentry.dev/sdk/event-payloads/exception/) interface of the event message - ordered from oldest to newest.

As an example, if the exception tree is:

- A
  - B
    - C
      - D
  - E
    - F
      - G

The corresponding issues sent in the `exceptions` interface would be `[D, C, B, A]` in that order.
The issue title would be based on exception `A`, and issue grouping would consider exceptions `A`, `B`, `C`, and `D` only.

Exceptions `E`, `F`, and `G` _should not_ be sent in the `exceptions` interface.  The reasons for this are:
- They may be representing completely different issues that shouldn't be grouped together in Sentry.
- They may be representing different quantities of the _same_ issue, and the quantity should not affect issue grouping in Sentry either.
- Sending them all in one list would imply a causal relationship between `D` and `E` (in that example), which does not exist.

However, we don't want to completely lose track of these other exceptions either.  Thus they should still be sent
with the event, but in another section instead.  We will add it to the `extras` property of the event.

The format should be as follows:

```json
"extras": {
  "exception_group": {
    "exception": {},
    "is_exception_group_type": true,
    "items": []
  }
}
```

- The name of the key within the `extras` object will be `exception_group`.
- Its value will be an object containing two properties: `exception` and `items`.
  - The `exception` property is _required_.  It is an object that conforms to the [`exception` interface](https://develop.sentry.dev/sdk/event-payloads/exception/).
  - The `is_exception_group_type` is required to be set `true` for exceptions that are actually exception groups.  In other words, `ExceptionGroup`, `AggregateException`, `AggregateError`, etc.
    - To conserve space, it should be omitted for other types of exceptions. (The default is `false` when omitted.)
  - The `items` array is _optional_.  It is an array of additional exception group objects.
- The number of nested objects is not constrained.  However, data may be truncated if the total size exceeds 16kB.

_Note: We chose `extras` over `contexts`, because items in `contexts` are limited to 8kB, whereas items in `extras` are limited to 16kB, per [documentation](https://develop.sentry.dev/sdk/data-handling/#variable-size)._

### Additional SDK requirements

The SDK should set a pre-formatted message on the event (via `logentry.formatted`) to the following text:
> _"This issue was raised as part of an exception group. See the Additional Data section for details."_

The SDK should also provide an option to control whether top-level exception groups are kept with the list of exceptions, or stripped away.
- The name of this option should be platform specific.  For example, `KeepAggregateExceptions` in .NET, or `keep_exception_groups` in Python.
- When `false`, after deriving the `exceptions` array as previously described, the array is trimmed until reaching an exception that is not the exception group type.
- The default should be `false`, such that exception groups themselves do not become the titles of issues by default.

For example, if the exception group is:

- `ExceptionGroup`
  - `ExceptionGroup`
    - `ValueError`
      - `ExceptionGroup`
        - `TypeError`
        - `ReferenceError`
    - `SyntaxError`
      - `NameError`
  - `MemoryError`
    - `BufferError`
      - `ArithmeticError`

Then:
- When `keep_exception_groups` is `true`:
  - `exceptions` is `[TypeError, ExceptionGroup, ValueError, ExceptionGroup, ExceptionGroup]`
- When `keep_exception_groups` is `false`:
  - `exceptions` is `[TypeError, ExceptionGroup, ValueError]`

Recall that exceptions are sent to Sentry from oldest to newest, and that we discard all but the first-path through the tree.
Also note that exception groups in the middle of the first-path chain should be retained.  Only the end is trimmed.

### Example Event

The following shows the properties sent on a Sentry `event` object related to this specification.

In this .NET example, the title of the issue is `"System.InvalidOperationException: An invalid operation occurred."`.
The exception chain has two exceptions in it, and the extras contains the full exception tree, including the top-level
`AggregateException`, and an ancillary `NullReferenceException`.  A log entry message is also added to the event to assist the user.

Note that for brevity of this example, only `type` and `value` have been supplied for each exception.
In practice, the entire `exception` interface is valid for each object, including `type`, `value`, `stacktrace`, `module`, `mechanism`, and `thread_id`.

```json
{
  "logentry": {
    "formatted": "This issue was raised as part of an exception group. See the Additional Data section for details."
  },
  "exception": {
    "values": [
      { "type": "System.IO.FileNotFoundException", "value": "A file was not found." },
      { "type": "System.InvalidOperationException", "value": "An invalid operation occurred." }
    ]
  },
  "extras": {
    "exception_group": {
      "exception": { "type": "System.AggregateException", "value": "One or more exceptions occurred." },
      "is_exception_group_type": true,
      "items": [
        {
          "exception": { "type": "System.InvalidOperationException", "value": "An invalid operation occurred." },
          "items": [
            {
              "exception": { "type": "System.IO.FileNotFoundException", "value": "A file was not found." }
            }
          ]
        },
        {
          "exception": { "type": "System.NullReferenceException", "value": "Object reference not set to an instance of an object." }
        }
      ]
    }
  }
}
```

### Sentry UI Changes

The `exception_group` section added to `extras` may generally be difficult to read in JSON format, especially if the individual
exceptions contain `stacktrace` elements.  To support Phase 2 (described below), we need all of the exception information to be
retained with the event.  However, we only need the UI to show a minimal representation.

In general, the design should have the following features:
- Tree-like, with expand/collapse features.
- The first level should be expanded by default.
- The `type` and `value` of each exception should be visible.
- The design _may_ incorporate features of the stack trace (such as the first line containing file name, function name, etc.)
  - However, the design shall not require symbolication to have occurred.
    (Only the exception in the `exceptions` section will be symbolicated, not the exception within `exception_group`.)

A UI design is forthcoming. A mockup will be added here when ready.


## Phase 2

_NOTE: This phase describes work that would add additional value, but is not a firm requirement.
Sentry has not yet committed implementing this._

In the first phase, the focus was on ensuring that all of the exception group information was captured, and that
the issue which appears in Sentry represents one single item to focus on.  In this second phase, Sentry will
generate additional issues using the extra exception group information.

### Mechanism

During Sentry's event processing, if the `exception_groups` section is present, then a message will be added to a queue.
A background event processor will receive incoming messages from that queue.  It's focus is to identify additional events to create.
An event will be generated for any event that is part of a top-level exception group, other than primary event (since it already exists).

The event processor should consider whether the primary event was generated with or without the leading exception groups
(as controlled by `keep_exception_groups` in the SDKs) and follow suit.

As an example, if the exception tree is:

- A
  - B
    - C
      - D
  - E
    - F
      - G

If the primary event contained exceptions `[D, C, B, A]`, then the processor should generate a new event containing exceptions `[G, F, E, A]`.

However, if the primary event contained exceptions `[D, C, B]`, then the processor should generate a new event containing exceptions `[G, F, E]`.

Consider another more detailed example:

- `ExceptionGroup`
  - `ExceptionGroup`
    - `ValueError`
      - `ExceptionGroup`
        - `TypeError`
        - `ReferenceError`
    - `SyntaxError`
      - `NameError`
  - `MemoryError`
    - `BufferError`
      - `ArithmeticError`

Assuming the SDK had `keep_exception_groups=false` it would have sent the primary event with exceptions `[TypeError, ExceptionGroup, ValueError]`.
The processor shall create additional events having exceptions as follows:

- `[NameError, SyntaxError]`
- `[ArithmeticError, BufferError, MemoryError]`

Note that it does _not_ need to create an event for `[ReferenceError, ExceptionGroup, ValueError]`, because there was already an event whose
latest exception was `ValueError`.  This means that not every possible path through the tree will lead to a separate event.

The processor should only create a new event for each new top-level exception.  In other words, it will traverse the tree from the
root node until it finds an exception where the `is_exception_group_type` flag is `false` (or absent).

Lastly, consider that if `keep_exception_groups` had been `true`, then the primary event would have had exceptions
`[TypeError, ExceptionGroup, ValueError, ExceptionGroup, ExceptionGroup]`.  Thus the two new events should have exceptions as follows:

- `[NameError, SyntaxError, ExceptionGroup, ExceptionGroup]`
- `[ArithmeticError, BufferError, MemoryError, ExceptionGroup]`

### Additional Processing Requirements

When the processor generates new issues, most of the of the information the SDK sent with the original issue shall be retained, including:

- Event level properties such as `timestamp`, `platform`, `level`, etc.
- `breadcrumbs`
- `contexts`
- `debug_meta`
- `extras` (including `exception_group`)
etc.

The only new information on the event shall be `event_id` and `exception`.

Any fields of the fields generated via processing of the original event should be omitted (such as title, culprit, and issue grouping details).
The event will then be put back through processing to generate remaining data based on the new set of exceptions.
A flag can be added to `_meta` with the new event, which can be subsequently checked to prevent reprocessing loops.

Additionally, the processor may impose some arbitrary limits on the number of events it will generate from a given exception group.
When doing so, it should try to generate at least one event of each _different_ top-level exception `type` in the group.

## Summary

- At the end of Phase 1, only one "primary exception" from an exception group will be present as a Sentry issue.
- At the end of Phase 2, all remaining top-level exceptions represented by an exception group will be present as Sentry issues.

# Drawbacks 

- Modifying the way Exceptions are sent to Sentry will affect existing issue grouping rules
  that customers may have set up.  This change could create new alerts when first deployed.

- The design proposed above does retain backwards compatibility with older versions of Sentry.
  However, without the proposed UI changes, previous versions (self-hosted, etc.) of Sentry
  will display the exception group as formatted JSON.  This could be a bit confusing to the user,
  until such time they upgrade their Sentry instance to a version that includes the UI changes.

# Unresolved questions

We'll need to decide an order of precedence for languages that can capture exceptions independently
from a cause (`cause` not necessarily `exceptions[0]`).  This is currently being discussed for Python
at https://github.com/getsentry/sentry-python/issues/1788#issuecomment-1483247910

JavaScript and other languages should follow suit, once decided.

# Other Options Considered

We considered the following, each had pitfalls that led to the plan described above.

## Do Nothing

This would mean leaving things the way they currently are.

Pros:

- Nothing to do.

Cons:

- Issues created by SDKs other than .NET are titled and grouped by the exception group instead of an actionable exception,
  and do not necessarily include the entire chain of exceptions.
- Issues created by the .NET SDK have the issues described in the next section, "Unwinding the Exception Tree".
- Overall, reduced ability to use Sentry for error monitoring, as the usage of exception groups increases.

## Unwinding the Exception Tree

Without any modification to ingest or UI, the SDKs can attempt to unwind the tree of exception groups,
flattening them into a single list of exceptions.  Then, the containing exception group can (optionally) be discarded.

The .NET SDK currently does this (as of v3.18.0, June 2022), but it is considered a hack and
has many disadvantages.  This option would have the other SDKs copy these hacks from .NET.

Pros:

- SDK changes are straightforward.
- Already implemented in the .NET SDK.
- Doesn't require any protocol, ingest, or UI changes.

Cons:

- Doesn't accurately represent the exception group.
- Implies a causal relationship between sibling exception that doesn't exist.
- Obscures the actual causal relationships between parent and child exceptions.
- In some cases, requires relocating stack traces from the exception group to the first
  child exception, otherwise no code location will be represented.  Doing so grossly
  misrepresents the true nature of the exception caused at the highlighted stack frame.
- In other cases, there are already stack traces on both the exception group and the
  first child exception.  Thus the location of the exception group will be completely lost.

## Splitting Events in the SDK

This approach would involve the SDK sending multiple separate events for each top-level exception in an exception group.

Pros:

- All exceptions would come through at once.
- No server-side processing would need to be performed.

Cons:

- Too much duplicate date is sent from the SDK at run time.
- It can quickly exceed the SDKs internal maximum queue length.
- It can trigger rate limits and spike-protection mechanisms.

## Splitting Events in Relay

This approach would involve the SDK sending one event containing the exception group, and relying on Sentry Relay
to split out top-level exceptions into separate events.
It would require the creation of a new `exception_group` interface, placed directly on the incoming event.

Pros:

- One event sent from the SDK, so none of the cons involved with splitting in the SDK.

Cons:

- Could be very CPU intensive.
- Too much business logic.
- Could back up overall ingestion throughput.
- Would not be backwards compatible with the existing event schema.

## Presenting the Entire Exception Group in one Issue

This approach would involve keeping the exception group intact as a single issue, rather than splitting
it apart anywhere.  Like the previous option, it would require the creation of a new `exception_group`
interface, placed directly on the incoming event.  However it would also require a new workflow in Sentry
and a new user interface.

Pros:

- One event passed all the way through the system.

Cons:

- Requires an entirely new way to think about events and issues.
- Significant UI work, most likely leading to a UI that is not very user friendly.
- Would not be backwards compatible with the existing event schema.

## Using "Synthetic" Exceptions

This would remove the `keep_exception_groups` SDK option, and instead _always_ keep
exception groups - but mark them as `synthetic` (in the `mechanism` details).

Pros:

- One less option in the SDK.
- Only one way to display and process exception groups.
- Renders stack trace of the exception group types.

Cons:

- Title of issue would be incorrect, referring to the first in-app frame of the exception group.
- Issue grouping would be incorrect, including details of the exception group.
