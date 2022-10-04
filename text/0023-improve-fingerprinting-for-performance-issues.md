* Start Date: 2022-10-04
* RFC Type: feature 
* RFC PR: <link>

# Summary

Performance issues has started with detecting N+1 issues and adding them to the issues page. This was a first proof of concept, now we are looking to add different types of performance issues to and group those events on the issues page. However there is an drawback of performance spans and transactions versus error events. Error events have titles and stack traces which can provided unique meta-data for [fingerprinting](https://docs.sentry.io/product/data-management-settings/event-grouping/fingerprint-rules/) and [grouping](https://docs.sentry.io/product/sentry-basics/grouping-and-fingerprints/). Today spans do not necessarily provide enough distinct metadata to be able to efficaciously group performance events.

# Motivation

We want to enable scaling out the number of different types of performance issues which can be detected and grouped.

# Background

We need communicate the issue around fingerprinting for performance issues, and suggest different ways to add more contextual data to improve fingerprinting. Alternatively we are open to solutions which work around fingerprinting.

# Supporting Data

Example performance issue type proposals (only ideation from this list and for context not commitments for delivery):
* Slow DB spans
* Consecutive similar spans
* Identical spans
*  N+1 DB Queries
* N+1 API Calls
* UI Freeze
* Slow Assets
* Component Re-renders
* Main thread I/O + ANR/Slow Frame
* Shader Compilation
* Txn Deviations
* Cancelled HTTP Requests / Flaky Network
* Degraded performance for a demographic
* Excessive DOM size

# Options Considered

1. Client side/SDK Includes application file name in span/transaction
2. Can we fetch more info on Sentry server side from profiling if available 
3. Could SDKs detect something and create a unique identifier artificially to empower fingerprinting?

# Drawbacks

Depending on where we put the logic for adding more contextual data, would we be adding too much overhead in SDKs/host application.

# Unresolved questions

* Can we specify why fingerprinting is required?
* what the threshold would be for uniqueness to enable fingerprinting for performance issues?
