- Start Date: 2024-07-05
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/137
- RFC Status: draft

# Summary

Today, Sentry SDKs will continue any trace they get via e.g. a `sentry-trace` header. However, it is possible to receive incoming traces from external organizations, in which case it is incorrect to continue the trace.

We should implement a way to avoid incorrectly continuing such a trace. The easiest way to do this is to restrict trace continuation to happen for the same Organization only.

# Motivation

Today, if some external service (e.g. Zappier) makes an API call to a customers API, and includes a `sentry-trace` header, the API will continue the trace, even if that belongs to a completely different Sentry Org/Project. This is incorrect and that trace _should not_ be continued, but instead a new trace should be started in this case.

# Background

This problem has existed forever basically, but now is the time to finally fix it.

# Supporting Data

Example issue where this happens: https://github.com/getsentry/sentry-javascript/discussions/12774

# Options Considered

This RFC proposes the following Option (A):

## Option A: (Optionally) pass the Org in baggage header & use it to restrict

We should add a new option to all Sentry SDKs, `org`. This optional option takes an org slug, similar to sentry-cli. For example:

```js
Sentry.init({
    dsn: 'xxx',
    org: 'sentry',
});
```

When this option is set, it will propagate the org in the baggage entry as `sentry-org=sentry`. By default, nothing is done with this.

In addition to this, users can opt-into strict behavior by setting `strictTracePropagation: true` in their `init` code:

```js
Sentry.init({
    dsn: 'xxx',
    org: 'sentry',
    strictTracePropagation: true,
});
```

When this is enabled, the SDK should not continue any trace that does not continue a matching `sentry-org` baggage entry.

Clarifications on this:

* If `strictTracePropagation: true` is configured, but no `org` is defined, the SDK may warn.
* If `strictTracePropagation: true` is configured, but an incoming request has no baggage header at all (but it _has_ a `sentry-trace` header), it should _not_ be continued.

For now, this will be opt-in, but SDKs are free to switch the default to `true` in a major release. In onboarding for new projects, we should include `strictTracePropagation: true` by default.

In addition to allowing to manually configure the `org`, SDKs may also infer from other places. For example, if a bundler plugin is used we may infer it from there, if possible. 

We may also adjust the DSN structure (which is currently being reworked anyhow) to also include the DSN. In this case, new DSNs may infer the org from there, ensuring that users do not need to manually set the `org` in addition to `dsn`.

## Option B

Another option could be to configure something similar to `tracePropagationTargets` that leads to the SDK only continuing traces for allow-listed URLs. But this requires configuration by the user (and it may also change over time, ...).

# Drawbacks

This adds two new options to the SDKs, but they are both optional and opt-in. No current behavior will change for the time being, until a major (where possibly the default may change).

# Unresolved questions

- TODO