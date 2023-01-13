- Start Date: 2023-01-13
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/60
- RFC Status: draft

# Summary

Right now Session Replays are associated with frontend events (errors, transactions, etc.) via tagging the events with the replay_id. We also tag replays with the associated event_id, which allows us to search / rank replays by their associated errors.

We'd like to take this a step further, and link downstream events that occur on the backend with the replay.

This feature will likely require cross-team collaboration, so a few options are presented.

# Motivation

Far and away the most useful replays are those that occur with errors associated. There are cases where no frontend error occurs, but a backend one does. A developer seeing this backend error could find a replay that caused it extremely useful.

# Background

The reason this decision or document is required. This section might not always exist.

# Supporting Data

- TODO

# Options Considered

Option A:

- through the `sentry-trace` header, or dynamic sampling context, propagate a has-replay flag or replay id
- modify backend SDKs to append the replay_id / flag on to the `trace` object
- in post processing of an event, forward these events to a replay consumer for further processing
  - if we have the replay_id, we can simply writ the event_id/replay_id to our clickhouse table
  - if we only have a flag, we'll have to query on our replays table for the trace_id -> replay_id association. we may have to insert a delay here because of that.
- We may want to the SDK portion anyways, as with dynamic sampling we'll likely want to sample events w/ replays

Option B:

- Since we _do_ have the trace_id on the replay events, we could do something like the following:
- no SDK changes made at all
- in the background, consistently run a query where we take all trace_ids associated with replays, and run clickhouse queries to find the associated backend transactions with replays.
- we'd then emit an event that gets written to our clickhouse table which contains the replay_id and event_id.
- this likely does not scale well as the number of replays/traces is unbounded.

Option C:

- This is unlikely to be done, but there has been talk before of creating a "graph" type datastore of events, where you could pass a list of events/traces/issues and quickly retrieve back a list of associated events. If we had a store like this, we'd simply pass it a transaction_name/issue_id/list of traces, and get back a list of replay_ids.
- This store would not help with combined queries like "show me replays greater than 1 min that have a backend error associated", as I assume we could not join it with a clickhouse query easily. It would only be for showing associated replays on a backend issue / transaction / event, and

Option D:

... There may be other options I haven't considered and am open to more discussion.

# Drawbacks

### Option A

This requires a decent amount of cross team collaboration. Although we may want to do the SDK portion anyways for dynamic sampling.

### Option B

This likely doesn't scale very well, although i'm curious with an index on trace_id if it wouldn't be terrible.

### Option C

This is a lot of work and may not be feasible now, if ever.

# Unresolved questions

- What % of backend errors would have a replay associated with them today, given that only replays tagged via `sessionSampleRate` will be eligible for this relation?
