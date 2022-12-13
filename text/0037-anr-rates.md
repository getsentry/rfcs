* Start Date: 2022-10-15
* RFC Type: decision
* RFC PR: [#37](https://github.com/getsentry/rfcs/pull/37)
* RFC Status: draft

# Summary 

Calculate ANR (App Not Responding) rates with session backed data to match Google Play Console's Android vitals as closely as possible. The accepted solution is introducing a new, optional tag called `abnormal_mechanism` in the release health metrics dataset to track the type of ANR which will allow us to calculate the ANR rate without discrepancies introduced by client-side sampling. This tag will only be set by the Android SDK for sessions that experience an ANR event. We will be limiting the cardinality of the tag values; currently expecting to distinguish between background and foreground (user-perceived) ANRs, with a potential to extend to a third value to track AppHangs from iOS in the future.

# Motivation

ANR rate is an app health diagnostic (much like crash rate) that Google Play Console provides to allow developers to compare stability of releases. Google Play Console (platform that Google provides for developers to monitor the performance of their app, where they would find ANR rate) is not accessible to all developers on a project/team. We want to surface ANR rates and user-perceived ANR rates in Sentry to consolidate these app health diagnostics in one place.

# Background

ANRs are triggered if the UI thread on an Android app is blocked for too long. Android vitals provides the following [definition](https://developer.android.com/topic/performance/vitals/anr#android-vitals) for ANRs:

**ANR rate:** The percentage of your daily active users who experienced any type of ANR.

**User-perceived ANR rate:** The percentage of your daily active users who experienced at least one *user-perceived ANR*. Currently only ANRs of type `Input dispatching timed out` are considered user-perceived.

**Daily active user**: Unique user who uses your app on a single day on a single device, potentially over multiple sessions. If a user uses your app on more than one device in a single day, each device will contribute to the number of active users for that day. If multiple users use the same device in a single day, this is counted as one active user.

<aside>
💡 User-perceived ANR rate is a *core vital* meaning that it affects the discoverability of your app on Google Play.
</aside>
  

ANRs are currently surfaced as error events with tag `mechanism:ANR`. With the data we already have on hand, we can calculate ANR rate as follows:

```bash
(unique users who experienced error events with tag mechanism: ANR)
___________________________________________________________________
                    (total unique users)
```

There are a couple problems with this:

1. Total ANRs is affected by client side sampling and dropped events if org/project is close to error quota
2. The most accurate count of total unique users will probably come from the release health metrics dataset
3. Getting this information will require clickhouse queries to two different datasets and post-processing to calculate the ANR rate

Issues outlined in 1 & 2 will result in us showing *wrong* ANR rates and 3 will limit the capabilities of ANR rate - can’t allow sort and search, can’t add it to dashboards or alerts and is not future-proof in case we want to use ANR rates in issue detection.

# Supporting Data


# Options Considered

## Introduce a new tag in the release health metrics dataset (Option 1)

Introduce a new optional tag `abnormal_mechanism` in the release health metrics dataset to track ANRs with sessions in addition to sending the ANR error events. 

On the SDK side, this will result in the following changes:
  - Add an optional top-level field called `abnormal_mechanism` with values of type `string` to the [session update payload](https://develop.sentry.dev/sdk/sessions/#session-update-payload)
  - SDK sends a session update with `abnormal_mechanism` tag and an `abnormal` session status when it detects an ANR
  - Allowed string values for the `abnormal_mechanism` tag are `'anr_background'` and `'anr_foreground'`

On the ingestion side:
  - We add a string-based enumeration field called `abnormal_mechanism` to the session protocol
  - There will initially be three possible values `'anr_background'`, `'anr_foreground'` or None
  - Enumerate allowed values during ingestion to prevent accidentally storing unwanted values which will increase cardinality of storage; ingestion will remove unknown values
  - Values will be stored as strings

On metrics extraction:
  - `abnormal_mechanism` tag will only be extracted on abnormal sessions to restrict cardinality
  - `abnormal_mechanism` tag will only be extracted for user count since that's what is required to calculate ANR rate (by definition of ANR rate)
  - It will not be supported on aggregate sesion payloads since they don't have a concept of unique users (but froented/mobile SDKs shouldn't be sending aggregate session payloads anyway)

Add the new tag key and values to the [metrics indexer](https://github.com/getsentry/sentry/blob/89a64883412cd39abbc9b9746a232e4987f65140/src/sentry/sentry_metrics/indexer/strings.py#L78).

We will then calculate and expose ANR rates through the `MetricsReleaseHealthBackend`. It will result in a clickhouse query similar to counting abnormal or errored users:

```sql
SELECT 
    (uniqCombined64MergeIf((value AS _snuba_value), equals((arrayElement(tags.value, indexOf(tags.key, 'abnormal_mechanism')) AS `_snuba_tags[abnormal_mechanism]`), 'anr_foreground') AND in((metric_id AS _snuba_metric_id), [user])) AS `_snuba_session.anr_user`), 
    (uniqCombined64MergeIf((value AS _snuba_value), equals((metric_id AS _snuba_metric_id), 'user')) AS `_snuba_count_unique(sentry.sessions.user)`), 
    (divide(`_snuba_session.anr_user`,`_snuba_count_unique(sentry.sessions.user)`) AS `_snuba.anr_rate`)
   FROM metrics_sets_v2_local
  WHERE equals(granularity, ...)
    AND equals((org_id AS _snuba_org_id), ...)
    AND in((project_id AS _snuba_project_id), [...])
    AND greaterOrEquals((timestamp AS _snuba_timestamp), toDateTime('...', 'Universal'))
    AND less(_snuba_timestamp, toDateTime('...', 'Universal'))
    AND in(_snuba_metric_id, [user])
  LIMIT 2
```

1. This is a more generic solution that’s extensible to "freeze mechanisms" (ex. app hangs on iOS) from other operating systems
2. This can also be extended to track the four different types of ANRs outlined [here](https://developer.android.com/topic/performance/vitals/anr). Differentiating ANRs due to `Input dispatching timed out` separately will allow us to calculate user-perceived ANR rate
3. Stand-alone addition that won’t require any migration, less risky, doesn’t affect existing calculations

## Drawbacks

1. Increases the cardinality of the release health metrics data, however this tag would only be set by Android SDKs for now, so would only affect Android sessions

## Introduce a new session.status tag value (Option 2)

SDK sends a session update with (`session.status:frozen`) when it hits an ANR in addition to creating an ANR event and we calculate ANR rate with a query similar to counting abnormal or errored users:

```sql
SELECT 
    (uniqCombined64MergeIf((value AS _snuba_value), equals((arrayElement(tags.value, indexOf(tags.key, 'session.status')) AS `_snuba_tags[session.status]`), 'frozen') AND in((metric_id AS _snuba_metric_id), [user])) AS `_snuba_session.anr_user`), 
    (uniqCombined64MergeIf((value AS _snuba_value), equals((metric_id AS _snuba_metric_id), 'user')) AS `_snuba_count_unique(sentry.sessions.user)`), 
    (divide(`_snuba_session.anr_user`,`_snuba_count_unique(sentry.sessions.user)`) AS `_snuba.anr_rate`)
   FROM metrics_sets_v2_local
  WHERE equals(granularity, ...)
    AND equals((org_id AS _snuba_org_id), ...)
    AND in((project_id AS _snuba_project_id), [...])
    AND greaterOrEquals((timestamp AS _snuba_timestamp), toDateTime('...', 'Universal'))
    AND less(_snuba_timestamp, toDateTime('...', 'Universal'))
    AND in(_snuba_metric_id, [user])
  LIMIT 2
```

## Drawbacks

1. We are introducing a new terminal session state but the android system displays a dialogue asking the user if they would like to wait or force quit the app. So an ANR doesn't necessarily mean a terminating session state. Downstream session status changes will no longer be captured.
2. This will probably affect downstream crash/free rate calculations, require update to crash/free rate calculations before we can even start writing this new session status
3. Because of 2. will be harder to iterate on and roll back, seems risky
4. Won’t be able to extend to `Input dispatching timed out`
    
# Unresolved questions
