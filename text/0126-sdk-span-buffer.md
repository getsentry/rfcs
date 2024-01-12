- Start Date: 2023-11-28
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/126
- RFC Status: In Progress
- RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)

# Summary

This RFC aims to find a strategy for buffering spans to avoid sending one envelope per span.

# Motivation

Putting every span into a single envelope is unacceptable, as this would cause numerous HTTP requests. Instead, SDKs must use a strategy to batch multiple spans together. They should find a balance for the following requirements:

- **Send few HTTP requests.** SDKs need to batch spans together to avoid multiple HTTP requests.
- **Lose few spans in the event of a crash.** Losing a few spans in memory is acceptable, but SDKs must keep that to a respectable minimum.
- **Keep a minimum amount of spans in memory** to reduce the memory footprint.

# Background

As of November 28, 2023, the auto instrumentation of spans requires an active transaction bound to the scope to have something to attach the spans to. The SDKs lose spans when no active transaction is tied to the scope. Some SDKs, such as JavaScript, implement the [concept](https://github.com/getsentry/rfcs/blob/760467b85dbf86bd8b2b88d2a81f1a258dc07a1d/text/0101-revamping-the-sdk-performance-api.md) of `Sentry.startSpan` and `Sentry.startInactiveSpan` , which still uses a transaction under the hood. As single-span ingestion is around the corner, we can use it to send every auto-instrumented span, whether there is an ongoing transaction or not.

## What happened to carrier transactions?

On Mobile, we initially agreed on using transactions as carriers for spans in the [RFC mobile transactions and spans](https://github.com/getsentry/rfcs/blob/760467b85dbf86bd8b2b88d2a81f1a258dc07a1d/text/0118-mobile-transactions-and-spans.md).
We planned on implementing [carrier transactions](https://github.com/getsentry/team-mobile/issues/157), but then [reverted the RFC](https://github.com/getsentry/rfcs/pull/125) and decided to use single span ingestion instead because the [PR for it is already merged](https://github.com/getsentry/relay/pull/2620).

# Options Considered

## Option 1: Span Buffer <a name="option-1"></a>

A strategy to achieve this is to keep a buffer of **only finished spans**  in memory and batch them together in envelopes. The buffer uses a combination of **timeout** and **span size**, which is the serialized span size in bytes. If counting the serialized span byte size is not possible on a platform, it can implement the alternative called **weight**, which is an approximation of how much bytes a span allocates. A section below explains weight in more detail. We recommend that SDKs use the span buffer in the client because we don't want the transport to be aware of spans, as it mainly deals with envelopes. This concept is similar to [OpenTelemetry's Batch Processors](https://github.com/open-telemetry/opentelemetry-collector/blob/main/processor/batchprocessor/README.md).

The buffer starts a timeout of `x` seconds when the SDK adds the first span. When the timeout exceeds, the buffer sends all spans no matter how many items it contains. The buffer also sends all items after the SDK captures spans with weight more than `y`, but it must keep the span children together with their parents in the same envelope. When the buffer sends all spans, it resets its timeout and removes all spans in the buffer. When a span and its children have more weight than the max buffer weight `y`, the SDK surpasses the buffer and sends the spans together in one envelope directly to Sentry. The buffer handles both auto-instrumented and manual spans.

The specification is written in the [Gherkin syntax](https://cucumber.io/docs/gherkin/reference/) and uses `x = 10` seconds for the timeout and `y = 1024 * 1024` for the maximum span byte size in the buffer. SDKs may use different values for `x` and `y` depending on their needs. If the timeout is set to `0`, then the SDK sends every span immediately. Initially, we don’t plan adding options for these variables, but we can make them configurable if required in the future, similar to `maxCacheItems`.

```Gherkin
Scenario: No spans in buffer 1 span added
    Given no spans in the SpanBuffer
    When the SDK adds 1 span
    Then the SDK adds this span to the SpanBuffer
    And starts a timeout of 10 seconds
    And doesn't send the span to Sentry

Scenario: Span added before timeout exceeds
    Given 1 span in the SpanBuffer
    Given 9.9 seconds pass
    When the SDK adds 1 span
    Then the SDK adds this span to the SpanBuffer
    And doesn't reset the timeout
    And doesn't send the spans in the SpanBuffer to Sentry

Scenario: Spans with size of y - 1 added, timeout exceeds
    Given spans with size of y - 1 in the SpanBuffer
    When the timeout exceeds
    Then the SDK adds all the spans to one envelope
    And sends them to Sentry
    And resets the timeout
    And clears the SpanBuffer

Scenario: Spans with size of y added within 9.9 seconds
    Given no spans in the SpanBuffer
    When the SDK adds spans with a weight of y within 9.9 seconds
    Then the SDK puts all spans into one envelope
    And sends the envelope to Sentry
    And resets the timeout
    And clears the SpanBuffer

Scenario: 1 span added app crashes
    Given 1 span in the SpanBuffer
    When the SDK detects a crash
    Then the SDK does nothing with the SpanBuffer
    And loses the spans in the SpanBuffer

Scenario: Unfinished spans
    Given no span is in the SpanBuffer
    When the SDK starts a span but doesn't finish it
    Then the SpanBuffer is empty

Scenario: Spans in buffer, span with children
    Given spans with a size of y - 1 in the SpanBuffer
    When the SDK finishes a span with one child
    Then the SDK puts the spans with a size of y - 1 already in the SpanBuffer into an envelope
    And sends the envelope to Sentry.
    And stores the span with its child into the SpanBuffer
    And resets the timeout

Scenario: Span with more children than max buffer weight
    Given one span A is in the SpanBuffer
    When the SDK starts a span B
    And starts child spans with a size of y for span B
    When the SDK finishes the span B and all it's children
    Then the SDK directly puts all spans of span B into one envelope
    And sends the envelope to Sentry.
    And doesn't store the spans of span B in the SpanBuffer
    And keeps the existing span A in the SpanBuffer
    And doesn't reset the timeout

Scenario: Timeout set to 0 span without children
    Given the timeout is set to 0
    When the SDK finishes one span without any children
    Then the SDK puts the span into one one envelope
    And sends the envelope to Sentry.

Scenario: Timeout set to 0 span with children
    Given the timeout is set to 0
    When the SDK finishes one span with children of a weight of 100
    Then the SDK puts the span with the children into one envelope
    And sends the envelope to Sentry.

Scenario: Timeout set to 0 spans without children
    Given the timeout is set to 0
    When the SDK finishes two spans without any children
    Then the SDK puts every span into one envelope
    And sends both envelopes to Sentry.

```

### Weight

A simple way to calculate the weight of a span is to call serialize and recursively count the number of elements in the dictionary. Every key in a dictionary and every element in an array add a weight of one. For a detailed explanation of how to count the weight, see the example below. As serialization is expensive, the span buffer will keep track of the serialized spans and directly pass them to the envelope item to avoid serializing multiple times.

```JSON
{
    // All simple properties count as 1 so in total 12
    "timestamp": 1705031078.623853,                     
    "start_timestamp": 1705031078.337715,
    "description": "ExtraViewController full display",
    "op": "ui.load.full_display",
    "span_id": "794d0cba0ac64235",
    "parent_span_id": "45054abc6ded413a",
    "trace_id": "65880cfc084f4bd5ab3abc7d598b3c14",
    "status": "ok",
    "origin": "manual.ui.time_to_display",
    "hash": "a925395473cfe97d",
    "sampled": true,
    "type": "trace",

    // The data object has 5 simple properties, which count as 5
    // and one list with 3 elements counting as 3
    "data": {
        "frames.frozen": 0,
        "frames.slow": 1,
        "frames.total": 1,
        "thread.id": 259,
        "thread.name": "main",
        "list" : [1, 2, 3]
    },

    // Tags count as 2
    "sentry_tags": {
        "environment": "ui-tests",
        "main_thread": "true",
    },

    // The weight is 
    // 12 (simple properties)
    // 8  (data)
    // 2  (tags)
    // = 22
}
```

### Pros <a name="option-1-pros"></a>

1. SDKs send fewer HTTP requests than sending every span individually to Sentry.

### Cons <a name="option-1-cons"></a>

1. Spans are lost in the event of a crash.
2. Spans are delayed for 10 seconds until the SDK sends them to Sentry. For example, when manually playing around with Sentry while debugging, it takes longer until spans appear in the performance product.

# Drawbacks

Please add any drawbacks you can think of as a comment or just commit directly.

# Unresolved questions

- What values are SDKs going to pick for x and y?
- Which platforms would need to implement weights? If none, we can drop the concept.
- Should we add an option to make x and y configurable from the start?
- Do SDKs have to send span children in the same envelope as their parent?
- Should we call the solution SpansAggregator to align with metrics?
