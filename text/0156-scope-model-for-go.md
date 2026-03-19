
- Start Date: 2026-03-19
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/156
- RFC Status: draft

## Summary

This RFC evaluates how `sentry-go` should model scope state so it can align with Sentry’s three-scope model while remaining idiomatic in Go. The document compares a mutable scope-in-`ctx` design with an immutable copy-on-write `context.Context` design and recommends the latter as the better long-term fit for Go concurrency, isolation, and OpenTelemetry alignment.

## Motivation

The upstream [scopes spec](https://develop.sentry.dev/sdk/foundations/state-management/scopes/) is designed around three scope types: a global scope, an isolation scope, and a current scope. 

The intent of the upstream scopes spec is:

- users should not need to think about isolation-scope forking
- integrations should fork isolation automatically
- current scope is for local span changes or `withScope` manual instrumentation changes
- the model should align with Open Telemetry’s immutable context propagation

The problem is that the three scope model, does not map directly to how Go handles async code isolation.

### Why Go is different

- No built-in thread-local or async-local state comparable to other SDKs.
- It already has an async propagation mechanism through `context.Context` .
- Concurrency is explicit and users can start goroutines freely. With the current upstream scopes spec there’s no runtime guarantees. The intent of the upstream scopes spec should be maintained in `users should not need to think about isolation-scope forking` and having an API that guarantees isolation.
- `context.Context` is immutable. The current sentry-go implementation used a mutable (`*Scope`). The mutable approach already created multiple problems in the current implementation of the SDK (every scope method is locked with mutexes).

In Go, `context.Context` is the standard library’s immutable request-scoped propagation mechanism. It is commonly used to carry cancellation, deadlines, tracing state, and other operation-local values across API boundaries. Deriving a new `context.Context` returns a new value without mutating the original.

The expected outcome of this RFC is to choose a scope propagation model that gives correct request isolation semantics, maps cleanly to Go’s concurrency model, and provides a clear integration contract for automatic isolation handling.

## Background

### Current architecture

Today the SDK is built around:

- a process-global ambient `Hub` via `CurrentHub()`
- a mutable `Scope` attached to the top layer of a `Hub`
- optional per-request or per-operation propagation by storing a cloned `Hub` in `context.Context`

 and the user facing API:

- `CurrentHub()` returns the process-global hub.
- `Hub.Clone()` clones the top scope and reuses the client.
- `SetHubOnContext(ctx, hub)` stores a `Hub` in a `context.Context`.
- `GetHubFromContext(ctx)` retrieves the `Hub` from a `context.Context`.
- `Scope` is mutable and protected by a mutex.
- `ConfigureScope` mutates the current hub's top scope in place.
- `WithScope` clones the current scope, pushes it temporarily onto the hub stack, then pops it after the callback.

### Consequences of the current design

- Request isolation is integration-driven. Middleware typically clones the current hub at request entry and store the clone in `context.Context`.
- `context.Context` currently carries a `Hub`, not a scope value.
- The `Hub` stored in `context.Context` owns a mutable top `Scope`.
- Two goroutines using the same `context.Context` can still mutate the same scope.
- Locks make concurrent access safer, but they do not provide semantic isolation.
- Tracing already uses `context.Context` independently for active span propagation, while `sentry-go` also mirrors span state onto the scope. This means the SDK currently has two partially overlapping [propagation systems](https://github.com/getsentry/sentry-go/blob/340c142cf974aaba7dcb6545101fe125a7d8ad7c/scope.go#L577).

### Background information for how `sentry-go` already works

The current `Hub`/`Scope` model of the SDK uses `context.Context` to store a mutable `*Hub`:

```go
ctx := context.Background()
ctx = sentry.SetHubOnContext(ctx, sentry.CurrentHub().Clone())
hub = sentry.GetHubFromContext(ctx) 
// goroutines with the same ctx can concurrently mutate the same Hub reference.
// the SDK partially solves this with locks.
```

The important note here is that `context.Context` itself is immutable, but the stored `Hub` and `Scope` are mutable.

## Options Considered

### Mapping the three scope types to `sentry-go`

Based on the three-scope model from the upstream scopes spec, the closest mapping for Go would be:

- global scope -> process-level singleton state, today effectively `CurrentHub()` when no request-local `ctx` is involved
- isolation scope -> request-local or task-local state stored on `context.Context` by integrations at request/task entry
- current scope -> span-local derived state, for example from `WithScope` or when starting a new span

In terms of the current SDK:

- global scope is closest to `CurrentHub()` used without `ctx`
- isolation scope is closest to `SetHubOnContext(ctx, sentry.CurrentHub().Clone())`
- current scope is closest to `WithScope(...)` / `PushScope()` on the active hub

In terms of the proposed scope-oriented API:

- global scope would remain process-global state outside request-local `ctx`
- isolation scope would be the main scope value carried by `ctx`
- current scope would be a derived fork of the scope in `ctx`

This mapping should drive API semantics explicitly:

- top-level setup without a request-local `ctx` should continue to operate on global scope
- integrations should create isolation scope at request/task entry
- span start and `WithScope`-style local overrides should derive current scope from the isolation scope already present on `ctx`

### Storing scope on `context.Context`

The API should store just the `Scope` on `context.Context`, deprecating the old `Hub` design like this:

```go
func SetScopeOnContext(ctx context.Context, scope Scope) context.Context {
	return context.WithValue(ctx, Key, scope)
}

func GetScopeFromContext(ctx context.Context) Scope {
	if scope, ok := ctx.Value(Key).(Scope); ok {
		return scope
	}
	return nil
}
```

but the major change with this proposal is to not store a mutable `*Scope` inside the `ctx`.

### Option 1: Mutable Scope, familiar Sentry design (This is the easiest migration path, but it preserves the core semantic problem: shared mutable scope state)

This option makes `ctx` the main scope carrier:

- active scope is fetched from `context.Context` .
- `ctx` stores a mutable `*Scope` .
- users need to continue using `scope.SetTag(...)` , `scope.SetAttributes(...)` .
- scope mutations still need locks.
- Capture APIs need `ctx` to be passed.

The way this option works is for integrations to have a request-local scope at request entry, where scope mutations happen (in a ”thread-local” way), and a derived `context.Context` carries that mutable scope there.

### API example:

```go
ctx := sentry.NewContext(context.Background()) 
sentry.ConfigureScope(ctx, func(scope *sentry.Scope) {
	scope.SetTag("release", "1.2.3")
	scope.SetUser(sentry.User{ID: "123"})
})

http.Handle("/hello", sentryhttp.New(sentryhttp.Options{}).HandleFunc(func(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	sentry.ConfigureScope(ctx, func(scope *sentry.Scope) {
		scope.SetTag("route", "/hello")
		scope.SetRequest(r)
	})

	sentry.WithScope(ctx, func(scope *sentry.Scope) {
		scope.SetLevel(sentry.LevelWarning)
		sentry.CaptureMessage(ctx, "hello warning")
	})
}))
```

This remains problematic even if integrations clone a scope at request entry. If two goroutines reuse the same `ctx`, they still share the same mutable `*Scope` and therefore the same logical isolation state.

### Pros

- Familiar mutable scope (sentry like).
- Smaller migration burden for users.
- Preserves scope mutation patterns.
- A mutable scope means less allocations.

### Cons

- `context.Context` still stores a pointer to a mutable state and we still have shared mutable state.
- Users still need to think about mutation when starting goroutines or when re-using contexts. There is a need to know to fork scope on concurrent environments.
- We need to keep locks (anti-pattern).
- hard to map to Open Telemetry.

### Option 2: Immutable Copy-on-Write Context API (Recommended Approach)

This option makes scope update return a new `context.Context` rather than mutating shared scope state in place.

- Scope data is treated as immutable from the API perspective.
- APIs such as `scope.SetAttributes(...)` would just manipulate `context.Context`.
- A mutation returns a new `ctx` effectively carrying a new scope.
- Copy-on-write replaces all lock-based mutations.
- Capture APIs need `ctx` to be passed.

### API example:

```go
// ctx should always be ovewritten on a SetX
ctx = sentry.SetTag(ctx, "key", "value")
ctx = sentry.SetAttributes(ctx, ...)
ctx = sentry.SetUser(ctx, user)
```

This fits existing Go APIs well. `otel`, `grpc/metadata`, and similar packages already use the `ctx = SetX(ctx, ...)` pattern, so while this is a migration for sentry-go, it is not a conceptual departure from normal Go `context` propagation.

### Pros

- Idiomatic Go (most popular go libraries work this way).
- Stronger isolation semantics.
- Easier to reason and user friendly.
- Removes scope level locking. Race conditions are impossible, simplifies SDK maintainance.
- Users don’t need to manage hidden mutable shared state.
- In general `context.Context` is meant to be immutable, so this option makes the most sense in the Go ecosystem. We simplify the `Scope` API for users.
- This aligns much more naturally with OTel’s immutable `context` model.
- Goroutine propagation becomes safe by default as long as the caller passes `ctx` and each goroutine receives an immutable scope snapshot instead of a shared mutable scope pointer.

### Cons

- Major change from current SDK architecture, both for us and the users.
- More cloning and allocations on write (instead of using a mutable scope). This is `semi-solved` with the vision of using only `SetAttributes`, users would only need one more scope allocation compared to the mutable scope proposal (option 1).
- We would need to be mindful on future APIs, since every logical mutation requires deriving a new `context.Context` value.

### Integration responsibilities under Option 2

To satisfy the upstream scopes spec requirement, integrations need to create an isolation scope automatically. 

Examples:

- `sentryhttp` should derive a new isolation scope at request entry before invoking the handler
- goroutine/task helper APIs should preserve the incoming `ctx` snapshot instead of reaching for ambient global state
- tracing helpers should derive current scope from the active isolation scope on `ctx`

Pseudo-shape:

```go
func middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := sentry.NewContext(r.Context()) // forks isolation scope
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
```

This is the Go equivalent of what other SDKs do at async/task boundaries. The important point is that the integration owns the isolation fork, not the user.

## Supporting Data

### Performance considerations

- Allocations
  - The `attribute` API currently copies slices/maps into arrays (stack allocated - since they’re fixed size). We cannot/shouldn’t keep mutable user data, so option 1 has more frequent allocations. However in the future where the SDK would use only the `attribute` API, the values would be copied once to the stack, and then further scope copies would point to the same underlying data on the stack. Allocation drawback would be alleviated.
- Lock contention
  - The main runtime cost is lock acquisition on every mutation that touches the scope state.
- Performance wise: lock contention vs allocations
    - lock impact is (probably?) worse on performance (pending benchmarks)
    - allocations can be alleviated while locks would always be there due to design
    - locks would always apply vs allocations (might?) become a problem if users are setting many attributes.
    - even with mutable scope we still allocate when every isolated code segment finishes.


### Recommendation

Option 2 would be my personal recommendation. It maps the upstream scopes spec to Go-like concepts (does not really feel `Sentry` like), but would simplify integration development, is more user friendly, remove locks, can be a performance improvement (pending benchmarks) and align with the Go environment and what users would expect (users won’t have to think when and where to use `WithScope`). Maintenance wise, a race-free solution makes the most sense and it’s really easy to argue about.

## Some more API considerations

### CaptureX

Whichever option we decide to go with, we need to migrate `CaptureX(error)`  to `CaptureX(ctx, error)` , since everything would be `context` related and we would need to strictly type the API. The main benefits would be: 

- Remove custom [workaround](https://github.com/getsentry/sentry-go/blob/340c142cf974aaba7dcb6545101fe125a7d8ad7c/scope.go#L577) since tracing/scopes are divergent currently
- Improve user experience with some integrations (eg. [sentry.EventHint](https://docs.sentry.io/platforms/go/tracing/instrumentation/opentelemetry/#linking-errors-to-transactions)).
- The `CaptureException(ctx, error)` already should to happen for the OTLP integration (see above sentry.EventHint bullet), to correctly link errors to traces.

Today we effectively maintain two propagation systems: `context.Context` for tracing and `Hub`/`Scope` for event state. Moving capture APIs to `ctx` lets OTel span state and Sentry scope state travel through the same propagation channel.

### General API deprecation

Whichever approach we go with we should make `ctx` mandatory on our APIs. We already mandate `ctx` usage for logs and metrics.

The main problem here is that Go doesn’t have function overloading. Many breaking changes on the public API. (we are still v0, but it might be a significant change for users)

### `WithScope` under Option 2

Under an immutable `ctx` model, `WithScope` does not need to disappear. It can become a small compatibility helper that derives current scope and passes the derived `ctx` into the callback.

For example:

```go
func WithScope(ctx context.Context, fn func(context.Context)) {
	fn(NewContext(ctx))
}
```

This preserves the intent of `WithScope` for local instrumentation while aligning it with immutable `context` propagation. That makes it a good migration shim even if we eventually deprecate it in favor of direct `ctx = sentry.SetX(ctx, ...)` usage.

## Unresolved questions

If an API receives a `context.Context` that does not carry a Sentry scope, should the SDK:

- no-op
- fallback to global scope
- create a fresh isolation scope

This matters because the upstream scopes spec expects captures to conceptually merge global, isolation and current scopes.
