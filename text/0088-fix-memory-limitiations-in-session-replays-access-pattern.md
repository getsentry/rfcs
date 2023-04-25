- Start Date: 2023-04-24
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/88
- RFC Status: draft

# Summary

The Session Replay index page will run out of memory when processing queries for our largest customers. This document contains proposed solutions for addressing this short-coming.

# Motivation

Our goal is to make the Session Replay product highly scalable. We expect changes to the product will eliminate our OOM issues and increase performance for customers with large amounts of ingested data.

# Background

The Session Replay index page runs out of memory when processing request for large customers. Improvements have been made to the situation by running subqueries prior to execution of the main query event. This is not always possible due to our current product requirements.

# Options Considered

### Change the Product's Query Access Pattern

**Proposal**

**Drawbacks**

**Questions**

### Remove Ability to Query Aggregated Data on the Index Page

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
