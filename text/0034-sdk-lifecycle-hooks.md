- Start Date: 2022-11-03
- RFC Type: feature
- RFC PR: [https://github.com/getsentry/rfcs/pull/34](https://github.com/getsentry/rfcs/pull/34)
- RFC Status: approved
- RFC Driver: [Abhijeet Prasad](https://github.com/AbhiPrasad)

# Summary

This PR proposes the introduction of lifecycle hooks in the SDK, improving extensibility and usability of SDKs at Sentry.

Lifecyle hooks can be registered as a top level method, and allow for integrations/sdk users to have finely grained control over the event lifecycle in the SDK.

```ts
Sentry.on("hook-name", (...args) => {
  someLogic();
});
```

# Motivation

There are three main ways users can extend functionality in the SDKs right now.

At it's current form, the SDK is an event processing pipeline. It takes in some data (an error/message, a span, a profile), turns it into the event, attaches useful context to that event based on the current scope, and then sends that event to Sentry.

```
| Error | ---> | Event | ---> | EventWithContext | ---> | Envelope | ---> | Transport | ---> | Sentry |
```

```
| TransactionStart | ---> | SpanStart | ---> | SpanFinish | ---> | TransactionFinish | --> | Event | ---> | EventWithContext | ---> | Envelope | ---> | Transport | ---> | Sentry |
```

```
| Session | ---> | Envelope | ---> | Transport | ---> | Sentry |
```

The SDKs provide a few ways to extend this pipeline:

1. Event Processors (what Integrations use)
2. `beforeSend` callback
3. `beforeBreadcrumb` callback

But these are all top level options in someway, and are part of the unified API as a result. This means that in certain scenarios, they are not granular enough as extension points.

# Proposal

SDK hooks live on the client, and are **stateless**. They are called in the order they are registered. SDKs can opt-in to whatever hooks they use, and there can be hooks unique to an SDK.

```ts
class Client {
  hooks: {
    [hookName: string]: HookCallback[];
  };

  on(hookName: string, callback: HookCallback) {
    this.hooks[hookName].push(callback);
  }
}
```

## Hooks

Hooks can return `null` to short-circuit the pipeline.

- `captureException`

```ts
type onCaptureException<T = any> = (
  exception: T,
  hint?: EventHint,
  scope?: Scope
) => T | null;
```

- `captureMessage`

```ts
type onCaptureMessage = (
  message: string,
  level?: Severity,
  hint?: EventHint,
  scope?: Scope
) => string | null;
```

- `captureEvent`

```ts
type onCaptureEvent = (
  event: Event,
  hint?: EventHint,
  scope?: Scope
) => string | null;
```

- `capture

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known?
