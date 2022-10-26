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

# Supporting Data

[Metrics to help support your decision (if applicable).]

# Options Considered

If an RFC does not know yet what the options are, it can propose multiple options.  The
preferred model is to propose one option and to provide alternatives.

# Drawbacks

Why should we not do this?  What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

* What parts of the design do you expect to resolve through this RFC?
* What issues are out of scope for this RFC but are known?
