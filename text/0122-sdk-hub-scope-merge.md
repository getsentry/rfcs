- Start Date: 2023-11-07
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/122
- RFC Status: draft

# Summary

We want to streamline Hub & Scope usage for the SDK.

# Motivation

Generally, Hubs and Scopes are a very Sentry-specific concept, and can be a bit hard to explain. 
Also, how Hub & Scope forking behaves is currently a bit tricky, and does not play well e.g. with how OpenTelemetry contexts work.

This RFC aims to streamline this by merging the concepts of Hub and Scope into a singular Scope concept.

It also proposes the new concepts of global & isolated scopes.

# Background

TODO

# Proposed Solution

Hubs will be removed as a concept for SDK users. 
Instead, from a users perspective only Scopes remain, which will become the singular entity to hold context data etc.

Scopes will be _similar_ to how they work today, but not entirely the same. 
Scopes can have data (e.g. tags, user, ...) added to them the same way you can do today. 
This RFC _does not_ aim to change any of the data that is kept on the scope and is applied to events.

The following APIs will be removed/deprecated:

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
export function setCurrentScope(scope: Scope): void;

// get the currently active global scope
export function getGlobalScope(): Scope;

// get the currently active isolation scope
export function getIsolationScope(): Scope;

// similar to `withScope`, but defines an isolation scope
export function withIsolationScope(callback: (scope: Scope) => unknown): unknown;
```

The following APIs already exist but will behave differently:

* `withScope()` will still work, but it will actually fork an execution context. So this will roughly do the same as doing `hub.run()` today in languages that have that, which forks an execution context. 

APIs that are currently on the hub should instead be called directly on the scope (e.g. `scope.captureException()` etc.), or via a global method (e.g. `Sentry.captureException()`).

The current scope may be kept similar to how we currently keep the current hub, but this is SDK specific and not part of this RFC.

## Clients

Instead of a client being optional, there will now _always_ be a client. It may be a Noop Client that does nothing, if `init()` has not been called yet.

A scope has a reference to a client. By default it will reference a noop client. You can bind a client to a scope via `scope.setClient()`. 
The client is inherited by forked scopes.

```js
const client1 = new Client();
const scope = new Scope();

scope.getClient(); // <-- returns a noop client by default

scope.setClient(client1);
scope.getClient(); // <-- returns client1
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

const scope1 = new Scope();
const scope2 = new Scope();

scope1.setClient(client1);
scope2.setClient(client2);

scope1.captureException(); // <-- isolated from scope2
```

## Scopes

Scopes behave similar to how they behave today. 
When a scope is forked via `withScope()`, a new scope is created that inherits all data currently set on the parent scope.

The main change to Scopes is that they do not push/pop anymore, but instead fork an execution context (in languages where this makes sense/is possible).
Basically, `withScope()` should behave like `hub.run()` does today in languages that have execution context forking.

`client.getScope()` should return the current scope of this client in the current execution context.

From a users perspective, this should mostly not be noticeable - they can always run `getScope()` to get the current scope, or `withScope(callback)` to fork a new scope off the current scope.

You can make a scope the current one via `setCurrentScope(scope)`, which should bind the scope to the current execution context (or a global, in SDKs without execution context). This is a replacement for the current APIs like `makeMain(hub)` or `setCurrentHub(hub)`.

You can still clone scopes manually the same way as before, e.g. via `Scope.clone(oldScope)` or a similar API. In contrast to `withScope()`, this will _not_ fork an execution context.

You can update the client of a scope via `scope.setClient(newClient)`. This will not affect any scope that has already been forked off this scope, but any scope forked off _after_ the client was updated will also receive the updated client.

Every scope is always tied to a client.

## Global Scope

In addition to the currently active scope, there will also be a new special scope, the **Global Scope**.
The global scope is _not_ the initial scope, but a special scope that belongs to a client and is applied to any event that belongs to this client.

You can get the current global scope via `getGlobalScope()`. There _may_ be a function `setGlobalScope(scope)` to update the global scope - or SDKs can decide that there is no need to update the global scope, you can only mutate it.

If you call `getGlobalScope()` before a client is initialized, we should still get a global scope back (tied to a Noop client). Once an actual client is initialized, the global scope of the noop client should be merged into the new global scope for the new client. This should ensure that even if you call `getGlobalScope().setTag(...)` before the SDK is initialized, no data is lost.

The reason that the global scope is not the same as the initial scope of a client, is that you cannot accidentally mutate it - nothing ever inherits off the global scope.

## Isolation Scopes

Furthermore, there can also be **Isolation Scopes**.
Similar to the global scope, these are also applied to events. However, isolation scopes can be created, either by us internally (the most common scenario), or also by users. The new APIs for this are:

```js
// Returns the currently active isolation scope.
export function getIsolationScope(): Scope;

// Create a new isolation scope for this scope
// This will NOT make this scope the isolation scope, but will create a new isolation scope (based on the currently active isolation scope, if one exists)
scope.isolate();

// Similar to `withScope`, but it forks a new scope AND sets a new isolation scope for this context
export function withIsolationScope(callback: (scope) => void): void;
```

You can fetch the currently active isolation scope via `getIsolationScope()`. You can define a new isolation scope via `scope.isolate()`, which will define a new isolation scope for this scope, and for all scopes that will be forked off this scope. When a client is created & bound, an initial isolation scope will immediately be created, similar to the global scope for a client.

An isolation scope is attached to the current execution context, similar to the active scope. There is always exactly one active isolation scope. If you call `getIsolationScope()` before a client has been created, a noop isolation scope is returned, which should be merged in once a client is actually created (same as with the global scope).

Similar to the global scope, an isolation scope is always a separate scope, so nothing will inherit off it - except for a potential superseding isolation scope. 
If an isolation scope is created, and there is already an isolation scope in the current execution context, then the new isolation scope should be forked off the previous one (with copy-on-write).

### When to create an isolation scope

For most server-side SDKs, an isolation scope will be created for each request being processed. 
Roughly, it will equate to each time we currently fork a hub.

### Examples for isolation scopes

Example for instrumentation that we would write:

```ts
function wrapHttpServerRequest(original: Function): Function {
  // Fork an execution context for this server request, that is isolated
  return Sentry.withIsolatedScope((scope) => {
    // anything in here will have the same isolated scope!
    return original();
  })
}
```

Example for hooking into external auto-instrumentation (e.g. OpenTelemetry):

```ts
let onRequestHook: (span: Span) => void;

// This method is not defined by us, but is some external code
// Here just for demonstration purposes of how that may be implemented
function otelWrapHttpServerRequest(original: Function): Function {
  // Fork an execution context for this server request,
  // but without isolating this!
  return Sentry.withScope((scope) => {
    onRequestHook(trace.getActiveSpan());
    return original(); 
  });
}

// This would be our custom sentry configuration
onRequestHook = () => {
  const scope = getScope();
  scope.isolate(); // Add an isolation scope to the already forked scope
}
```

## Applying scopes

Scopes are applied in this order to events:

```ts
class Scope {
  public captureEvent(event: Event, additionalScope?: Scope) {
    // Global scope is always applied first
    const scopeData = getGlobalScope().getScopeData();

    // Apply isolations cope next
    const isolationScope = getIsolationScope();
    merge(scopeData, isolationScope.getScopeData());
    
    // Now the scope data itself is added
    merge(scopeData, scope.getScopeData());

    // If defined, add the captureContext/scope
    // This is e.g. what you pass to Sentry.captureException(error, { tags: [] })
    if (additionalScope) {
      merge(scopeData, additionalScope.getScopeData());
    }

    // Finally, this is merged with event data, where event data takes precedence!
    mergeIntoEvent(event, scopeData);
  }
}
```

Note that there is _always_ exactly one global & one isolation scope active.

## What about environments that do not have isolation of execution contexts (e.g. mobile, browser)?

Where not useful, you simply don't have to use the isolation scope. But it's always there, if the need arises. 
While it is empty it does nothing anyhow.

## What should be called from top level methods?

Top level APIs should generally interactive with the current active scope:

```js
Sentry.setTag();
Sentry.setUser();
Sentry.captureException();
// ...
```

The only exception is `addBreadcrumb()`. This should generally add breadcrumbs to the currently active isolation scope.
SDKs _may_ also add an option to the client to opt-in to put breadcrumbs on the global scope instead (e.g. for mobile or scenarios where you always want breadcrumbs to be global).

## Should users care about Clients?

Generally speaking, for most regular use cases the client should be mostly hidden away from users. 
Users should just call `Sentry.init()`, which will setup a client under the hood. Users should generally only interact with scopes, and we should keep clients out of most public facing APIs.

The client is only there to allow an escape hatch when users need to do more complex/special things, like isolating Sentry instances or multiplexing. So client APIs should be designed to _allow_ to do things that cannot be done via `Sentry.init()`, but our main focus should be on making the default experience easy to understand, which includes that users should not have to care about the concept of clients by default.

## What about other Hub references?

While the Hub is mainly exposed via `getCurrentHub()`, it is also used as argument or similar in many places. 
These occurences should be updated to instead take a scope or a client.

## What about backwards compatibility?

We should strive to provide a wrapper/proxy `getCurrentHub()` method that still exposes the key functionality to ease upgrading. E.g.:

```js
import { getScope, getClient, captureException, withScope } from '../internals';

function getCurrentHub() {
  return {
    getClient,
    getScope,
    captureException,
    withScope,
    // ...
  }
}
```

Based on the SDK, we can decide to keep _everything_ in this proxy (then we can do this even in a minor release),
or keep _most of it_ (if we do a major) - to break as little things in user land as possible.

## What about globals?

This RFC does not propose any concrete way to store the current scope. This is up to the concrete SDK and may behave the same way as it currently does for the hub, or differently if that makes more sense in a given scenario.

# Drawbacks

* This changes _a lot_ of public APIs and behavior.

# Unresolved questions

TODO
