* Start Date: 2022-11-28
* RFC Type: decision
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
* RFC Status: draft
* RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)

# Summary

This RFC aims to clarify if SDKs should report file I/O on the main thread (__FIOMT__) as errors or performance issues.

# Motivation

On June 21, 2022, we decided with [DACI](https://www.notion.so/sentry/Performance-Issue-Creation-POC-e521772ebccb482b83b08f4f8a3db2cb) to create performance issues in Ingest. While implementing the FIOMT for Android, the question arose as to why SDKs don't report FIOMT.

# Options Considered

## Option 1: SDKs report FIOMT as errors

SDKs report FIOMT as errors with a stacktrace. 

To clarify the threshold and configuration, an experimental feature phase can help to get feedback.

### Pros

1. SDKs can capture a stack trace which will helps actionability and fingerprinting/grouping.
2. Users don't have to enable performance monitoring.
3. No running transaction required.
4. Sentry can tie together transaction and error far more easily since both objects exist at the point of time the performance issue will be created.

### Cons

1. Double dipping quotas, sending the transaction and the error created within that transaction.
2. [Cons 1-3 of option 2](#option-2-cons).
3. The opposit of [pros of 2-4 of option 2](#option-2-pros).

## Option 2: SDKs report FIOMT as performance issues

SDKs detect and report FIOMT as a performance issue. To achieve this we need to:

1. answer billing questions.
2. make changes in Ingest to accept performance issues.

### Pros <a name="option-2-pros"></a>

1. No double dipping of quotas.
2. Sentry correctly categorizes FIOMT as a performance issue and returns it when searching inside Sentry for performance issues.
3. Sentry presents FIOMT as a performance issue, highlighting root causes and resources to fix the issue.
4. Performance-issue-specific quotas and thresholds apply to FIOMT.
5. Planned UX and workflow changes specific to performance issues also apply to FIOMT issues.

### Cons <a name="option-2-cons"></a>

1. Need for per-SDK rollout.
2. Changing the algorithm or thresholds requires SDK rollout.
3. Detection is mixed between ingest and SDK.
4. [Cons 1-3 of option 3](#option-3-cons).

## Option 3: Ingest reports FIOMT as performance issues

This option leaves the detection of FIOMT to Ingest.

### Pros

1. No need for per-SDK rollout.
2. Changing the algorithm or thresholds doesn't require SDK rollout.
4. Consistent location for detector logic.

### Cons <a name="option-3-cons"></a>

1. Users have to enable performance monitoring.
2. A transaction is required to be running while a performance issue is happening.
3. We can't attach a stacktrace to the span that caused the issue, so identifying the root cause is more challenging.
