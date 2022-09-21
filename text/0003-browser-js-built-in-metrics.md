* Start Date: 2022-08-18
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/3
* RFC Status: approved
* RFC Driver: [Abhijeet Prasad](https://github.com/AbhiPrasad)

# Expanding Built-In Performance Metrics for Browser JavaScript.

# Summary

This RFC details expanding list of built-in performance metrics for the browser JavaScript SDK, with additional data the Browser SDK captures. It propose adding a metric that is already captured by the SDK: `connection.rtt`, and a brand new metric that is not yet captured, `inp`.

Note: References to `performance metrics` (external name) are equivalent to `measurements` (internal name) for the purpose of this document.

# Background

The Sentry product now supports the ability to set [Performance Metrics in the product](https://docs.sentry.io/product/sentry-basics/metrics), via attaching numeric tags to transaction data. Internally, we refer to these numeric tags as `measurements`. Some of these performance metrics are considered "built-in", and are automatically sent from certain SDKs. These built-in performance metrics are defined in an [explicit allowlist in Sentry's Relay config](https://github.com/getsentry/sentry/blob/dddb995d6f33527cc5fd2b6c6d484b29bb02253d/src/sentry/relay/config/__init__.py#L407-L428), and are [defined in Relay themselves as well](https://github.com/getsentry/relay/blob/4f3e224d5eeea8922fe42163552e8f20db674e86/relay-server/src/metrics_extraction/transactions.rs#L270-L276). 

The Browser JavaScript SDKs currently has [seven built-in performance metrics](https://docs.sentry.io/platforms/javascript/performance/instrumentation/performance-metrics/), `fp`, `fcp`, `lcp`, `fid`, `cls`, `ttfb`, and `ttfb.requesttime`. In addition to built-in performance metrics, the product supports sending arbitrary custom performance metrics on transactions. For example in JavaScript:

```ts
const transaction = Sentry.getCurrentHub().getScope().getTransaction();

// Record amount of times localStorage was read
transaction.setMeasurement('localStorageRead', 4);
```

In the product, we display the built-in performance metrics and custom performance metrics in different sections of the event details. In addition, transactions have a [limit of 5 custom performance metrics that they can send](https://github.com/getsentry/sentry/blob/dddb995d6f33527cc5fd2b6c6d484b29bb02253d/src/sentry/relay/config/__init__.py#L430-L431).

# Proposals

## Existing Data

Aside from the seven built-in performance metrics the JavaScript SDKs set, the JavaScript SDK also sets [`connection.rtt` and `connection.downlink` as performance metrics](https://github.com/getsentry/sentry-javascript/blob/74db5275d8d5a28cfb18c5723575ea04c5ed5f02/packages/tracing/src/browser/metrics/index.ts#L396-L402). Since these are not in the built-in allow list in Relay/Sentry, **they are considered custom performance metrics, and take away from the custom performance metric quota that exists on transactions**.

`connection.rtt` is the [the estimated effective round-trip time of the current connection, rounded to the nearest multiple of 25 milliseconds](https://developer.mozilla.org/en-US/docs/Web/API/NetworkInformation/rtt). `connection.downlink` is the [effective bandwidth estimate in megabits per second, rounded to the nearest multiple of 25 kilobits per seconds](https://developer.mozilla.org/en-US/docs/Web/API/NetworkInformation/downlink). These were originally added to the SDK [Oct 2020](https://github.com/getsentry/sentry-javascript/pull/2966) to help grab info about network connectivity information.

Here, we propose that we should remove the reporting of `connection.downlink` and move `connection.rtt` to be a built-in performance metrics. `connection.rtt` will help users understand the network conditons of their transactions at a high level, and help them see how using things like PoP servers or more aggressive caching maybe help their pageload times. At a high level, `connection.rtt` should help the developer understand general network conditions across their production performance data.

We need to make a decision about `connection.downlink` and `connection.rtt`, as they are taking away from user's custom performance metrics quota.

## New Data

A new metric we would like to introduce is `inp`. `inp`, or [Interaction to Next Paint](https://web.dev/inp/) is the newest chrome web vital. We've already had some user interest in adopting this, as we already support the other web vitals (`lcp`, `fcp`, etc.). `inp` also opens the door for us to introduce [user interaction instrumentation](https://github.com/getsentry/sentry-javascript/issues/5750), like creating transactions to measure the performance of user clicks or inputs.

To instrument `inp` in our SDK, we require the usage of the [web-vitals v3 library](https://github.com/getsentry/sentry-javascript/issues/5462), but we can go ahead and make it a built-in performance metrics beforehand.

## Rollout

As we are only adding two built-in performance metrics, we will not have to do a phased rollout plan. Instead the rollout is as follows:

1. Add `connection.rtt` as a built-in metric to Relay/Sentry.

2. Update the JS SDK to stop sending `connection.downlink`, as we are only going to send `connection.rtt` as a performance metric.

3. Add `inp` as a built-in metric to Relay/Sentry.

4. Update the JS SDK to web vitals v3.

5. Add `inp` performance metric to all JS Browser SDK transactions.

# Appendix

## Removed Proposals

In the initial version of the proposal, a new built-in performance metric `long_task.count` was proposed. This was dropped because of the high burden of introducing too many built-in performance metrics. Below we've included the rationale for including `long_task.count` in the first place.

> [Long Tasks](https://developer.mozilla.org/en-US/docs/Web/API/Long_Tasks_API) are JavaScript tasks that take 50ms or longer to execute. They are considered problematic because JavaScript is single threaded, so blocking the main thread is a big performance hit. In the SDK, [we track individual long task occurences as spans](https://github.com/getsentry/sentry-javascript/blob/74db5275d8d5a28cfb18c5723575ea04c5ed5f02/packages/tracing/src/browser/metrics/index.ts#L54-L59) and record them onto transactions.
>
> In Sentry, we've been recording [`longTaskCount` on transactions](https://github.com/getsentry/sentry/blob/20780a5bdd988daa44825ce3c295452c280a9add/static/app/utils/performanceForSentry.tsx#L125) as a Custom Performance Metric for the Sentry frontend. So far, tracking the `longTaskCount` has been valuable as it allows us at a high level to see the most problematic transactions when looking at CPU usage. Since we already record long task spans in the SDK, it should be fairly easy to generate the count as a measurement, and promote into a built-in measurement. Here we would use `long_task.count` as the measurement name instead of `longTaskCount` that we used for internal testing.

In the second version of the proposal, it was proposed that [`device.memory`](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/deviceMemory) and [`hardware.concurrency`](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/hardwareConcurrency) would be inlcuded as new built-in performance metrics. This was removed because of the low value of these metrics and the fact that they are limiting in the data they provide. For `device.memory`, it seems that [WebKit won't ever support this](https://github.com/w3c/device-memory/issues/24). In addition, it's imprecise [OOB for fingerprinting reasons](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/deviceMemory). `hardware.concurrency` is valuable since it can help users decide on usage of [APIs like Web Workers](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/hardwareConcurrency), but perhaps it's better suited in `processor_count` under [Device Context](https://develop.sentry.dev/sdk/event-payloads/contexts/#device-context). Below we've included the rationale for including `device.memory` and `hardware.concurrency` in the first place.

> In the same PR that added `connection.rtt` and `connection.downlink`, we also added support for grabbing [`deviceMemory`](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/deviceMemory) and [`hardwareConcurrency`](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/hardwareConcurrency). Currently these are set as [tags on the transaction](https://github.com/getsentry/sentry-javascript/blob/74db5275d8d5a28cfb18c5723575ea04c5ed5f02/packages/tracing/src/browser/metrics/index.ts#L405-L411). This should become performance metrics, as SDKs should not be settings tags like this one events, and there is value in seeing these numeric values on transactions. Here we would also rename `deviceMemory` -> `device.memory` and `hardwareConcurrency` -> `hardware.concurrency`.
>
> Another additional option is to move all [browser Navigator](https://developer.mozilla.org/en-US/docs/Web/API/Navigator) related fields into a brand new SDK context - that is avaliable to all events, not just performance ones.
