- Start Date: 2023-06-12
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/101
- RFC Status: draft
- RFC Driver: [Abhijeet Prasad](https://github.com/abhiprasad)

# Summary

This RFC proposes to revamp the performance API in the SDKs. The new API aims to accomplish the following:

- Align both the internal schemas and top level public API with OpenTelemetry and their SDKs.
- De-emphasize the concept of transactions from users using a Sentry performance monitoring SDK.
- Optimize for making sure performance data is always sent to Sentry.
- Open the SDK up for future work where we support batch span ingestion instead of relying on a transaction solely.

# Planned Work

The RFC proposal comes in two steps.

1. Introduce three new top level methods, `Sentry.startActiveSpan` and `Sentry.startSpan` and their language specific variants as well as `Sentry.setMeasurement`.

This allows us to de-emphasize the concept of hubs, scopes and transactions from users, and instead have them think about just spans. Under the hood, `Sentry.startActiveSpan` and `Sentry.startSpan` should create transactions/spans as appropriate. `Sentry.setMeasurement` is used to abstract away `transaction.setMeasurement` and similar.

1. Introduce a new span schema that is aligned with OpenTelemetry.

We change the data model that is referenced and used internally inside the SDK to better reflect OpenTelemetry. This involves adding shims for backwards compatibility and removing redundant fields.

# Background

Right now every SDK has both the concept of transactions and spans - and to a user they both exist as vehicles of performance data. In addition, the transaction exists as the carrier of distributed tracing information ([dynamic sampling context](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/) and [sentry-trace info](https://develop.sentry.dev/sdk/performance/#header-sentry-trace)), although this is going to change with the advent of tracing without performance support in the SDKs.

Below is JavaScript example of how to think about performance instrumentation in the JavaScript SDKs (browser/node)

```jsx
// op is defined by https://develop.sentry.dev/sdk/performance/span-operations/
// name has no specs but is expected to be low cardinality
const transaction = Sentry.startTransaction({
  op: "http.server",
  name: "GET /",
});

// Need to set transaction on span so that integrations
// can attach spans (I/O operations or framework-specific spans)
// to the correct parent.
Sentry.getCurrentHub().getScope().setSpan(transaction);

// spans have a description, while transactions have names
// op is an optional attribute, but a lot of the product relies on it
// existing.
// description technically should be low cardinality, but we have
// no explicit documentation to say that it should (since spans
// were not indexed at all for a while).
const span = transaction.startChild({ description: "Long Task" });
expensiveAction();
span.finish();

anotherAction();

const secondSpan = transaction.startChild({ description: "Another Task" });

// transaction + all child spans sent to Sentry only when `finish()` is called.
transaction.finish();
Sentry.getCurrentHub().getScope().setSpan(undefined);

// second span info is not sent to Sentry because transaction is already finished.
secondSpan.finish();
```

In our integrations that add automatic instrumentation, things look something like so:

```jsx
const parentSpan = Sentry.getCurrentHub().getSpan();

// parentSpan can be undefined if no span is on the scope, this leads to
// child span just being lost
const span = parentSpan?.startChild({ description: "something" });

Sentry.getCurrentHub().getScope().setSpan(span);

work();

span.finish();

// span is finished, so parent is put back onto scope
Sentry.getCurrentHub().getScope().setSpan(parentSpan);
```

Most users do the above also when nested within their application, as often you assume that a transaction is defined that you can attach (very common in a web server context).

To add instrumentation to their applications, users have to know concepts about hubs/scopes/transactions/spans and understand all the different nuances and use cases. This can be difficult, and presents a big barrier to entry for new users.

Also, since transactions/spans are different classes (span is a parent class of transaction), users have to understand the impacts that the same method will have on both the transaction/span. For example, currently calling `setTag` on a transaction will add a tag to the transaction event (which is searchable in Sentry), while `setTag` on a span just adds it to the span, and the field is not searchable. `setData` on a span adds it to `span.data`, while `setData` on a transaction is undefined behaviour (some SDKs throw away the data, others add it to `event.extras`).

Summarizing, here are the core Issues in SDK Performance API:

1. Users have to understand the difference between spans/transactions and their schema differences.
2. Users have to set/get transactions/spans from a scope (meaning they also have to understand what a scope/hub means).
3. Nesting transactions within each other is undefined behaviour - no obvious way to make a transaction a child of another.
4. If a transaction finishes before it’s child span finishes, that child span gets orphaned and the data is never sent to Sentry. This is most apparent if you have transactions that automatically finish (like on browser/mobile).
5. Transactions have a max child span count of 1000 which means that eventually data is lost if you keep adding child spans to a transaction.

# Improvements

## New SDK API

The new SDK API has the following requirements:

1. Newly created spans must have the correct trace and parent/child relationship
2. Users shouldn’t be burdened with knowing if something is a span/transaction
3. Spans only need a name to identify themselves, everything else is optional.
4. The new top level APIs should be as similar to the OpenTelemetry SDK public API as possible.

There are two top level methods we'll be introducing to achieve this: `Sentry.startActiveSpan` and `Sentry.startSpan`. `Sentry.startActiveSpan` will take a callback and start/stop a span automatically. In addition, it'll also set the span on the current scope. Under the hood, the SDK will create a transaction or span based on if there is already an existing span on the scope.

```ts
namespace Sentry {
  declare function startActiveSpan<T>(
    spanContext: SpanContext,
    callback: (span: Span) => T
  ): T;
}

// span that is created is provided to callback in case additional
// attributes have to be added.
// ideally callback can be async/sync
const returnVal = Sentry.startActiveSpan(
  { name: "expensiveCalc" },
  (span: Span) => expensiveCalc()
);

// If the SDK needs async/sync typed different we can expose this
// declare function startActiveSpanAsync<T>(
//   spanContext: SpanContext,
//   callback: (span: Span) => Promise<T>,
// ): Promise<T>;
```

In the ideal case, `startActiveSpan` should generally follow this code path.

1. Get the active span from the current scope
2. If the active span is defined, create a child span of that active span based on the provided `spanContext`, otherwise create a transaction based on the provided `spanContext`.
3. Run the provided callback
4. Finish the child span/transaction created in step 2
5. Remove the child span/transaction from the current scope and if it exists, set the previous active span as the active span in the current scope.

If the provided callback throws an exception, the span/transaction created in step 2 should be marked as errored. This error should not be swallowed by `startActiveSpan`.

`Sentry.startSpan` will create a span, but not set it as the active span in the current scope.

```ts
namespace Sentry {
  declare function startSpan(spanContext: SpanContext): Span;
}

// does not get put on scope
const span = Sentry.startSpan({ name: "expensiveCalc" });

expensiveCalc();

span.finish();
```

The only methods that all SDKs are required to implement are `Sentry.startActiveSpan` and `Sentry.startSpan`. For languages that need it, they add an additional method for async callbacks: `Sentry.startActiveSpanAsync`. Other languages can also attach a suffix to the methods to indicate that the spans are being started from different sources, but these are language/framework/sdk dependent.

For example with go:

```go
sentry.StartSpanFromContext(ctx, spanCtx)
```

Or when continuing from headers in javascript:

```js
Sentry.startSpanFromHeaders(spanCtx, headers);
```

Since we want to discourage accessing the transaction object directly, the `Sentry.setMeasurement` top level method will also be introduced. This will set a custom performance metric if a transaction exists. If a transaction doesn't exist, this method will do nothing. In the future, this method will attach the measurement to the span on the scope, but for now it'll only attach it to the transaction.

```ts
namespace Sentry {
  declare function setMeasurement(key: string, value: number): void;
}
```

## Span Schema

To remove the overhead of understanding transactions/spans and their differences, we propose to simplify the span schema to have a minimal set of required fields.

### Existing Span Schema

The current transaction schema inherits from the error event schema, with a few fields that are specific to transactions.

A full version of this protocol can be seen in [Relay](https://github.com/getsentry/relay/blob/2ad761f64db3df9b4d42f2c0896e1f6d99c16f49/relay-general/src/protocol/event.rs), but here are some of the fields that are important:

| Transaction Field | Description                                                                                                                                                | Type            |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `name`            | Name of the transaction. In ingest and storage this field is called `transaction`                                                                          | String          |
| `end_timestamp`   | Timestamp when transaction was finished. Some SDKs alias this to `end_timestamp` but convert it to `timestamp` when serializing to send to Sentry.         | String \| Float |
| `start_timestamp` | Timestamp when transaction was created.                                                                                                                    | String \| Float |
| `tags`            | Custom tags for this event. Identical in behaviour to tags on error events.                                                                                | Object          |
| `spans`           | A list of child spans to this transaction.                                                                                                                 | Span[]          |
| `measurements`    | Measurements which holds observed values such as web vitals.                                                                                               | Object          |
| `contexts`        | Contexts which holds additional information about the transaction. In particular, `contexts.trace` has additional information about the transaction "span" | Object          |

The transaction also has a trace context, which contains additional fields about the transaction.

| Transaction Field | Description                                                                                                                   | Type   |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| `trace_id`        | Trace ID of the transaction. Format is identical between Sentry and OpenTelemetry                                             | String |
| `span_id`         | Span ID of the transaction. Format is identical between Sentry and OpenTelemetry                                              | String |
| `parent_span_id`  | Parent span ID of the transaction. Format is identical between Sentry and OpenTelemetry                                       | String |
| `op`              | Operation type of the transaction. [Standardized by Sentry spec](https://develop.sentry.dev/sdk/performance/span-operations/) | String |
| `status`          | Status of the transaction. Sentry maps status to HTTP status codes, while OpenTelemetry has a fixed set of status'            | String |

The current span schema is as follows:

| Span Field        | Description                                                                                                                                                                                           | Type            |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `description`     | Description of the span. Same purpose as transaction `name`                                                                                                                                           |
| `trace_id`        | Trace ID of the span. Format is identical between Sentry and OpenTelemetry                                                                                                                            | String          |
| `span_id`         | Span ID of the span. Format is identical between Sentry and OpenTelemetry                                                                                                                             | String          |
| `parent_span_id`  | Parent span ID of the span. Format is identical between Sentry and OpenTelemetry                                                                                                                      | String          |
| `end_timestamp`   | Timestamp when span was finished. Some SDKs alias this to `end_timestamp` but convert it to `timestamp` when serializing to send to Sentry.                                                           | String \| Float |
| `start_timestamp` | Timestamp when span was created.                                                                                                                                                                      | String \| Float |
| `op`              | Operation type of the span. [Standardized by Sentry spec](https://develop.sentry.dev/sdk/performance/span-operations/)                                                                                | String          |
| `status`          | Status of the span. Sentry maps status to HTTP status codes, while OpenTelemetry has a fixed set of status'                                                                                           | String          |
| `tags`            | Custom tags for this span.                                                                                                                                                                            | Object          |
| `data`            | Arbitrary additional data on a span, like `extra` on the top-level event. We maintain [conventions for span data keys and values](https://develop.sentry.dev/sdk/performance/span-data-conventions/). | Object          |

As you can see, the fields on the transaction/span differ in a few ways, the most noteable of which is that transactions have `name` while spans have `description`. This means that spans and transactions are not interchangeable, and users have to know the difference between the two.

In addition, user's have the burden to understand the differences between `name`/`description`/`operation`. `operation` in particular can be confusing, as it overlaps with transaction `name` and span `description`. In addition, `operation` is not a required field, which means that it is not clear what the default value should be.

Transactions also have no mechanism for arbitrary additional data like spans do with `data`. Users can choose to add arbitrary data to transactions by adding it to the `contexts` field (as transactions extend the event schema), but this is not obvious and not exposed in every SDK. Since contexts are already well defined in their own way, there is no way of using [Sentry's semantic conventions for span data](https://develop.sentry.dev/sdk/performance/span-data-conventions/) for transactions.

### New Span Schema

To simplify how performance data is consumed and understood, we are proposing a new span schema that the SDKs send to Sentry. The new span schema aims to be a superset of the [OpenTelemetry span schema](https://github.com/open-telemetry/opentelemetry-proto/blob/4967b51b5cb29f725978362b9d413bae1dbb641c/opentelemetry/proto/trace/v1/trace.proto) and have a minimal top level API surface. This also means that spans can be easily converted to OpenTelemetry spans and vice versa.

The new span schema is as follows:

| Span Field        | Description                                                  | Type            | Notes                                                                                                                                                                                                                                                              |
| ----------------- | ------------------------------------------------------------ | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `name`            | The name of the span                                         | String          | Should be low cardinality. Replacing span `description`                                                                                                                                                                                                            |
| `trace_id`        | Trace ID of the span                                         | String          | Format is identical between Sentry and OpenTelemetry                                                                                                                                                                                                               |
| `span_id`         | Span ID of the span                                          | String          | Format is identical between Sentry and OpenTelemetry                                                                                                                                                                                                               |
| `parent_span_id`  | Parent span ID of the span                                   | String          | Format is identical between Sentry and OpenTelemetry. If empty this is a root span (transaction).                                                                                                                                                                  |
| `end_timestamp`   | Timestamp when span was finished                             | String \| Float |                                                                                                                                                                                                                                                                    |
| `start_timestamp` | Timestamp when span was finished                             | String \| Float |                                                                                                                                                                                                                                                                    |
| `op`              | Operation type of the span                                   | String          | Use is discouraged but kept for backwards compatibility for product features                                                                                                                                                                                       |
| `status`          | Status of the span                                           | String          | An optional final status for this span. Can have three possible values: 'ok', 'error', 'unset'. Same as OpenTelemetry's Span Status                                                                                                                                |
| `attributes`      | A set of attributes on the span.                             | Object          | This maps to `span.data` in the current schema for spans. There is no existing mapping for this in the current transaction schema. The keys of attributes are well known values, and defined by a combination of OpenTelemtry's and Sentry's semantic conventions. |
| `measurements`    | Measurements which holds observed values such as web vitals. | Object          |                                                                                                                                                                                                                                                                    |

For the purposes of this RFC, the version on the span schema will be set to 2. This will indicate to all consumers that the new span schema is being used.

Just like both the old Sentry schema and the OpenTelemetry schema, we keep the same fields for `span_id`, `trace_id`, `parent_span_id`, `start_timestamp`, and `end_timestamp`. We also choose to rename `description` to `name` to match the OpenTelemetry schema.

Having both the `name` and `op` fields is redundant, but we choose to keep both for backwards compatibility. There are many features in the product that are powered by having a meaningful operation, more details about this can be found in the documentation around [Span operations](https://develop.sentry.dev/sdk/performance/span-operations/). In the future, we can choose to deprecate `op` and remove it from the schema.

The most notable change here is to formally introduce the `attributes` field, and remove the `span.data` field. This is a breaking change, but worth it in the long-term. If we start accepting `attributes` on transactions as well, we more closely align with the OpenTelemetry schema, and can use the same conventions for both spans and transactions.

### Shimming the old schema

To ensure that we have backwards compatibility, we will shim the old schema to the new schema. This has to be done for both transactions and spans.

For transactions, we need to start adding the `attributes` field to the trace context, the same way we do for spans. This will allow us to use the same conventions for both transactions and spans. For spans, we can keep and deprecate the `span.data` field, and forward it to `span.attributes` internally. For example, `span.setData()` would just call `span.setAttribute()` internally.

Since status is changing to be an enum of 3 values from something that previously mapped to http status code, we need to migrate away from it in two steps. First, we'll be marking http status of spans in `span.attributes`, using our [span data semantic conventions](https://develop.sentry.dev/sdk/performance/span-data-conventions). For example, `http.request.status_code` can record the request status code. Next, we'll introduce a mapping where 2xx status codes map to `ok`, 4xx and 5xx status codes map to `error`, and all other status codes map to `unset`.

Similar to `span.data`, we can keep and deprecate the `span.description` field and forward it to `span.name` internally. For example, `span.setDescription()` would just call `span.setName()` internally.

## Next Steps

Since we only have `beforeSend` hooks for a transaction, we should look toward building similar hooks for span start and finish as well. This can be done after the span schema has been changed in the SDKs.
