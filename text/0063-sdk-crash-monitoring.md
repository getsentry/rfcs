# SDK Crash Monitoring

- Start Date: 2023-01-18
- RFC Type: feature
- RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
- RFC Status: draft
- RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)
- RFC Approver: tbd

## Summary

This RFC aims to detect crashes caused by our SDKs to improve reliability.

## Motivation

As an APM company, the reliability of our SDKs is one of our most essential quality goals. If our SDK breaks the customer, we fail. Our SDK philosophy refers to this as [degrade gracefully](https://develop.sentry.dev/sdk/philosophy/#degrade-gracefully).

For some SDKs, like mobile SDKs, we primarily rely on users to reach out when our SDKs cause crashes cause we don't operate them in production. If users don't report them, we are unaware. Instead, we should detect crashes caused by our SDKs when they happen so we can proactively fix them.

## Background

Google Play SDK console only works for Android.

## Options Considered

- [Option 1: SDKs report FIOMT as errors](#option-1)
- [Option 2: SDKs report FIOMT as performance issues](#option-2)
- [Option 3: Ingest reports FIOMT as performance issues](#option-3)

### Option 1: Detect during event processing <a name="option-1"></a>

During event processing, after processing the stacktrace, the server detects if a crash stems from any of our SDKs by looking at the top frames of the stacktrace. If the server detects that it does, it could duplicate the event and store it in a special-cased sentry org where each SDK gets its project.

A good candidate to add this functionality is the `event_manager`. Similarly, where we call [`_detect_performance_problems`](https://github.com/getsentry/sentry/blob/4525f70a1fb521445bbb4c9250b2e15e05b059c3/src/sentry/event_manager.py#L2461), we could add an extra function called `detect_sdk_crashes`.

As we’d only make this visible to Sentry employees, we might not have to strip out any data cause of data privacy reasons, as employees could view the original events anyways. Of course, employees would need to go through the _admin portal and form.

### Pros <a name="option-1-pros"></a>

1. No need for per-SDK rollout.
2. No extra events or data sent to Sentry.

### Cons <a name="option-1-cons"></a>

1. Please add your cons.

### Option 2: Detect in SDKs <a name="option-2"></a>

When the SDK sends a crash event to Sentry, it checks the stacktrace and checks if the crash stems from the SDK itself by looking at the top frames of the stacktrace. If it does, the SDK duplicates the event and sends it to a special-cased sentry org where each SDK gets its project.

### Cons <a name="option-2-cons"></a>

1. Opposite of [Pro 1 of option 1](#option-1-pro).
2. Extra events sent from SDKs to Sentry.
3. Changing the DSN needs an SDK update.

### Option 3: Client Reports <a name="option-3"></a>

Similar to option 2, we use client reports instead of sending events. We would need the entire event to get enough context to fix a crash. So basically, we would add the crash event to client reports.

### Pros

1. Opposite of [Con 2 of option 2](#option-2-cons).

### Cons

1. Opposite of [Pro 1 of option 1](#option-1-pro).
2. [Con 3 of option 2](#option-2-cons).
3. Extend the protocol of client reports.
4. `The client reports feature doesn't expect 100 percent correct numbers, and it is acceptable for the SDKs to lose a small number of client reports`, [develop docs](https://develop.sentry.dev/sdk/client-reports/#sdk-side-recommendations). So the SDK might drop some crashes, but maybe that's acceptable.
5. `Bugs in our SDKs are out of scope for client reports and are not being tracked using client reports at the moment`, [develop-docs](https://develop.sentry.dev/sdk/client-reports/#basic-operation).


## Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

## Unresolved questions

- Do we need to strip sensitive values from the events because of PII or is going through the _admin portal enough?
