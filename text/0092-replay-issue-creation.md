- Start Date: 2023-05-15
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/92
- RFC Status: draft

# Summary

The Session Replay team wants to detect certain categories of issues that can greatly benefit from videos and context in the Session Replay product.

These issues can only be detected on the SDK. The Replay back-end will never have enough data to find these issues. For that reason this is primarily an SDK driven workload. What role should the Replay back-end have in Replay issue creation? Should the Replay SDK use the Replay back-end to generate new issues or should the SDK generate those issues through a generic, non-replay-specific interface? Each option would have significantly different product implications that will be discussed below.

# Motivation

1. Inform the long-term strategy for detecting and ingesting Session Replay generated issues.
2. Provide actionable feedback to developers that could not otherwise be captured in a performance span or error event.
3. Increase product awareness in platform customers and encourage adoption.

# Options Considered

### Option 1: SDK Generates Issues Through a Generic Interface

When the SDK encounters a "replay issue" it will make an HTTP request to a generic interface which will handle the issue creation process.

**Pros:**

1. We can be tested in isolation without impacting existing production services.
2. We can expose these new features in a more product agnostic way.
   - This would allow us to reach much larger customer segments when compared to Replay customers.

**Cons:**

1. Uses errors quota.
2. Unclear if we're able to use dynamic thresholds.
   - E.g. "Experienced 10 occurences in the past hour".
3. The replay containing the issue could not be sampled.

### Option 2: SDK Generates Issues Through a Session-Replay Specific Interface

The SDK publishes a "replay issue" to the Replay back-end. The back-end will decide to process the issue or not.

**Pros:**

1. Does not use errors quota.
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

We have decided to couple these new issues to the Session Replay product and use the Session Replay back-end to process issue events. Generic issue interfaces are not well supported at the time of writing. Using the Session Replay back-end we can accomplish our product goals. Should an HTTP interface for creating issue events be created this RFC can be re-addressed.