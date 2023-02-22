- Start Date: 2023-01-13
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/60
- RFC Status: draft

# Summary

Today, replays are associated with frontend events (errors, transactions, etc.) via tagging the events with the replay_id. We also tag replays with the associated event_id, which allows us to search / rank replays by their associated errors.

We'd like to take this a step further, and link downstream events that occur on the backend with the replay.

This feature will likely require cross-team collaboration, so a few options are presented below.

# Motivation

Far and away the most useful replays for developers are those that occur with errors associated. There are cases where no frontend error occurs, but a backend one does. A developer seeing this backend error could find a replay that caused it extremely useful. For one, a developer can see how a backend error manifests in the user experience and how impactful/detrimental it was to the user experience. This bridges the backend to the frontend. Alternatively, if a developer is debugging a frontend error, they can more easily uncover if the root cause was something deeper in the stack (i.e., stemming from the backend).

Also, we're able to give a more complete user session view by communicating to customers _all_ errors that happen in their user session.

Additionally, part of our Session Replay strategy is to more deeply integrate replays in the existing product experiences to increase the overall value of the Sentry platform. Issues is our bread and butter, and we want to be able to provide valuable replays for frontend and backend errors.

On the performance side, we want to be able to connect backend transactions to replays. For example, seeing how a slow API translates to the user experience.

## Supporting quotes

> XX does a good job of displaying the session replays. To me the biggest differentiator that Session Replay has is its connectivity to the rest of the Sentry ecosystem.
> XX is perfect for determining front-end only issues, but doesn't give enough information to find root causes when the issue is deeper in the system. and It would be great if we could link replays to BE errors. This is our current setup. 1) FE Web App; 2) BE Web App.

# Options Considered

## Option A: Dynamic Sampling Context / Baggage Header

[Link To relevant docs about dynamic sampling context / baggage](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#baggage)

We'd add a new baggage http header `sentry-replay_id`. This value would automatically make it onto the trace envelope header, and from there we could add it onto the event's payload if it exists.

- in `post_process`, if a replay_id exists on the event (we've previously defined a context for this) emit a message to our snuba processer which would write the `event_id`/`replay_id` to our replays table. [Link to post_process code where we'd emit kafka message](https://github.com/getsentry/sentry/blob/b1c6aa7b1a4ca0bfa2f402df61bf5d23b169e7ed/src/sentry/tasks/post_process.py#L452)

## Option B: sentry-trace Header

[Link to sentry-trace header information](https://develop.sentry.dev/sdk/performance/#header-sentry-trace)

- The current sentry-trace header format is `sentry-trace = traceid-spanid-sampled`. If we want to maintain compatibility with traceparent/zipkin-b3, we'd extend this to add the flags field. The format would be `traceid-spanid-sampled-flags`, of which flags can contain 8 bits. We'd add a "has_replay" bit to the flags field.
- In ingest we'd then add `hasReplay:true` somewhere on the event.
- in `post_process`, if this flag is true, we'll emit an event for further processing
- We'd need to wait a little bit to ensure that the corresponding replay_event to our backend error is written. We'd then do a lookup to get the replay_id, then finally emit a message to our snuba processer which would write the `event_id`/`replay_id` to our replays table.

## Option C:

- Since we _do_ have the trace_id on the replay events, we could do something like the following:
- no SDK changes needed
- in the background, consistently run a query where we take all trace_ids associated with replays, and run clickhouse queries to find the associated backend transactions with replays.
- we'd then emit an event that gets written to our clickhouse table which contains the replay_id and event_id.
- this likely does not scale well as the number of replays/traces is unbounded.

## Option D:

- This is unlikely to be done, but there has been talk before of creating a "graph" type datastore of events, where you could pass a list of events/traces/issues and quickly retrieve back a list of associated events. If we had a store like this, we'd simply pass it a transaction_name/issue_id/list of traces, and get back a list of replay_ids.
- This store would not help with combined queries like "show me replays greater than 1 min that have a backend error associated", as I assume we could not join it with a clickhouse query easily. It would only be for showing associated replays on a backend issue / transaction / event.

### Option E:

... There may be other options I haven't considered and am open to more discussion.

# Drawbacks

## Option A

A thing to keep in mind when adding a replay ID to the Dynamic Sampling Context is the immutability of DSC and traces starting in the backend.

Simple example: A trace starts in the backend for a server-side rendered website, DSC is frozen there, if we assume that DSC cannot be unfrozen, the frontend cannot add a replay ID as part of the pageload transaction.

Given this drawback, could we add this to a baggage header that may or may not be part of the DSC?

## Option A

This requires a decent amount of cross-team collaboration and a lot of SDK modifications potentially. We may want to do this anyways for dynamic sampling, as we've discussed always having associated transactions during a replay always sampled.

## Option B

This in every way feels inferior to option A, as the backend is still quite complicated as there's a race condition.

## Option C

This is very brittle and likely wouldn't scale super well. A naive solution if SDK changes aren't possible.

## Option D

This is a lot of work and may not be feasible now.

# Unresolved questions

- What % of backend errors would have a replay associated with them today, given that only replays tagged via `sessionSampleRate` will be eligible for this relation?
