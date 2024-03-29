- Start Date: 2024-02-08
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/131
- RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)
- RFC Status: approved
- RFC Approver: [Karl Heinz Struggl](https://github.com/kahest)

# Summary

This RFC aims to find a solution for passing auto-instrumented native SDK spans up to the hybrid SDKs.

## Option Chosen

On 2024-02-28, we decided to move forward with [Option 2: Spans Aggregator](#option-2) because of
the following reasons:

- Option 4 doesn't allow filtering of native spans on the hybrid layer.
- Option 3 has a high risk of severe problems because of too frequent cross-platform communication.
- Option 1 is a duplicate of Option 2, and with single-span ingestion, we no longer want a
self-clearing cache. Instead, SDKs must send every span to Sentry.
- Option 2 reuses SpansAggregator, which is a prerequisite for single-span ingestion. Furthermore,
it reduces the frequency of cross-platform communication and works well with both transactions and
single-span ingestion.

Participants of the decision:

- Philipp Hofmann
- Karl Heinz Struggl
- Markus Hintersteiner
- Stefan Jandl
- Stefano Siano
- Kryštof Woldřich
- Gino Buenaflor


# Motivation

The native SDKs instrument file IO operations, DB queries, HTTP requests, and more, but this
information doesn't end up in the hybrid transactions or anywhere else. Our hybrid SDKs instrument
most of the mentioned operations on the hybrid layer, but they lack information on how long the
actual native operations take. It could happen that one DB query from the hybrid layer gets
converted into multiple native DB queries. Such information would be insightful for our users.
Furthermore, there could be native-only operations that our hybrid SDKs currently don't capture. Therefore,
we want to pass native spans up to the native layers so users know what's happening on the native layer.

Furthermore, the hybrid SDKs can then establish a parent-child relationship between the spans. For
example, if there is only one HTTP span on the hybrid layer and one HTTP span on the native layer
that occurred within the lifetime of the hybrid HTTP span, the hybrid SDK can set the native span as
a child of the hybrid span. Of course, the hybrid SDK must also compare the URL in that case or
apply other logic to avoid wrong parent-child relationships. 

# Background

The mobile Starfish team wants to have more data for hybrid SDKs to improve the value of our
performance offering. @shruthilayaj brought up this topic several times during mobile Starfish team
syncs. After (@krystofwoldrich and @philipphofmann) hacked together a POC for HTTP spans from Cocoa
to RN, we decided this would be a valuable feature. You can visit the code on
[Cocoa](https://github.com/getsentry/sentry-cocoa/tree/poc/network-tracker-finished-spans) and
[RN](https://github.com/getsentry/sentry-react-native/tree/kw-cocoa-spans-to-rn-poc) and the internal
[Notion doc](https://www.notion.so/sentry/RN-Span-ID-to-Cocoa-POC-085194074d39415684eb3d0e37b70c99).

The solution has to support the following requirements:

1. It should be compatible with both transactions and single-span ingestion. It must be compatible
with single-span ingestion. Not being compatible with transactions might be acceptable, as we have
plans to remove them.
2. It must work with transactions bound to the scope and active spans. We don't have to worry about
multiple transactions or spans running in parallel, as on mobile, the SDKs can never tell to which
transaction bound to the scope or active span an auto-instrumented span belongs. Therefore, they
attach it to the transaction bound to the scope or the active span.
3. Native auto-instrumented spans must go through the hybrid layer because of span filtering and sampling,
meaning native SDKs must not send spans themselves.
4. The native SDKs must support attaching screen frame data to the spans.

# Options Considered

## Option 1: Self Clearing Cache With Hooks <a name="option-1"></a>

The native SDKs implement a self-clearing cache for their auto-instrumented spans with hooks to
start and stop the cache. Whenever the native SDKs add a span to their cache, they discard all
spans older than a configurable threshold. To make cache clearing efficient, the SDKs keep the spans
in a data structure ordered by span timestamp and use a binary search to find the last index of the
range of spans to delete, which makes inserting a span `O(log n)`. Furthermore, the native SDKs
offer a callback when all ongoing spans are finished to support `waitForChildren`.

### Pros <a name="option-1-pros"></a>

1. Less cross hybrid layer communication than [option 3](#option-3).

### Cons <a name="option-1-cons"></a>

1. With single-span ingestion, we don't want to have a self-clearing cache. Instead, every span
should end up in Sentry.
2. Adding spans to the cache is `O(log n)`.

## Option 2: Spans Aggregator <a name="option-2"></a>

The native SDKs use the [SpansAggregator](/text/0126-sdk-spans-aggregator.md) to cache the spans.
The SpansAggregator doesn't pass the spans down to the transport for sending. Instead, when its
timeout exceeds or aggregated spans exceed the maximum byte size, the SpansAggregator passes the
spans up to the hybrid layer. The SpansAggregator implements a new method for retrieving all spans
so that hybrid SDKs can attach spans to transactions bound to the scope, or to active spans.
Furthermore, until single-span ingestion lands, the native SDKs offer a callback when all ongoing
spans are finished to support `waitForChildren` and provide hooks to start and stop the
SpansAggregator, same as [option 1](#option-1).

The following specification is written in the [Gherkin syntax](https://cucumber.io/docs/gherkin/reference/)
to explain how the solution reacts to multiple edge cases. To simplify the requirements, the
specification only deals with active spans, which are similar to transactions bound to the scope. A
few points to consider for the specification:

1. An active span always refers to the hybrid SDKs because native SDKs don't have active spans when
in hybrid mode.
2. When the hybrid SDKs add the spans from the native layer to their SpansAggregator, the spans must
pass through all hooks as when finishing a hybrid span.
3. The hybrid SpansAggregator keeps its behavior. No changes are required.
4. After the hybrid SDKs pull spans from the native SpansAggregator, the native SpansAggregator
removes all its spans.

```Gherkin
Scenario: No active span, native SpansAggregator flushes
    Given no active span
    When the native SpansAggregator has to flush all its spans
    Then native SDK pushes all native spans up to the hybrid SDK
    And doesn't send its native spans directly to Sentry
    And the hybrid SDK adds all native spans to its SpansAggregator

Scenario: Active span, native SpansAggregator flushes
    Given an active span
    When the native SpansAggregator has to flush all its spans
    Then native SDK pushes all native spans up to the hybrid SDK
    And the hybrid SDK filters for spans belonging to the active span 
    And adds these spans to the active span
    And adds the non matching spans to the hybrid SpansAggregator

Scenario: Active span finishes
    Given an active span
    When it finishes
    Then hybrid SDK gets all spans from the native SpansAggregator
    And the hybrid SDK filters for spans belonging to the active span 
    And adds these spans to the active span
    And adds the non matching spans to the hybrid SpansAggregator

Scenario: Active span, hybrid SpansAggregator flushes
    Given an active span
    When the hybrid SpansAggregator has to flush all its spans
    Then it pulls spans from the native SpansAggregator
    And filters for spans belonging to the active span 
    And adds these spans to the active span
    And adds the non matching spans to the hybrid SpansAggregator
    And sends all spans from the hybrid SpansAggregator to Sentry

Scenario: No active span, hybrid SpansAggregator flushes
    Given no active span
    When the hybrid SpansAggregator has to flush all its spans
    Then it pulls spans from the native SpansAggregator
    And adds these to the hybrid SpansAggregator
    And sends native and hybrid spans to Sentry
```

### Pros <a name="option-2-pros"></a>

1. Reusing existing functionality of the SpansAggregator.
2. Works well with single-span ingestion and transactions.
3. Adding spans to the SpansAggregator is `O(1)`.
4. Less cross hybrid layer communication than [option 3](#option-3).

### Cons <a name="option-2-cons"></a>

1. Please add your cons.

### Open Questions

1. How does this logic work with manual spans from the native layer?

## Option 3: Native Callbacks<a name="option-3"></a>

The native layers offer callbacks whenever they start and finish auto-instrumented spans and don't
keep track of spans. For example, the HTTP request instrumentation offers two callbacks: one for
starting the HTTP request and another for finishing the HTTP request. The hybrid SDKs then subscribe
to these callbacks and create the spans themselves.

### Cross Platform Communication Overhead

This section gives an overview of the different ways platforms handle cross-platform communication:

1. __React Native__: The old architecture of React Native relies on a bridge mechanism that uses a
queue that uses serialization. The new architecture uses JavaScrip Interface (JSI), eliminating
serialization overhead.

2. __Flutter__ uses [platform channels](https://docs.flutter.dev/resources/architectural-overview#platform-channels)
with serialization, but you can also use the foreign function interface
[FFI](https://docs.flutter.dev/resources/architectural-overview#foreign-function-interface),
which only works for C-based APIs.

3. __Unity__ uses [P/invoke](https://docs.unity3d.com/Manual/uwp-pinvoke.html), which is similar to
[type marshaling in .NET](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/type-marshalling).

We didn't look into all cross-platform frameworks because we already see a pattern of using
serialization, and we don't expect it to be much worse than serialization.

No matter the strategy, every cross-platform call adds some overhead because each call requires some
overhead, such as copying memory from one runtime to the other or from managed to unmanaged code. On
some platforms, boxing and unboxing are involved; for others, serialization. The overhead will vary
depending on many different factors, such as:

- the cross-platform framework
- the frequency of the cross-platform call
- the user's device
- the customer's app
- and more

All that said reducing the frequency of cross-platform calls should be the better approach.

### Pros <a name="option-3-pros"></a>

1. This option works well with idle transactions and `waitForChildren` because these concepts need to
know when spans start and finish, but this is a weak argument as with single-span ingestion, this
concept will become obsolete.
2. Works well with single-span ingestion, as the hybrid SDKs get callbacks for each span.
3. Complete flexibility for hybrid SDKs. Hybrid SDKs have full control over how they want to deal with
native-span information.

### Cons <a name="option-3-cons"></a>

1. Each span requires two calls across the layers, which could negatively impact performance.
2. Hybrid SDKs need extra communication for retrieving frame data for the native spans.

## Option 4: Native SDKs Use Single Span Ingestion<a name="option-4"></a>

The native SDKs don't pass the spans up to the hybrid SDKs. Instead, they use single-span ingestion,
and the backend has to establish parent-child relationships.

### Pros <a name="option-4-pros"></a>

1. No performance overhead of passing spans across layers.
2. Less work.

### Cons <a name="option-4-cons"></a>

1. Only works with single-span ingestion and not with transactions, which is a weak argument as this
is the future.
2. Establishing proper parent-child relationships for the backend might be tricky when the spans
don't arrive in the same envelope.
3. Hybrid SDKs can't filter native spans. Users would have to write native code for filtering.

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- How expensive is a call from hybrid to native and vice versa? If they are very cheap, then
[con 2 of option 3](#option-3-cons) is obsolete. We need to take into account that this could be
different per platform.
