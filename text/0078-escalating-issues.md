# Escalating Issues

- Start Date: 2023-03-06
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/78
- RFC Status: active

## Summary

Allow customers to mark issues as archived-until-escalating. Issues marked as such will not be shown in the issue stream. When an issue starts escalating we will mark the issue as escalating and allow it to show up again in the issue stream (similar to when issues go from ignored to unignored or from resolved to unresolved). This work removes the need of doing mental math to set an “Ignore until X count is reached” to clear the For Review tab.

## Motivation

It makes it easier for customers to move known issues out of the Issue Stream without loosing the ability of becoming aware when the issue starts getting worse.

## Background

The Sentry Issue Stream is often laden with several issues that developers cannot actually fix or issues that occur for very few users and are not a priority to be fixed. 

However, developers do not ignore such issues because they are worried that they will miss escalations, and using the Ignore Until involves a bit of mathematical juggling that most developers don’t wish to spend time on especially given that high trafficked apps will see a lot of issues come up.

We want to help developers identify an issue that is escalating.

## Supporting Data

Several Sentry customers ingest errors that belong to issues that have been ongoing since a month or longer. This leads to the issue stream showing many old issues.

## Option

Allow customers to mark issues as archived-until-escalating. Issues marked as such will not be shown in the issue stream. When an issue starts escalating we will mark the issue as escalating and allow it to show up again in the issue stream (similar to when issues go from ignored to unignored or from resolved to unresolved). This work removes the need of doing mental math to set an “Ignore until X count is reached” to clear the For Review tab. 

Issue forecast generation will be produced with the data team’s algorithm ([private link](https://github.com/getsentry/data-analysis/tree/spike_protection) to repo - [page](https://www.notion.so/Issue-Spiking-Algorithm-9c7be98895574f3b98c991deb0bbed9e) about the design of the algorithm). This algorithm can handle Spiking and Bursty Issues. For V1 we will be creating a periodic task that will query for issues marked as archived-until-escalating to generate the forecasts. We may be able to use the same cron as the weekly email report but we can’t adapt the queries for this work.

To make it clear, every time an issue is marked as archived-until-escalating we will create an initial forecast while the cron task will focus on updating the forecast.

In order for the pipeline to determine if an issue needs to be marked as escalating, we need to evaluate the total count of events for the day as the events come in. We will compare day to day (e.g. Monday to Monday). We will use the cached forecast for the issue which will be used as the ceiling to blow through. The data team has produced an algorithm that can generate the forecast (see link). 

A forecast will be produced by looking at the last 7 days of data and generating a forecast for the next 7 days (As documented in the algorithm’s Notion page) and store it as something like this:

```txt
{
  "date_created": 2022-10-19 22:00:00,
  "group_id": 12345689, # primary key, index
  "forecast": [{
    "2022-10-19": 500,
    "2022-10-20": 600,
    ...
  }]
}
```

We should be cautious in the storage format as in V2 we would be storing a forecast for *every* issue older than 30 days and any issues marked by the customer to be archived-until-escalating. Issues with less than 7 days of data will have a flat ceiling forecast which will be refreshed on the weekly forecast update.

An analysis on how expensive querying Snuba can be found in [here](https://www.notion.so/Support-escalating-issues-detection-1267f6bda052438e9eb1a4ed6ec1f6de).

The query get the data to generate the forecast will look something like this:

- Get a list of all group IDs that have been marked to be monitored for escalation
- Bucket them per project since we will have to do a query per project
- Ask Snuba to return the count for each issue bucketed hourly
- Process data and store it as a forecast

```sql
MATCH (errors_new_entity)
SELECT group_id, bucketed_hourly_timestamp, count(*)
WHERE group_id in (1234, 5678, 902)  # IDs of archived-until-escalating issues
AND timestamp < some value
AND timestamp > some value
GROUP BY bucketed_timestamp, group_id
ORDER BY group_id, bucketed_hourly_timestamp DESC
LIMIT 10000 OFFSET 10000
```

Notice that this is a paginated call for all issues across all orgs, thus, making it a single paginated call. It will return 168 hour counts for every issue.

Somewhere in the product, we will analyze today’s count for an issue and if it blows through the floor we mark the issues as escalating and will show up in the issue stream of the customer.

Support alerting when an issue starts escalating (e.g. “This issue changed state to escalating”).

## Drawbacks

Known issues:

- Teaching a new behavior to customers.
- Changing the terminology from ignoring issues to archiving issues.

## Unresolved questions

- For v2, we will automate the process of moving old issues from ongoing to archived-until-escalating.
