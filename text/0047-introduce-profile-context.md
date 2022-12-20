- Start Date: 2022-12-20
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/47
- RFC Status: draft

# Summary

We want to introduce the concept of a profiling context, much like a tracing context, starting with
transactions so we can easily relate a group of transactions back to the respective profile.

# Motivation

We already have a way to relate a group of profiles back to the respective transaction. And up to
this point, we have been using this relationship to map single transaction at a time to the
respective profile. This is now insufficient as we would like to be able to relate a group of
transactions back to the respective profile. This is to enable various touch points into profiling
in the existing performance product.

The intended use cases include

- fetching a list of transaction with the profile ID
- filtering transactions to only those that have a profile

# Background

Profiles will be closely associated to transactions and creating this relation will enable us to
build a richer integration between the Performance and Profiling products.

Since the Profiling product will be initially tied to the Performance product, we want to ensure
that there is a smooth integration through various touch points to allow users to navigate from
Performance to Profiling and vice versa.

# Options Considered

## SDK

### Option A: Add a new context type

Introduce a key in the transaction payload under contexts called `profile` to include information
related to the profile.

```json
{
  ...,
  "contexts": {
    ...,
    "profile": {
      "profile_id": "<id>"
    }
  }
}
```

### Option B: Use the existing trace context

Use the existing trace context and add a new key for the `profile_id`.

```json
{
  ...,
  "contexts": {
    ...,
    "trace": {
      "profile_id": "<id>"
    }
  }
}
```

## Storage

To support querying for this relationship, we have to store the profile ID, extracted from the
profile context set by the SDK, on the existing transactions dataset. The types of queries we want
to do are as follows:

1. Selecting the profile ID
2. Selecting rows that have a profile ID since not all transactions will have a profile
3. Selecting a transaction with a specific profile ID (this use case is less common)

### Option A: Add a new column to the transactions dataset

The new `profile_id` column will have type `Nullable(UUID)`. The queries would roughly look like

1. `SELECT profile_id FROM transactions_local`
2. `SELECT ... FROM transactions_local WHERE isNotNull(profile_id)`
3. `SELECT ... FROM transactions_local WHERE profile_id = "<id>"`

### Option B: Use the contexts columns on the transactions dataset

The `profile_id` will be added to the existing array columns for contexts. The queries would roughly
look like

1. `SELECT contexts.value[indexOf(contexts.key, "profile_id")] FROM ...`
2. `SELECT ... FROM ... WHERE has(contexts.key, "profile_id")`
3. `SELECT ... FROM ... WHERE contexts.value[indexOf(contexts.key, "profile_id")] = "<id>"`

# Drawbacks

## Option A:

1. Have to add a new column to the transactions dataset

## Option B:

1. Is there bloom filter index on contexts? Will it be performant enough?

# Unresolved questions

- Which option should we use for storing the profile ID on the transaction?
- The relationship between errors and profiles are out of scope for this RFC.
