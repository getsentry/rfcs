- Start Date: 2023-05-10
- RFC Type: feature
- RFC PR: [https://github.com/getsentry/rfcs/pull/89](https://github.com/getsentry/rfcs/pull/89)
- RFC Status: draft
- RFC Driver: [Abhijeet Prasad](https://github.com/AbhiPrasad)
- RFC Approver: TBD

# Summary

TODO: Abhi

# Motivation

When Sentry performance monitoring was initially introduced, OpenTelemetry was in early stages. This lead to us adopt a slightly different span model from OpenTelemetry, notably we have this concept of transactions that OpenTelemetry does not have. We've described this, and some more historical background, in our [performance monitoring research document](https://develop.sentry.dev/sdk/research/performance/).

Now that we are looking to explore single span ingestion and the indexing of spans, this gives us the opportunity to align our span schema more closely to OpenTelemtry's, which is what this RFC is proposing.

This opens us up to a few benefits:

- We can directly ingest data from OpenTelemetry SDKs if needed.
- We remove the barrier of understanding our span model for new users since OpenTelemetry is a standard.
- We reduce complexity in the SDKs by removing the need to map between our span model and OpenTelemetry's.

# The New Span Schema

The top level fields of a span should be as constrained as possible - we’ve learned from the event schema at sentry that is quite the maintenance overhead for both users and sdk authors to keep track many different top level fields.

Roughly based on [https://develop.sentry.dev/sdk/performance/opentelemetry/#span-protocol](https://develop.sentry.dev/sdk/performance/opentelemetry/#span-protocol)

| Required Attributes                                                                                                                                          |                       |                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [trace_id](https://github.com/open-telemetry/opentelemetry-proto/blob/7aa439cb0ba78afbd009d83f32fdda6c128e0342/opentelemetry/proto/trace/v1/trace.proto#L87) | 16 byte array         | The SDKs use uuid for correlation ids                                                                                                                                                                                                                                     |
| parent_span_id                                                                                                                                               | 8 byte array          |                                                                                                                                                                                                                                                                           |
| span_id                                                                                                                                                      | 8 byte array          |                                                                                                                                                                                                                                                                           |
| start_timestamp                                                                                                                                              | whatever relay wants  |                                                                                                                                                                                                                                                                           |
| end_timestamp                                                                                                                                                | whatever relay wants  | called timestamp currently in the Sentry transaction schema                                                                                                                                                                                                               |
| name                                                                                                                                                         | string                | Low cardinality, differs from otel span name in exact usage. Replacement field with span description.                                                                                                                                                                     |
| version                                                                                                                                                      | 2                     | Version of the span schema, used to indicate to ingest/storage that they should look at segments, treat status differently etc.                                                                                                                                           |
| Optional Attributes                                                                                                                                          |                       |                                                                                                                                                                                                                                                                           |
| op                                                                                                                                                           | string                | The core function of this span. For sentry should follow this list - https://develop.sentry.dev/sdk/performance/span-operations/                                                                                                                                          |
| status                                                                                                                                                       | ok \| error           | defaults to ok in Relay - but can be overridden to be error (either locally or in Relay by parsing data)                                                                                                                                                                  |
| data                                                                                                                                                         | `Record<string, any>` | A dictionary of arbitrary keys and values, matching https://github.com/open-telemetry/opentelemetry-proto/blob/7aa439cb0ba78afbd009d83f32fdda6c128e0342/opentelemetry/proto/trace/v1/trace.proto#L182. Parsing span data is how you can assign semantic meaning to a span |
| measurements                                                                                                                                                 | Whatever Relay wants  | a dictionary of measurements that get extracted as metrics (web vitals, custom perf metrics)                                                                                                                                                                              |
| is_segment                                                                                                                                                   | boolean               |                                                                                                                                                                                                                                                                           |
| segment_id                                                                                                                                                   | 8 byte array          | needs to be unique to a trace only so we can get away with just 8 byte arrays, same len as span ids                                                                                                                                                                       |

Instead of using top level fields on a span, we can parse the data dictionary for specific well-known keys to further refine metrics/information we can extract from the span. Think of span data working exactly as `event.contexts` work today - with fields we have strong knowledge about.

Today we already have some conventions around span data: [https://develop.sentry.dev/sdk/performance/span-data-conventions/](https://develop.sentry.dev/sdk/performance/span-data-conventions/), so we know the pattern works well.

[Luckily otel has done the hard work of defining a bunch of well known keys and their values - we can copy and use these values exactly](https://opentelemetry.io/docs/reference/specification/trace/semantic_conventions/). They’ve also defined cardinality and type for all these key/value pairs - we don’t need to do that extra work. If we end up making new known values we can contribute them upstream to otel and update our own local list of conventions (we might have to do this for browser/mobile)

Since every key has a specific convention/meaning - there is no risk of different platforms using the same key differently. This also allows us to define paramaterization/PII strategies per specific data key/value pair.

# Migration Plan

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- Are we using segments
- Do we still need `span.op`?
- Do we need to split up `span.data` to be more specific?
