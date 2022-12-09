- Start Date: 2022-12-09
- RFC Type: feature
- RFC PR: N/A
- RFC Status: draft

# Summary

Introduce an infrastructure monitoring agent in all SDKs supported by us. This agent will be triggered every time the user launches the application and will send us information about the state of their integration with Sentry.

# Motivation

As part of the SDK onboarding improvements initiative, user tests have recently been done, where we collect data about the user experience when trying to integrate Sentry for the first time with their applications.

Several discoveries were made, but one in particular that caught our attention is that many users, after following all the installation steps and sending the first error, were confused and frustrated if they did not see it in the Sentry's application.

After refreshing the Sentry's application page a few times to see if they get an error and not getting it, they were left wondering if they missed something while configuring Sentry, which led them to open the onboarding documentation again.

We also noticed that when they successfully sent an issue to Sentry, they were confused as they were taken to the issue stream page without receiving any feedback in the UI, which was initially awaiting for an event.

# Background

Historically there has never been supported use cases where Sentry has allowed SDKs would “call home” and check-in. Client Reports provided functionality which moved in that direction. Originally users could only see server-side “dropped” events, but client reports allowed us to gather numbers on how many events are “discarded” before ever leaving the SDK. It was originally designed as a solution to determine if a problem existed in any of the SDKs where we had a lot of discards due to technical issues. But what we have found is that sales and support find this information to be empowering, allowing them to see for the customer what their sample rate might be and tell them if they are really missing errors or transactions due to Sentry dropping or due to the SDK discarding for any number of outcome reasons. With this in mind, there are more use cases to be built on top of client reports. One of these is a ping endpoint functionality, similar to a health endpoint, so developers can check if their apps have the SDKs initialized correctly.

# Supporting Data

AJ:

> I am looking at cohort where of all the orgs sending txn only 13% actually use perf

I believe orgs sending txn rate is pretty good for new projects because most devs don’t look at the details in the code snippet and end up sending txn. However, the challenge is they don’t know about Perf or never go there

# Options Considered

## Heartbeat/Pulse endpoint

Create an endpoint called heartbeat or pulse that would be used via a request whenever the user successfully launches their app.

The request body would initially be quite simple, containing only the following:

`{type: 'heartbeat'}`

Sentry when collecting this information will be able to give feedback to the user through the user interface, such as that he can now send an error or perform other actions.

In the future, we can also use this mechanism to send other information to Sentry, such as whether the user has configured performance, profiling, etc.

## Session

We're still not sure about this option and are planning to work on a Spike, but the idea is that we'll be able to use the user's session to find out if Sentry's integration with an SDK is working properly.

# Drawbacks

We would like to know through this RFC if there are any drawbacks that we should consider

# Unresolved questions

- If we decide to use the Heartbeat/Pulse endpoint solution, can it be sent along with the envelope?
- Are there any implications with the proposed solutions?
- We noticed that we currently store information about the first event. See:

  `postgresql on <getsentry_project>.<<firstevent>>`

  If we decide to go with the first proposed solution, is this something we can reuse during implementation?
