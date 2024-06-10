- Start Date: 2024-06-04
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/136
- RFC Status: draft

# Summary

This RFC aims to find a strategy to define a better lifetime for traces so they don’t reference hundreds of unrelated
events.

# Motivation

On mobile, traces can have hundreds of unrelated events caused by the possibly never-changing
`traceId` required for tracing without performance. This occurs mostly when users don’t have performance
enabled.

# Background

In the summer of 2023, all mobile SDKs implemented [Tracing without performance](https://www.notion.so/Tracing-without-performance-efab307eb7f64e71a04f09dc72722530?pvs=21),
see also [team-sdks GH issue](https://github.com/getsentry/team-sdks/issues/5).
The goal of this endeavor was to

> always have access to a trace and span ID, add a new internal `PropagationContext` property to the
> scope, an object holding a `traceId` and `spanId`

On mobile, most users interact purely with the static API, which holds a reference to a global
Hub and Scope. Therefore, mobile SDKs create a `PropagationContext` with `traceId` and `spanId`
during initialization, and these usually persist for the entire lifetime of the app. Mobile
SDKs prefer the `traceID` of transactions bound to the scope over the `PropagationContext`. So
when performance is disabled, or no transition is bound to the scope, mobile SDKs use the same
`traceId` and `spanId` for all captured events. This can lead to traces with hundreds of
unrelated events confusing users. JS addressed this recently by updating the `PropagationContext`
based on routes, see [Ensure browser traceId lifetime works as expected](https://github.com/getsentry/sentry-javascript/issues/11599).

# Options Considered

## Option 1: Update `PropagationContext` based on screens <a name="option-1"></a>

Mobile SDKs base the lifetime of the `traceId` of the `PropagationContext` on screens/routes,
which is similar to a route on JavaScript. Mobile SDKs already report the screen name automatically
via `view_names` with the [app context](https://develop.sentry.dev/sdk/event-payloads/contexts/#app-context)
and use the same information for the name of screen load transactions, which the screen load
starfish module uses. Whenever the screen name changes automatically or with a yet to be defined
[manual API](https://www.notion.so/sentry/Specs-Screens-API-084d773272f24f57aeb622c07619264e),
mobile SDKs must renew the `traceId` of the `PropagationContext`. The screen load transaction
and subsequent events on the same screen must use the same `traceId`. When the app moves to the
foreground after being in the background for longer than 30 seconds, which is the same approach
mobile SDKs use for determining the end of a session, mobile SDKs renew the `traceId` of the
PropagationContext. If the app stays in the background for shorter or equal to 30 seconds,
mobile SDKs must not renew the `traceId` of the PropagationContext when the app moves again to
the foreground.

### Pros <a name="option-1-pros"></a>

1. Similar to [JavaScript]((https://github.com/getsentry/sentry-javascript/issues/11599)) updating
it based on routes, so it should be easy to implement for React-Native.
2. Works for spans first, as all spans get added to one trace per screen.

### Cons <a name="option-1-cons"></a>

1. For single-screen applications such as social networks, the lifetime of a trace could still be
long, and multiple unrelated events could be mapped to one trace.
2. For applications running for a long time in the background, such as running apps, the lifetime of
a trace could still be long, and multiple unrelated events could be mapped to one trace.
3. It doesn’t work well for declarative UI frameworks as Jetpack Compose and SwiftUI for which the
SDKs can’t reliably automatically detect when apps load a new screen.

# Drawbacks

Please add drawbacks here if you can think of any.

# Unresolved questions

- None.
