* Start Date: YYYY-MM-DD
* RFC Type: feature / decision / informational
* RFC PR: <link>

# Summary

This document describes preferred capabilities of an expanded issue platform.  This
only covers the underlying data model and preferences for ingestion and pipeline without
detailed considerations for user experience or detailed technical designs.

# Motivation

The current issue platform is not much of a platform, it evolved out of the
grouping system which assigns a group (also referred to as issue) to an
(error/default/security) event when it is ingested.  Recently this has been
expanded so that transaction events can also have issues associated through
the performance issue detector.

This association is rather static and expensive to change.  Today to assign a
grouping hash the event has to pass through the entire pipeline at which point
the grouping code runs and assigns a fingerprint.  This fingerprint then is
statically associated with a group.

The consequences of this are limiting to us:

* merges/unmerges are incredibly expensive as they require rewrites in clickhouse.
  These are also lossy operations as some fidelity is lost whenever merges are happening.
* grouping / issue detection code cannot run on the edge as the final creation of
  the grouping hash requires expensive processing such as applying source maps,
  processing minidumps and run through symbolication.
* grouping implies issue creation which means that the information available for the
  grouping code can only take a single event into account.
* it makes metrics extraction at the edge for errors impossible as we do not know
  yet for what we want to extract metrics for.

Various suggestions have been proposed over the years for evolving this system
and some more detailed motivations can be found in the [Supergroups RFC](https://github.com/getsentry/rfcs/pull/29)

# Background

We have committed to evolving the issue platform over the next 12 months to bring
issues to more product verticals (performance, session replay and profiling).  We
also want to closer marry together the dynamic sampling feature and our issue
code so that we can ensure that for any issue a customer nagivates on, we have
sufficient sampled data available to be able to pointpoint to the problem and
are able to help the customer to resolve the issue.

# Desired Capabilities

This section goes more into detail of the individual capabilities and why they
are desirable.

## Lossless, Fast Merge / Unmerge

Today a merge involves a rewrite and inherently destroys some data because the
merge performs rewrites.  It can be seen as throwing data points into a larger
cloud and some information is lost about how they were distributed beforehand.

It also comes with a very high cost where large merges routinely cause backlogs
and load on clickhouse that make it impossible to use this feature at scale.

This is particularly limiting as we know that groups have a dependency to be too
precise and that merges are something we would like to enable more of.

A desirable property thus would be the ability to "merge" groups by creating an
aggregate view of other groups.  You can think of this operation similarly to a
graphics program that lets you group various shapes together but to ungroup back
to the original individual shapes on demand.  Because the invidiual groups remain
but they are "hidden" behind the merged group all their properties also remain in
some form.  For instance the short IDs are not lost.  Likewise data attached to
these groups can remain there (notes, workflow events etc.).

This would potentially also enable desired functionality such as
[supergroups](https://github.com/getsentry/rfcs/pull/29).

Cheap merges in particular would enable us to periodically sweep up small groups
into larger ones after the fact.

## Edge Issue Detection

The value of individual events within a predefined group goes down over time.  In
the case of errors as a user I have a high interest in the overall statistics
associated with them, but I'm unlikely to gain value out of every single event.
In fact I probably only need one or two errors for each dimension I'm filtering
down to, to understand enough of my problem.

The fingerprinting logic today however requires the entire event to be processed
before we are in the situation to properly detect that we already have seen a
certain number of events.  We are for instance already using a system to restricted
retaining of event data with minidumps where the cost of storage is significant.

For many event types however the cost of processing outways the cost of storage.
To enable detect of issues at the edge we likely need to explore a tiered approach
of fingerprinting.

### Multi Level Fingerprinting

The edge is unlikely to ever know precisely in which issue an event lands.  However
the edge might have enough information to de-bias certain event hashes.  As an example
while the final fingerprint for a JavaScript event will require source maps to be
applied at all times, the stability of a stack trace is high enough even on minified
builds within a single release.  This means that it becomes a possibility to create
hashes specifically for throtteling at the edge that the edge can compute as well.
A sufficiently advanced system could thus provide sufficient information to the edge
to drop a certain percentage of qualifying events.

### Sandboxed Edge Processing

Today all processing at the edge is done within the relay rust codebase.  While this
codebase is already relatively modular and in a constant path towards more modularization,
it requires a re-deployment and update of Relay to gain the latest code changes.  This
makes the system relatively static with regards to at-customer deployments.  It also
places some restrictions even within our own infrastructure with regards to the amount
of flexibility that can be provided for experimental product features.

We would like to explore the possibility of executing arbitrary commands at the edge
within certain parameters to make decisions.

* fingerprinting: with multi-level fingerprinting we might be able to make some of the
  fingerprinting dynamic and executed off a ruleset right within relay
* dynamic sampling rules: relay could make the sampling logic conditional on more complex
  expressions and logic, not expressable within the rule set of the system today
* issue detection: within a transaction performance issues can often be detected on the
  composition of contained spans.  For instance N+1 issues are detectable within a single
  event purely based on the database spans and the contained operations.  Some of this
  logic could be fine tuned or completely written within a module that is loaded by
  relay on demand.
* PII stripping: some of the PII stripping logic could be off-loaded to dynamic modules as
  well.

In terms of technologies considered the most obvious choice involves a WASM runtime.  There
are different runtimes which currently compiled down to WASM and in the most simplistic
case one could compile Rust or AssemblyScript down to a WASM module that is loaded on demand.

The general challenges with processing at the edge is that not all events currently contain
enough information to be processable there.  In particular minidumps and native events need
to undergo a symbolication step to be on the same level of fidelity as a regular error
event.  Likewise some transaction events might require more expensive processing to clean up
the span data.  Some of this is exploratory work.
