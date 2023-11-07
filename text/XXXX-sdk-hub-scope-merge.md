- Start Date: 2023-11-07
- RFC Type: feature
- RFC PR: TODO
- RFC Status: draft

# Summary

We want to streamline Hub & Scope usage for the SDK.

# Motivation

Generally, Hubs and Scopes are a very Sentry-specific concept, and can be a bit hard to explain. 
Also, how Hub & Scope forking behaves is currently a bit tricky, and does not play well e.g. with how OpenTelemetry contexts work.

This RFC aims to streamline this by merging the concepts of Hub and Scope into a singular Scope concept.

# Background

TODO

# Proposed Solution

Hubs will be removed as a concept for SDK users. 
Instead, from a users perspective only Scopes remain, which will become the singular entity to hold context data etc.

Scopes will be _similar_ to how they work today, but not entirely the same. 
Scopes can have data (e.g. tags, user, ...) added to them the same way you can do today. 
This RFC _does not_ aim to change any of the data that is kept on the scope and is applied to events.

The following APIs will be removed:

* `getCurrentHub()`
* `configureScope()` (instead just get the scope and set on it directly)
* Any APIs currently on the Hub only: 
  * `hub.pushScope()`
  * `hub.popScope()`
  * `hub.isOlderThan()`
  * `hub.bindClient()`
  * `hub.getStack()`
  * `hub.getStackTop()`
  * `hub.run()` (use `withScope()` instead)

Instead, we will introduce some new APIs:

```ts
// get the currently active scope. replacement for `getCurrentHub().getScope()`
export function getScope(): Scope;

// get the currently active client. May return a NOOP client. Replacement for `getCurrentHub().getClient()`.
export function getClient(): Client;

// make a scope the current scope. Replacement for `makeMain(hub)`
export function makeCurrentScope(scope: Scope): void;
```

The following APIs already exist but will behave differently:

* `withScope()` will still work, but it will actually fork an execution context. So this will roughyl the same as doing `hub.run()` today.

APIs that are currently on the hub should instead be called directly on the scope (e.g. `scope.captureException()` etc.), or via a global method (e.g. `Sentry.captureException()`).

## Clients

Instead of a client being optional, there will now _always_ be a client. It may be a Noop Client that does nothing, if `init()` has not been called yet.

Each client gets a fresh initial scope when it is initialized:

```js
const client = new Client();
client.getScope(); // <-- fresh, initial scope for this client
scope.getClient(); // <-- get client of scope
```

You can make a scope the current one like this:

```js
makeCurrentScope(client.getScope());
// this scope/client will now be available via e.g. `getScope()` or `getClient()`
// this is what init() calls under the hood
```

The current scope may be kept similar to how we currently keep the current hub, but this is SDK specific and not part of this RFC.

When calling `getScope()` before a scope was made the current one (=before init was called), we will return a scope for a noop client. 
A noop client is a regular client that simply does not send anything.

This way, the API for `getClient()` can always return a client, and users do not have to guard against this being undefined all the time. 
We may also expose a util like `sentryIsInitialized()` that checks if the current client is a Noop client (which currently you could have checked as `getCurrentHub().getClient() === undefined`).

If you want to have multiple isolated clients, you can achieve this easily with this new setup:

```js
const client1 = new Client();
const client2 = new Client();

const scope1 = client1.getScope();
const scope2 = client2.getScope();

scope1.captureException(); // <-- isolated from scope2
```

## Scopes

Scopes behave similar to how they behave today. 
When a scope is forked via `withScope()`, a new scope is created that inherits all data currently set on the parent scope.

The main change to Scopes is that they do not push/pop anymore, but instead fork an execution context (in languages where this makes sense/is possible).
Basically, `withScope()` should behave like `hub.run()` does today.

`client.getScope()` should return the current scope of this client in the current execution context.

From a users perspective, this should mostly not be noticeable - they can always run `getScope()` to get the current scope, or `withScope(callback)` to fork a new scope off the current scope.

You can make a scope the current one via `makeCurrentScope(scope)`, which should bind the scope to the current execution context (or a global, in SDKs without execution context).

## What about other Hub references?

While the Hub is mainly exposed via `getCurrentHub()`, it is also used as argument or similar in many places. 
These occurences should be updated to instead take a scope or a client.

## What about backwards compatibility?

We should strive to provide a wrapper/proxy `getCurrentHub()` method that still exposes the key functionality to ease upgrading. E.g.:

```js
import {getScope, getClient} from '../internals';

function getCurrentHub() {
  return {
    getClient,
    getScope
  }
}
```

We need to decide what to keep in that proxy and what not.

## What about globals?

This RFC does not propose any concrete way to store the current scope. This is up to the concrete SDK and may behave the same way as it currently does for the hub, or differently if that makes more sense in a given scenario.

# Drawbacks

* This changes _a lot_ of public APIs and behavior.

# Unresolved questions

TODO
