* Start Date: 2022-11-28
* RFC Type: decision
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
* RFC Status: draft
* RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)

# Summary

This RFC aims to clarify if SDKs should report file I/O on the main thread as errors, not performance issues.

# Motivation

On June 21, 2022, we decided with [DACI](https://www.notion.so/sentry/Performance-Issue-Creation-POC-e521772ebccb482b83b08f4f8a3db2cb) to create performance issues in Ingest. While implementing the file I/O on the main thread performance issue for Android, the question arose as to why SDKs don't report file I/O on the main thread as errors.

# Options Considered

## Option 1: SDKs report file I/O on the main thread as errors

SDKs report file I/O on the main thread as errors with a stacktrace. 

To clarify the threshold and configuration, an experimental feature phase can help to get feedback.

### Pros

1. SDKs can capture a stack trace which will helps actionability and fingerprinting/grouping.
2. No running transaction required.
3. Sentry can tie together transaction and error far more easily since both objects exist at the point of time the performance issue will be created.

### Cons

1. Need for per-SDK rollout.
2. Double dipping quotas, sending the transaction and the error created within that transaction.
3. Not able to use dynamic thresholds and configurations, code changes would be required to update settings.
4. Stack traces are inherently expensive to process
5. Detection is mixed between ingest and SDK

## Option 2: SDKs report file I/O on the main thread as performance issues

This option may open another can of worms since there may be billing implications if we need to start ingesting performance issue

## Option 3: Ingest reports file I/O on the main thread as performance issues

This option leaves the performance issue detection to Ingest.

### Pros

1. No need for per-SDK rollout.
2. Less SDK overhead as they don't have to detect the issues.
3. Changing the algorithm, or thresholds doesn't require SDK rollout, which means we can address customer issues far faster.
4. Consistent location for detector logic

### Cons

1. Users have to enable performance monitoring.
2. A transaction is required to be running while a performance issue is happening.
3. Transactions are high volume which means we may send too many stack traces, so we can't have stacktraces only the span that caused the issue. Which makes it harder to identify the root cause.
