- Start Date: 2022-11-03
- RFC Type: feature
- RFC PR: [https://github.com/getsentry/rfcs/pull/34](https://github.com/getsentry/rfcs/pull/34)
- RFC Status: approved
- RFC Driver: [Abhijeet Prasad](https://github.com/AbhiPrasad)

# Summary

This PR proposes the introduction of lifecycle hooks in the SDK, improving extensibility and usability of SDKs at Sentry.

To test out this RFC, we implemented it in the [JavaScript SDK](https://github.com/getsentry/sentry-javascript/blob/7aa20d04a3d61f30600ed6367ca7151d183a8fc9/packages/types/src/client.ts#L153) with great success, so now we are looking to propose and implement it in the other SDKs.

Lifecyle hooks can be registered on a Sentry client, and allow for integrations/sdk users to have finely grained control over the event lifecycle in the SDK.

```ts
interface Client {
  // ...

  on(hookName: string, callback: (...args: unknown) => void) => void;

  emit(hookName: string, ...args: unknown[]) => void;

  // ...
}
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

The following are some examples of how sdk hooks can unblock new features and integrations, but not a definitive list:

- Integrations want to add information to spans when they start or finish. This is what [RFC #75 is running into](https://github.com/getsentry/rfcs/pull/75), where they want to add thread information to each span.
- Integrations want to add information to envelopes before they are sent to Sentry.
- Integrations want to run code on transaction/span finish (to add additional spans to the transaction, for example).
- Integrations want to mutate an error on `captureException`
- Integrations want to override propagation behaviour (extracing/injecting outgoing headers)

# Proposal

SDK hooks live on the client, and are **stateless**. They are called in the order they are registered. SDKs can opt-in to whatever hooks they use, and there can be hooks unique to an SDK.

Hooks are meant to be mostly internal APIs for integration authors, but we can also expose them to SDK users if there is a use case for it.

As hook callbacks are not processed by the client, they can be async functions.

```ts
// Example implementation in JavaScript

type HookCallback = (...args: unknown[]): void;

class Client {
  hooks: {
    [hookName: string]: HookCallback[];
  };

  on(hookName: string, callback: HookCallback): void {
    this.hooks[hookName].push(callback);
  }

  emit(hookName: string, ...args: unknown[]): void {
    this.hooks[hookName].forEach(callback => callback(...args));
  }
}
```

SDKs are expected to have a common set of hooks, but can also have SDK specific hooks.

## Hooks

These following are a set of example hooks that would unblock some use cases listed above. The names/schema of the hooks are not final, and are meant to be used as a starting point for discussion.

To document and approve new hooks, we will create a new page in the develop docs that lists all the hooks, and what they are used for.

`startTransaction`:

```ts
on('startTransaction', callback: (transaction: Transaction) => void) => void;
```

`finishTransaction`:

```ts
on('finishTransaction', callback: (transaction: Transaction) => void) => void;
```

`startSpan`:

```ts
on('startSpan', callback: (span: Span) => void) => void;
```

`finishSpan`:

```ts
on('finishSpan', callback: (span: Span) => void) => void;
```

`beforeEnvelope`:

```ts
on('beforeEnvelope', callback: (envelope: Envelope) => void) => void;
```
