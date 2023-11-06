- Start Date: 2023-11-06
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/120
- RFC Status: draft

# Summary

We want to streamline Hub & Scope usage for the JavaScript SDK and beyond, to also better align with OpenTelemetry models etc.

# Motivation

Generally, Hubs and Scopes are a very Sentry-specific concept, and can be a bit hard to explain. 
Also, how Hub & Scope forking behaves is currently a bit tricky, and does not play well e.g. with how OpenTelemetry contexts work.

In OpenTelemetry, contexts are forked very often, because Contexts are copy-on-write - each time you want to set _anything_ on a context, you need to fork it.
This frequent forking leads to a lot of problems with how sentry scopes apply. 
Because any function or callback may have a forked context, attaching data inside of e.g. such a callback would lead to this never being applied to events correctly:

```js
app.get('/my-route', function() {
  db.query(myQuery, function() {
    console.log('query done!');
  });

  throw new Error(); // <-- this error would not have the "query done!" breadcrumb!
});
```

Since in the example above `db.query()` internally adds spans for the DB operations, which triggeres a new context in OpenTelemetry, nothing that happens inside of this callback would be added to any events outside of the callback. 

Making matters worse, the exact behavior there relies on how auto-instrumentation works under the hood. Depending on what is forked and where, breadcrumbs etc. _may_ be available outside, or not. This is unpredictable and hard to explain.

In order to a) Simplify the concepts our users have to learn about and b) Make interoperability with OpenTelemetry context forking better, this RFC sets out to rework how our scopes work. This is focusing on JavaScript for now, but may be applicable to other languages as well.

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

* `getScope()` - get the currently active scope. replacement for `getCurrentHub().getScope()`
* `getClient()` - get the currently active client. May return undefined if no client is configured. Replacement for `getCurrentHub().getClient()`.
* `bindClient(client)` - make a client the "current" client 
* The following new APIs that will be explained more below:
  * `getGlobalScope()`
  * `getRequestScope()`
  * `getRootScope()`
  * `setRootScope()`

The following APIs already exist but will behave differently:

* `withScope()` will still work, but it will actually fork an execution context. So this will roughyl the same as doing `hub.run()` today.

Note: The following hub APIs are already exported on their own and can continue to be used as before:

* `captureException()`
* `captureMessage()`
* `captureEvent()`
* `lastEventId()`
* `addBreadcrumb()`
* `setUser()`
* `setTags()`
* `setExtras()`
* `setTag()`
* `setExtra()`
* `setContext()`
* `getIntegration()`
* `captureCheckIn()`

These are not exported yet separately, but probably should be:

* `traceHeaders()`
* `captureSession()`
* `startSession()`
* `endSession()`
* `shouldSendDefaultPii()`


## Special Scopes

In addition to the inherited scope data, it is also possible to add data via additional scopes: 

* There is a special global scope, which always exists.
* And in addition to this, users can also add additional scopes which will be applied to events. 

This RFC proposes to add two types of scopes which can be added, request scopes & root scopes. 
They behave very similarly, the distinction is mostly to make things clearer for users.

### Global Scope

First, there is a _Global Scope_. This scope is tied to the client, and anything added to the global scope will always be added to _all_ events.
Note that the global scope _is not_ the initial scope, but a separate, "empty" scope. This way, you cannot accidentally pollute it. 
You can access it via `getGlobalScope()`:

```js
Sentry.init();

const scope = Sentry.getScope(); // <-- the initial scope, that other scopes will inherit from
const globalScope = Sentry.getGlobalScope(); // <-- the global scope that will be applied to all events

scope !== globalScope
```

Global scope data is applied to _all_ events.

### Request Scope

A request scope is a scope valid for a request. This is relevant for Node server SDK usage only.
Request scope should automatically be set by the SDK. Users can _access_ them in order to add data that should be valid for the whole request, e.g. a user:

```js
const app = express();
app.get('/my-route', () => {
  const requestScope = getRequestScope();
  requestScope?.setUser(user);
});
```

Request scope data is applied to all requests in this request. Request scope is defined to also work e.g. in other callbacks and similar:

```js
fastify.addHook('preValidation', () => {
  // You can attach stuff to the request scope even from other places,
  // ensuring it is added to all events in that request
  const requestScope = getRequestScope();
  requestScope.addEventProcessor(...);
});
```

Note that like the global scope, the request scope _is not_ the same as the scope in the route handler:

```js
app.get('/my-route', () => {
  // anything added here will apply to all events in this request
  const requestScope = getRequestScope();
  // anything added here will be inherited normally
  const scope = getScope();
  requestScope !== scope;
});
```

This is also done to a) avoid accidentally polluting the request scope, and b) to clarify things and avoid relying on internals (e.g. what is the exact scope that is active in a route handler depends on the instrumentation implementation).

### Root Scope

A root scope is functionally the same as a request scope, only that it is designed to be set by the user.
This can be useful for e.g. manually instrumenting queue jobs or similar, where we don't have a request.
Users can use `setRootScope()` and `getRootScope()` to interact with this:

```js
function myJob() {
  // Isolate this function
  withScope((jobScope) => {
    // Everything in this scope should have a root scope
    setRootScope();

    withScope(innerScope => {
        getRootScope()?.setTag('job', 'done');
    });
  });
}
```

The root scope behaves the same way as the request scope.

The main reason to have these two different types is that "Request Scope" is a much more natural way to think about this for our users in
actual scenarios. Having per-request isolation is by far the most common execution context scenario we care about, 
and explaining a request scope is much easier than the more abstract root scope. 

It is also a bit easier to explain that root scopes are _always_ manual while request scopes are generally defined by us or other instrumentation.

### How scopes are applied

Internally, scopes work as follows:

* Each scope can have additional scopes applied to them
  * These applied scopes are inherited by child scopes
  * When a request or root scope is defined, this is added to the current scope as additional scope
  * This means that this scope and all child scopes will have the request/root scope attached
* Technically, a scope can have x request/root scopes attached to it.
* When an event is captured, scope data is applied as follows:
```js
function applyScopeToEvent(event, scope) {
  // Global scope is always applied first
  const scopeData = getGlobalScope().getScopeData();

  // After that, all additional scopes are applied _in order_:
  for (const additionalScope of scope.getAdditionalScopes()) {
    merge(scopeData, additionalScope.getScopeData());
  }

  // Now the scope data itself is added
  merge(scopeData, scope.getScopeData());

  // Finally, this is merged with event data, where event data takes precedence!
  mergeIntoEvent(event, scopeData);
}
```

## Breadcrumbs

Adding breadcrumbs will have a new logic. Instead of adding to the current scope, breadcrumbs should be added like this:

```js
function addBreadcrumb(breadcrumb) {
  const requestScope = getRequestScope();
  const rootScope = getRootScope();
  // const currentScope = getScope(); <-- not used here
  const globalScope = getGlobalScope();

  const scope = requestScope || rootScope || globalScope;
  scope.addBreadcrumb(breadcrumb);
}
```

This way, breadcrumbs should be available consistently, no matter where in the scope hierarchy they've been added.

## What about frontend/non-request environments?

In frontend or other non-request environments, request scopes will simply never be set. 
This means that breadcrumbs go on the global scope by default, unless a user manually creates a root scope somewhere.

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

Currently, we keep the hub as a global and on the execution context. 
Instead, we should either keep scope & client there, or only the scope with a reference to the client.

# Drawbacks

* This changes _a lot_ of public APIs and behavior.

# Unresolved questions

* Do we _need_ to provide the custom root scope functionality? Or can we get away without it?
* Is there a better naming than "Root Scope" for this behavior/functionality?
* Should we remove Request Scope in favor of just using root scope?
