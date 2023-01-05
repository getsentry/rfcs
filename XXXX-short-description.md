- Start Date: 2023-01-05
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/48
- RFC Status: draft

# Summary

This RFC is almost exactly the same as https://github.com/getsentry/rfcs/pull/47.

Right now errors and transactions are tagged with the replay_id simply on the tags object in the event schema. This isn't ideal as tags should be reserved for user use only.

We'd like to create a context `replay` which for now would contain the singular field `replay_id`.

We also should consider moving this out of the tags column within clickhouse for errors/txs. The replay_id is ideally stored as its own column

# Options Considered

For the SDK event schema, instead of a nested context we could just add it as a top level "replay_id".

For the clickhouse schema change, instead of adding a dedicated replay_id column, we could instead add it to contexts, or leave it in tags.

# Drawbacks

This will require some backwards compatibility changes and overall

# Unresolved questions

- Need a go-ahead on event schema proposal, snuba schema changes.
