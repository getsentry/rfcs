# SDK Crash Monitoring

- Start Date: 2023-01-18
- RFC Type: feature
- RFC PR: [#63](https://github.com/getsentry/rfcs/pull/63)
- RFC Status: Decided
- RFC Driver: [Philipp Hofmann](https://github.com/philipphofmann)
- RFC Approver: Karl Heinz Struggl

## Summary

This RFC aims to detect crashes caused by our SDKs to improve reliability.

## Motivation

As an APM company, the reliability of our SDKs is one of our most essential quality goals. If our SDK breaks the customer, we fail. Our SDK philosophy refers to this as [degrade gracefully](https://develop.sentry.dev/sdk/philosophy/#degrade-gracefully).

For some SDKs, like mobile SDKs, we primarily rely on users to report  SDK crashes because we don't operate them in production. If users don't report them, we are unaware. Instead, we should detect crashes caused by our SDKs when they happen so we can proactively fix them.

This solution doesn't seek to detect severe bugs, such as the transport layer breaking or the SDK continuously crashing. CI or other quality mechanisms should find such severe bugs. Instead, the proposal focuses on surfacing crashes that are hard to catch with CI.

### SDK Crash Health

In Looker, we could calculate the ratio of crashes reported by each SDK versus the crashes caused by itself to have a metric for how many crashes each SDK causes.

## Background

The Google Play SDK Console provides insights into crashes for SDK maintainers. We regularly use it for the Android/Java SDK. While it would be great also to build something similar for SDK maintainers within Sentry, it's a bit complicated cause of PII and such. Narrowing down the scope to only Sentry SDKs makes the problem easier to solve.

## Legal Perspective

__This is not yet signed off by our legal team.__ The following parameters should apply. This is to account for (1) contractual requirements related to our use and retention of customer data, (2) privacy obligations related to PII, and (3) future commitments we will make related to data locality.  

Parameters:

1. __No PII__ - PII is stripped from the data
2. __Limited Use__ - Data is used solely to detect crashes caused by our SDKs and fix our SDKs (and not for any other purposes)
3. __Limited Retention__ - Data persists for no longer than 30 days (shortest retention period we make available) but ideally no longer than 2 weeks (to account for customer manual deletion requests)
4. __Data Locality__ - Future data locality elections will be respected

If we strip the data, so we only collect data related to our SDKs, we wouldn’t need data locality from a legal perspective.

## Option Chosen

On 2023-01-18, we decided unanimously to move forward with [Option 1: Detect during event processing](#option-1) and giving our customers the possibility to opt out of this feature. Participants in the decision:

- Philipp Hofmann
- Manoel Aranda
- Joris Bayer
- Karl Heinz Struggl
- Daniel Griesser
- Matthew Trostel

The group decided on option 1 as it doesn't require any changes to SDKs, and we can implement it on the backend. The biggest con of options 2 and 3 is that they need a per-SDK rollout to detect SDK crashes.

## Options Considered

For every solution, the server or the SDK has to strip all irrelevant data for us to have enough information to solve an SDK crash to reduce privacy implications and risk. They should strip stacktrace frames from our customers, remove most of the context, etc.

- [Option 1: Detect during event processing](#option-1)
- [Option 2: Detect in SDKs](#option-2)
- [Option 3: Client Reports](#option-3)

### Option 1: Detect during event processing <a name="option-1"></a>

During event processing, after processing the stacktrace and symbolication, the server detects if a crash stems from any of our SDKs by looking at the top frames of the stacktrace. If the server detects that it does, it duplicates the event and stores it in a special-cased sentry org where each SDK gets its project. Some SDKs, such as Java,  don’t send SDK frames, and they would need to start sending them, and Sentry might need some UI changes not to confuse users.

A good candidate to add this functionality is the `event_manager`. Similarly, where we call [`_detect_performance_problems`](https://github.com/getsentry/sentry/blob/4525f70a1fb521445bbb4c9250b2e15e05b059c3/src/sentry/event_manager.py#L2461), we could add an extra function called `detect_sdk_crashes`.

### Pros <a name="option-1-pros"></a>

1. No need for per-SDK rollout.
2. No extra events or data sent to Sentry.
3. Easier to maintain.

### Cons <a name="option-1-cons"></a>

1. Requires changes on the backend.

### Option 2: Detect in SDKs <a name="option-2"></a>

When the SDK sends a crash event to Sentry, it checks the stacktrace and checks if the crash stems from the SDK itself by looking at the top frames of the stacktrace. If it does, the SDK also sends the event to a special-cased sentry org, where each SDK gets its project.

### Pros <a name="option-2-pros"></a>

1. No backend changes required.

### Cons <a name="option-2-cons"></a>

1. Opposite of [Pro 1 of option 1](#option-1-pros).
2. Extra events sent from SDKs to Sentry.
3. Changing the DSN needs an SDK update.
4. The SDK might end up in an endless loop, if there is a bug in this functionality.

### Option 3: Client Reports <a name="option-3"></a>

Similar to option 2, we use [client reports](https://develop.sentry.dev/sdk/client-reports/) instead of sending events. We would need the entire event to get enough context to fix a crash. So basically, we would add the crash event to client reports.

> Client reports are a protocol feature that let clients send status reports about themselves to Sentry [develop docs](https://develop.sentry.dev/sdk/client-reports/).

> Bugs in our SDKs are out of scope for client reports and are not being tracked using client reports at the moment, [develop-docs](https://develop.sentry.dev/sdk/client-reports/#basic-operation).

According to the develop docs, client reports could be used for such a feature.

> The client reports feature doesn't expect 100 percent correct numbers, and it is acceptable for the SDKs to lose a small number of client reports, [develop docs](https://develop.sentry.dev/sdk/client-reports/#sdk-side-recommendations).

So the SDK might drop some crashes, but  that's acceptable.

### Pros

1. Opposite of [Con 2 of option 2](#option-2-cons).

### Cons

1. Opposite of [Pro 1 of option 1](#option-1-pros).
2. [Con 3-4 of option 2](#option-2-cons).
3. Extend the protocol of client reports, and changes on the backend to pull events from the client reports.

## Drawbacks

1. Option 3: Not all SDKs have implemented client reports yet. PHP most likely will never add it.
2. The proposal only works for errors that the SDK can still send to Sentry. If the SDK keeps crashing or there is a significant bug preventing the SDK from sending events, this solution won't help to surface such problems.

Please add any drawbacks you can think of as a comment or just commit directly.

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

## Unresolved questions

- How can we we maintain data locality with Option 1 (ie. the hybrid cloud project)?
