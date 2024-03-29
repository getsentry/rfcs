- Start Date: 2022-12-09
- RFC Type: feature
- RFC PR: N/A
- RFC Status: Approved

# Summary

Through “heartbeat” monitoring, we want a way for the SDKs to communicate with Sentry so that they are at the bare minimum connected.

This will also be expanded in the future to include richer diagnostic information about SDK configuration, such as the configuration of products 'error monitoring', 'performance monitoring', 'profiling', 'replays' and potentially more.

# Motivation

User onboarding is negatively impacted by not having the means to confirm that the connection between the SDK and Sentry has been established, forcing users to submit a first error or transaction, which can create further confusion.

This type of situation is something we've seen in most of the user tests we've done recently. Participants trying to integrate Sentry with their SDKs for the first time were confused by sending events and not receiving an error in the Sentry application. This made them wonder if the DSN was correct or not and some also thought that they might have missed some important information in the instructions.

Our hypothesis is that users are pushed through the flow to ensure connection and that they are “onboarded” but lose valuable time appreciating what we want them to be able to do with the product.
We also believe that if we separate the need for a first event and that it is an error event, we can focus on onboarding and not on generating an error.

# Use Cases

**1. Initial Project Setup**

Today we are basically relying on customers sending a first error event in order to give users feedback on their setup during their onboarding and project creation. We want to decouple these two events in order to give users more precise feedback on the success of their configuration.

The idea is that every time an application is started, the user will be informed through the UI that the Sentry SDK is present and connected.

**User story**: As a user integrating Sentry into a new project, I want to receive feedback on the successful connection between my application and Sentry during this process, before starting to send events such as errors or transactions.

This is highly platform-dependent:

1. for front-end and mobile applications the heartbeat on start-up is enough
2. for back-ends it’s necessary to periodically send a heartbeat to know that it is still connected

**2. SDK diagnostics through Client Reports (Down the road)**

As part of options 2 and 3 presented in the next section, we would like to use the Client Reports service to collect diagnostic data from SDKs. This collected data will help us provide more accurate user feedback regarding the incorrect configuration that users may have set when trying to instrument Sentry in their SDKs.

We still don't know exactly what data it would be interesting to collect, but an idea would be, for example, the information if a session was sent without a release name. That way we would know that the DSN was set up correctly, so there is a connection between Sentry and the user SDK, but the release name is missing, and that is the reason why no session was identified on the Sentry server.

**User story**: As a new Sentry user, instrumenting Sentry in my SDK with a `correct` DSN, I would like to know if the rest of my configuration is correct and if not, what I have configured wrong.

_Note_ This is something we certainly want to work on soon, but which will gain more focus in the next phases of this project. For this first phase, the information collected by the Client Report service is already satisfactory and we will be working with it.

# Options Considered

**1. Release Health (Session Tracking)**

It is an already existing and robust technology that gives us all the information we need for use case 1 and would cause almost no work to everyone envolved. Also, since it's already supported by many SDKs, when we release the new feature, adoption will be almost immediate.

**2. Client Reports**

Client Report is an existing technology that we can update in the future to bring more diagnostic data about the SDK.

Currently it only sends data to Sentry when a problem is detected, for example a rate limit and in the future we would like this technology to constantly send data to Sentry regardless of errors.

**3. Combination of Release Health + Client Reports + Transactions + Errors**

The heartbeat solution shall be created in a way, where we can connect one or several signals - from Release Health Session, from Client Reports and from Transactions and Error events - In this way, the information we collect will be even more reliable and if in case a service is available, we can fall back on the next available one.

# Conclusion

The creation of a new endpoint as initially proposed (see appendix) is not necessary since we already have a technology in place that already give usually the information needed for the first two use cases.

For the last use case, we can use the Client Report technology, but some updates will be needed, as currently this technology does not send data to Sentry constantly and does not provide all the data that we will possibly need. We still need to evaluate what data would be interesting to collect for the new onboarding flow.

A mechanism that combines the three proposed options is also something we want to implement, so that the diagnostic data is even more reliable and, in case there is an unavailable service, we can fall back to the next one available.

# Documents

- [Previous internal DACI](https://www.notion.so/sentry/Boot-up-and-or-heart-beat-b4308d3562a34aa6bba3c86bab575ea8) (employees only)
- [Heartbeat Kick-off meeting](https://www.notion.so/sentry/SDK-Onboarding-Improvements-261a3d1deed94522bcff1361fc8bd756?p=ed5580c63cbf4298ac78eb0b4a9b508a&pm=s) (employees only)
- [Sentry heartbeat doc](https://www.notion.so/sentry/Sentry-Heartbeat-c94ff5781c144b4c87b24fc1a302faa7) (employees only)
- [SDK Onboarding Improvements](https://www.notion.so/sentry/SDK-Onboarding-Improvements-261a3d1deed94522bcff1361fc8bd756) (employees only)

# Appendix

> The RFC described below has already been discussed and the proposal has been discarded. We are keep it here for documentation purposes only.

[Previous RFC](https://github.com/getsentry/rfcs/blob/ff09a49fe353e36dae426223c5d897700c9d3053/text/0044-heartbeat.md)
