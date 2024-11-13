- Start Date: 2024-11-12
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/143
- RFC Status: draft

# Summary

This RFC aims to find strategies to minimize the damage of a crashing SDK in production.

# Motivation

Our customers use Sentry to ship confidently. We lose trust if our SDKs continuously crash our customers' apps. Our QA process should prevent fatal incidents, but you can never reduce that risk to 0.00%. If the Sentry SDKs crash in the wrong location, our customers must rely on users or other tools than Sentry to get informed. Such fatal incidents are hazardous, mainly for applications with a long release cycle, such as mobile apps, because customers can't deploy a hotfix within minutes or hours. A repeated Sentry SDK crash will again make it to our customers. The question is not if but when. When it does, we need to have strategies to minimize the damage.

# Background

The Cocoa SDK had an incident in July/August 2024 that crashed our customers' apps in production without sending crash reports to Sentry. Our SDK crash detection couldn't detect this problem because Sentry received no data. We only knew about the issue when customers reported that they stopped receiving data for their newest release and shared crash reports from AppStoreConnect with us.

# Options Considered

The proposed options below don’t exclude each other. We can implement one, some, or all of them. The combination of options can differ per SDK as the technical possibilities and requirements might vary.

## Edge Cases

The options should address the following edge cases:

| # | Description | Potential Damage |
| --- | --- | --- |
| 1. | The Sentry SDK continuously crashes during its initialization _[continue at 1.1, 1.2]_ | |
| 1.1. | and can't send SDK crash reports to Sentry. | Crashes and no data. |
| 1.2. | and can send some SDK crash reports to Sentry. | Crashes and some data. |
| 2. | The Sentry SDK continuously crashes after its initialization _[continue at 2.1, 2.2]_ | |
| 2.1. | and can't send SDK crash reports to Sentry. | Crashes and no data. |
| 2.2. | and can send some SDK crash reports to Sentry. | Crashes and some data. |
| 3. | The SDK continuously crashes when creating most crash reports, so there is no crash report. | No data. |

## Risks

Potential risks of incorrectly disabling the Sentry SDK. The damage would be no data.

| # | Description | Note |  
| --- | --- | --- |
| 1. | The user's application crashes shortly after the initialization of the Sentry SDK. | |
| 2. | The user's application crashes async during the initialization of the Sentry SDK _[continue at 2.1, 2.2, 2.3]_ | |
| 2.1. | and the Sentry SDK can write a crash report, which it sends on the next launch. | A wrong strategy could easily incorrectly disable the SDK in that scenario. |
| 2.2. | and the Sentry SDK can write a crash report, which it can't send on the next launch. | There isn't much we can do about this, except educating our customers about the importance of initializing the Sentry SDK as early as possible. Even if we incorrectly disable the SDK, it makes no difference. |
| 2.3. | and the Sentry SDK can't write a crash report, because it happens before initializing the crash handlers. | Same as note on 2.2. |

## Option 1: Stacktrace Detection

This approach doesn’t work with static linking, as the Sentry SDKs end up in the same binary as the main app. As we don’t have symbolication in release builds, we can’t reliably detect if the memory address stems from the Sentry SDK or the app. We might be able to compare addresses with known addresses of specific methods or classes, but this won’t work reliably. As with iOS, many apps use static linking, so we must use an alternative approach.

Notes on edge cases above:

1. It would work.
2. It wouldn’t work with this point, as it only works if there is a crash report.
3. It would work.
4. It would work.
5. It would correctly ignore that scenario.

## Option 2: Marker Files

> __Note:__
> We use marker files because checking the file's existence is significantly more performant than reading its contents.

The SDK must be launched at least once. When it launches the first time, it writes a marker file to disk using the SDK version and the timestamp as the filename. When the SDK completes the init phase, it writes another marker file to the disk with the SDK version, timestamp, and a success init suffix in the filename.

The first thing the SDK does when initializing is to check if it was launched at least once and if there is a success init marker file. If the SDK was launched at least once, but there is no success init marker file, it knows that it’s broken and must disable itself. If both marker files exist, the SDK deletes the success init marker file and again waits for the SDK to complete the init phase to write a new success init marker file.

Notes on edge cases above:

1. This could trigger the start-up crash detection logic, which should execute sending the crash report on the main thread. So, if something is broken there, the SDK won’t write the success init marker file. If the SDK can send the crash report successfully but still causes the crash, we get crash events, and the SDK crash detection will notify us. In that case a [Remote Kill Switch](https://www.notion.so/Remote-Kill-Switch-12d8b10e4b5d8043b7e0e5f803d97b6b?pvs=21) would allow us to disable the SDK remotely.
2. If this occurs during the init phase, the SDK will disable itself. If it occurs later, it wouldn’t work.
3. It would work.
4. It wouldn’t work, but we would know via the SDK crash detection.
5. It would correctly ignore that scenario.

## Option 3: Remote Kill Switch

There might be scenarios where the SDK can’t detect it’s crashing. We might be able to detect via the SDK crash detection that the SDK causes many crashes, and we could manually or, based on some criteria, disable the SDK. We could also allow our customers to disable the SDK remotely if they see many crashes in the Google Play Console or App Store Connect.

[Marker Files](https://www.notion.so/Marker-Files-12d8b10e4b5d80929f7de15e5f929683?pvs=21) detect if the SDK continuously crashes early during initialization. Therefore, it’s acceptable if the remote kill switch requires an async HTTP request to determine whether it should be enabled or not.

## Option 4: Failed SDK Endpoint

We could add a unique endpoint for sending a simple HTTP request with only the SDK version and a bit of meta-data, such as the DSN, to notify Sentry about failed SDKs. We must keep this logic as simple as possible, and it should never change to drastically minimize the risk of causing more damage. The HTTP request must not use other parts of the SDK, such as client, hub, or transport. The SDKs must only send this request once. 

As we can’t have any logic running, such as rate-limiting or client reports, it’s good to have a specific endpoint for this to reduce the potential impact on the rest of the infrastructure.

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known?
