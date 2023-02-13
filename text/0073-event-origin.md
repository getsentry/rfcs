- Start Date: 2023-02-10
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/73
- RFC Status: draft

# Summary

This RFC aims to give Sentry developers insights into which types of events and transactions our customers use.

# Motivation

We, the SDK developers, would like to get insights into the types of events and transactions
our customers use, which is only partially possible when writing this.

# Background

While Looker allows queries for `Exception Stack Mechanism Type` to gain insight into
different error events, it doesn't allow querying for different transaction types. We
use the SDK integration list to determine which organizations have specific performance
integrations enabled. The downside is that the SDK sends this list for each event, not
giving us insights into how many events/transactions/spans stem from a specific parts
of the SDK. 
Furthermore, knowing what created an event, transaction, or span helps investigating issues.


# Options Considered

For every option, Looker picks up the field, but we don't need to index it and make it searchable in Discover. Amplitude could look at this field as a property when users visit issue or transaction detail pages.

- [Option 1: Event SDK Origin](#option-1)
- [Option 2: Event Origin](#option-2)
- [Option 3: Transaction Info Type](#option-3)


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

## Option 2: Event Origin <a name="option-2"></a>

Similar to option 1, but `origin` is a top level optional property directly on the event, to determine what exactly created the event. It has two fields: 

- `type`: Required, type str. Identifies what created the event. At the moment it can be `sdk` or `performance-issue`.
- `name`: Required, type str. Contains more detailed information on what exactly created the event, such as: `swift-ui`, `http-client-errors`, `sentry-crash`, `metric-kit`, `anr`, `jetpack-compose`, `next-js`, `flask`, `django`, `log4net`, `apollo3`, `dio.http`, `file-io-on-main-thread`, `n+1-queries`, `n+1-api-calls`, `consecutive-db-calls`, etc. 
This information is similar to `sdk.integrations`, but instead of always containing the list of all enabled integrations, this property exclusively includes the integration/part creating the event.

### Pros <a name="option-2-pros"></a>

1. Works for all existing event types including performance issues.
2. Works for future non yet existend event types.
3. Works for performance issues created by SDKs.

### Cons <a name="option-2-cons"></a>

1. [Con  of option 1](#option-1-cons).

## Option 3: Transaction Info Type <a name="option-3"></a>

Add a new property to the [transaction info](https://develop.sentry.dev/sdk/event-payloads/transaction/#transaction-annotations) named `origin`


### Cons <a name="option-3-cons"></a>

1. [Con  of option 1](#option-1-cons).
2. Naming is similar to `source` and can be confusing
3. Only works for transactions


Please add your option here: ...

# Drawbacks

- Each solution requires extending the protocol.

Please comment if you see any drawbacks.

# Unresolved questions

- How does Looker pick up these properties?
- Should we make the option searchable in Discover?
