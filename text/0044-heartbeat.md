- Start Date: 2022-12-09
- RFC Type: feature
- RFC PR: N/A
- RFC Status: Approved

# Summary

Through “heartbeat” monitoring, we want a way for the SDKs to communicate with Sentry so that they are at the bare minimum connected.

This will also be expanded in the future to include richer diagnostic information about SDK configuration such as configured products (bug tracking, performance profiling, replay) or features (e.g. releases, customer sample rates, frameworks, integrations ) and potentially more.

# Motivation

User onboarding is negatively impacted by not having the means to confirm that the connection between the SDK and Sentry has been established, forcing users to submit a first error or transaction, which can create further confusion.

This type of situation is something we've seen in most of the user tests we've done recently. Participants trying to integrate Sentry with their SDKs for the first time were confused by sending events and not receiving an error in the Sentry application. This made them wonder if the DSN was correct or not and some also thought that they might have missed some important information in the instructions.

Our hypothesis is that users are pushed through the flow to ensure connection and that they are “onboarded” but lose valuable time appreciating what we want them to be able to do with the product.
We also believe that if we separate the need for a first event and that it is an error event, we can focus on onboarding and not on generating an error.

# Use Cases

**1. Initial Project Setup**

Today we are basically relying on customers sending a first error event in order to give users feedback on their setup during their onboarding and project creation. We want to decouple these two events in order to give users more precise feedback on the success of their configuration.

**User story**: As a user integrating Sentry into a new project, I want to receive feedback on the successful connection between my application and Sentry during this process, before starting to send events such as errors or transactions.

**2. Sentry connection monitoring**

Every time an application starts up a heartbeat helps to establish that the Sentry SDK is present and connected.

**User story**: As a user, I want to know whether Sentry is connected or not so that I am sure everything is working correctly and I can avoid any observability gaps.

This is highly platform-dependent:

1. for front-end and mobile applications the heartbeat on start-up is enough
2. for back-ends it’s necessary to periodically send a heartbeat to know that it is still connected

**3. Sentry config visibility across releases (secondary)**

Especially for mobile projects, where a number of different releases might still be active concurrently with different configurations, it can be hard for customers to keep track and cumbersome to search through code in order to determine what options were set.

**User story**: As a mobile customer, I want to have visibility in the Sentry product of my different configurations across releases, so that I can easily verify what options were set for a particular release if needed.

_Note_: this is about SDK diagnostics, so probably better fits to Client Reports.

# Options Considered

**1. Release Health (Session Tracking)**

It is an already existing and robust technology that gives us all the information we need for use cases 1 and 2 and would cause almost no work to everyone envolved. Also, since it's already supported by many SDKs, when we release the new feature, adoption will be almost immediate.

**2. Client Reports**

Client Report is an existing technology that we can update in the future to bring more diagnostic data about the SDK.

Currently it only sends data to Sentry when a problem is detected, for example a rate limit and in the future we would like this technology to constantly send data to Sentry regardless of errors.

**3. Combination of Release Health + Client Reports + Transactions + Errors**

The heartbeat solution shall be created in a way, where we can connect one or several signals - from Release Health Session, from Client Reports and from Transactions and Error events - In this way, the information we collect will be even more reliable and if in case a service is available, we can fall back on the next available one.

# Conclusion

The creation of a new endpoint as initially proposed (see appendix) is not necessary since we already have a technology in place that already give usually the information needed for the first two use cases.

For the last use case, we can use the Client Report technology, but some updates will be needed, as currently this technology does not send data to Sentry constantly and does not provide all the data that we will possibly need. We still need to evaluate what data would be interesting to collect for the new onboarding flow.

A mechanism that combines the three proposed options is also something we want to implement, so that the diagnostic data is even more reliable and, in case there is an unavailable service, we can fall back to the next one available.

# Appendix

> Everything described below has already been discussed and the proposal has been discarded. We are keep it here for documentation purposes only.

# Summary

Introduce a heartbeat in all SDKs supported by us. The heartbeat will carry diagnostic data and will be triggered every time the user launches the application.

# Motivation

As part of the [SDK onboarding improvements initiative](https://www.notion.so/sentry/SDK-Onboarding-Improvements-261a3d1deed94522bcff1361fc8bd756) (employees only), user tests have recently been done, where we collect data about the user experience when trying to integrate Sentry for the first time with their applications.

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

This is [one of the designs](https://www.figma.com/file/4EkecQGYtbpOY1G6oEir4X/Exploration%3A-User-Journey?node-id=215%3A1147&t=fGJbtdmq2tDAI8iE-0) we have in mind for the UI (employees only).

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

# Others

- [Previous internal DACI](https://www.notion.so/sentry/Boot-up-and-or-heart-beat-b4308d3562a34aa6bba3c86bab575ea8) (employees only)
- [Heartbeat Kick-off meeting](https://www.notion.so/sentry/SDK-Onboarding-Improvements-261a3d1deed94522bcff1361fc8bd756?p=ed5580c63cbf4298ac78eb0b4a9b508a&pm=s) (employees only)
