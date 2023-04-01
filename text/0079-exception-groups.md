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
Simply capturing the exception group by itself is insufficient, and current workarounds are problematic.

See also:
- [Python user feedback](https://github.com/getsentry/sentry/issues/37716)
- [.NET user feedback](https://github.com/getsentry/sentry-dotnet/issues/270)
- [JavaScript user feedback](https://github.com/getsentry/sentry-javascript/issues/5469)

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

**NOTE**: _This has changed significantly from prior versions of the draft RFC._

We will focus having the SDKs capture all available information, and adjust the issue grouping rules in Sentry to use that new information.

**The SDKs will do the following:**

- Capture the entire tree of exceptions represented by the exception group.
- Capture any other chained exceptions that are not part of the exception group.
- Use the existing `exception` value of the Sentry event.
- Add a few new fields to each exception's `mechanism` data, as described below.

**Sentry will do the following:**

- Take the new mechanism fields into account when grouping issues.  See [Sentry Issue Grouping](#sentry-issue-grouping) below for more details.
- Present a user interface that depicts the structure of the exception group on the issue details page.  See [Sentry UI Changes](#sentry-ui-changes) below for more details.

## Important Notice

The new grouping rules _MUST_ be fully implemented in Sentry.io and a published version of self-hosted
Sentry before any SDK can release a non-preview version that includes these changes.  The SDK's release notes
should mention the required version of Sentry.

Although the protocol changes are backwards compatible, the current problems
with exception groups will persist or be exacerbated without the new grouping rules in place.

SDKs that currently require the user to opt-in to send chained exceptions can continue to do so without side-effects.
SDKs that send chained exceptions _by default_ may see an immediate change to exception grouping after implementing this feature.

## New Mechanism Fields

The [Exception Mechanism Interface](https://develop.sentry.dev/sdk/event-payloads/exception/#exception-mechanism)
will have the following new fields added:

### `source`

An optional string value describing the source of the exception.

- The SDK should populate this with the name of the property or attribute of the parent exception that this exception
  was acquired from.  In the case of an array, it should include the zero-based array index as well.
- Python Examples: `"__context__"`, `"__cause__"`, `"exceptions[0]"`, `"exceptions[1]"`
- .NET Examples:  `"InnerException"`, `"InnerExceptions[0]"`, `"InnerExceptions[1]"`
- JavaScript Examples: `"cause"`, `"errors[0]"`, `"errors[1]"`

### `is_exception_group`

An optional boolean value, set `true` when the exception is the exception group type specific to the platform or language.
The default is `false` when omitted.

- For example, exceptions of type `ExceptionGroup` (Python), `AggregateException` (.NET), and `AggregateError` (JavaScript)
  should have `"is_exception_group": true`.  Other exceptions can omit this field.

### `exception_id`

An optional numeric value providing an ID for the exception relative to this specific event.

- The SDK should assign simple incrementing integers to each exception in the tree, starting with `0` for the root of the tree.
  In other words, when flattened into the list provided in the `exception` values on the event, the last exception
  in the list should have ID `0`, the previous one should have ID `1`, the next previous should have ID `2`, etc.

### `parent_id`

An optional numeric value pointing at the `exception_id` that is the parent of this exception.

- The SDK should assign this to all exceptions _except_ the root exception (the last to be listed in the `exception` values).

## Interpretation

The `exception_id` and `parent_id` fields work in conjunction to represent the hierarchical nature of the tree of exceptions.
If not provided, the previous interpretation will be assumed - which is that each exception in the list of `exception` values
is a child of the one immediately following it in the list.

The [Exception Interface](https://develop.sentry.dev/sdk/event-payloads/exception/) will not change in structure,
but it will change in _interpretation_ with regard to multiple exception values.

- The previous interpretation was: _"Multiple values represent chained exceptions."_.
- The new interpretation will be: _"Multiple values are related by the optional `mechanism.exception_id`
  and `mechanism.parent_id` fields. When not present, multiple values represent chained exceptions."_


## Additional SDK Requirements

### Mechanism Type

When setting the `mechanism.type` field, SDKs should use the following guidelines:

- For the root exception (the last to be in the `exception.values` list), set `mechanism.type` to the name
  of the integration that produced the exception (as was the case before this proposal).  If the exception was
  captured manually, set the `mechanism.type` to `"generic"`.

- For all other exceptions in the list, set the `mechanism.type` to `"chained"`.  This will indicate that the exception
  is part of the chain of exceptions stemming from the root exception (regardless of whether it is in an exception group or not).

Do not omit the `mechanism.type` field, nor send it empty or null.

### Exception Value
 
When setting the `value` field of the exception for an exception group type, SDKs should only deliver the meaningful part
of the exception message, excluding any string that may have been automatically added by their platform.

For example:

- In Python, the `value` field should not contain details such as `" (2 sub-exceptions)"`.  Use the `message` attribute to get the raw message from an `ExceptionGroup`.  If there is no message, omit the `value` and just send `type`.

- In .NET, the `value` field should not contain details such as `" (Exception 1) (Exception 2)"`.  The following extension method can be used to get the raw message:

  ```csharp
  internal static string GetRawMessage(this AggregateException exception)
  {
    var message = exception.Message;
    return exception.InnerException is { } inner
      ? message[..message.IndexOf($" ({inner.Message})", StringComparison.Ordinal)]
      : message;
  }
  ```

### Keep Aggregate Exceptions

The .NET SDK previously had implemented an option called `KeepAggregateExceptions`.  This flag should be deprecated,
in favor of _always_ sending the entire chain of aggregate exceptions as explained in this SDK.  This may affect
existing issue grouping, and should be noted in the change log when released.

Other SDKs should _not_ implement a similar option.

## Example Event

Given the Python code:

```python
try:
  raise RuntimeError("something")
except:
  raise ExceptionGroup("nested",
    [
      ValueError(654),
      ExceptionGroup("imports",
        [
          ImportError("no_such_module"),
          ModuleNotFoundError("another_module"),
        ]
      ),
      TypeError("int"),
    ]
  )
```

The event would contain:

```json
{
  "exception": {
    "values": [
      {
        "type": "TypeError",
        "value": "int",
        "mechanism": {
          "type": "chained",
          "source": "exceptions[2]",
          "exception_id": 6,
          "parent_id": 0
        }
      },
      {
        "type": "ModuleNotFoundError",
        "value": "another_module",
        "mechanism": {
          "type": "chained",
          "source": "exceptions[1]",
          "exception_id": 5,
          "parent_id": 3
        }
      },
      {
        "type": "ImportError",
        "value": "no_such_module",
        "mechanism": {
          "type": "chained",
          "source": "exceptions[0]",
          "exception_id": 4,
          "parent_id": 3
        }
      },
      {
        "type": "ExceptionGroup",
        "value": "imports",
        "mechanism": {
          "type": "chained",
          "source": "exceptions[1]",
          "is_exception_group": true,
          "exception_id": 3,
          "parent_id": 0
        }
      },
      {
        "type": "ValueError",
        "value": "654",
        "mechanism": {
          "type": "chained",
          "source": "exceptions[0]",
          "exception_id": 2,
          "parent_id": 0
        }
      },
      {
        "type": "RuntimeError",
        "value": "something",
        "mechanism": {
          "type": "chained",
          "source": "__context__",
          "exception_id": 1,
          "parent_id": 0
        }
      },
      {
        "type": "ExceptionGroup",
        "value": "nested",
        "mechanism": {
          "type": "generic",
          "handled": false,
          "is_exception_group": true,
          "exception_id": 0
        }
      },
    ]
  }
}
```

**Reminder:** In .NET, `InnerException` is always the same as `InnerExceptions[0]`, thus it does not need to be reported separately.
However, Python's `__cause__` and `__context__`, and JavaScript's `cause`, are independent and thus _should_ be reported separately
if they have values.

## Sentry Issue Grouping

Issue grouping rules for exception groups are complex, because the nature of exception groups is that they may or may not represent
more than one distinct issue.  While this may require some further experimentation to get right, the initial plan is as follows:

First, determine the list of "top-level" exceptions.  These are the exceptions that represent distinct issues contained in
the exception group.

1. Start from the exception having `mechanism.exception_id:0`.
2. If it has `mechanism.is_exception_group:true`, then recursively search each child.
3. When reaching one where `mechanism.is_exception_group:false` (or not present), include it as a "top-level" exception,
   and do not traverse any of its child exceptions.

Next, determine from the top-level exceptions which of them would have been grouped together, had they been in separate events.

- Apply grouping rules between the top-level exception to determine the distinct number of issues represented by the group.
- For each top-level exception, only consider the first-path through any child exceptions.

Finally:

- If there is only one distinct group of top-level exceptions, group the event with other events based on that top-level exception only.
  Ignore any parent exception groups.

- If more than one distinct top-level exception exists, then group the event based on the parent exception group that they have in common.
  This will often be the root-level exception group.

As an example, consider simplified issue grouping rules that only considered the exception `type`.  When applied to an exception group such as:

- `ExceptionGroup`
  - `ValueError`
  - `TypeError`
  - `TypeError`

There are two distinct top-level exceptions, `ValueError` and `TypeError`.  They have the `ExceptionGroup` in common.
Thus the three exceptions considered for issue grouping are `ExceptionGroup`, `ValueError`, and the first `TypeError`.

Now consider this example:

- `ExceptionGroup`
  - `ExceptionGroup`
    - `ValueError`
    - `ValueError`
      - `TypeError`
    - `ValueError`
  - `ValueError`
  - `ValueError`

Then there are 5 top-level exceptions, all of type `ValueError`.  Thus, the event should only be grouped based on a single `ValueError`,
and the others should be ignored for purposes of issue grouping.  That one of them has a chained `TypeError` is not relevant,
at least not in this initial plan.

A further modification to the plan might consider all possible branches of chained exceptions, but that is not proposed at this time.

### Additional Issue Grouping Requirements

SDKs typically set `mechanism.type` and `mechanism.handled` on the root exception only (the last item in the `exception.values` list).
These fields must _always_ be considered as part of issue grouping, even if the rest of the exception group is being ignored.

## Issue Titles

As a side-effect of issue grouping, issues will be titled (and subtitled) based on the top-most exception that is not ignored from
the grouping.  In other words, if there is more than one distinct top-level exception, the issue will be titled by the exception group itself.  In the above examples, the first issue would be titled as `ExceptionGroup`, and the second issue would be titled as `ValueError`.

## Sentry UI Changes

The Issue Details page will be updated to improve usability of exception groups.  The exact details are at the discretion of the design team,
however the following should be considered:

- A condensed tree-like visualization of the exception group should be added somewhere on the page.
  Each exception in the tree should have an in-page link to jump to that exception and ensure it is expanded.
- Some exceptions should be collapsed by default, including any where `mechanism.is_exception_group === true`, and perhaps others.
- The `mechanism.source` field, if available, should be displayed on each exception in the exceptions section.
- We may want to include a way to navigate from each exception to its parent exception, or back to the exception group.

# Drawbacks 

- Modifying the way Exceptions are sent to Sentry will affect existing issue grouping rules
  that customers may have set up.  This change could create new alerts when first deployed.

- The design proposed above retains backwards compatibility with older versions of Sentry.
  However, without the proposed UI changes, previous versions (self-hosted, etc.) of Sentry
  will treat the exceptions list as if they were all one long chain of direct exceptions.
  This could be a bit confusing to the user, until such time they upgrade their Sentry
  instance to a version that includes the UI and issue grouping changes.

# Other Options Considered

We considered the following, each had pitfalls that led to the plan described above.

## Do Nothing

This would mean leaving things the way they currently are.

Pros:

- Nothing to do.

Cons:

- Overall, reduced ability to use Sentry for error monitoring, as the usage of exception groups increases.
- Events created by the .NET SDK have several problems for exception groups (`AggregateException`), such as:
  - There's no structure represented by the chain of events, so every relationship appears as parent/child, even
    those that should actually be siblings.
  - In some cases, some stack traces are relocated from the exception group to the first child exception,
    otherwise no code location will be represented.  Doing so grossly misrepresents the true nature of the
    exception caused at the highlighted stack frame.
  - In other cases, there are already stack traces on both the exception group and the
    first child exception.  Thus the location of the exception group is lost completely.
  - The `KeepAggregateException` option is global for the entire application, and can't be adjusted on a case-by-case basis.
- Issues created by other SDKs such as Python and JavaScript are not prepared to deal with exception groups at all.
  - Issues are always titled and grouped by the exception group, even when there's only a single type of exception contained within.
  - Because none of the items in the `exceptions` or `errors` lists are part of the _cause_, they're currently not passed to Sentry at all.
    This makes it impossible to identify the actual cause of an exception raised via an exception group.

## Sending Hierarchical Data

This approach was seriously considered.  It would involve creating a new tree-like data structure that more closely
resembles the original tree of exceptions.  It would have been placed on either a new `exception_group` interface,
or added to the existing `contexts` or `extra` collections.

Pros:

- The event would contain a more direct representation of the exception data.
- Less work for the SDKs.

Cons:

- Much of the server-side processing would have to be reconsidered, including relay, symbolication, and trimming.
- It would not be backwards compatible, without duplicating significant data into the exceptions list anyway.

## Sending One Exception Chain Only

This approach would involve not capturing the entire exception group, but trying to determine which top-level
exception was worth capturing, from within the SDK.

Pros:

- Fully compatible with existing Sentry, without any changes to grouping rules or UI.
- Fully backwards compatible as well.

Cons:

- Potential to loose a lot of useful data.
- Misrepresents the exception that was actually raised.
- Looses track of the actual location in source code where the exception group was raised.

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

## Using Synthetic Exceptions

This approach would set `mechanism.synthetic:true` on exception groups types, to attempt to keep them from
being considered during issue grouping.

Pros:

- If it worked, issue grouping would need less adjustment.

Cons:

- It doesn't work for this use case.
  - Title of issue would be incorrect, referring to the first in-app frame of the exception group.
  - Issue grouping would be incorrect, including details of the exception group.
