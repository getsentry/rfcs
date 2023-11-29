- Start Date: 2023-11-28
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/126
- RFC Status: draft
- RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)

# Summary

This RFC aims to find a strategy for batching spans together to avoid sending one envelope per span.

# Motivation

Putting every span into a single envelope is unacceptable, as this would cause numerous HTTP requests. Instead, SDKs must use a strategy to batch multiple spans together. They should find a balance for the following requirements:

- **Send few HTTP requests.** SDKs need to batch spans together to avoid multiple HTTP requests.
- **Lose few spans in the event of a crash.** Losing a few spans in memory is acceptable, but SDKs must keep that to a respectable minimum.
- **Keep a minimum amount of spans in memory** to reduce the memory footprint.

# Background

As of November 28, 2023, the auto instrumentation of spans requires an active transaction bound to the scope to have something to attach the spans to. The SDKs lose spans when no active transaction is tied to the scope. Some SDKs, such as JavaScript, implement the [concept](https://github.com/getsentry/rfcs/blob/760467b85dbf86bd8b2b88d2a81f1a258dc07a1d/text/0101-revamping-the-sdk-performance-api.md) of `Sentry.startSpan` and `Sentry.startInactiveSpan` , which still uses a transaction under the hood. As single-span ingestion is around the corner, we can use it to send every auto-instrumented span, whether there is an ongoing transaction or not.

## What happened to carrier transactions?

On Mobile, we initially agreed on using transactions as carriers for spans in the [RFC mobile transactions and spans](https://github.com/getsentry/rfcs/blob/760467b85dbf86bd8b2b88d2a81f1a258dc07a1d/text/0118-mobile-transactions-and-spans.md).
We planned on implementing [carrier transactions](https://github.com/getsentry/team-mobile/issues/157), but then [reverted the RFC](https://github.com/getsentry/rfcs/pull/125) and decided to use span ingestion instead because it won’t take long until the [PR for it gets merged](https://github.com/getsentry/relay/pull/2620).

# Options Considered

## Option 1: Batch Span Ingestion <a name="option-1"></a>

A strategy to achieve this is to keep a buffer of **only finished spans** in memory and batch them together in envelopes. The buffer starts a timeout of x seconds when the SDK adds the first span. When the timeout exceeds, the buffer sends all spans no matter how many items it contains. The buffer also sends all items after the SDK captures y spans. When the buffer sends all spans, it resets its timeout and removes all spans in the buffer. The buffer handles both auto-instrumented and manual spans.

The specification is written in the [Gherkin syntax](https://cucumber.io/docs/gherkin/reference/) and uses x = 10 seconds for the timeout and y = 50 spans for the maximum spans in the buffer. SDKs may use different values for x and y depending on their needs. Initially, we don’t plan adding options for these variables, but we can make them configurable if required in the future, similar to `maxCacheItems`.

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

Scenario: 49 span added, timeout exceeds
    Given 49 span in the SpanBuffer
    When the timeout exceeds
    Then the SDK adds all the spans to one envelope
    And sends them to Sentry
    And resets the timeout
    And clears the SpanBuffer

Scenario: 50 spans added within 9.9 seconds
    Given no spans in the SpanBuffer
    When the SDK adds 50 spans within 9.9 seconds
    Then the SDK puts all 50 spans into one envelope
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
    Then the SpanBuffer is still empty
    
Scenario: Open span, many children
    Given no span is in the SpanBuffer
    When the SDK starts a span but doesn't finish it yet
    And starts+finishes 60 child spans
    When the span finishes
    Then the SpanBuffer contains 61 spans
    And sends the envelope to Sentry

### Pros <a name="option-1-pros"></a>

1. SDKs send fewer HTTP requests than sending every span individually to Sentry.

### Cons <a name="option-1-cons"></a>

1. Spans are lost in the event of a crash.
2. Spans are delayed for 10 seconds until the SDK sends them to Sentry. For example, when manually playing around with Sentry while debugging, it takes longer until spans appear in the performance product.

# Drawbacks

Please add any drawbacks you can think of as a comment or just commit directly.

# Unresolved questions

- What values are SDKs going to pick for x and y?
- Should we add an option to make x and y configurable from the start?
