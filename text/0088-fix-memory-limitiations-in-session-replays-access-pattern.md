- Start Date: 2023-04-24
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/88
- RFC Status: draft

# Summary

The Session Replay index page will run out of memory when processing queries for our largest customers. This document contains proposed solutions for addressing this short-coming.

# Motivation

Our goal is to make the Session Replay product highly scalable. We expect changes to the product will eliminate our OOM issues and increase performance for customers with large amounts of ingested data.

# Background

The Session Replay data model is different from most at Sentry. Replays are received in parts referred to as "segments". One row does not represent one replay. Instead many rows are aggregated together to represent a single replay. This problem is distinct from normal `GROUP BY` operations because of the high cardinality of our grouping key.

When we ask a question such as "which replays did not visit this url?", we have to aggregate every row in the database (minus whatever rows were reduced by conditions in the WHERE clause). As it turns out the number of rows is very large and the amount of data is significant enough that we run out of memory on large customers.

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

# Example Queries

Current main aggregation query:

```sql
SELECT (
    replay_id,
    project_id,
    arrayMap((`trace_id`) -> replaceAll(toString(`trace_id`), '-', '') AS `trace_id`, groupUniqArrayArray(trace_ids)) AS `traceIds`,
    arrayMap((`error_id`) -> replaceAll(toString(`error_id`), '-', '') AS `error_id`, groupUniqArrayArray(error_ids)) AS `errorIds`,
    min(replay_start_timestamp) AS `started_at`,
    max(timestamp) AS `finished_at`,
    dateDiff('second', started_at, finished_at) AS `duration`,
    arrayFlatten(arraySort((`urls`, `sequence_id`) -> identity(`sequence_id`), arrayMap((`url_tuple`) -> tupleElement(`url_tuple`, 2), agg_urls), arrayMap((`url_tuple`) -> tupleElement(`url_tuple`, 1), agg_urls))) AS `urls_sorted`, groupArray(tuple(segment_id, urls)) AS `agg_urls`,
    count(segment_id) AS `count_segments`,
    sum(length(error_ids)) AS `count_errors`,
    sum(length(urls)) AS `count_urls`,
    ifNull(max(is_archived), 0) AS `isArchived`,
    floor(greatest(1, least(10, intDivOrZero(plus(multiply(count_errors, 25), multiply(count_urls, 5)), 10)))) AS `activity`,
    groupUniqArray(release) AS `releases`,
    any(replay_type) AS `replay_type`,
    any(platform) AS `platform`,
    any(environment) AS `agg_environment`,
    any(dist) AS `dist`,
    any(user_id) AS `user_id`,
    any(user_email) AS `user_email`,
    any(user_name) AS `user_username`, IPv4NumToString(any(ip_address_v4)) AS `user_ip`,
    any(os_name) AS `os_name`,
    any(os_version) AS `os_version`,
    any(browser_name) AS `browser_name`,
    any(browser_version) AS `browser_version`,
    any(device_name) AS `device_name`,
    any(device_brand) AS `device_brand`,
    any(device_family) AS `device_family`,
    any(device_model) AS `device_model`,
    any(sdk_name) AS `sdk_name`,
    any(sdk_version) AS `sdk_version`,
    groupArrayArray(tags.key) AS `tk`,
    groupArrayArray(tags.value) AS `tv`,
    groupArray(click_alt) AS `click_alt`,
    groupArray(click_aria_label) AS `click_aria_label`,
    groupArrayArray(click_class) AS `clickClass`,
    groupArray(click_class) AS `click_classes`,
    groupArray(click_id) AS `click_id`,
    groupArray(click_role) AS `click_role`,
    groupArray(click_tag) AS `click_tag`,
    groupArray(click_testid) AS `click_testid`,
    groupArray(click_text) AS `click_text`,
    groupArray(click_title) AS `click_title`
)
FROM replays_dist
WHERE (
    project_id IN array(4551897674350594) AND
    timestamp < '2023-05-08T17:48:31' AND
    timestamp >= '2023-02-07T17:48:31'
)
GROUP BY project_id, replay_id
HAVING (
    min(segment_id) = 0 AND
    finished_at < '2023-05-08T17:48:31'
)
ORDER BY started_at DESC
LIMIT 10
OFFSET 0
GRANULARITY 3600
```

Current subquery optimization. The subquery collects IDs which it feeds into the main aggregation query. This is only used in a limited number of circumstances. See "Existing Solution" section.

```sql
SELECT (
    replay_id,
    timestamp,
    replay_start_timestamp AS `started_at`
)
FROM replays_dist
WHERE (
    project_id IN array(4551897700564994) AND
    timestamp < toDateTime('2023-05-08T17:55:11.850729') AND
    timestamp >= toDateTime('2023-02-07T17:55:11.850729') AND
    segment_id = 0
)
ORDER BY started_at DESC
LIMIT 10
OFFSET 0
GRANULARITY 3600
```

# Options Considered

Any option may be accepted in whole or in part. Multiple options can be accepted to achieve the desired outcome.

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

The number of rows aggregated can be reduced by restricting the maximum time range we query over. We should validate the timestamp range such that it does not exceed a 24-hour period. This would satisfy every organization which ingests fewer than 1 billion replay-segments every 90 days.

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
  - The performance of a single consumer will be dominated by the performance of our Key, Value store. If we assume 10ms to process each message then we will process 100 messages per second per consumer. We can achieve some multiple of that throughput by partitioning on messages on replay_id.

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

OLTP databases such as PostgreSQL and AlloyDB support updates which appear to be a key requirement for the Replays product. Our scale is small enough that a sharded PostgreSQL database could handle it. Read volume is low relative to write volume. We could optimize our database for this use case.

**Drawbacks**

- Race conditions will require single-threaded processing of like replay-id events.
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

The minimum time to backfill the entire dataset will be 15 minutes per billion rows (one insert per second at 10 segments per replay at 100k replays per batch) assuming single-threaded writes. Fan out reduces this problem but requires the use of asynchronous inserts. Querying 100k aggregated replays (1 million rows) is assumed to be a major source of delay in a single-threaded ingest environment.

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
- Ryan Albrecht asks: Can we extract the segment-0 replay_id, push it to a Kafka queue with a processing delay of 1 hour (the maximum length of a replay), and then aggregate the replay_id (after the delay) publishing it to our target table?
  - This has the benefit of not needing a cron job to aggregate windows of time.
    - We would be using point queries to pluck out the replays that need to be finalized.
    - Additional metadata like project_id, timestamp could be passed to reduce the impact of the replay_id lookups.
      - Timestamps could be min, maxed to perform range scans over the key
      - Project ID could use the IN operator.
  - As far as I'm aware Kafka does not have a concept of delayed processing. It processes each message it receives in order as quicky as it is able.
  - However, other technologies do have this concept. We could tell another process to schedule a message to the Kafka topic after `n` internal.
    - RabbitMQ has this behavior.
    - We can use Celery to schedule a task with an ETA of 1 hour.
  - The Kafka consumer receiving these messages would aggregate and then bulk-insert the replays.
    - A single aggregated read query is issued to retrieve the set of replays.
    - A single bulk insert is issued to set the replays in the aggregated table.
  - Potential load on the system is segments per second divided by 10 (average number of segments per replay). Currently this evaluates to 20 replays/second.
  - Possible problems:
    - Because consumers can backlog we want to make sure all of our messages are published to the same topic. That way a long backlog on consumer `A` will not impact the ability of message `B` to aggregate the final replay object.
    - This adds complexity to the consumer but not an unmanageable amount.
    - The replay-events consumer is a Snuba consumer so we may encounter some minor procedural challenges that a consumer wholly owned by the replays team would not.
    - Replays are always "live" for one hour. They are not eagerly closed.
    - Because this uses I/O it will block our snuba consumer from running at peak efficiency. Should the message be forwarded to another topic after order has been guaranteed?
- Bruno Garcia asks: The complexity of integrating a new message queue (RabbitMQ in the above answer) into our ingest pipeline seems high. What sort of scaling issues arise, how do we handle outages of each service component, can a cron job (using a sliding window query) simplify?
  - Scale: The message throughput for RabbitMQ will be roughly 1/10th of what we process on our Kafka consumer (we only process one message per replay_id). The messages will be small and the Celery task's only function will be to forward the message back to the Kafka consumer. The load recieved by RabbitMQ and the task process should be very managable. Additionally, there are other bottlenecks in the system which will take precedence.
  - Outages: If Relay is down new messages are rejected and the queues are drained. If the Kafka consumer is down then the messages backlog until the consumer resumes processing. If RabbitMQ is down the Kafka consumer must pause.
  - Simplify with cron job: If the cron job has an outage it can be resumed from a save point. However, if the Kafka consumer is down then we need to pause the cron so that it does not write incomplete aggregation rows. Both use cases require a piece of infrastructure to be paused in the event of an outage.
    - If our Kafka consumer encounters a RabbitMQ failure it can pause processing, publish the message to a DLQ, or publish the message back to itself to retry automatically at a later time.

### 11. Configure ClickHouse to Optimize Aggregations [NOT VIABLE]

**Proposal**

Use `optimize_aggregation_in_order` to limit the number of rows we need to aggregate. In testing this eliminates OOM errors. Queries complete somewhat speedily.

**Drawbacks**

- Can not use user defined ordering.

**Questions**

### 12. Aggregate Replay Event Metadata in the SDK and Set Final Flag

**Proposal**

The SDK can maintain a buffer of the replay metadata. Once the replay has finished the SDK will flush that buffered data on the final segment. The segment marked as "final" can then be fetched without aggregation.

**Drawbacks**

- Requies SDK upgrade.
- API will need to fallback to aggregating behavior if no final segments can be found (or otherwise detect old SDK usage prior to querying).

**Questions**

- Is it possible for the SDK to know when its done and mark the request object with a final attribute?
- Click tracking is ingested into the same table as replay events but it is not sourced from the same location. How do we handle click tracking?
  - The SDK could buffer this data as well and send it on the final segment.

### 13. Aggregate Replay Event Metadata in the SDK and Store in Replacing Merge Tree Table

**Proposal**

We can leverage the SDK to buffer replay metadata. Buffered metadata is continuously aggregated and sent redundantly to the server. Old replay rows are replaced by new replay rows. Replacement is determined by the event with the most segments. The row with the most segments contains all of the information contained within the previous segments plus whatever metadata was aggregated in its time slice.

**Drawbacks**

- Likely requires the use of `FINAL` to fetch the most recent row.
- Not backwards compatible. Requires SDK upgrade.
- Requires table migration.
  - Either double writer or materialized view.

**Questions**

- Will using `FINAL` be a problem? Is it a big deal relative to the problems we're experiencing currently?
- How do we handle click tracking?
  - The SDK could buffer this data as well and send it on the final segment.

# Selected Outcome

The Snuba service will accept the `SETTINGS` query clause and the Replays query will be updated to limit the total number of unique values aggregated.  The following settings will applied to each query:

1. Set max_rows_to_group_by to 1,000,000.
2. Set group_by_overflow_mode to any.

1 million was chosen as the maximum size of a representative sample of the dataset.  `SAMPLE` is not considered because we need replays to be whole.  Missing segments (that were removed by sampling) can have deep implications to the product.

Should the above solution not solve the problem Proposal 11 "Manually Manage An Aggregated Materialized View" will be used as a fallback.

**Summary**

We will rely on Kafka's ordering guarantees and RabbitMQ's delayed message processing semantics to create a static record of all of the aggregation states.

**Key Qualifications for Acceptance**

1. Backwards compatible with the possibility of a back-filling data migration.
2. Risk of data-loss is minimized by keeping an uncompressed record of the data in the database.
   - Row compression can be attempted as many times as necessary.
3. All filters and sorts can be applied to non-aggregated columns.
   - I.e. filtering in the `WHERE` clause and ordering against column literals in the `ORDER BY` clause.
4. Duplicates can be tolerated and pruned asynchronously.
   - Using `GROUP BY` and the `any` function you can select a scalar value from the first value you encounter.
   - This does not use extra memory so long as we don't filter in the HAVING clause or sort by an aggregated value. Both of these conditions are unnecessary.
5. No new services or ops resources are required.
   - We can re-use our already provisioned RabbitMQ resources.

# Rejected Proposals

**Proposals 1 and 2**

Worse product experience. Rejected without much consideration.

**Proposal 3 and 4**

Non-viable.

**Proposal 5, 12, and 13**

Does not fully solve the problem. All of these proposals rely on some process external to the database buffering replay event metadata. While this is a tempting solution to the problem because none of these processes can determine _when_ a replay has completed we are forced to de-duplicate in the database layer. This de-duplicatation step would have required the use of a `ReplacingMergeTree` (not `CollapsingMergeTree` as was stated for proposal 5). The query pattern would have required use of the `FINAL` keyword argument.

`FINAL` has different output but functions similarly to `GROUP BY`. We build a hashmap of replay_ids, that hashmap gets too big, and the process runs out of memory. For this reason buffering within the database was considered non-viable.

Adopting Redis as the buffering mechanism incurred the risk of data-loss and a more complex pipeline. It was rejected because a better alternative (our primary datastore) was found.

Adopting buffering on the SDK had several challenges:

- It was not backwards compatible.
- Safe storage of the buffered events would require writing duplicates to the database which in turn requires `FINAL`.

**Proposal 6 and 8**

Not enough organizational resources to support the Replays team.

**Proposal 7**

1. Unlikely to solve the problem.
2. Unable to access newer versions and still be in compliance with organization policies.
3. Stability concerns.

**Proposal 9**

Not heavily explored but likely performance bottlenecks in this solution.

**Proposal 11**

Non-viable. `optimize_aggregation_in_order` requires the sort order to match the layout on disk. Adopting this feature would require removing custom sorts.
