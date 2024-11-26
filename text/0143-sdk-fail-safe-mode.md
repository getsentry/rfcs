- Start Date: 2024-11-12
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/143
- RFC Status: draft

# Summary

This RFC aims to find strategies to minimize the damage of crashing SDKs in production.

# Motivation

Our customers use Sentry to ship confidently. They lose trust in Sentry if our SDKs continuously crash their apps, which our QA process should prevent, but you can never reduce that risk to 0.00%. Such fatal incidents are hazardous, mainly for applications with a slow release cycle, such as mobile apps, because customers can't deploy a hotfix within minutes or hours. A repeated Sentry SDK crash will again make it to our customers. When it does, we need to have strategies to minimize the damage.

# Background

The Cocoa SDK had an incident in July/August 2024 that crashed our customers' apps in production without sending crash reports to Sentry. Our SDK crash detection couldn't detect this problem because Sentry received no data. We only knew about the issue when customers reported that they stopped receiving data for their newest release and shared crash reports from AppStoreConnect with us.

# Options Considered

The proposed options below don’t exclude each other. We can implement one, some, or all of them. The combination of options can differ per SDK as the technical possibilities and requirements might vary.

## Crashing Scenarios <a name="crashing-scenarios"></a>

The options should cover the following scenarios:

| # | Description | Potential Damage |
| ---: | --- | --- |
| | __Sentry SDK__  | |
| 1. | The Sentry SDK continuously crashes during its initialization _[continue at 1.1, 1.2]_ | |
| 1.1. | _[continued from 1.]_ and __can't__ create SDK crash reports. | Crashes and no data. |
| 1.2. | _[continued from 1.]_ and __can__ create and send some SDK crash reports. | Crashes and some data. |
| 2. | The Sentry SDK continuously crashes after its initialization _[continue at 2.1, 2.2]_ | |
| 2.1. | _[continued from 2.]_ and __can't__ create SDK crash reports. | Crashes and no data. |
| 2.2. | _[continued from 2.]_ and __can__ create and send some SDK crash reports. | Crashes and some data. |
| 3. | The SDK continuously crashes while it's being initialized async, _[continue at 3.1, 3.2]_ |  |
| 3.1. | _[continued from 3.]_ and __can't__ create SDK crash reports. | Crashes and no data. |
| 3.2. | _[continued from 3.]_ and __can__ create and send some SDK crash reports. | Crashes and some data. |
| 4. | The SDK continuously crashes when creating most crash reports, so there is no crash report. | No data. |
| | __User's Application__ | |
| 5. | The user's application crashes shortly after the initialization of the Sentry SDK. | Potentially incorrectly disabling the SDK and no data. |
| 6. | The user's application crashes async during the initialization of the Sentry SDK _[continue at 6.1, 6.2, 6.3]_ |  |
| 6.1. | _[continued from 6.]_ and the Sentry SDK can write a crash report, which it creates and sends on the next launch. | Potentially incorrectly disabling the SDK and no data. |
| 6.2. | _[continued from 6.]_ and the Sentry SDK can write a crash report, which it creates but can't send on the next launch. | There isn't much we can do about this, except educating our customers about the importance of initializing the Sentry SDK as early as possible. Even if we incorrectly disable the SDK, it makes no difference. |
| 6.3. | _[continued from 6.]_ and the Sentry SDK can't write a crash report, because it happens before initializing the crash handlers. | Same as 6.2. |
| 7. | The user's application crashes before the initialization of the Sentry SDK. | Same as 6.2. |
| | __Hybrid SDKs__ | |
| 8. | The hybrid SDK crashes during its initialization, _[continue at 8.1, 8.2]_ |  |
| 8.1. | _[continued from 8.]_ and the underlying native SDK __can__ initialize. |  |
| 8.2. | _[continued from 7.]_ and the underlying native SDK __can't__ initialize. |  |

## Option 1: Checkpoints <a name="option-1"></a>

The SDK stores checkpoints via marker files to disk to identify if it completes SDK initialization. When it doesn't, the SDK disables itself. The SDKs should use marker files because checking the file's existence is significantly more performant than reading its contents. To be aware of when the SDK disables itself, we could implement this option in combination with the [Option 3:Failing SDK Endpoint](#option-3).

The specification is written in the [Gherkin syntax](https://cucumber.io/docs/gherkin/reference/). The specification might not work for all edge cases yet, as it can be complicated to get it right. We'll figure out the exact details once we decide to implement it, but it should cover the main scenarios.

```Gherkin
Scenario: SDK version inits the first time
    Given there is no launch marker file for the SDK version
    And there is no success init marker file for the SDK version
    When the SDK inits
    Then the SDK creates a launch marker file for the SDK version

Scenario: SDK version inits the first time with successful init
    Given there is no launch marker file for the SDK version
    And there is no success init marker file for the SDK version
    When the SDK reaches the successful init checkpoint
    Then the SDK creates a success init marker file for the SDK version

Scenario: SDK version inits the first time with failed init
    Given there is no launch marker file for the SDK version
    And there is no success init marker file for the SDK version
    When the SDK crashes before reaching the successful init checkpoint
    Then the SDK can't create a success init marker file for the SDK version
    And the SDK doesn't disable itself

Scenario: SDK version inits successfully second time with previous successful init
    Given there is a launch marker file for the SDK version
    And there is a success init marker file for the SDK version
    When the SDK inits
    Then it deletes the success init marker file for the SDK version
    When the SDK reaches the successful init checkpoint
    Then the SDK creates a success init marker file for the SDK version

Scenario: SDK version inits with failure second time with previous successful init
    Given there is a launch marker file for the SDK version
    And there is a success init marker file for the SDK version
    When the SDK inits
    Then it deletes success init marker file for the SDK version
    When the SDK crashes before reaching the successful init checkpoint
    Then the SDK can't create a success init marker file for the SDK version

Scenario: SDK version inits with previous failed init
    Given there is a launch marker file for the SDK version
    And there is no success init marker file for the SDK version
    When the SDK inits
    Then it disables itself

Scenario: New SDK version inits with previous failed init
    Given there is a launch marker file for a previous SDK version
    And there is no success init marker file for the previous SDK version
    And there is no success init marker file for the current SDK version
    When the new SDK version inits
    Then the SDK deletes marker files from the previous SDK version
    And the SDK creates a launch marker file for the current SDK version
```

### Crashing Scenarios <a name="option-1-crashing-scenarios"></a>

Notes on [crashing scenarios](#crashing-scenarios):

| Scenario | Covered | Notes |
| --- | --- | --- |
| 1.1. | ✅ - yes |  |
| 1.2. | ✅ - yes |  |
| 2.1. | ⛔️ - no | |
| 2.2. | ⛔️ - no | But it could be detected via the SDK crash detection. |
| 3.1. | ✅ - yes | But it could be that it disables itself incorrectly, as the app is actually crashing. |
| 3.2. | ✅ - yes | same as 3.1. |
| 4. | ✅ - yes | The SDK correctly ignores this scenario. |
| 6.1. | ⛔️ - no | The SDK could incorrectly disable itself. |
| 6.2. | ⛔️ - no | same as 6.1. |
| 6.3. | ⛔️ - no | same as 6.1. |
| 7. | ✅ - yes | The SDK correctly ignores this scenario. |
| 8.1. | ✅ - yes | The native SDKs could implement the checkpoints for the initializing the hybrid SDKs. |
| 8.2. | ⛔️ - no | When the checkpoint logic of the hybrid and the native SDKs is flawed it won't work. |


### Pros <a name="option-1-pros"></a>

1. It can detect if the SDK crashes during its initialization even for any technical setup and when the crash handlers can't capture the crash.
2. SDKs could use checkpoints to identify the failure of other critical actions, such as writing a crash report.


### Cons <a name="option-1-cons"></a>

1. It requires extra disk I/O.
2. It could incorrectly disable the SDK when the app crashes async during the initialization of the Sentry SDK.
3. Once the SDK is disabled, it stays disabled until the next SDK version.

## Option 2: Remote Kill Switch <a name="option-2"></a>

There might be scenarios where the SDK can’t detect it’s crashing. We might be able to detect via the SDK crash detection that the SDK causes many crashes, and we could manually or, based on some criteria, disable the SDK. We could also allow our customers to disable the SDK remotely if they see many crashes in the Google Play Console or App Store Connect.

[Checkpoints](https://www.notion.so/Marker-Files-12d8b10e4b5d80929f7de15e5f929683?pvs=21) detect if the SDK continuously crashes early during initialization. Therefore, it’s acceptable if the remote kill switch requires an async HTTP request to determine whether it should be enabled or not.

### Crashing Scenarios <a name="option-2-crashing-scenarios"></a>

| Scenario | Covered | Notes |
| --- | --- | --- |
| 1.1. | ⛔️ - no |  |
| 1.2. | ⛔️ - no |  |
| 2.1. | ✅ - yes | |
| 2.2. | ✅ - yes|  |
| 3.1. | ⛔️ - no | |
| 3.2. | ⛔️ - no |  |
| 4. | ⛔️ - no |  |
| 5. | ✅ - yes | The SDK correctly ignores this scenario. |
| 6.1. | ✅ - yes | same as 5. |
| 6.2. | ✅ - yes | same as 5. |
| 6.3. | ✅ - yes | same as 5. |
| 7. | ✅ - yes |  |
| 8.1. | ✅ - yes | The native SDKs can send a crash report of the hybrid SDKs. |
| 8.2. | ⛔️ - no |  |

### Pros <a name="option-2-pros"></a>

1. It works for continuous SDK crashes after the SDK is initalized.
2. We could reenable the SDK if we disable it by mistake.
3. We can disable the SDKs only for specific customers.
4. We could allow customers to disable the SDK themselves.

### Cons <a name="option-2-cons"></a>

1. It doesn't work for continuous SDK crashes during SDK init.

## Option 3: Failing SDK Endpoint <a name="option-3"></a>

We could add a unique endpoint for sending a simple HTTP request with only the SDK version and a bit of meta-data, such as the DSN, to notify Sentry about failed SDKs. We must keep this logic as simple as possible, and it should never change to drastically minimize the risk of causing more damage. The HTTP request must not use other parts of the SDK, such as client, hub, or transport. The SDKs must only send this request once.

As we can’t have any logic running, such as rate-limiting or client reports, it’s good to have a specific endpoint for this to reduce the potential impact on the rest of the infrastructure.

### Crashing Scenarios <a name="option-3-crashing-scenarios"></a>

This option doesn't contain the scenarios table because they aren't applicable.

### Pros <a name="option-3-pros"></a>

1. We know when a SDK disables itself.

### Cons <a name="option-3-cons"></a>

1. Potential risk of crashing while performing this action.

## Option 4: Stacktrace Detection <a name="option-4"></a>

Before sending a crash report, the SDK identifies an SDK crash by looking at the topmost frames of the crashing thread. If the topmost frames stem from the SDK itself, it disables itself. The [SDK crash detection](https://github.com/getsentry/sentry/tree/master/src/sentry/utils/sdk_crashes) already uses this approach in the event processing pipeline.

This approach doesn’t work with static linking, as the Sentry SDKs end up in the same binary as the main app. As we don’t have symbolication in release builds, we can’t reliably detect if the memory address stems from the Sentry SDK or the app. We might be able to compare addresses with known addresses of specific methods or classes, but this won’t work reliably. As with iOS, many apps use static linking, so we must use an alternative approach.

### Crashing Scenarios <a name="option-4-crashing-scenarios"></a>

Notes on [crashing scenarios](#crashing-scenarios):

| Scenario | Covered | Notes |
| --- | --- | --- |
| 1.1. | ⛔️ - no | It doesn't work when the SDK crashes before parsing and sending the crash report. |
| 1.2. | ✅ - yes | |
| 2.1. | ⛔️ - no | same as 1.1. |
| 2.2. | ✅ - yes | |
| 3.1. | ⛔️ - no | same as 1.1. |
| 3.2. | ✅ - yes | |
| 4. | ⛔️ - no |  |
| 5. | ✅ - yes |  |
| 6.1. | ✅ - yes | It wouldn't disable the SDK. |
| 6.2. | ✅ - yes | same as 5.1. |
| 6.3. | ✅ - yes | same as 5.1. |
| 7. | ✅ - yes | The SDK correctly ignores this scenario. |
| 8.1. | ✅ - yes | The native SDKs can send a crash report of the hybrid SDKs. |
| 8.2. | ⛔️ - no |  |

### Pros <a name="option-4-pros"></a>

1. It requires little to no extra overhead.
2. It can ignore async app crashes during SDK initialization.

### Cons <a name="option-4-cons"></a>

1. __Doesn't work with static linking:__ This approach doesn’t work with static linking, as the Sentry SDKs end up in the same binary as the main app. As we don’t have symbolication in release builds, we can’t reliably detect if the memory address stems from the Sentry SDK or the app. We might be able to compare addresses with known addresses of specific methods or classes, but this won’t work reliably. As with iOS, many apps use static linking, so we must use an alternative approach.
2. __Wrongly disabling the SDK:__ We frequently see wrongly reported SDK crashes in the SDK crash detection. As SDKs use bytecode manipulation, swizzling, or monkey patching, the stacktraces sometimes contain Sentry frames in the crashing thread, but the root cause isn't Sentry but the user's code.
3. It doesn't work when the SDK crashes during or before sending the crash report.
4. It doesn't work when the SDK crashes before installing the crash handlers.

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- How does [checkpoints](#option-1) work with the new start up crash detection logic?