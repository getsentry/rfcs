- Start Date: 2024-07-12
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/138
- RFC Status: draft

# Summary

The hierarchy between Pageload Spans and SSR Spans is currently very confusing.
SSR Spans are the ancestors of Pageload Spans, even though in a real-world scenario the Pageload is always the first thing that happens.
This document discusses how this came to be and how it could be improved.

# Motivation

Today SSR traces look as follows:

![Confusing Trace with Pageload Span being longer than Trace Root](0138-confusing-trace.png)

The server is the root of the trace and the Pageload Span is attached to some span part of the server transaction.
This is the case because the client SDK loads when the page is served and loaded on the end-user's browser.

If we look closely, the trace looks weird though.
The pageload span starts before the trace root even started.
The reason for this is because we are using browser timings for when the initial page request started as the start timestamp for the pageload span.

UX-wise it would be ideal, if the SSR span were a child of the "request" span, which is a child of the "pageload" span.
That way, we are displaying things in the actual order they're happening.

# Options Considered

We can solve this two ways:

- Flipping the order in the SDKs
- Flipping the order in Sentry

None of the options considered are entirely straight forward.

## Flipping the order in the SDKs

The way this would work is for the server SDK to generate an ID that will be used for two things:

- Optimistically use this ID for the `parent_span_id` of the SSR Span.
- Make the Browser SDK use this ID as the `span_id` for the "request" span.

The ID would need to be transferred from the server to the client in some way.
For this we could hijack the existing `baggage` meta tag implementations.

The drawbacks of flipping the order in the SDK is that we would make the data incorrect:
By optimistically setting the `parent_span_id` of the SSR Span, we may run into situations where we unintentionally orphan that span. (For example when somebody requests the page with a non-browser client that will never run the Browser SDK)

An additional drawback is that we would have to implement this functionality in all of Sentry's SDKs.

## Flipping the order in Sentry

TODO:
I would need performance team people to chime in here to outline possibilities and limitations.
In general I think we should evaluate two approaches: Flipping at ingestion-time, and flipping at read time.

Flipping at ingestion time is hard because you basically don't know when your trace is complete enough to make the swapping decision.

Flipping at read time is hard because you would need all the spans of the entire trace to make an informed flipping decision. It is not enough to just look at transaction hierarchy.

Flipping serverside is potentially hard because you don't have any domain specific knowledge of what subtree should end up as child of the "request" span. An idea would be to always use the trace root as subtree.

A potential downside is that it's not transparent to developers (SDK devs and Sentry users) what the hell is happening and why spans are being flipped.
