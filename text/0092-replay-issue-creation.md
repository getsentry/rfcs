- Start Date: 2023-05-15
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/92
- RFC Status: draft

# Summary

We want to detect certain categories of issues only available through the Session Replay product. The first of these issues is the "Slow Click" detection issue.

# Motivation

1. Inform the long-term strategy for detecting and ingesting Session Replay generated issues.
2. Provide actionable feedback to developers that could not otherwise be captured in a performance span or error event.
3. Increase product awareness in free-tier customers and encourage adoption.

# Options Considered

### Option 1: SDK

We create a set of detectors on the SDK. When a detector is activated we submit a new issue event. The issue creation process would be generic and would not involve any Replay-specific services to process.

**Pros:**

1. Can be tested in isolation without impacting existing production services.

**Cons:**

1. Uses quota.
2. There's overhead associated with submitting a new issue through an HTTP request.
3. Unable to use dynamic thresholds.
   - E.g. "Experienced 10 occurences in the past hour".
4. The replay containing the slow click could be sampled.

### Option 2: Ingest

We create a set of detectors on the backend. When a detector is activated we publish to the issue creation topic.

**Pros:**

1. Does not use quota.
2. Overhead is low.
   - Publishing to a Kafka consumer can happen asynchronously.
3. We can use dynamic thresholds.
   - E.g. "Experienced 10 occurences in the past hour".
4. Replay is guaranteed to be sampled.

**Cons:**

1. Poor rollout could impact service availability during testing period.

# Unresolved questions

# Decisions

No decisions have been made.
