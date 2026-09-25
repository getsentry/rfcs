- Start Date: 2026-09-25
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/165
- RFC Status: draft
- RFC Author: @antonis
- RFC Approver: <TBD, Mobile/SDK TSC>

# Summary

Turn assertion violations (`invariant`, `assert`, `precondition`, `Debug.Assert`, `console.assert`, and similar) into grouped, non-fatal Sentry error events, instead of letting them be stripped from release builds or crash with unreadable minified messages.

The proposal has two parts:

* **Part A: convention and runtime API** for all SDKs. A uniform `mechanism.type = "assertion"`, a `mechanism.data` schema, grouping rules, PII rules, and a public `captureAssertionViolation()` API.
* **Part B: build-time instrumentation** for select SDKs. An opt-in build transform that rewrites assertion call sites so violations survive release stripping and carry the condition, runtime values, and a stack anchored at the site, with no app source changes.

A working React Native reference implementation (Metro/Babel) exists in getsentry/sentry-react-native#6592.

# Motivation

A React Native app crashes in a release build. The stack trace ends inside an `invariant` call with a minified error code and no message, so nobody can tell which invariant broke or with what values. The check the developer wrote to catch exactly this case ran, but its meaning was stripped.

Developers write assertions to encode invariants, then the toolchain deletes that intent before it reaches production, which is where it matters most:

* JS/RN: `invariant` and `console.assert` are dead-code-eliminated from release bundles.
* Android/Java: `assert` is disabled unless the JVM runs with `-ea`, so every `assert` is silent in production.
* Swift/Cocoa: `assert` and `assertionFailure` are removed under `-O`.
* .NET: `Debug.Assert` is removed in Release builds.
* Python: `assert` is stripped with `-O`.
* Dart/Flutter: `assert` is stripped in profile and release.

So a large class of correctness checks produces zero production signal. This feature recovers it as grouped non-fatal events carrying the failed condition, the values involved, and a precise stack.

# Supporting Data

Measured against React Native 0.87.1 and a sample app's dependency tree:

* The `react-native` framework ships ~186 `invariant()` call sites (179 in `Libraries/`) and 103 `__DEV__` guards. `@react-native/*` adds ~26 more invariants and 38 `console.assert()`.
* Across a full app dependency tree: 317 `invariant()` and 174 `console.assert()` call sites in 16 packages (excluding build-only tooling like metro and babel, which never ships to the device).

Two distinct signals fall out of this:

* **Resurrection.** `console.assert` and `__DEV__`-guarded checks are stripped entirely from release, so they produce zero production signal today.
* **Readability.** RN strips only the *message* from `invariant`, so an invariant that fires in release still crashes, but with a minified code and no context. This feature restores the condition and runtime values.

These are source call sites, not runtime firings; most never fire. The point is that the ones that do fire in production currently produce nothing useful.

# Decision

All violations are captured as **non-fatal (handled) error events** in the issues pipeline, not Logs. An assertion is a correctness violation ("this must never happen"), which is issue-grade signal that deserves grouping, regression detection, alerting, and assignment. Severity is expressed with `level`: hard preconditions use `error`, report-only assertions use `warning`.

# Design

## Part A: convention and runtime API (all SDKs)

Public API, with idiom-neutral naming:

```
captureAssertionViolation(condition, { pragma, message, values })
```

The concept and base name are shared across SDKs; each applies its own language casing (for example `capture_assertion_violation` in Python), the same convention as `captureException`.

Event shape:

* `mechanism.type = "assertion"`, uniform so the class is filterable regardless of idiom.
* `mechanism.data.pragma` records the specific idiom, so flavors stay separable.
* `mechanism.handled` is `false` for hard preconditions that abort, `true` for report-only. We set this ourselves and do not block on any pending mechanism-types work.
* Grouping key is pragma plus call site, so a noisy site collapses into one issue.

## Part B: build-time instrumentation (select SDKs)

An opt-in build transform rewrites assertion call sites to report before their original behavior (throw or no-op). Requirements:

* Off by default, enabled through the SDK's existing build integration.
* First-party code by default, dependencies via an explicit allowlist.
* Lazy evaluation of message and values, so no cost on the passing path and no side effects on the reporting path.
* Original semantics preserved: hard preconditions still abort after reporting, report-only stays report-only.
* Reports in release builds only by default, configurable. Dev builds already surface assertions loudly, so reporting there is opt-in.

## Which SDKs implement Part B

An SDK implements Part B only if both hold:

1. The ecosystem has an idiomatic assertion mechanism that is stripped or disabled in release.
2. The SDK already owns a build-instrumentation pathway, so marginal cost is low.

By this test the strong fits are RN (pilot, done), Android, Flutter, and .NET. Part A ships first and independently. See [Appendix A](#appendix-a-part-b-sdk-fit) for the per-SDK assessment.

# Open problems

* **Volume.** Since everything is an error event, this is the critical one. The SDK throttles per call site on the client: the first occurrence is always captured, repeats are rate-limited, so a hot-path assertion never serializes or sends thousands of events. Call-site grouping collapses what does send into one issue. Server-side quotas remain the backstop. We prefer throttling over random sampling so a rare but important violation is never dropped.
* **PII.** Capturing runtime values is high risk. Default: primitives inline only, object and array snapshots behind `sendDefaultPii`, plus a redaction hook. Inherits [RFC 0062](https://github.com/getsentry/rfcs/blob/main/text/0062-controlling-pii-and-credentials-in-sd-ks.md) and [RFC 0038](https://github.com/getsentry/rfcs/blob/main/text/0038-scrubbing-sensitive-data.md).
* **Performance.** Part B re-adds cost that stripping removed. Off by default, ideally release-configurable, zero cost on the passing path.

# Alternatives

* **Runtime API only (Part A, drop Part B).** Universal but loses the headline value (no source changes, survives stripping). Kept as the guaranteed floor.
* **Route report-only assertions to Logs.** Rejected: it discards the grouping, alerting, and regression tracking that make assertion signal useful, and doubles the per-SDK surface. Revisit only if volume controls prove insufficient.
* **Do nothing.** Stripped assertions stay dark in production.

# Unresolved questions

* Final `mechanism.data` schema and the exact value-capture type policy, pending security and PII review (see Open problems).

# Prior art

* [RFC 0062](https://github.com/getsentry/rfcs/blob/main/text/0062-controlling-pii-and-credentials-in-sd-ks.md), [RFC 0038](https://github.com/getsentry/rfcs/blob/main/text/0038-scrubbing-sensitive-data.md): PII and data scrubbing.
* [RFC 0148](https://github.com/getsentry/rfcs/blob/main/text/0148-logs-for-crashes.md): logs for crashes, which informed the events-vs-logs decision.

# Appendix A: Part B SDK fit

| SDK | Fit | Why |
|---|---|---|
| Android (Java/Kotlin) | Strongest | `assert` off without `-ea`; gradle plugin already does bytecode weaving |
| React Native | Strong | idioms stripped by DCE; Metro/Babel (reference impl) |
| Flutter/Dart | Strong | `assert` stripped in release; Dart build hooks |
| .NET / MAUI / Unity | Strong | `Debug.Assert` removed in Release; Roslyn/IL tooling |
| Cocoa/Swift | Medium | idiomatic but only Swift macros, opt-in not existing sites |
| Browser/Node JS | Medium | bundler DCE; Node `assert` already throws |
| Python | Low | `assert` stripped, but AST/import hooks are invasive |
| Go | N/A | no assert idiom |
