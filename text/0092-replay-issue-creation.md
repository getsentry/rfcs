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

### Option 1: SDK Creates Issues Through the Error Interface

When the SDK encounters a "slow click" it will use `sentry.captureException(slowClick)` to create an error issue on the Issues platform.

**Pros:**

- Significantly larger customer reach (i.e. all javascript SDK customers).
- Opportunity to upsell customers on Session Replay from a "slow click" event.
- No code changes required on the Session Replay back end.
- No code changes required by the Issues team.

**Cons:**

- Requires SDK changes.
- Can not change issue sampling parameters without an SDK update.
  - Or can you? It depends on how protected this endpoint is. If the teams responsible for maintaining it are not interested in the replay team adding `if is_slow_click(event): then do special sampling stuff`.

**Questions:**

- Can we sample these issue events on the back-end?
  - Yes its certainly possible.
  - However, it depends on how protected this endpoint is. If the teams responsible for maintaining it are not interested in the replay team adding `if is_slow_click(event): then do special sampling stuff` then we will not be able to meet this criteria.
  - If error processing is functionally immutable (i.e. there is no organizational will-power to allow product teams to sample within the error pipeline) then we will not be able to sample on the back-end.

### Option 2: SDK Creates Issues Through an Issues HTTP Endpoint

When the SDK encounters a "slow click" it will use `http.post("/issues", data=slowClick)` to create an error issue on the Issues platform.

**Pros:**

- Significantly larger customer reach (i.e. all javascript SDK customers).
- Opportunity to upsell customers on Session Replay from a "slow click" event.
- No code changes required on the Session Replay back end.

**Cons:**

- Requires SDK changes.
- Requies code changes by the Issues team to create a generic interface for creating issues.

**Questions:**

- Can we sample these issue events on the back-end?
  - Yes its certainly possible.
  - However, it depends on how protected this endpoint is. If the teams responsible for maintaining it are not interested in the replay team adding `if is_slow_click(event): then do special sampling stuff` then we will not be able to meet this criteria.
  - If the issue interface is functionally immutable (i.e. there is no organizational will-power to allow product teams to sample within this interface) then we will not be able to sample on the back-end.

### Option 3: Replay SDK Pushes Issues to Session Replay Backend Which Raises an Issue

When the SDK encounters a "slow click" it will append the slow click to the recording events payload. The back-end will search for these events and then publish them to the Issues platform's kafka consumer.

**Pros:**

- We can sample slow click events without worrying about input from other teams.
- No code changes required by the Issues team.
- No SDK changes required as the SDK is already sending slow-click events.

**Cons:**

- Significantly smaller pool of customers who will see "slow click" issues.
- No opportunity to upsell the Session Replay product.
- Requies code changes by the Session Replay back-end team.
  - Requires addition of event sampling, issue platform integration, and merging of the replay-event and recording-event payloads.
  - Merging the replay-event and recording-event payloads together is not a trivial change and requires careful deployment.

# Unresolved questions

# Decisions

No decision has been made.
