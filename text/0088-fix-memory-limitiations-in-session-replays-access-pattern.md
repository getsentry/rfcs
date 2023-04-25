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

Any option may be accepted in whole or in part. Multiple options can be accepted to achieve the desired outcome. The options are ordered from perceived ease to perceived difficulty.

### Change the Product's Query Access Pattern

**Proposal**

Our current subquery solution works very well. However, there are escape hatches which require us to issue an aggregation query over the whole dataset. Those escape hatches should be closed.

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

The number of rows aggregated can be reduced by restricting the maximum time range we query over. We should validate the timestamp range such that it does not exceed a 24-hour period. This would satify every organization which ingests fewer than 1 billion replay-segments every 90 days.

**Drawbacks**

- To search for a unique value a user would need to issue a query for each day of the retention period or until the value was found.
- Small customers would not see any replays on their index page due to the limited window size.
  - Necessitates a special flag for large customers to enable this optimization.
  - We may not know who needs this flag in advance and we may present a degraded customer experience without realizing.

**Questions**

### Reduce the Scan Range on the Back End

**Proposal**

The number of rows aggregated can be reduced by restricting the maximum time range we query over. For select queries the backend can issue multiple queries on subsets of the range. For example, if we assume that no sort value was provided or that the sort value was applied to the timestamp column then the back end can transparently query a subset of the window attempting to populate the result set without querying the entire range.

**Drawbacks**

- Requires O(retention_days) queries to satisfy the result set in the worst case.
- Adds an additional layer of complexity and does not solve our OOM issue.

**Questions**

### Normalize Schema and Remove Snuba Join Restriction

**Proposal**

- Normalize schema.
- Use joins.

**Drawbacks**

- Performance.

**Questions**

### Migrate to CollapsingMergeTree Table Engine and Pre-Aggregate Data in Key-Value Store

**Proposal**

Instead of aggregating in ClickHouse we should maintain a stateful representation of the Replay in an alternative service (such as a key, value store). Additionally, we will migrate to the "VersionedCollapsingMergeTree" table engine and write our progress incrementally.

The versioned engine works as follows:

- A sign is used to determine whether the row is a state row or cancel row.
- A row can be canceled by re-writing the row with a negative sign.
- New state rows can be written by incrementing the version and assigning a positive sign.
- The version and row state must be stored or otherwise fetched from ClickHouse before each write.

The ingestion process can be described as follows:

- A replay-segment is received.
- The replay-id is used to look up previously aggregated data in the KV store.
  - If data was returned collate it with the new data and store.
  - If data was not returned store the new data.
- The new row is written to ClickHouse with the version column incremented by 1.
- The old row is re-written to ClickHouse with the sign value set to -1.

**Drawbacks**

- The aggregation process is not expected to be atomic and we will encounter race-conditions where two segments with the same replay-id attempt to mutate the same key at the same time.
  - To solve this we will need to partition our Kafka messages by replay-id and process sequentially.
  - This has scalability limitations but those limitations are likely to be less than existing limitations.
  - Aggregation states can be updated atomicly with some databases. See "Use Alternative OLAP Database" proposal.
  - Alternatively we can tolerate losing aggregation states and continue using parallel consumers.
- Kafka will sometimes produce duplicate messages. If we assume order we can set a requirement on segment_id > previous_segment_id.
  - Order can not be assumed. Valid aggregation states could be lost.
  - A delay in scheduling in Relay could cause segment_id 1 to be processed prior to segment_id 0.
  - This is expected to be uncommon but not impossible.
  - Alternatively, we could tolerate duplicates and accept that segment_count and other values have some margin of error.
- To eliminate the need for grouping queries we would need to supply the `FINAL` keyword.
- Our column types are not ideal for this use case.

**Questions**

### Stateful Streaming using Apache Spark or Similar Service

**Proposal**

Instead of aggregating in ClickHouse we should aggregate our replays in a stateful service such as Apache Spark before writing the final result to ClickHouse.

TODO: Josh to fill in specifics.

**Drawbacks**

- Replays are not available until they have finished.
- There are no existing Apache Spark installations within the Sentry org.
- The Replays team is not large enough or experienced enough to manage a Spark installation.
  - This would require another team assuming the burden for us.
  - Otherwise, additional budget would need to be allocated to the Replays team to hire outside experts.

**Questions**

### Upgrade ClickHouse Version to Utilize Experimental Features

**Proposal**

Upgrading to a newer version of ClickHouse will enable us to use experimental features such as "Live View" and "Window View".

**Drawbacks**

- Would require Sentry to manage the ClickHouse installation.
  - Feature is not present in a stable release.
  - Feature is not present on any version of ClickHouse in Altinity.

**Questions**

### Use an Alternative OLAP Database

**Proposal**

OLAP Databases such as Apache Pinot support upserts which appear to be a key requirement for the Replays product. An aggregation state schema can be defined for merging columns in real-time https://docs.pinot.apache.org/basics/data-import/upsert.

**Drawbacks**

- Changes to the data model would be necessary. We will not be able to aggregate array columns.
- Pinot has ordering constraints.
  - If segments arrive after their successor has already been ingested the aggregated state will not contain those rows.
- There are no existing Apache Pinot installations within the Sentry org.
- The Replays team is not large enough or experienced enough to manage a Pinot installation.
  - This would require another team assuming the burden for us.
  - Otherwise, additional budget would need to be allocated to the Replays team to hire outside experts.
- We need to re-write our application logic for querying the datastore.
- Migration pains.

**Questions**

### Use an Alternative OLTP Database

**Proposal**

OLTP databases such as PostgreSQL and AlloyDB support updates which appear to be a key requirement for the Replays product.

**Drawbacks**

- Race conditions will require single-threaded processing of replay events.
- Duplicate messages will necessitate ordering requirements.
- Always a possibility for dropped and duplicated data regardless of safe guards.
- AlloyDB is still in developer preview on Google Cloud.
- We need to re-write our application logic for querying the datastore.
- Migration pains.

**Questions**

# Selected Outcome

No outcome has been decided.
