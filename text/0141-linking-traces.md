- Start Date: 2024-11-08
- RFC Type: feature 
- RFC PR: <[link](https://github.com/getsentry/rfcs/pull/141)>
- RFC Status: draft

# Summary

This RFC introduces the ability to link or connect traces in Sentry. The required changes involve SDKs, Ingest, Search and Storage, Backend as well as product teams.
The goal of this initiative is to be able to link multiple traces together so that the Sentry product can show what happened before a specific trace while preserving the integrity of individual traces.
This RFC proposes to use "Span Links" as a vehicle for specifying relationships between spans in multiple traces. It also discusses other options considered, as well as concrete use cases for this feature.

# Motivation

At the time of writing this RFC, Sentry (the product as well as SDKs) cannot connect multiple traces to deliver a "bigger picture" of what happened before (or after) a specific trace. 
A trace is therefore the highest level of connecting signals (errors, traces, profiles, etc.).
The notable exception is Session Replay, where we are indeed able to provide this bigger picture.

This RFC proposes a method of achieving linkage between (and within) traces in the entire Sentry product, to satisfy a number of currently sub-optimally solved use cases.

## Frontend Traces and User Journeys

The most important application of linking traces are frontend applications. We would like to display a user journey (session) to make debugging of issues easier as developers get more context on what happened before a specific issue. 
Today, we are limited to the duration of one trace (id), which is handled differently and kept alive for different times across our various SDKs. A concrete example are our [JavaScript Browser SDKs](https://develop.sentry.dev/sdk/platform-specifics/javascript-sdks/browser-tracing/#tracing-model) which by default keep a trace alive as long as users
are on the same page or (URL) route. This was a compromise in which we accepted that a trace would consist of multiple trace root spans (transactions), which is generally discouraged by tracing models like OpenTelemetry.
Another example of a suboptimal trace model is the one used in most mobile SDKs. In these SDKs we 

## Queues and Async Operations

Somewhat related, we also face situations in which child spans are not started and finished within the time span of their parent span. As per OpenTelemetry specification, this violates the integrity of a trace. A concrete example for this is that we [currently recommend](https://docs.sentry.io/platforms/javascript/guides/node/tracing/instrumentation/custom-instrumentation/queues-module/) users to create one trace for a producer-consumer (Queue) cycle, where the spans from the consumer likely start after the producer spans finished. OpenTelemetry in fact [recommends](https://opentelemetry.io/docs/concepts/signals/traces/#span-links) to start separate traces for the consumer, producer or more generally async operations and to link these traces via a span link.

## Additional Use Cases

In addition, besides inter-trace links, we might also be interested in linking spans within one trace, for example to link spans that are related to each other but not in a direct (parent-child or linear) hierarchy. While this is not the main objective of the RFC, our proposed solution would also facilitate this linkage. Some concrete examples (but out of scope):
- (Async) data flow operations (e.g. RxJS pipes) where we would be able to link individual operations.
- Websocket spans where we could link individual web socket messages
- More generally, whenever we want to "casually" establish a relationship between spans that cannot or should not be achieved via a hard relationship (traceId or parent spanId)

# Concrete Goals of achieving linked traces

Once this RFC is accepted, we have settled on all important details needed to implement connected traces.
This means, we have all the necessary information to support the following concrete goals:

TODO: List concrete product/UI goals

- SDKs can add support for adding links to spans
- We can ingest and store span links
- Frontend SDKs can automatically add span links so that the current trace root span links back to the previous trace root span


## Secondary goals

- We can shorten the lifetime of frontend traces because we're now able to link to the previous trace instead. This is something we'll do but it's a follow-up and can only be addressed once the primary goals are achieved. 

## Out of scope/Non-Goals

- Querying across linked traces: Given the "linked list" nature of one root span linking back to its previous root span, we accept that obtaining a complete list is an expensive query operation. Therefore, we consider use cases that require a complete list of all linked traces out of scope. We can address this as a follow-up if technically possible but we're aware that this is likely a sub-optimal data structure for such queries. 
- Linking transactions started during the rendering of statically generated HTML pages and pageload transactions. A span link is ideal here because we don't want the hard link of a trace id. However, a casual link would still increase context and completeness. We might do it but not at this point as it's a follow-up item.
- Unsampled traces are not linked. Errors across unsampled traces are not linked. For example, if the first trace was sampled negatively, the next trace will not link to it as this would result in a link to a non-existing trace.

# Background

This section provides background information of important concepts for this RFC

## OpenTelemetry Span Links

OpenTelemetry introduced the concept of span links to establish casual relationships between individual spans. Such links can be established by

- passing a `links` property to the Otel `startSpan` methods 
- calling `span.addLink(s)` on the span that should link to another span

This also means, that one span can link to multiple other spans. 

Span links are defined in the `Link` interface, which contains the `spanContext` of the span to link to, as well as a set of attributes that describe the link.

Span links are supported by all OpenTelemetry platforms we currently use (or plan on using) for our SDKs: [JavaScript (Node)](https://opentelemetry.io/docs/languages/js/instrumentation/#span-links), [Python](https://opentelemetry.io/docs/languages/python/instrumentation/#adding-links), [Elixir](https://opentelemetry.io/docs/languages/erlang/instrumentation/#linking-the-new-span) and [Java](https://opentelemetry.io/docs/languages/java/api-components/#span).


In an OTLP span export, span links are serialized as follows:

```json
// output was shortend to important fields
{
  "resourceSpans": [
    {
      "scopeSpans": [
        {
          "spans": [
            {
              "traceId": "627a2885119dcc8184fae7eef09438cb",
              "spanId": "ec53f20e4318380d",
              "links": [ // <-- link
                {
                  "attributes": [ // <-- link attributes
                    {
                      "key": "sentry.link.type",
                      "value": {
                        "stringValue": "parent"
                      }
                    }
                  ],
                  // span and trace linked to (from span.spanContext()): 
                  "spanId": "6c71fc6b09b8b716", 
                  "traceId": "627a2885119dcc8184fae7eef09438cb", 
                }
              ],
              "droppedLinksCount": 0
            },
            {
              "traceId": "627a2885119dcc8184fae7eef09438cb",
              "spanId": "6c71fc6b09b8b716",
              "parentSpanId": "13d4cb0933154c29",
              "name": "span-links-txn",
              "links": [],
              "droppedLinksCount": 0
            }
          ]
        }
      ]
    }
  ]
}
```


## Current Session Models in Sentry SDKs

Sentry SDKs do actually send session data, in fact even two types of sessions. However, neither of the two sessions are used and associated with a trace. 

- SDK error sessions: SDKs currently send a session that counts and describes the error status of such a session. Depending on the error, the session is marked as crashed, abnormal or healthy, which is information that powers our Release (Health) product. These sessions are fundamentally flawed though because (at least in Browser JS) they only last as long as the currently loaded page. Every soft or hard navigation causes the session to be ended and a new one to be started. 
- Replay Session: Frontend SDKs persist a replayId in the browser's `sessionStorage` which (even though the name does not suggest it) more accurately models a session than the SDKs' error sessions. We cannot have a hard dependency on this session as Replay is an extra product by Sentry, meaning this replayId is not always reliably set. However, the model of persisting the replay id can be used as a blueprint for how we could persist the last traceId. 

Upon decision from Leadership as well as from it being noted in Sentry's Goal Hierarchy, we will not associate spans or traces via any of these sessions. Instead, the sessions will stay as-is and we will link traces in a "linked list"-style approach as described in this RFC. 

# Supporting Data

Sentry users would like to get as much insight as possible when inspecting (errors or performance) issues. Right now, with the notable exception of Session Replay, we can only provide answers as to what happened before an error occured up to the point when a trace was started. If we can link from the current to the previous trace, we can significantly widen the insight into the entire user journey, which is often crucial to understand why and how a specific issue occured. 

Given that 32% of ARR can be attributed alone to events sent from Sentry frontend JavaScript SDKs and a further 15% from mobile SDK, a significant portion of sent events would directly benefit from better linkage between events. Considering that frontend applications almost always have a backend counter part, another 44% of ARR can be attributed to backend SDKs that would implicitly also benefit from a better tracing models. Wins all around!

While linked traces themselves are not identical to user sessions, we're aware that users have been asking for some kind of connectedness in various forms on GitHub as well as via Sales/Solution Engineers. Typically, in a frontend application context, users would expect Sentry to show them a user _session_. In such cases we explain that Sentry [does track sessions](#current-session-models-in-sentry-sdks), albeit in a flawed way. Right now, we cannot answer questions like, what happened in a previous trace that might have had an impact on the trace with an error. With linked traces, we can.

Looking at other observability providers, they have support for user sessions

- Datadog's browser RUM SDK [tracks a user session](https://github.com/DataDog/browser-sdk/blob/main/packages/core/src/domain/session/sessionManager.ts) via the browser's `sessionStorage` for [up to 15 minutes](https://docs.datadoghq.com/real_user_monitoring/browser/data_collected/).
- Honeycomb.io supports a [session id](https://docs.honeycomb.io/send-data/javascript-browser/honeycomb-distribution/) which is not persisted in storage.
- [Logrocket sessions](https://docs.logrocket.com/docs/what-defines-a-session) can span multiple tabs and have a lifetime of 30 minutes, with some further heuristics for closing tabs

Again, linked traces are not identical to sessions but they can also help answer questions that sessions could answer.

## Implications of Long-lived traces

As mentioned [above](#frontend-traces-and-user-journeys), our current long-lived traces in Browser JS have some negative implications on the Sentry UX:

- Multiple root spans (transactions): Our product can (and should) handle multiple root spans. However, there are some rough edges which are hard to solve from a UI/UX perspective. Our Trace explorer gives traces a name, for instance. If multiple root spans exist, we can only use a heuristic for which span name to use for the "trace name". Furthermore, multiple root spans contradict the conventional concept of a trace, where a trace should only consist of one root span.
- Trace Duration: As soon as a trace spans more than one root span or multiple events, the duration of the trace itself becomes meaningless. While we strongly recommend to generally avoid deducing information from the trace duration, we could improve the current situation by sending less long-lived traces
- Context: While long lived traces do potentially provide more context, given they could include spans or events that happened before an error, they can sometimes contain "too much" context. For instance, very long-running traces in web applications without navigations would contain close to the entire user journey. This makes it harder to understand cause-effect relationships within a trace.
- UI/UX of the trace view: Long running traces are not ideally displayed in the trace view, given the x-axis would span a large time frame. This makes it necessary for users to zoom in and pan around much more than for single-root span traces.
- Sampling and quota increase: If a trace is sampled positively, all transactions within this trace will be sampled positively. This also means that while the positively sampled trace is ongoing, we'd always propagate the positive sampling decision via the `sentry-trace` header to downstream services on outgoing requests. Assuming these services are configured to only sample already sampled traces, we'd send more events on an org-wide basis than if we rolled the dice more often (like in short-lived traces). This [increases quota usage](https://github.com/getsentry/sentry-ruby/issues/2318) for our customers without them necessarily being aware of it. 
 
If we can link traces, we can ultimately shorten individual trace lengths and remove most of these disadvantages again.

To be clear, the Sentry product will always need to support long-lived/multiple root span traces. While we can remove them from SDKs supporting this model, older SDK versions will stick around and users can also manually create long-lived traces.

# Options Considered

## [Preferred] Span Links

We propose to add links on a span level, as defined and specified by [OpenTelemetry](https://opentelemetry.io/docs/concepts/signals/traces/#span-links). In addition to linking to span ids, a span link also holds meta information about the link, collected via attributes. We'll make use of these attributes by annotating our created span links with a `sentry.link.type` attribute which we can later use in the product to query for linked traces.

### SDK APIs

To support adding span links, SDKs need to expose at least an `addLink` method on their respective `Span` interface. For completeness with OpenTelemetry, ideally they also expose `addLinks`:

```TypeScript
interface Span {
  // return value can differ depending on platform
  addLink(link: Link): this;
  addLinks(links: Link[]): this;
}
```

Furthermore, when starting spans (via `startSpan` functions), links can also be passed into the span start options:

```TypeScript
function startSpan(options: StartSpanOptions);

interface StartSpanOptions: {
  //... other options (name, attributes, etc)
  links?: Link[];
}
```

SDKs should follow the OpenTelemetry spec for the [`Link` interface](https://github.com/open-telemetry/opentelemetry-js/blob/main/api/src/trace/link.ts) as defined by the platform. Non-Otel SDKs should orient themselves on Otel, resulting in the following interface:

```typescript
interface Link {
  // contains the SpanContext of the span to link to
  context: SpanContext;
  // key-value pair with primitive values
  attributes?: Attributes;
}


// see https://github.com/open-telemetry/opentelemetry-js/blob/main/api/src/trace/span_context.ts
// or interface of respective platform
interface SpanContext {
  traceId: string,
  spanId: string,
  traceFlags: string,
}

type Attributes = Record<string, AttributeValues>
type AttributeValues = string | boolean | number | Array<string> | Array<boolean> | Array<number>
```

Note: On some platforms, the Otel `Link` interface exposes another optional property: `droppedAttributesCount`. POtel SDKs should support passing in this property as defined by the API but can further ignore it when serializing the span link to Sentry envelopes.  In [JS for example](https://github.com/open-telemetry/opentelemetry-js/blob/main/api/src/trace/link.ts), the `droppedAttributeCount` can be passed, while [Python](https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-api/src/opentelemetry/trace/span.py#L120) does not permit it. 
Non-Otel SDKs are free to ignore this property.

#### Usage Example

Adding span links should be possible at span start time, as well as when holding a reference to the span:

```typescript
// 1st trace starts
const pageloadSpan = startInactiveSpan(...)

// 2nd trace starts
const navigation1Span = startInactiveSpan({
  name: '/users', 
  links: [{
    context: pageloadSpan.spanContext(), 
    attributes: {
      'sentry.link.type': 'previous_trace'
    }
  }]
});

// 3rd trace starts
const navigation2Span = startSpan({name: '/users/:id'}, (span) => {
  span.addLink({
    context: navigation1Span.spanContext(), 
    attributes: {
      'sentry.link.type': 'previous_trace'
    }
  })
})
```

In this example, by adding span links, we can link from the last navigation trace all the way back to the initial pageload trace. By passing the `'sentry.link.type': 'previous_trace'` attribute, we can identify the link as a previous trace link in Sentry and display the spans accordingly. 

#### SDKs relying on Transactions

Adding span links should behave identically regardless of links being added to a root/segment (transaction) or child spans. For SDKs still having public APIs around transactions, their respective `Transaction` interface and `startTransaction` function(s) should support the same APIs. 

#### Storing links and previous traces

SDKs are free to chose whatever storage mechanism makes sense to store span links themselves as well as to hold references to a previous span. This is considered an implementation detail and out of scope for this RFC.

### Envelope Item Payload Changes

Span trees are serialized to transaction event envelopes in all Sentry SDKs. Therefore, the envelope item needs to accommodate span links in its payload.

We propose to store span links in the `trace` context if the root span has links, similarly to how we serialize root span attributes today:

```typescript
// event envelope item
{
  type: "transaction";
  transaction: string;
  contexts: {
    trace: {
      span_id: string;
      parent_span_id: string;
      trace_id: string;
      // new field for links:
      links?: Array<{
        "span_id": string,
        "trace_id": string, 
        attributes: Record<string, AttributeValue>,
      }>
      // ...
    }
  }
  // ...
}
```

For links stored in child spans, SDKs should serialize them to `spans[i].links`:

```typescript
// event envelope item
{
  type: "transaction";
  transaction: string;
  spans: Array<{
    span_id: string;
    parent_span_id: string;
    trace_id: string;
    // new field for links:
    links?: Array<{
      "span_id": string,
      "trace_id": string, 
      attributes: Record<string, AttributeValue>,
    }>
    // ...
  }>
  // ...
}
```

### Ingest / Relay

Relay should forward the span links in the format that is required for further processing and storage. 
Importantly, we must never require span links to be defined. They are completely optional.

TODO: This section lacks a lot of details we still need to clarify with the ingest team

### Storage

We need to adapt our events table to support storing span links in our current event storage. Furthermore, we need to take span links into account for the EAP storage architecture.

TODO: Evaluate if possible:

The span links need to be stored in a way that they can be queried. For example: Given a transaction `t`, list transactions that have span links to  `t`.
This would enable use cases where we could show "next" traces, instead of previous traces. 

TODO: This section lacks a lot of details we still need to clarify with the SnS team


## [Alternative] Previous Trace Id

A slightly simpler but less powerful approach to span links would be to specifically store a "previous trace id" attribute on the current root span and serialize it as such in the event envelope item.
Setting such a previous trace id could happen on `startSpan()` calls or by calling `span.setAttribute()` at any time. 

While this might seem simpler at first glance, it has a some drawbacks:
- Spans can only have a 1:1 relationship, either with a `traceId` or a `traceId-spanId` value. Span links support a 1:* relationship, where one span can link to multiple other spans in- or outside its trace
- Span links are an established concept in OpenTelemetry. With Sentry increasingly adapting Otel standards, as well as creating an OTLP endpoint in the future, we should embrace Otel-suggested solutions rather than building our own.
- Attributes are not indexed, meaning queries like getting the "next" instead of previous traces are likely impossible


# Drawbacks

- Implementing span links requires a lot of of changes across SDKs, ingest, SnS. Also there are product changes required to make use of links. 

# Answered Questions

- Can we do this with our current event storage? Are we blocked on EAP?
  Yes. We will certainly need to adapt our current event storage but it is possible to do this without being blocked on EAP. We'll separately also need to adjust the planned span schema for EAP but this is not a blocker.


- How would we handle errors outside of an active span?
  Errors happening while no span is active, should (as currently is the case in JS Browser SDKs) belong to the last created trace. Therefore, they will store all required fields in their `trace` context.

# Unresolved Questions

- Should we (try to) keep sampling decisions consistent for subsequent (frontend) traces? IOW: If we sample the initial trace, should all subsequent traces be force-sampled as well? 


# Tmp: Additional information

 While in backend SDKs most use cases have a clear definition for starting and ending a trace (the request lifecycle), frontend SDKs don't have clear borders when traces start and end. Therefore, over the years and iterations, we created different trace models for frontend SDKs where sometimes traces intentionally span more than one root span. Other times, traces end after a certain idle time or other debouncing mechanism.
