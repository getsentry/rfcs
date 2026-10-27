- Start Date: YYYY-MM-DD
- RFC Type: informational
- RFC PR: <link>
- RFC Status: draft

# Summary

This rfc is intended to provide a high level via of the issue platform, it's 
capabilities, how to interact with it and plans for the future.

# Motivation

The primary purpose of the issue platform is to allow different teams at Sentry to 
detect problems relevant to our users in their data, and create new issues types from 
that data.

# High Level Concepts

 - Event: A general term for data sent from SDKs to Sentry. This includes errors, transactions, profiles, replays, etc.
 - Issue: An aggregation of events representing a unique problem we detected in the user’s system.
 - Detector: A logical unit that analyzes data looking for problematic patterns and outputs found problems.
 - Issue Occurrence: An event specifically associated with an issue. These are raised from detectors and sent to Sentry via the occurrences api.
 - Fingerprint: An identifier of a unique occurrence. It’s used for grouping occurrences into issues.
 - Issue Category: The broad category that an issue belongs to. `Error`, `Performance` and `Profile` are examples of this.
 - Issue Type: The specific type of an issue. `N + 1 DB query` is an example of this. Type implies category.


# Ingestion Schema

Ingestion Schema
Ingestion occurs via Kafka. The message format looks like

 - id: str - A uuid representing the issue occurrence id.
 - project_id: int.
 - fingerprint: Sequence[str] - The fingerprint to uniquely identify a specific issue
 - issue_title: str - The title of the occurrence. Will be used as issue title.
 - subtitle: str - Used as the sub header on the issue.
 - resource_id: str | None - An optional id that we can use to link to an external system
 - evidence_data: Mapping[str, Any] - An arbitrary json blob of data for use with the frontend to render any custom components necessary for this issue type.
 - evidence_display: A list of data to display in the ui and notifications. This will typically be displayed in a tabular format. Each entry is a dict in format
   - name: str: Name of the value to display in the table
   - value: str: Value to display in the table
   - important: bool - Up to one piece of data in evidence_display should be marked as important. This entry will be used in notifications where space is constrained.
 - type: int - The issue type that this occurrence belongs to. Must be registered as a dataclass like so: https://github.com/getsentry/sentry/blob/5fd8242aca575c84314f1b6744be2ec1d2e9e471/src/sentry/issues/grouptype.py#L143-L148
 - detection_time: float - Timestamp representing when the occurrence was detected
 - level: str - The error level we want to display for the occurrence.

One (but not both) of these should also be passed
 - event_id: str - A uuid representing the event id. Pass this if you want to use an event that has already been stored into nodestore.
 - event: dict - A dictionary that matches our event format (https://develop.sentry.dev/sdk/event-payloads/). Pass as much of this as makes sense for your issue type. Use this method if your event isn’t already in nodestore.

 # General Data Flow
## Ingest
All data enters the issue platform via our Kafka topic. The topic accepts Issue Occurrences. There are two main components to the issue occurrence:
 - Issue Occurrence data as defined in the earlier schema. This data is used fill in core values on an issue, such as the title. They also contain information about the specific problem occurring in the event, since each event could have multiple occurrences detected in it. We store this in nodestore, under a separate namespace to events.
 - Event data. This is the underlying data that the occurrence was detected in. This fits our standard event format, but doesn’t have to have been sent to sentry as an event payload. Events can be either
  - An id of an existing event. This is mostly to handle events that are already received by sentry and stored in nodestore, like errors and transactions
  - A full event payload. In this case, the detector fits their data to the event format as best as they can and sends it through. We set the type of this event to “generic”, then save it via `EventManager`, so it ends up in nodestore.

Once we’ve ingested the occurrence and optionally the event, we then create/update the issue based on the fingerprint (note: currently, we just grab the first fingerprint out of the list and use that, but this can be expanded).

We then write the event to Snuba via Eventstream. This is written to our own dataset designed to handle a wide range of different events.

## Search
Search remains powered by Snuba. The main difference is that we’re making 3 separate queries, one to errors, one to transactions (performance issues) and one to the issue platform. We join these results and combine with the group table to produce the issue list.

This will be unified into a query to errors and a query to the issue platform dataset, once performance issues have been migrated over.

## Issue Details
This page remains largely the same. The main difference is that we return the occurrence data with the event, which is used to display the `evidence_display` data by default. Frontend teams might also customize the display of the page for an issue type using `evidence_data`.

## Creating a new issue type
To create a new issue type the team just implements a subclass with the relevant data (https://github.com/getsentry/sentry/blob/5fd8242aca575c84314f1b6744be2ec1d2e9e471/src/sentry/issues/grouptype.py#L151-L156).

Originally, we planned to make this dynamic. For now, we're going to leave this requiring a pr, but if we do decide want to make this dynamic in the future it won't be a huge undertaking.


# Future Plans:
- Port performance issues to the issue platform. This gives us more consistency, and will improve query performance since we no longer need to query the transactions table, which contains mostly irrelevant data.
- Improve the release process for new issue types. This is via a policy layer, that will automatically set up ways to release new issue types to LA, EA and GA and save adding a bunch of boilerplate code.

# Things we’ve cut:
Errors. We originally had plans to send errors through the issue platform to centralise everything. We’ve decided against this because it seems like a high risk task without much reward. The primary reason we wanted to send errors through the issue platform was so that we could split up detection from ingestion. We might still want to separate detection from ingestion in the future, and this doesn't necessarily have to involve the issue platform, or could involve a separate path through issue platform ingestion that still writes to the same errors dataset.

3rd party detectors. We don’t have a specific use case for these at the moment. Ideally, we’d find an external partner to work with first before we commit to building a whole system around 3rd parties contributing new issues to Sentry.