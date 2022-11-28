* Start Date: 2022-11-28
* RFC Type: decision
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
* RFC Status: draft
* RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)

# Summary

This RFC aims to clarify which types of performance issues SDKs shall create.

# Motivation

On June 21, 2022, we decided with [DACI](https://www.notion.so/sentry/Performance-Issue-Creation-POC-e521772ebccb482b83b08f4f8a3db2cb) to create performance issues in Ingest. While implementing the file I/O on the main thread performance issue for Android, the question arose as to why SDKs don't report easy-to-detect and matured performance issues. 

# Options Considered

## Option 1: SDKs report easy to detect and matured performance issues

We still need to clarify what easy to detect and matured precisely means, which is not the goal of this document. For example, file I/O on the main thread could be a candidate.

To clarify the threshold and configuration for performance issues, an experimental feature phase can help to get feedback.

### Pros

1. SDKs can capture a stack trace which will help with actionability.
2. No running transaction required.
3. Sentry can tie together transaction and error far more easily since both objects exist at the point of time the performance issue will be created.
4. As we limit this only to easy detect peformance issues the SDK overhead should be minimal.

### Cons

1. Need for per-SDK rollout.
2. Double dipping, sending the transaction and the error created within that transaction.
3. Not able to use dynamic thresholds and configurations, code changes would be required to update settings.


## Option 2: SDKs should report all peformance issues

We already decided against this option in this [DACI](https://www.notion.so/sentry/Performance-Issue-Creation-POC-e521772ebccb482b83b08f4f8a3db2cb#907db42314864ae2a4b5348835c250c9)

### Pros

1. SDKs can capture a stack trace which will help with actionability.
2. No running transaction required.
3. Can tie together transaction and error far more easily since both objects exist at the point of time the performance issue will be created

### Cons

1. Double dipping, sending the transaction and the error created within that transaction.
2. Code on SDK could cause overhead.
3. Not able to use dynamic thresholds, code changes would be required to update settings.

## Option 3: Ingest creates the performacne issues

This option leaves the performance issue detection to Ingest. For more info see previous [DACI](https://www.notion.so/sentry/Performance-Issue-Creation-POC-e521772ebccb482b83b08f4f8a3db2cb#169fa914e8c343468e9523906d0e2fff).

### Pros

1. No need for per-SDK rollout.
2. Less SDK overhead as they don't have to detect the issues.
3. Changing the algorithm doesn't require SDK rollout.

### Cons

1. Users have to enable performance monitoring.
2. A transaction is required to be running while a performance issue is happening.
3. No stack traces, so no way to show where the performance problem was detected.
