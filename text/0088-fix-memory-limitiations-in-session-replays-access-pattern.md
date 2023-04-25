- Start Date: 2023-04-24
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/88
- RFC Status: draft

# Summary

The Session Replay index page will run out of memory when processing queries for our largest customers. This document contains proposed solutions for addressing this short-coming.

# Motivation

Our goal is to make the Session Replay product highly scalable. We expect changes to the product will eliminate our OOM issues and increase performance for customers with large amounts of ingested data.

# Background

The Session Replay data model is different from most at Sentry. Replays are received in parts referred to as "segments". One row does not represent one replay. Instead many rows are aggregated together to represent a single replay. When we ask a question such as "which replays did not visit this url?", we have to aggregate every row in the database (minus whatever rows were reduced by conditions in the WHERE clause). As it turns out the number of rows is very large and the amount of data is significant enough that we run out of memory on large customers.

**Key Ingest Considerations**

- Replay segments are not guaranteed to be received in order.
- Replay segments are typically sent every 5 seconds while the session is active.
- Replays can be "idle" for up to 30 minutes before sending a new segment when user activity resumes.
- Replays can be up to 1 hour in duration.

# Existing Solution

We have introduced a second, non-aggregated query which precedes our main aggregation query. This query will trigger if we are exclusively querying by static values which are consistent throughout the lifespan of a Replay. It will return a list of replay IDs which we can then pass to our main aggregation query. The aggregation query is then only responsible for aggregating a subset of replays (the pagination limit). This optimization allows us to query very efficiently while still providing aggregated results to the end user.

**Drawbacks**

The non-aggregated query does not allow **exclusive** filter conditions against **non-static** columns. For example, we can not say "find a replay where this url does not exist". The query will find _rows_ where that condition is true but it will not find _replays_ where that is condition true.

The non-aggregated query does not allow multiple, **inclusive** filter conditions against **non-static** columns. For example, we can not say "find a replay where this url exists and this other url exists". It will find rows which have both urls but not replays which have both urls. Transforming the `AND` operator to an `OR` operator does not satisfy the condition because it will match replays which contain one of the urls - not both.

# Options Considered

### Change the Product's Query Access Pattern

**Proposal**

Our current solution works well but there are escape hatches which require us to issue the aggregation query over the whole dataset. Those escape hatches should be closed.

- Remove ability to filter and sort by aggregated values (e.g. count_errors, activity_score).
- Remove ability to filter by negation values which change (e.g. urls).
- Remove ability to use the AND operator when a non-static value is present.
  - Filtering by browser_name AND os_name would be permitted.
  - Filtering by browser_name AND click_action would be disallowed.
    - Click rows do not store browser information because they are internally generated.
    - Should this condition change these filters could be supported.
  - Filtering by error_id AND url would be disallowed.
    - Filtering by error_id OR url would be allowed.

**Drawbacks**

- Significant reduction in index page quality.
- Removes the most important features of our index page. Count-errors sort, activity sort, duration sort and filter.

**Questions**

### Reduce the Scan Range on the Front End

**Proposal**

**Drawbacks**

**Questions**

### Reduce the Scan Range on the Back End

**Proposal**

**Drawbacks**

**Questions**

### Normalize Schema and Remove Snuba Join Restriction

**Proposal**

**Drawbacks**

**Questions**

### Migrate to CollapsingMergeTree Table Engine and Pre-Aggregate Data in Key-Value Store

**Proposal**

so the ingest flow essentially goes -> get a segment -> look up replay_id in KV store -> if replay_id exists, then collate the new data with the data in the KV -> flip the sign then write it to clickhouse

**Drawbacks**

**Questions**

### Stateful Streaming using Apache Spark or Similar Service

**Proposal**

**Drawbacks**

**Questions**

### Upgrade ClickHouse Version to Utilize Experimental Features

**Proposal**

**Drawbacks**

**Questions**

### Investigate Alternative Databases

**Proposal**

**Drawbacks**

**Questions**

# Selected Outcome

No outcome has been decided.
