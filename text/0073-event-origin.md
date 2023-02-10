- Start Date: 2023-02-10
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/73
- RFC Status: draft

# Summary

One paragraph explanation of the feature or document purpose.

# Motivation

We, the SDK developers, would like to get insights into which types of events and transactions our customers use. Looker doesn't allow querying for different kinds of transactions at the moment. Furthermore, knowing what created an event, transaction or span helps debug SDK issues.

# Background

Looker doesn't allow querying for different kinds of transactions or events. For events, we have kind of abuse `Exception Stack Mechanism Type`, which ends up in Looker, to query for different types of events.

We use the SDK integration list to determine which organizations have specific performance integrations enabled. The downside is that the SDK sends this list for each event, not giving us insights into how many events/transactions/spans stem from a specific parts of the SDK.


# Options Considered

For every option, looker picks up this field, but we don't need to index it and make it searchable in Discover. Amplitude could look at this field as a property when users visit issue or transaction detail pages.

- [Option 1: Event SDK Origin](#option-1)
- [Option 2: Transaction Info Type](#option-2)

## Option 1: Event SDK Origin <a name="option-1"></a>

Add a new property to the [SDK interface of the event payload](https://develop.sentry.dev/sdk/event-payloads/sdk/) named `origin` to determine which part of the SDK created the event. 

The property is optional and of type string. Examples: 

- `swift-ui`
- `http-client-error`
- `sentry-crash`
- `metric-kit`
- `anr`
- `file-io-on-main-thread`
- `next-js`


### Pros <a name="option-1-pros"></a>

1. Works for all events including performance issues.

### Cons <a name="option-1-cons"></a>

1.  Doesn't work for spans.

## Option 2: Transaction Info Type <a name="option-1"></a>

Add a new property to the [transaction info](https://develop.sentry.dev/sdk/event-payloads/transaction/#transaction-annotations) named `origin`


### Cons <a name="option-2-cons"></a>

1. [Con  of option 1](#option-1-cons).
2. Naming is similar to `source` and can be confusing
3. Only works for transactions


Please add your option here: ...


# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known?
