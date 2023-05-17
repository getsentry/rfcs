- Start Date: 2023-05-15
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/92
- RFC Status: draft

# Summary

We want to detect certain categories of issues only available through the Session Replay product. These issues can only be detected on the SDK. The Replay back-end will never have enough data to find these issues. For that reason this is primarily an SDK driven workload. The question is: what role should the Replay back-end have in Replay issue creation? Should the Replay SDK use the Replay back-end to generate new issues or should the SDK generate those issues through a generic, non-replay-specific interface? Each option would have significantly different product implications that will be discussed below.

# Motivation

1. Inform the long-term strategy for detecting and ingesting Session Replay generated issues.
2. Provide actionable feedback to developers that could not otherwise be captured in a performance span or error event.
3. Increase product awareness in platform customers and encourage adoption.

# Options Considered

### Option 1: SDK

When the SDK encounters a "replay issue" it will make an HTTP request to a generic interface which will handle the issue creation process.

**Pros:**

1. Can be tested in isolation without impacting existing production services.

**Cons:**

1. Uses quota.
2. Unclear if we're able to use dynamic thresholds.
   - E.g. "Experienced 10 occurences in the past hour".
3. The replay containing the issue could be sampled.

### Option 2: Ingest

The SDK publishes a "replay issue" to the Replay back-end. The back-end will decide to process the issue or not.

**Pros:**

1. Does not use quota.
2. Overhead is low.
   - Publishing to a Kafka consumer can happen asynchronously.
3. We can use dynamic thresholds.
   - E.g. "Experienced 10 occurences in the past hour".
4. Replay is guaranteed to be sampled.

**Cons:**

1. Poor rollout could impact service availability during testing period.
2. Requires coordination between the SDK and Ingest to create new issue types.

# Unresolved questions

# Decisions

No decisions have been made.
