- Start Date: 2023-02-10
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/73
- RFC Status: in progress

# Summary

This RFC aims to give Sentry developers insights into which types of transactions and spans our customers use.

# Motivation

We, the SDK developers, would like to get insights into the types of transactions / spans
our customers use, which is only partially possible when writing this.

# Background

While Looker allows queries for `Exception Stack Mechanism Type` to gain insight into
different error events, it doesn't allow querying for different transaction types. We
use the SDK integration list to determine which organizations have specific performance
integrations enabled. The downside is that the SDK sends this list for each event, not
giving us insights into how many transactions/spans stem from a specific parts of the SDK. 


# Options Considered

For every option, Looker picks up the field, but we don't need to index it and make it searchable in Discover. Amplitude could look at this field as a property when users visit transaction detail pages.

- [Option 1: Event SDK Origin](#option-1)
- [Option 2: Event Origin](#option-2)
- [Option 3: Transaction Info Type](#option-3)
- [Option 4: Use Amplitude](#option-4)
- [Option 5: Span Origin](#option-5)
- [Option 6: Trace Context and Span Origin](#option-6)


## Option 1: Event SDK Origin <a name="option-1"></a>

Add a new property to the [SDK interface of the event payload](https://develop.sentry.dev/sdk/event-payloads/sdk/) named `origin` to determine which part of the SDK created the event. 

The property is optional and of type string. Examples: 

- `swift-ui`
- `http-client-error`
- `sentry-crash`
- `metric-kit`
- `anr`
- `next-js` 


### Pros <a name="option-1-pros"></a>

1. Works for all event and transactions.
2. Works for performance issues created by SDKs.

### Cons <a name="option-1-cons"></a>

1. Doesn't work for spans.
2. Doesn't work for performance issues.
3. Extends protocol and data structures.
4. Doesn't give insight into which types of transactions/spans our users are interacting with.

## Option 2: Event Origin <a name="option-2"></a>

Similar to option 1, but `origin` is a top level optional property directly on the event, to determine what exactly created the event. It has two fields: 

- `type`: Required, type str. Identifies what created the event. At the moment it can be `sdk` or `performance-issue`.
- `name`: Required, type str. Contains more detailed information on what exactly created the event, such as: `swift-ui`, `http-client-errors`, `sentry-crash`, `metric-kit`, `anr`, `jetpack-compose`, `next-js`, `log4net`, `apollo3`, `dio.http`, `file-io-on-main-thread`, `n+1-queries`, `n+1-api-calls`, `consecutive-db-calls`, etc. 
This information is similar to `sdk.integrations`, but instead of always containing the list of all enabled integrations, this property exclusively includes the integration/part creating the event.

### Pros <a name="option-2-pros"></a>

1. Works for all existing event types including performance issues.
2. Works for future non yet existend event types.
3. Works for performance issues created by SDKs.

### Cons <a name="option-2-cons"></a>

1. Doesn't work for spans.
2. Extends protocol and data structures.
3. `type` is already available in Discover via `issue.category`.
4. Doesn't give insight into which types of transactions/spans our users are interacting with.

## Option 3: Transaction Info Type <a name="option-3"></a>

Add a new property to the [transaction info](https://develop.sentry.dev/sdk/event-payloads/transaction/#transaction-annotations) named `origin`.

### Cons <a name="option-3-cons"></a>

1. Doesn't work for spans.
2. Naming is similar to `source` and can be confusing.
3. Only works for transactions.
4. Extends protocol and data structures.
5. Doesn't give insight into which types of transactions/spans our users are interacting with.


## Option 4: Use Amplitude <a name="option-4"></a>

Most transactions/spans already contain enough information to identify the type. We can use Amplitude to grab that information, such as transaction and span names and operations, to classify them. This option works great in combination with any other option and is not mutually exclusive.

### Pros <a name="option-4-pros"></a>

1. Works for spans.
2. No need to extend protocol and data structures.
3. Gives insight into which types of transactions/spans our users are interacting with.

### Cons <a name="option-4-cons"></a>

1. It might not work for all different transactions and spans, as they could miss information to identify what created them or of which type they are.

## Option 5: Span Origin <a name="option-5"></a>

Add a `origin` property to the [span interface](https://develop.sentry.dev/sdk/event-payloads/span/), so both transactions and spans get the benefit of it. The SDK sets this property, and it's not exposed to the user to avoid high cardinality. 

The property is optional and of type str. Examples:

- `manual`
- `auto`
- `auto.swift-ui`
- `auto.core-data`
- `auto.ui-view-controller`
- `auto.file-io`
- `auto.app-start`
- `auto.jetpack-compose`

```json
"trace": {
    "trace_id": "40072a6227d648449aa8665307a1fde3",
    "span_id": "f2e763bf95c640df",
    "op": "ui.load",
    "status": "ok",
    "exclusive_time": 23.461104,
    "hash": "e2839639c27b6393",
    "sampled": "true",
    "start_timestamp": 1679374744.0518713,
    "timestamp": 1679374744.6143088,
    "type": "trace",
    "origin": "auto.ui-view-controller",
}
```

```json
{
  "spans": [
    {
      "start_timestamp": 1588601261.481961,
      "description": "loadView",
      "timestamp": 1588601261.488901,
      "parent_span_id": "f2e763bf95c640df",
      "trace_id": "40072a6227d648449aa8665307a1fde3",
      "op": "ui.load",
      "span_id": "b01b9f6349558cd1",
      "origin": "auto.ui-view-controller",
    },
    {
      "start_timestamp": 1588601261.535386,
      "description": "BYZ-38-t0r-view-8bC-Xf-vdC.nib",
      "timestamp": 1588601261.544196,
      "parent_span_id": "f2e763bf95c640df",
      "trace_id": "40072a6227d648449aa8665307a1fde3",
      "op": "file.read",
      "span_id": "b980d4dec78d7344",
      "origin": "auto.file-io",
    },
    {
      "timestamp": 1679374744.587838,
      "start_timestamp": 1679374744.587426,
      "exclusive_time": 0.411987,
      "description": "calculatePI",
      "op": "ui.load",
      "span_id": "800b9c31b7f34ba2",
      "parent_span_id": "f2e763bf95c640df",
      "trace_id": "40072a6227d648449aa8665307a1fde3",
      "status": "ok",
      "origin": "manual",
    },
  ]
}
```

### Pros <a name="option-5-pros"></a>

1. Helps users to understand which parts of transactions where auto or manually instrumented.
2. This addition can help the performance product to build new features and performance issues.

### Cons <a name="option-5-cons"></a>

1. Most of the time, the spans already contain enough information to know if they were auto or manually created. The extra property is redundant in most cases.
2. Doesn't give insight into which types of transactions/spans our users are interacting with.
3. Extends protocol and data structures.

## Option 6: Trace Context and Span Origin <a name="option-6"></a>

Same as [option 5](#option-5), but also add a `origin` property to the [trace context](https://develop.sentry.dev/sdk/event-payloads/contexts/#trace-context).

```json
{
  "contexts": {
    "trace": {
      "op": "navigation",
      "description": "User clicked on <Link />",
      "trace_id": "743ad8bbfdd84e99bc38b4729e2864de",
      "span_id": "a0cfbde2bdff3adc",
      "status": "ok",
      "origin": "auto.user-interaction-tracing",
    }
  }
}
```

### Pros <a name="option-6-pros"></a>

1. Helps users to understand which parts of transactions where auto or manually instrumented.
2. This addition can help the performance product to build new features and performance issues.

### Cons <a name="option-6-cons"></a>

1. Two different locations for the same information.

# Drawbacks

- Each solution except [option 4](#option-4) requires extending the protocol.

Please comment if you see any drawbacks.

# Unresolved questions

- How does Looker pick up these properties?
- Should we make the option searchable in Discover?
- What extra data do we need to send to Amplitude to be able to move forward with [option 4](#option-4)?
