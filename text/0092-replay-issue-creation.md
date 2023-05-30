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

### Option 1: SDK Creates Issues With "captureException" Method

When the SDK encounters a "slow click" it will use `sentry.captureEvent(slowClick)`.

**Pros:**

- Significantly larger customer reach (i.e. all javascript SDK customers).
- Opportunity to upsell customers on Session Replay from a "slow click" event.
- No code changes required on the Session Replay back end.
- No code changes required by the Issues team.

**Cons:**

- Requires SDK changes.
- Can not change issue sampling parameters without an SDK update.
  - Or can you?
  - What if we sample within the error processing pipeline on the back-end?
  - If error processing is functionally immutable (i.e. there is no organizational will-power to allow product teams to sample within the error pipeline) then we will not be able to sample on the back-end.
- Consumes from user error quota: If too noisy, might give the impression we're 'wasting' their error quota

### Option 2: SDK Creates Issues Through an Issues HTTP Endpoint

When the SDK encounters a "slow click" it will use `http.post("/issues", data=slowClick)` to create an error issue on the Issues platform.

**Pros:**

- Significantly larger customer reach (i.e. all javascript SDK customers).
- Opportunity to upsell customers on Session Replay from a "slow click" event.
- No code changes required on the Session Replay back end.
- We can sample slow click issues on the backend.
  - This would require buy-in and coordination from the Issues team.
  - There is nothing preventing us from looking at an HTTP request and making a go/no-go decision.

**Cons:**

- Requires SDK changes.
- Requies code changes by the Issues team to create a generic interface for creating issues.
  - This would likely disrupt our June 18 deadline.
  - Unless the Issues team has excess capacity and a willingness to work on it immediately.

### Option 3: Replay SDK Pushes Issues to Session Replay Backend Which Raises an Issue

When the SDK encounters a "slow click" it will append the slow click to the recording events payload. The back-end will search for these events and then publish them to the Issues platform's kafka consumer.

**Pros:**

- We can sample slow click events on the back-end without worrying about input from other teams.
- No code changes required by the Issues team.

**Cons:**

- Requires the Session Replay SDK.
  - Significantly smaller pool of customers who will see "slow click" issues.
- Requires code changes by the Session Replay back-end team.
  - Requires addition of event sampling, issue platform integration, and merging of the replay-event and recording-event payloads.
  - Merging the replay-event and recording-event payloads together is not a trivial change and requires careful deployment.

# Unresolved questions

# Decisions

No decision has been made.
