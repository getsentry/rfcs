- Start Date: 2024-11-08
- RFC Type: feature 
- RFC PR: <[link](https://github.com/getsentry/rfcs/pull/141)>
- RFC Status: draft

# Summary

This RFC aims to introduce the ability to link or connect traces in Sentry. It involves SDKs, Ingest, Search and Storage, Backend and at a later stage product teams.
The goal of this initiative is to be able to link multiple traces together so that the Sentry product can show what happened before a trace while preserving the integrity of individual traces.
This RFC proposes to use "Span Links" as a vehicle specifying relationships between spans and traces. It also discusses other options considered, as well as concrete use cases for this feature.

# Motivation

At the time of writing this RFC, Sentry (the product as well as SDKs) cannot connect multiple traces to deliver a "bigger picture" of what happened before (or after) a specific trace. For example, for frontend applications, we would like to display a user journey (session). Today, we are always limited to the duration of one trace (id), which is handled and kept alive for different times across different SDKs.

TODO: Second problem: child spans outliving their parent spans within a trace

# Background

- TODO: OpenTelemetry Span Links
- TODO: Browser SDK trace model
- TODO: Mobile trace model

# Supporting Data

- TODO: Not much data available but we can list specific problems of long-living traces and lack of inter-trace context

# Options Considered

## [Preferred] Span Links

TODO: 
- SDK implementation (Otel interface, special link attributes)
- Ingest changes
- SnS changes (current event storage/EAP?)
- How to handle sampling
- How to handle non-transaction/span events: Last traceId

## [Alternative] Previous Trace Id
TODO

# Drawbacks

TODO:
- Requires a lot of changes across SDKs, ingest, SnS
- Sampling implications

# Unresolved questions

- Can we do this with our current event storage? Are we blocked on EAP?

# Tmp: Additional information

 While in backend SDKs most use cases have a clear definition for starting and ending a trace (the request lifecycle), frontend SDKs don't have clear borders when traces start and end. Therefore, over the years and iterations, we created different trace models for frontend SDKs where sometimes traces intentionally span more than one root span. Other times, traces end after a certain idle time or other debouncing mechanism.
