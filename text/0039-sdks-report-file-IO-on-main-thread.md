* Start Date: 2022-11-28
* RFC Type: decision
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
* RFC Status: Decided
* RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)
* RFC Approver: [Adam McKerlie](https://github.com/silent1mezzo)

# Summary

This RFC aims to clarify if SDKs should report file I/O on the main thread (__FIOMT__) as errors or performance issues.

# Motivation

On June 21, 2022, we decided with [DACI](https://www.notion.so/sentry/Performance-Issue-Creation-POC-e521772ebccb482b83b08f4f8a3db2cb) to create performance issues in Ingest. While implementing the FIOMT for Android, the question arose as to why SDKs don't report FIOMT, as they could add more context to make the issue more actionable.

# Background <a name="background"></a>

Performance issues differ from error issues because they don't cause an exception or stop the code from running and have a perceived performance impact on end-users. 

# Option Chosen

The best option for File I/O on the main thread performance issues is __Option 3: Ingest reports FIOMT as performance issues.__

We decided against __Option 1__ as FIOMT is not an error issue; it's a performance issue, as pointed out in [background](#background).
We chose __Option 3__ over __Option 2__ because we can easily detect it via spans ([PR is already complete](https://github.com/getsentry/sentry/pull/41646/)), and the
problem exists across multiple SDKs (iOS, Android, RN, Flutter, .NET, and possibly more). There's also a likely future where FIOMT is detected via profiles, and
running detection in the ingestion pipeline will help combine Performance and Profiling issues.

# Options Considered

* [Option 1: SDKs report FIOMT as errors](#option-1)
* [Option 2: SDKs report FIOMT as performance issues](#option-2)
* [Option 3: Ingest reports FIOMT as performance issues](#option-3)

## Option 1: SDKs report FIOMT as errors <a name="option-1"></a>

SDKs report FIOMT as errors with a stacktrace. 

To clarify the threshold and configuration, an experimental feature phase can help to get feedback.

### Pros

1. SDKs can capture a stack trace which will helps actionability and fingerprinting/grouping. It is worth noting that they are not mandatory as spans also point people to the issue. Attaching them to transactions would be too expensive.
2. Users don't have to enable performance monitoring.
3. No running transaction required.
4. Sentry can tie together transaction and error far more easily since both objects exist at the point of time the performance issue will be created.

### Cons

1. Double dipping quotas, sending the transaction and the error created within that transaction.
2. [Cons 1-3 of option 2](#option-2-cons).
3. The opposit of [pros of 2-5 of option 2](#option-2-pros).

## Option 2: SDKs report FIOMT as performance issues <a name="option-2"></a>

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

## Option 3: Ingest reports FIOMT as performance issues <a name="option-3"></a>

This option leaves the detection of FIOMT to Ingest, which can detect FIOMT for any SDK sending a span with `blocked_main_thread=true`, as outlined in [#36](https://github.com/getsentry/rfcs/pull/36).

### Pros

1. No need for per-SDK rollout. It's impossible to scale all performance issues across the SDKs we support.
2. Changing the algorithm or thresholds doesn't require SDK rollout.
3. Consistent location for detector logic.

### Cons <a name="option-3-cons"></a>

1. Users have to enable performance monitoring.
2. A transaction is required to be running while a performance issue is happening.
3. We can't attach a stacktrace to the span that caused the issue, so identifying the root cause is more challenging.

## Unresolved questions

1. For [option 2](#option-2) we need to answer billing questions.
