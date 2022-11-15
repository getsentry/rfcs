* Start Date: 2022-10-15
* RFC Type: decision
* RFC PR: [#37](https://github.com/getsentry/rfcs/pull/37)
* RFC Status: draft

# Summary

Calculate ANR (App Not Responding) rates with session backed data to match Google Play apps Android vitals as closely as possible.

# Motivation

ANR rate is an app health diagnostic (much like crash rate) that Google Play provides to allow developers to compare stability of releases. Google Play Console (platform that Google provides for developers to monitor the performance of their app, where they would find ANR rate) is not accessible to all developers on a project/team. We want to surface ANR rates (and potentially user-perceived ANR rates) in Sentry to consolidate these app health diagnostics in one place.

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
___________________________________________________________________ x 100 
                    (total unique users)
```

There are a couple problems with this:

1. Total ANRs is affected by client side sampling and dropped events if org/project is close to error quota
2. The most accurate count of total unique users will probably come from the sessions dataset, or maybe even the metrics dataset (but again this one is affected by client-side sampling)
3. Getting this information will require clickhouse queries to two different datasets and post-processing to calculate the ANR rate

Issues outlined in 1 & 2 will result in us showing *wrong* ANR rates and 3 will limit the capabilities of ANR rate - can’t allow sort and search, can’t add it to dashboards or alerts and is not future-proof in case we want to use ANR rates in issue detection.

# Supporting Data


# Options Considered

## Introduce a new tag in the sessions dataset (Option 1)

Introduce a new optional tag `freeze_mechanism` in the sessions dataset and track ANRs in sessions in addition to sending the ANR error events. 

SDK sends a session update (`freeze_mechanism:ANR`) when it hits an ANR in addition to creating an ANR error event.

We will then calculate ANR rate with a query similar to counting abnormal or errored users:

```sql
SELECT 
    (uniqCombined64MergeIf((value AS _snuba_value), equals((arrayElement(tags.value, indexOf(tags.key, 'freeze_mechanism')) AS `_snuba_tags[freeze_mechanism]`), 'ANR') AND in((metric_id AS _snuba_metric_id), [user])) AS `_snuba_session.anr_user`), 
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

1. Increases the cardinality of the sessions data, however this tag would only be set by Android SDKs for now, so would only affect Android sessions

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
