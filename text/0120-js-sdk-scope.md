- Start Date: 2023-11-06
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/120
- RFC Status: draft

# Summary

This RFC proposes changes on top of [RFC #122](https://github.com/getsentry/rfcs/pull/122). 
While that RFC proposes general changes to merge Hub & Scope, this RFC goes further and proposes a way to ensure we can get the correct breadcrumb & context data for any events, specifically in JavaScript but potentially also in other SDKs.

Things proposed in this RFC _do not_ have to be followed/implemented by all languages/SDKs, but any language/SDK may pick things from it that are relevant.

# Motivation

Especially when working with OpenTelemetry, the way how we currently always assign data to the current scope can break down in unexpected ways.

Because OpenTelemetry has to fork a context each time _anything_ is changed on it (copy-on-write), you end up with a lot of deeply nested scopes.

This leads to many scenarios where data is added to the "wrong" scope, from a users perspective:

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

We introduce a new global (or client) scope, as well as a request scope.

There will be new APIs for this:

* `getGlobalScope()`
* `getRequestScope()`

Plus an escape hatch for power users to make queues etc. easier to work with:

* `scope.captureBreadcrumbsHere()`

## Breadcrumbs

Breadcrumbs are a key case we want to solve with this RFC. This RFC proposes the following logic for adding/getting breadcrumbs:

* Each scope has a list of breadcrumbs
* When a breadcrumb is added, it is added based on the following logic:
  * Is there a "Breadcrumbs Scope" defined? If so, add it there.
  * Else, is there a "Request Scope" defined? if so, add it there.
  * Else, add it to the "Global Scope"

This means that e.g. in Browser JS SDK, all breadcrumbs will be global, while in request-based backend SDKs, they will be per-request.

In cases where you want to isolate breadcrumbs manually (e.g. a queue job), you can manually define a breadcrumbs scope.

## Global Scope

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

If not in a request, `getRequestScope()` will return `undefined`. While this means that users have to always check this return value, it will at least ensure that users capture incorrect cases - otherwise, they may be confused why their code is working but things are not actually added to the request events.

## Breadcrumbs Scope

If you need to manually isolate breadcrumbs, e.g. for a queue function, you can do this with the following new function:

```js
function myQueueJob() {
  Sentry.withScope((scope) => {
    scope.captureBreadcrumbsHere();
    // do something
  });
}
```

Note that breadcrumbs scopes are "invisible", we really just mark a scope with this. you cannot add other data to this scope. 
You can still add "queue spefific" data normally by just adding it to the initial scope.

Also note that implementation wise, `captureBreadcrumbsHere()` does _not_ mean that breadcrumbs should be put on this specific scope. 
The semantic meaning of this should be that breadcrumbs should be isolated to this scope and it's child scope - so any child scope should get these breadcrumbs as wel.

### How scopes are applied

When an event is prepared, scope data is applied as follows: 

```js
function applyScopeToEvent(event, scope) {
  // Global scope is always applied first
  const scopeData = getGlobalScope().getScopeData();

  const requestScope = scope.getRequestScope();

  // If it has a request scope, apply it next
  if (requestScope) {
    merge(scopeData, requestScope.getScopeData());
  }

  const breadcrumbsScope = scope.getBreadcrumbsScope();

  if (breadcrumbsScope) {
    mergeBreadcrumbs(scopeData, breadcrumbsScope.getBreadcrumbs());
  }

  // Now the scope data itself is added
  merge(scopeData, scope.getScopeData());

  // Finally, this is merged with event data, where event data takes precedence!
  mergeIntoEvent(event, scopeData);
}
```

## What about frontend/non-request environments?

In frontend or other non-request environments, request scopes will simply never be set. 
This means that breadcrumbs go on the global scope by default, unless a user manually creates a breadcrumb scope somewhere.


# Drawbacks

* TODO

# Unresolved questions

* Do we prefer `getGlobalScope()` or `getClientScope()`?
* What actual API should we use for the scope breadcrumbs? `scope.captureBreadcrumbsHere()` is just an initial draft...
