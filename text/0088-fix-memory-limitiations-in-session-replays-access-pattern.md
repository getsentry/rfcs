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
- Replays can be "idle" for up to 15 minutes before sending a new segment when user activity resumes.
- Replays can be up to 1 hour in duration.

# Existing Solution

We have introduced a second, non-aggregated query which precedes our main aggregation query. This query will trigger if we are exclusively querying by static values which are consistent throughout the lifespan of a Replay. It will return a list of replay IDs which we can then pass to our main aggregation query. The aggregation query is then only responsible for aggregating a subset of replays (the pagination limit). This optimization allows us to query very efficiently while still providing aggregated results to the end user.

**Drawbacks**

There are aggregated values which users want to sort and filter on. Columns such as count_errors and activity which are prominently featured on our index page. Sorting and filtering by these values disables the preflight query and only runs the aggregated query.

The non-aggregated query does not allow **exclusive** filter conditions against **non-static** columns. For example, we can not say "find a replay where this url does not exist". The query will find _rows_ where that condition is true but it will not find _replays_ where that is condition true.

The non-aggregated query does not allow multiple, **inclusive** filter conditions against **non-static** columns. For example, we can not say "find a replay where this url exists and this other url exists". It will find **ROWS** which have both urls but not **REPLAYS** which have both urls. Transforming the `AND` operator to an `OR` operator does not satisfy the condition because it will match replays which contain one of the urls - not both.

# Options Considered

Any option may be accepted in whole or in part. Multiple options can be accepted to achieve the desired outcome. The options are ordered from perceived ease to perceived difficulty.

### 1. Change the Product's Query Access Pattern

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

### 2. Reduce the Scan Range on the Front End

**Proposal**

The number of rows aggregated can be reduced by restricting the maximum time range we query over. We should validate the timestamp range such that it does not exceed a 24-hour period. This would satify every organization which ingests fewer than 1 billion replay-segments every 90 days.

**Drawbacks**

- To search for a unique value a user would need to issue a query for each day of the retention period or until the value was found.
- Small customers would not see any replays on their index page due to the limited window size.
  - Necessitates a special flag for large customers to enable this optimization.
  - We may not know who needs this flag in advance and we may present a degraded customer experience without realizing.

**Questions**

### 3. Reduce the Scan Range on the Back End

**Proposal**

The number of rows aggregated can be reduced by restricting the maximum time range we query over. For select queries the backend can issue multiple queries on subsets of the range. For example, if we assume that no sort value was provided or that the sort value was applied to the timestamp column then the back end can transparently query a subset of the window attempting to populate the result set without querying the entire range.

**Drawbacks**

- Requires O(retention_days) queries to satisfy the result set in the worst case.
- Adds an additional layer of complexity and does not solve our OOM issue.

**Questions**

### 4. Normalize Schema and Remove Snuba Join Restriction

**Proposal**

- Normalize schema.
- Use joins.

**Drawbacks**

- Performance.
- Requires Snuba work.

**Questions**

### 5. Migrate to CollapsingMergeTree Table Engine and Pre-Aggregate Data in Key-Value Store

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

- Bruno Garcia asked: How does the sequential message processing requirement impact scale?
  - The performance of a single consumer will be dominated by the performance of our Key, Value store. If we assume 10ms to process each message then we will process 100 messages per second per consumer. Because we can partition our consumers on replay_id we can achieve some multiple of that throughput through partitioning.

### 6. Stateful Streaming using Apache Spark or Similar Service

**Proposal**

Instead of aggregating in ClickHouse we should aggregate our replays in a stateful service such as Apache Spark before writing the final result to ClickHouse. With Spark, we can view our Kafka topic as a streaming DataFrame. Spark has a mechanism for stateful streaming based on windows, https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html#window-operations-on-event-time. We would use a "Session Window", with the timeout being the same as the one we define on the client to aggregate data per replay-id. we'd then take advantage of watermarking to ensure that late data still gets grouped accordingly.

**Drawbacks**

- Replays are not available until they have finished.
- The probability of data loss from an outage goes up.
  - If there are problems upstream we have to take action to pause the job.

**Questions**

- Bruno Garcia asks: How do we integrate this feature for self-hosted users?

### 7. Upgrade ClickHouse Version to Utilize Experimental Features

**Proposal**

Upgrading to a newer version of ClickHouse will enable us to use experimental features such as "Live View" and "Window View".

**Drawbacks**

- Would require Sentry to manage the ClickHouse installation.
  - Feature is not present in a stable release.
  - Feature is not present on any version of ClickHouse in Altinity.

**Questions**

### 8. Use an Alternative OLAP Database

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

### 9. Use an Alternative OLTP Database

**Proposal**

OLTP databases such as PostgreSQL and AlloyDB support updates which appear to be a key requirement for the Replays product. Our scale is small enough that a shared PostgreSQL database could handle it. Read volume is low relative to write volume. We could optimize our database for this use case.

**Drawbacks**

- Race conditions will require single-threaded processing of replay events.
- Duplicate messages will necessitate ordering requirements.
- Always a possibility for dropped and duplicated data regardless of safe guards.
- AlloyDB is still in developer preview on Google Cloud.
- We need to re-write our application logic for querying the datastore.
- Migration pains.

**Questions**

- Colton Allen asks: Is it possible to write to tables partitioned by the hour? When the hour expires the table is indexed for fast read performance. Replays on the most recent hour partition would be unavailable while we are writing to it. Does PostgreSQL expose behavior that allows us to query over multiple partitions transparently? Is this even necessary given our scale? Currently processing 200 messages per second.

### 10. Manually Manage An Aggregated Materialized View

**Proposal**

Use a cron job, which runs at some `interval` (e.g. 1 hour), that would select the finished replays from the last `interval`, aggregate them, and write them to a materialized view or some destination table. We then alter the index page to reflect two different dataset. The "live" dataset and the "video-on-demand" dataset. A "live" page would fetch replays from the last `interval`. A "video-on-demand" dataset would function similarly to the current replays index page however it would only contain data that has been aggregated by the cron job.

**Drawbacks**

- Requires product changes.
- Requires manual management of a secondary dataset.
- Introduces fragility with a secondary post-processing step.

**Questions**

- Colton Allen asks: What happens if the cron job runs once, a replay is aggregated and stored, the cron runs a second time after its interval but finds new rows for the previously aggregated replay?
  - Insert a new aggregation row. Do not group by or merge. On the read side we still WHERE query but accept that some replays that _should_ match a given condition are not returned.
  - We will need to validate our success rate to make sure we're writing as close to one row per replay-id as possible.
- Colton Allen asks: What happens if a new row is written to the table with an old timestamp? The aggregation process could have already run for that timestamp range.
  - An old timestamp does not necessarily indicate an old replay. The client clock could be incorrect.
    - Implementing a server-generated timestamp column could help with this.
  - An old timestamp does not necessarily indicate an incorrect clock. The message could have been backlogged on a consumer.
    - Write a new aggregation state row. We should tolerate multiple aggregation states for a replay.
- Colton Allen asks: What happens if the cron job is down for an extended period of time?
  - We will need to write a log of each successful run.
    - PostgreSQL could store run_id, from_ts, to_ts columns.
    - We query PostgreSQL for the max(to_ts) value and then bootstrap our process from there.
  - If a cron fails mid-run then no log is written.
    - Duplicate aggregations are possible and should be tolerated.
    - Duplicate aggregations can be merged asynchronously and should not impact the user-experience.
  - The cron should attempt to catch up sequentially. If the cron was down for `m` \* `n` hours and the interval is `n` hours then we will need to call the aggregation function `m` times.
    - If the process fails then it will restart from the previously stored max(to_ts).

# Selected Outcome

No outcome has been decided.
