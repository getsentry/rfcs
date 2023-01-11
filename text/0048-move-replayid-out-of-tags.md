- Start Date: 2023-01-05
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/48
- RFC Status: approved

# Summary

This RFC is almost exactly the same as https://github.com/getsentry/rfcs/pull/47.

Right now replay_ids are added to the error/transaction event tags object in the [event schema](https://sentry.io/organizations/sentry/performance/summary/replays/?project=11276&query=&statsPeriod=24h&transaction=%2Fsettings%2Faccount%2Femails%2F). This isn't ideal as tags should be reserved for user use only.

We'd like to create a context object `replay` which for now would contain the singular field `replay_id`.

We also want to move this potentially out of the tags columns within clickhouse for errors/txs. The replay_id can be stored as its own column or as a key in contexts.

# Motivation

Replays are linked together with errors and transactions throughout the product, relying on the current tag setup. We want to do this in a non-janky future-proof way.

# Options Considered

## SDK

### Option A: Add a new context type

```json
{
  ...,
  "contexts": {
    ...,
    "replay": {
      "replay_id": "<id>"
    }
  }
}
```

### Other Options

I suppose we could add the "replay_id" top level to contexts. Not sure what other options there could be.

## Storage

### Option A: Add a new column to the transactions dataset

The new `replay_id` column will have type `Nullable(UUID)`.

### Option B: Use the contexts columns on the errors/transaction dataset

The `replay_id` will be added to the existing array columns for contexts.

### Option C: Continue to store replay_id as a tag

From what I understand a high cardinality value like replay_id can cause poor performance with the bloom filter index, this may not be ideal.

# Drawbacks

Regardless of what options we choose, it will require work to be done, and backwards compatibility changes made in places.

# Unresolved questions

- Need a go-ahead on event schema proposal
- Is adding new columns for the replay_id the right path forward?

# Decisions

Going with a new context object ```{"replay":{"replay_id"}}``` on the SDK, and new columns in snuba storage.
