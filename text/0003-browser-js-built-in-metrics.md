* Start Date: 2022-08-18
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/3
* RFC Status: draft

# Expanding Built-In Performance Metrics for Browser JavaScript.

# Summary

This RFC details expanding list of built-in performance metrics for the browser JavaScript SDK, with additional data the Browser SDK captures. It propose adding two metrics that are already captured by the SDK: `connection.rtt` and `connection.downlink`, and three brand new metrics that are not yet captured, `deviceMemory`, `hardwareConcurrency`, and `longTaskCount`.

# Background

The Sentry product now supports the ability to set [Performance Metrics in the product](https://docs.sentry.io/product/sentry-basics/metrics), via attaching numeric tags to transaction data. Internally, we refer to these numeric tags as `measurements`. Some of these performance metrics are considered "built-in", and are automatically sent from certain SDKs. These built-in measurements are defined in an [explicit allowlist in Sentry's Relay config](https://github.com/getsentry/sentry/blob/dddb995d6f33527cc5fd2b6c6d484b29bb02253d/src/sentry/relay/config/__init__.py#L407-L428), and are [defined in Relay themselves as well](https://github.com/getsentry/relay/blob/4f3e224d5eeea8922fe42163552e8f20db674e86/relay-server/src/metrics_extraction/transactions.rs#L270-L276). 

The Browser JavaScript SDKs currently has [seven built-in measurements](https://docs.sentry.io/platforms/javascript/performance/instrumentation/performance-metrics/), `fp`, `fcp`, `lcp`, `fid`, `cls`, `ttfb`, and `ttfb.requesttime`. In addition to built-in measurements, the product supports sending arbitrary custom performance metrics on transactions. For example in JavaScript:

```ts
const transaction = Sentry.getCurrentHub().getScope().getTransaction();

// Record amount of times localStorage was read
transaction.setMeasurement('localStorageRead', 4);
```

In the product, we display the built-in performance metrics and custom performance metrics in different sections of the event details. In addition, there is a limit to the number of custom performance metrics that can be set on a transaction (TODO on what exactly this is).

# Proposals

## Existing Data

Aside from the seven built-in measurements the JavaScript SDKs set, the JavaScript SDK also sets [`connection.rtt` and `connection.downlink` as performance metrics](https://github.com/getsentry/sentry-javascript/blob/74db5275d8d5a28cfb18c5723575ea04c5ed5f02/packages/tracing/src/browser/metrics/index.ts#L396-L402). Since these are not in the built-in allow list in Relay/Sentry, **they are considered custom performance metrics, and take away from the custom performance metric quota that exists on transactions**.

`connection.rtt` is the [the estimated effective round-trip time of the current connection, rounded to the nearest multiple of 25 milliseconds](https://developer.mozilla.org/en-US/docs/Web/API/NetworkInformation/rtt). `connection.downlink` is the [effective bandwidth estimate in megabits per second, rounded to the nearest multiple of 25 kilobits per seconds](https://developer.mozilla.org/en-US/docs/Web/API/NetworkInformation/downlink). These were originally added to the SDK [Oct 2020](https://github.com/getsentry/sentry-javascript/pull/2966) to help grab info about network connectivity information.

Either we choose to promote these two values to built-in measurements, or we remove them entirely if we feel like they are not high value.

## New Data

In the same PR that added `connection.rtt` and `connection.downlink`, we also added support for grabbing [`deviceMemory`](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/deviceMemory) and [`hardwareConcurrency`](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/hardwareConcurrency). Currently these are set as [tags on the transaction](https://github.com/getsentry/sentry-javascript/blob/74db5275d8d5a28cfb18c5723575ea04c5ed5f02/packages/tracing/src/browser/metrics/index.ts#L405-L411). This should become performance metrics, as SDKs should not be settings tags like this one events, and there is value in seeing these numeric values on transactions.

Another additional option is to move all [browser Navigator](https://developer.mozilla.org/en-US/docs/Web/API/Navigator) related fields into a brand new SDK context - that is avaliable to all events, not just performance ones.

[Long Tasks](https://developer.mozilla.org/en-US/docs/Web/API/Long_Tasks_API) are JavaScript tasks that take 50ms or longer to execute. They are considered problematic because JavaScript is single threaded, so blocking the main thread is a big performance hit. In the SDK, [we track individual long task occurences as spans](https://github.com/getsentry/sentry-javascript/blob/74db5275d8d5a28cfb18c5723575ea04c5ed5f02/packages/tracing/src/browser/metrics/index.ts#L54-L59) and record them onto transactions.

In Sentry, we've been recording [`longTaskCount` on transactions](https://github.com/getsentry/sentry/blob/20780a5bdd988daa44825ce3c295452c280a9add/static/app/utils/performanceForSentry.tsx#L125) as a Custom Performance Metric for the Sentry frontend. So far, tracking the `longTaskCount` has been valuable as it allows us at a high level to see the most problematic transactions when looking at CPU usage. Since we already record long task spans in the SDK, it should be fairly easy to generate the count as a measurement, and promote into a built-in measurement.

## Decisions

Below Records each proposed built-in measurement, and the decision that was taken around them:

- [ ] `connection.rtt`
- [ ] `connection.downlink`
- [ ] `deviceMemory`
- [ ] `hardwareConcurrency`
- [ ] `longTaskCount`