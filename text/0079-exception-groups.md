- Start Date: 2023-03-06
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/79
- RFC Status: draft

# Summary

This RFC is intended to capture the changes required to Sentry to handle *exception groups*,
including changes to SDKs, protocol schema, ingestion, and UI.

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
But even in that case, the exception presented in Sentry would not be titled or grouped correctly.

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

Sending this to Sentry would result in an issue titled `"ExceptionGroup: Exception Group (1 sub-exception)"`,
which is unactionable.

# Supporting Data

- [Python customer feedback](https://github.com/getsentry/sentry/issues/37716)
- [.NET customer feedback](https://github.com/getsentry/sentry-dotnet/issues/270)

# Options Considered

## Option 1

Do nothing.

Pros:
- Nothing to do.

Cons:
- Issues are titled and grouped by the exception group instead of an actionable exception.
- Exception groups with the same sub-exceptions but different quantities of them will be grouped into separate issues.
- Exception groups with different sub-exceptions will be grouped into separate issues with identical titles.

## Option 2

Without any modification to ingest or UI, the SDKs can attempt to unwind exception groups,
flattening them into a single list of exceptions.  Then, the containing exception group can
(optionally) be discarded.

The .NET SDK currently does this (as of v3.18.0, June 2022), but it is considered a hack and
has many disadvantages.

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

## Option 3a

The SDK can send only the top-level items of an exception group in a new `exception_group` interface,
instead of the existing `exception` interface.

Example:

```json
{
  "exception_group": {
    "type": "exception_group",
    "value": "Exception Group (2 sub-exceptions)",
    "items": [
      {
        "values": [
          {"type": "Exception 1b", "value": "Description of Exception 1b"},
          {"type": "Exception 1a", "value": "Description of Exception 1a"},
          {"type": "Exception 1", "value": "Description of Exception 1"}
        ]
      },
      {
        "values": [
          {"type": "Exception 2b", "value": "Description of Exception 2b"},
          {"type": "Exception 2a", "value": "Description of Exception 2a"},
          {"type": "Exception 2", "value": "Description of Exception 2"}
        ]
      }
    ]
  }
}
```

_Note: The example here shows only `type` and `value`, but any of the other optional properties
(ex: `stacktrace`) would also be applicable to the `exception_group`._

Upon receiving the event, ingest/relay would break apart the exception group and create
separate events for each item within it.  Each event would have all information from the
original event, except for the following:
- Its `exception` interface would be populated with the `values` of the individual item.
- Its `exception_group` would have the `items` property removed.
- A UUID for the exception group would be created and assigned to an `id` property
  on the `exception_group` interface.  All split events would share the same `id`, and this
  would be an indexed property (for filtering).

The UI would be updated such that:
- Events containing an `exception_group` have the details of the group presented above
  the actual first exception in the event.
- A link is presented to navigate to other events in the exception group.  When clicked,
  it will go to the issues list page, filtered by the corresponding `exception_group.id`.

Pros:
- SDK changes are straightforward.
- UI changes are minimal.
- Accurately represents the most useful parts of the exception group.

Cons:
- Requires protocol, ingest, and UI changes.
- Discards some components of the exception group.  Specifically, if a nested inner exception
  contains an exception group, only the first child of that group will come through.

Example of discarded information:

- Group A
  - Exception 1
  - Group B
    - Exception 2
    - Exception 3

With this design, the SDK will not be able to send `Exception 3`.  Instead it would send:

```json
{
  "exception_group": {
    "value": "Group A",
    "items": [
      {
        "values": [
          {"value": "Exception 1"}
        ]
      },
      {
        "values": [
          {"value": "Exception 2"},
          {"value": "Group B"}
        ]
      }
    ]
  }
}
```

## Option 3b

Similar to option 3a, but reusing the `exception` interface instead of creating a new interface.

- A `group` property would be added, containing the details of the exception group.
- A `group_id` property would be appended to each item in the `values` array to cluster exceptions
  that belong to the same top-level exception.

```json
{
  "exception": {
    "group": {
      "type": "Exception Group",
      "value": "Exception Group (2 sub-exceptions)"
    },
    "values": [
      {"type": "Exception 2b", "value": "Description of Exception 2b", "group_id": "2"},
      {"type": "Exception 2a", "value": "Description of Exception 2a", "group_id": "2"},
      {"type": "Exception 2", "value": "Description of Exception 2", "group_id": "2"},
      {"type": "Exception 1b", "value": "Description of Exception 1b", "group_id": "1"},
      {"type": "Exception 1a", "value": "Description of Exception 1a", "group_id": "1"},
      {"type": "Exception 1", "value": "Description of Exception 1", "group_id": "1"}
    ]
  }
}
```

_Note: The example here shows only `type` and `value`, but any of the other optional properties
(ex: `stacktrace`) would also be applicable to the `group`._

Pros and cons are similar to 3a, except additional benefit is that it's backward compatible.
If sent to a Sentry self-hosted or single-tenant instance that has not been upgraded to detect
the change, the `group` and `group_id` information will be ignored - the effect being similar
to option 2.

## Option 4a

The SDK can send the entire tree of an exception group in a new interface, including exceptions
that are themselves nested exception groups.

The protocol design would be similar to option 3a, but allowing for any item with the `items` array
to use either the `exception` or `exception_group` interface.

Pros:
- SDK changes are straightforward.
- Accurately represents the entire exception group.

Cons:
- Requires protocol, ingest, and UI changes.
- UI changes are complicated.  The design would require multiple interactive pivots
  within the exception section of the issue details page.  The resulting design
  would likely confuse end-users, as not all information about the nested exception
  groups could be displayed at the same time.

## Option 4b

Similar to option 4a, but reusing the `exception` interface instead of creating a new interface.

_TBD_

# Drawbacks

- Modifying the way Exceptions are sent to Sentry will affect existing issue grouping rules
  that customers may have set up.  This change could create new alerts when first deployed.

- The changes to the Sentry protocol would not necessarily be backwards compatible with
  previous versions.  That would impact self-hosted and single-tenant customers, in that
  they would require the newer version of Sentry before they could be compatible with the
  newer SDK versions that implement this change.  This risk could be mitigated by adding an
  option to the SDK configuration to enable or disable this feature.

# Unresolved questions

- Should we put a maximum limit on the number of exceptions allowed within an exception group?
  (If so, SDKs would truncate.)
