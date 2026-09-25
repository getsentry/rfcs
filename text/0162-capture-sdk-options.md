- Start Date: 2026-09-21
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/162
- RFC Status: draft
- RFC Author: @mydea
- RFC Approver: 

# Summary

Today, we have no visibility into which options a given Sentry SDK instance was configured
with. This RFC proposes a mechanism for SDKs to report the configuration they were
initialized with (the arguments passed to `Sentry.init()`, plus relevant derived/effective
values) to Sentry, so that this information can be stored, surfaced, and acted upon.

Knowing the configured options unlocks a range of use cases — from self-healing and
debugging ("was this simply not enabled, or did the event never get sent?"), to product
analytics (which options are actually used, which matter most), to user-facing features
(showing all `Sentry.init()`s producing data into a project, auditing setups, and eventually
allowing configuration changes from the UI). We do not need to build all of these up front;
this RFC focuses on the capture and transport mechanism, with the downstream use cases
described as motivation and future work.

# Motivation

We currently cannot answer basic questions about how an SDK instance is configured. This
creates gaps in several areas:

- **Self-healing / support**: When data is missing or filtered, we cannot tell whether a
  feature was disabled, a sample rate dropped the event, or something failed. Knowing the
  configured options would let us distinguish "never enabled" from "enabled but filtered".
- **Analytics & product decisions**: We do not know which options are actually used in the
  wild. This data would inform what to highlight in docs, what to deprecate or remove in
  major versions, and where to invest.
- **Configuration-aware querying**: Configuration changes can affect trends over time (e.g.
  a change to filtering or sampling rules). Surfacing these changes would help explain shifts
  in data.
- **Setup audits & warnings**: We could audit `init()` setups to suggest improvements or warn
  users about potentially confusing behavior given their settings.
- **Discoverability of data sources**: Users could see all of the `Sentry.init()`s producing
  data into a project, understand the sources of their data, and see the filtering, sampling,
  and other configuration that affects it — including changes over time.

# Background

Today we do not capture the configuration of an SDK instance in any meaningful, first-class
way. There is no place in Sentry where you can look up "what options was this
`Sentry.init()` called with", and consequently none of the use cases in the Motivation are
possible today.

There are, however, a few adjacent things that already exist. They each capture a small
slice of related information, but none of them gives us the configured options, and none is
designed for that purpose:

- **SDK metadata on error/transaction events.** Events carry an `sdk` object (name, version,
  and lists of `integrations` and `packages`), and some settings leak into events
  indirectly. This tells us _which integrations are present_ and the SDK version, but not
  _how_ things were configured (sample rates, `beforeSend`, transport options, `debug`,
  `environment` defaults, `sendDefaultPii`, denyUrls/allowUrls, tracing options, and so on).
  It is also only present when an event is actually sent — so an instance that is configured
  but never produces an event (or whose events are all filtered) is invisible. This is the
  closest existing signal, but it is partial and event-coupled.

- **Client reports.** Client reports are sent as their own, separate envelope item
  (`client_report`), independent of any error or transaction event. Their _content_ is
  unrelated to configuration — they report aggregate counts of discarded events by `reason`
  and `category` (e.g. rate-limited, sample-rate, before-send). But they are a useful
  precedent for _how_ we might send configuration: they show that we already have a pattern
  for the SDK to emit a standalone, non-event payload on its own cadence (batched/periodic,
  flushed on shutdown). A "SDK configuration" report could plausibly follow a similar
  transport shape rather than being attached to individual events.

In short: what we have today is either a partial, event-coupled snapshot (SDK metadata) or a
transport precedent with unrelated content (client reports). Neither captures the configured
options, which is what this RFC is about.

<!-- Reference: Linear project
https://linear.app/getsentry/project/capture-sdk-options-js-08e8a89c71c9/overview -->

# Options Considered

Broadly, there are two ways to get configuration data from the SDK to Sentry. Both assume
the SDK can produce a serialized view of its options; they differ in _how that view is
transported and handled_.

## Option A (preferred): A dedicated envelope item for SDK options

Introduce a new, first-class envelope item type dedicated to SDK configuration. The SDK
serializes its options and sends them as a standalone payload, handled on its own path
server-side rather than being coupled to error/transaction events.

This is the preferred option because it decouples "what is this instance configured with"
from "did this instance send an event". It gives us a clean, purpose-built payload we can
version, store, and reason about independently, and it is not dependent on an error ever
being produced. It also follows the transport precedent set by client reports (a separate,
non-event envelope item on its own cadence; see Background).

With this option, the design work is mostly about two questions, which we will dive into in
more detail:

- **a) The shape of the envelope** — what exactly we put into the payload: which options we
  capture, how we represent non-serializable options (functions like `beforeSend`,
  integration instances), how we normalize/redact sensitive values, and how we keep the
  schema consistent and generalizable across SDKs (this starts with JS).
- **b) How/when to send it, and how/when to store it** — the send cadence (once per init, on
  change, periodically, flushed on shutdown), and the server-side handling: where it lands,
  how we group instances, how we deduplicate identical configs, and how we track changes over
  time.

## Option B: Expand error events to carry SDK options

Alternatively, we could piggyback on error (and transaction) events — for example by
expanding the existing `sdk` key on the event to carry the full configured options, and then
doing the work server-side to infer, group, and store this out of the event stream.

This avoids a new envelope type and reuses an existing, well-understood transport. However,
it inherits the drawbacks of being event-coupled: configuration is only observed when (and
as often as) events are sent, an instance that never produces an event is invisible,
identical config is re-sent on every event (wasteful, needs server-side dedup), and we
overload the event schema and pipeline with data that is not really about the event. The
server-side grouping/storage problem also becomes harder because the signal is buried inside
the high-volume event stream.

For these reasons Option A is preferred; the remaining sections focus on the questions it
raises.

# Envelope Shape

This section proposes the shape of the dedicated SDK-options payload (question **a** above).
The goal is a **language-agnostic** shape that works equally for JavaScript, Python, and every other SDK, so the server can handle a single, consistent schema.

## Envelope item type

We propose naming the new envelope item type **`sdk_config`**, following the existing
snake_case convention for item types (`event`, `transaction`, `client_report`, `session`, …).
`sdk_config` reads well because the payload is broader than just the raw `init()` options — it
also carries SDK identity, integration status, and general metadata.

Alternatives considered: `sdk_options` (closest to the literal `init()` arguments, but narrower
than what the payload actually contains) and `client_config` (risks confusion with Sentry
"client reports" and with the SDK's internal `Client`). We recommend `sdk_config`.

**Backward compatibility with older ingest / self-hosted.** Introducing a new envelope item type
is safe for older infrastructure. Envelopes are designed so that unknown item types are simply
**ignored**: an older Relay / self-hosted Sentry that predates `sdk_config` will not recognize the
item and will **discard it**, while still processing the other items in the same envelope (errors,
transactions, etc.) as usual. That is the desired behavior here — SDKs can start emitting
`sdk_config` unconditionally, and setups that cannot yet handle it lose only this
new-and-supplementary payload, with no impact on existing data. No SDK-side version gating is
required.

## Design principles

- **Primitives only.** The payload contains only JSON-serializable values: strings, numbers,
  booleans, `null`, arrays, and plain objects. No runtime constructs (functions, class
  instances, streams, etc.) ever appear literally.
- **Callbacks and other runtime values are reduced to markers.** We do not care about a
  callback's implementation, only that _a user-defined callback was set_. Any non-serializable
  value is normalized to a sentinel, following the exact rules in
  [Options serialization rules](#options-serialization-rules) below (functions → `"[Function]"`,
  integrations → their name, other runtime constructs → a type marker).
- **Effective config, natively named but flat.** The `options` block carries the SDK's final,
  effective options (after defaults and derivation), keyed by native option names. Nested objects
  are **flattened with dot notation** (e.g. `dataCollection.http.bodies`) rather than kept as nested
  objects, so the structure stays flat and uniform (see the serialization rules). Which of those
  keys the user explicitly set is recorded separately in `options_set_by_user`.
- **Generic representation of integration options.** Integrations are user-configurable
  (`Sentry.myIntegration({ filter: 'aaa' })`), so we must capture their options generically —
  keyed by integration name, with their options normalized by the same rules. We do not need
  to understand any specific integration's options; we just record them.
- **Room for well-known metadata and for open-ended data.** Alongside the raw options there is
  space for well-known, structured metadata (SDK identity, release/environment, etc.) and a
  free-form bucket SDKs can use for anything not yet modeled.

## Options serialization rules

When serializing the `options` block (and each integration's `options`), SDKs apply the following
rules, top to bottom, to every value. The goal is a deterministic, primitives-only representation
that is consistent across SDKs.

- **Primitives pass through.** Strings, numbers, booleans, and `null` are emitted as-is. Arrays are
  emitted as arrays, with each element serialized by these same rules.
- **Nested objects are flattened with dot notation.** We deliberately keep the structure **flat**:
  a nested option object is not emitted as a nested object but as dotted keys joining the path, e.g.
  `dataCollection: { http: { bodies: true } }` becomes `"dataCollection.http.bodies": true`. The
  same applies inside each integration's `options`. This gives a single, flat, uniform key space
  that is easy to store, query, and normalize; the leaf values are serialized by the other rules
  here. (Arrays are not flattened — they are kept as arrays.)
- **Functions become `"[Function]"`.** Any callback (`beforeSend`, `tracesSampler`,
  `beforeBreadcrumb`, transport factories, etc.) is replaced by the literal string `"[Function]"`.
  SDKs MAY include the function name when readily available (`"[Function: beforeSend]"`), but the
  bare `"[Function]"` marker is the required baseline — consumers must not depend on the name.
- **Integrations are replaced by their name.** In the `options.integrations` list, each configured
  integration is serialized to its **integration name string** (e.g. `MyIntegration` →
  `"MyIntegration"`), never the integration instance/object. The integration's _own_ configured
  options are captured separately, keyed by that same name, in the top-level `integrations` block.
  So `Sentry.init({ integrations: [Sentry.myIntegration({ filter: 'aaa' })] })` yields
  `"integrations": ["MyIntegration"]` in `options` and, in the `integrations` block,
  `"MyIntegration": { "options": { "filter": "aaa" } }`.
- **Other runtime constructs become a type marker.** Any remaining non-serializable value (a class
  instance, stream, socket, etc.) is replaced by a bracketed type marker, e.g. `"[SomeType]"`,
  reusing each SDK's existing normalization convention (e.g. JS `normalize()`).

These rules are what "normalized" means throughout this document. Scrubbing sensitive values is a
**separate, primarily server-side concern** (see `options`) — SDKs **MAY** scrub values they know
to be sensitive, but they do not attempt to guarantee fully-scrubbed data.

## Proposed shape

The shape below is the **stored** payload. SDKs send everything here **except**
`normalized_options`, which Relay derives at ingestion time from `options` (see
[Normalization at ingestion](#normalization-at-ingestion)).

```json
{
  "timestamp": "2026-09-21T12:00:00Z",

  "sdk": {
    "name": "sentry.javascript.node",
    "version": "10.0.0",
    "packages": [{ "name": "npm:@sentry/node", "version": "10.0.0" }]
  },

  "meta": {
    "release": "my-app@1.2.3",
    "environment": "production",
    "dist": "42",
    "runtime": { "name": "node", "version": "20.11.0" }
  },

  "options": {
    "dsn": "https://<public-key>@o0.ingest.sentry.io/0",
    "sampleRate": 1.0,
    "tracesSampleRate": 0.2,
    "sendDefaultPii": true,
    "debug": false,
    "environment": "production",
    "beforeSend": "[Function]",
    "tracesSampler": "[Function]",
    "denyUrls": ["https://example.com/ignore"],
    "dataCollection.http.bodies": true,
    "dataCollection.http.headers": false,
    "integrations": ["InboundFilters", "MyIntegration"]
  },

  "options_set_by_user": [
    "dsn",
    "tracesSampleRate",
    "sendDefaultPii",
    "beforeSend",
    "tracesSampler",
    "denyUrls"
  ],

  "options_hash": "9f2c1a7e",

  "normalized_options": {
    "sample_rate": { "key": "sampleRate", "value": 1.0 },
    "traces_sample_rate": { "key": "tracesSampleRate", "value": 0.2 },
    "send_default_pii": { "key": "sendDefaultPii", "value": true },
    "debug": { "key": "debug", "value": false },
    "before_send": { "key": "beforeSend", "value": "[Function]" }
  },

  "integrations": {
    "InboundFilters": { "options": {} },
    "ExpressIntegration": { "applied": true, "options": {} },
    "FastifyIntegration": { "applied": false, "options": {} },
    "KoaIntegration": { "options": {} },
    "MyIntegration": {
      "options": { "filter": "aaa", "shouldLog": "[Function]" }
    }
  },

  "_other": {}
}
```

## Fields

- **`timestamp`** — when the payload was generated/sent by the SDK. We need to know when a
  configuration was reported, both to order records and to track configuration changes over
  time (e.g. "you changed your filtering rules in May"). Format follows the existing Sentry
  convention (ISO 8601 shown here; could equally be epoch seconds to match event `timestamp`).
- **`sdk`** — SDK identity metadata: `name`, `version`, and `packages`. This is the same
  information SDKs attach to error/transaction events today; **this RFC proposes moving it
  here** so it lives in one canonical place. (The set of integrations, previously part of the
  event's `sdk` object as a list of names, is captured more richly in the top-level
  `integrations` block below.)
- **`integrations`** — a map keyed by integration name, where each entry holds everything we know
  about that integration in one place: its runtime status and its configured options. This
  consolidates what would otherwise be two parallel name-keyed maps. Per entry:
  - The **presence of the key** means the integration is registered/enabled.
  - An optional, opt-in **`applied`** boolean records whether the integration determined at runtime
    that it actually took effect (see "Reflecting which integrations are actually used").
  - **`options`** is the integration's own normalized options, nested under this key so arbitrary
    user options can never collide with well-known status keys like `applied`. Integrations with no
    options report `"options": {}`. This is how we generically capture things like
    `MyIntegration({ filter: 'aaa' })` without understanding any specific integration.
- **`meta`** — well-known, general metadata that we want first-class regardless of how it was
  set: `release`, `environment`, `dist`, and runtime/platform information (e.g. runtime name
  and version). These describe the instance producing data, complementing the raw `options`.
- **`options`** — a normalized snapshot of the SDK's **final, effective** configuration (i.e. the
  options object the SDK actually runs with, after defaults, env-var resolution, and any
  derived/integration-injected values), keyed by native names and flattened with dot notation, with
  all values reduced to primitives per the rules above. Sending the effective config — rather than only the literal
  `init()` arguments — is what lets us answer behavior questions ("what sample rate is actually in
  effect", "is it enabled"); it also reads directly off the SDK's existing options object with no
  extra plumbing, and reflects the settled state at send time (see the debounce in Sending). The
  `integrations` option is represented here as a list of names; each integration's identity,
  runtime status, and configured options live in the dedicated top-level `integrations` block, to
  avoid duplicating (and bloating) the raw options. Sensitive data
  (especially tokens and other secrets) is **primarily scrubbed server-side**; SDKs **MAY**
  additionally scrub values they know to be sensitive (e.g. a field that always holds a secret),
  but this is a best-effort defense-in-depth measure — SDKs do **not** attempt to guarantee
  fully-scrubbed data, and the server-side scrubbing remains the mechanism we rely on.
- **`options_set_by_user`** — a flat array of the **native option keys the user explicitly set**
  in `init()` (as opposed to values that came from defaults, env vars, or integrations). This is
  the signal that lets us distinguish default values from user-set values 
  — essential for adoption analytics and setup audits, where a default value is not
  "usage". This is effectively similar to `Object.keys(options)` where `options` are the user-provided options for `Sentry.init(options)`.
   Keys here use the **same flattened dot-notation as `options`**, so a user-set nested value is
  listed by its dotted leaf key (e.g. `dataCollection.http.bodies`) and always corresponds 1:1 to a
  key present in `options`.
- **`options_hash`** (optional) — an SDK-computed hash of the options that is **stable across
  instances sharing the same configuration** (same config → same hash). It is the optional
  component of the dedup key: when present, the server folds it in so genuinely different configs
  within the same `release`+`environment`+`dist` are stored as distinct records; when absent, dedup
  falls back to the composite key alone. If an SDK sets it, the **same value must also be stamped on
  every event** (attribute on spans/logs, context field on errors/transactions) so events correlate
  exactly to their config. See [Storing](#storing) for the full rules and caveats. It is computed
  off the normalized `options` block (the serialized options as defined in the serialization rules),
  which makes it deterministic and stable across instances; it need not be comparable across SDKs.
- **`normalized_options`** — a **Relay-derived** subset of `options`, keyed by canonical
  cross-SDK names, produced at ingestion (see below). SDKs never send this block. Each entry maps
  a canonical key to `{ "key": <native option name>, "value": <normalized value> }`, so consumers
  can compare the same option across SDKs while still seeing what it was called natively. Whether
  the user set it is answered the same way as for any other option — via `options_set_by_user`.
- **`_other`** — a free-form, SDK-defined bucket for anything not covered by the well-known
  fields above. The leading underscore signals that this is arbitrary, unstructured data.
  Keeps the schema forward-compatible: SDKs can record additional data without a schema change,
  and useful keys can later be promoted to first-class fields.

## Why effective options plus a flat set-by-user array

We deliberately split configuration into two SDK-sent pieces — the full **effective `options`**
and a flat **`options_set_by_user`** array — rather than, say, shipping both a user-provided and an
effective options tree, or wrapping every option value in a `{ value, source }` object. The
benefits:

- **Easy to implement in SDKs.** `options` is essentially the SDK's existing effective options
  object, serialized — most SDKs can read it straight from an existing API (e.g. JS
  `client.getOptions()`, or the equivalent effective-options accessor in other SDKs), so there is
  no second config snapshot to capture or keep around. `options_set_by_user` is produced by a
  single diff of the raw `init()` argument's keys against that object. No per-option plumbing, no
  wrapper types, no bookkeeping threaded through the option system.
- **Easy to reason about.** `options` means exactly one thing — the configuration the SDK actually
  runs with — and `options_set_by_user` means exactly one thing — which of those the user chose.
  There is no ambiguity about whether a given block is "before" or "after" defaults, and no mixed
  value/metadata shape to interpret. What each field represents is obvious from its name.
- **Can be joined as needed.** Keeping provenance as a separate flat set means any consumer can
  answer "was this user-set?" for _any_ option with a simple membership check, and can just as
  easily ignore provenance entirely when it does not care. The two pieces compose on demand
  (including for `normalized_options`, which joins against the same array) instead of being
  pre-fused into one heavier structure that every consumer pays for whether or not they need it.

The trade-off is that provenance is not co-located with each value (you look it up rather than
reading it inline), and the array is top-level-only. Both are acceptable given how much simpler
this keeps the SDK side and the schema.

### Known limitation: user-provided _form_ is not preserved

Because we send the **effective** options, we lose information when the user expressed a value in a
form that the SDK coerces into something else before it lands on the effective options. The value
we report is the coerced result, and `options_set_by_user` only tells us the option _was_ set — not
_how_ it was written. Concretely: a user can pass `integrations` as either an array or a
**function** (`(defaults) => Integration[]`), but the client always ends up holding a resolved
array — so we cannot tell, from the payload, whether the user configured integrations via a
function. We therefore cannot answer questions like "how many users pass `integrations` as a
function".

We accept this limitation for now:

- **It is rare.** In the JS SDK, the option type system pins genuine user-vs-effective _shape_
  divergence to essentially two options: `integrations` (array-or-function → array) and
  `stackParser` (array-or-function → function). Everything else keeps the same shape; only defaults
  or env values get filled in, which the effective `options` already captures faithfully.
- **`integrations` is the main case that matters**, and even there the question ("was it a
  function?") is a nice-to-have, not core to the primary use cases.

If we later decide this signal is worth capturing, we can layer it on **without reworking the
shape** — e.g. an optional, sparse `options_user_provided` block that records the user-provided
(serialized) value _only_ for the few keys whose provided form differs from the effective one (so
it would carry `{ "integrations": "[Function]" }` and otherwise be empty). We deliberately leave
that out of the initial design and revisit it only if a concrete need arises.

## Reflecting which integrations are actually used

Knowing which integrations are _registered_ is not the same as knowing which are actually
_doing anything_. In the Node SDK, for example, a large set of integrations is added by
default (`ExpressIntegration`, `FastifyIntegration`, `KoaIntegration`, …), but a given app
typically uses only one of them. For analytics and audits we care about the difference
between "this integration is present because it ships by default" and "this integration is
actually instrumenting this app".

This is captured generically, without enumerating any specific integration, via the `applied` key
on each entry of the top-level `integrations` map:

- The **presence of a key** means the integration is registered/enabled.
- An optional **`applied`** boolean means the integration determined at runtime whether it
  actually took effect. `ExpressIntegration` sets `applied: true` once it successfully patches
  Express; a defaulted integration whose target framework is absent can report
  `applied: false`. An integration that reports nothing simply omits `applied` (absent / unknown).

Key properties of this design:

- **Generic.** No integration-specific fields in the schema; any integration can contribute
  the well-known `applied` signal (and we can add further opt-in status keys later).
- **Opt-in and non-exhaustive.** Integrations are not required to report status. We selectively
  push this into the integrations where the signal is valuable to us (e.g. the framework
  integrations), and leave the rest unreported.
- **Namespaced from options.** `applied` (and any future status key) sits at the top of the entry,
  while the integration's own configured options are nested under the entry's `options` key, so
  the two never collide.

Note there is a timing implication: `applied` is often only known slightly after `init()` (once
instrumentation runs), which influences _when_ the payload is sent or updated. This is
discussed in the send/store section.

## Cross-SDK naming

Option keys differ across SDKs (JS `tracesSampleRate` vs. Python `traces_sample_rate`). To
compare the same option across languages we want a canonical cross-SDK vocabulary (in the spirit
of [0116-sentry-semantic-conventions](./0116-sentry-semantic-conventions.md)), but we do **not**
want every SDK to own that mapping and keep it in sync.

**Recommendation: SDKs send native names; Relay normalizes a defined subset.** The `options`
block keeps each SDK's **native option names as-is** — SDKs report options exactly as they are
named in that SDK, with no normalization to a shared vocabulary. This keeps the SDK side dumb and
maintenance-free: there is nothing to map, nothing to keep in sync, and new options are captured
automatically. The canonical mapping lives **server-side in Relay**, which reads a fixed set of
well-known options out of `options` and emits them into `normalized_options` under canonical keys
(see below).

This gets us the best of both: full, native fidelity in `options`, plus a normalized,
cross-SDK-comparable view in `normalized_options` — without pushing catalog upkeep into every SDK.

**Why Relay, not the SDK.** Doing the normalization server-side is a deliberate choice, for
several reinforcing reasons:

- **Simpler SDKs.** Each SDK only has to serialize and send its own native options (something it
  effectively already has). It does not need to know the canonical vocabulary, map its keys onto
  it, or reason about equivalence across languages — that logic never ships in the SDK at all.
- **Nothing to keep aligned across SDKs.** A canonical mapping owned by the SDKs would have to be
  implemented, and kept consistent, in _every_ SDK and language independently. Any drift (a
  mismatched canonical key, a missed option, an inconsistent value normalization) would silently
  corrupt cross-SDK comparisons. Centralizing removes that entire class of cross-SDK
  synchronization problem.
- **One place to implement and maintain.** The normalization logic and the knowledge of which
  canonical keys exist live in a **single system (Relay)** rather than being duplicated across N
  SDKs. There is one implementation to write, test, review, and reason about — not one per SDK.
- **Changeable over time without SDK releases.** What we choose to normalize will evolve. Because
  the catalog lives in Relay, we can add, rename, or refine normalized keys — and re-normalize
  already-ingested `options` — as a Relay change alone, with **no SDK update, release, or user
  upgrade** required. If normalization lived in the SDKs, every change would mean shipping every
  SDK and waiting for the ecosystem to upgrade, so the normalized dataset would always lag.

## Normalization at ingestion

`normalized_options` is produced by **Relay at ingestion time**, never sent by the SDK. For each
option in the normalization catalog, Relay looks it up in the incoming `options` (by the native
key registered for that SDK) and, if present, emits an entry:

```json
"normalized_options": {
  "traces_sample_rate": { "key": "tracesSampleRate", "value": 0.5 }
}
```

- The **outer key** is the canonical, cross-SDK name (snake_case).
- **`key`** is the native option name it was normalized from, so the original naming is not lost.
- **`value`** is the value of this option (the effective value from `options`).

Provenance is intentionally not repeated here: to check whether a normalized option was user-set,
look up its native `key` in `options_set_by_user`, exactly as you would for any raw option.

Only options in the catalog are normalized; everything else remains available under `options`.
Because the mapping is Relay-side (see [Why Relay, not the SDK](#cross-sdk-naming)), the catalog
can be extended without an SDK release, and already-stored raw `options` can be re-normalized.

### Which options we normalize

We start with a small, curated set of high-value options that are meaningful across SDKs. The
canonical key is the same across languages; only the native `key` differs.

| Canonical key          | Meaning                          | Native examples (JS → Python)             |
| ---------------------- | -------------------------------- | ----------------------------------------- |
| `sample_rate`          | Error sample rate                | `sampleRate` → `sample_rate`              |
| `traces_sample_rate`   | Tracing sample rate              | `tracesSampleRate` → `traces_sample_rate` |
| `profiles_sample_rate` | Profiling sample rate            | `profilesSampleRate` → `profiles_sample_rate` |
| `send_default_pii`     | Whether default PII is sent      | `sendDefaultPii` → `send_default_pii`     |
| `debug`                | Debug logging enabled            | `debug` → `debug`                         |
| `enabled`              | Whether the SDK is enabled       | `enabled` → `enabled`                     |
| `before_send`          | Whether a `before_send` hook is set (marker) | `beforeSend` → `before_send`  |
| `before_send_transaction` | Whether a `before_send_transaction` hook is set (marker) | `beforeSendTransaction` → `before_send_transaction` |
| `before_send_span`     | Whether a `before_send_span` hook is set (marker) | `beforeSendSpan` → `before_send_span` |
| `ignore_spans`         | Span-ignore rules                | `ignoreSpans` → `ignore_spans`            |
| `traces_sampler`       | Whether a `traces_sampler` hook is set (marker) | `tracesSampler` → `traces_sampler` |
| `data_collection.*`    | Data-collection settings (all flattened sub-keys) | `dataCollection.*` → `data_collection.*` |

A trailing `.*` (e.g. `data_collection.*`) denotes a **family of flattened sub-keys**: every dotted
key under that path (`dataCollection.http.bodies`, `dataCollection.http.headers`, …) is normalized,
each becoming its own `normalized_options` entry under the canonical dotted key.

`release`, `environment`, and `dist` are deliberately **not** in this catalog — they are already
promoted to first-class fields under `meta`. The catalog is intended to grow over time; the list
above is the initial, deliberately-conservative set, and the exact registry (canonical key ↔
per-SDK native key) is maintained alongside Relay.

# Sending and Storing

This section covers question **b**: when the SDK emits the options payload, and how it is
handled server-side. When to send is **not one-size-fits-all** — it differs meaningfully
between SDK types. Broadly we distinguish **server SDKs** (Node, Python, Java, Go, …) from
**client SDKs** (browser, mobile, desktop, gaming, …), which have very different lifecycles.
We start with the server case; the client case is trickier and is covered next.

## Sending — Server SDKs

For server SDKs, the payload is sent **once, shortly after `init()`**, but only once the
configuration has **settled**. The hard requirement is only this:

- **Send the final, settled options — not a half-initialized snapshot.** Some values are not
  known at the exact moment `init()` returns — for example an integration's runtime `applied`
  status (see "Reflecting which integrations are actually used"), lazily-registered integrations,
  or release/environment detected asynchronously. The SDK must wait until it can reasonably expect
  these to have settled before capturing and sending the payload.
- **One payload per init.** The goal is a single, stable payload per SDK instance/init, not a
  stream of updates. If the config meaningfully changes later, that is handled as a separate
  concern (and mostly matters for long-lived processes); the common case is one send per
  process start.

**How to wait is up to each SDK.** We deliberately do not mandate a single mechanism — each SDK
**MAY** use whatever hook or mechanism fits its runtime and lifecycle, as long as it reasonably
captures the final options. A few examples:

- **A short debounce delay** (a reasonable default, e.g. on the order of **2 seconds**): schedule
  the send a short time after `init()` rather than synchronously, letting the settling period
  collapse into one payload. The delay **MAY be configurable** so setups that settle slower (e.g.
  an SDK that only detects framework instrumentation after the first request) can tune it.
- **A lifecycle hook** the SDK already has — e.g. sending after the first request/transaction is
  processed, on an "SDK ready"/post-init hook, or when the event loop first goes idle.
- **Any equivalent trigger** that reliably fires after the config the SDK cares about is known.

Debouncing is the simplest baseline and a fine default, but it is an example, not a rule: an SDK
with a natural hook that guarantees settled options should prefer that. What matters is the
outcome — the payload reflects the effective configuration.

**Short-lived processes.** Some server environments (serverless functions, short CLI
invocations) may exit before the debounce timer fires. In those cases the SDK should flush the
pending options payload on shutdown / at the same points it already flushes events, so the
config is not lost. SDKs MAY use the same or a similar approach as to how they flush client
reports, if applicable. If the process dies before the first flush opportunity, the payload is
simply not sent for that invocation — acceptable given these instances are typically
numerous and short, and an equivalent instance will report.

## Sending — Client SDKs (browser, mobile, gaming)

Client SDKs are trickier. Unlike a server process — where one long-lived instance can send a
single payload that represents a whole fleet's worth of traffic — client instances are
**numerous and short-lived**: every page load, app launch, or game session is its own `init()`.
Sending the options payload naively from each one would be dramatically more data than the
server case. Because of that, the _when_ needs more thought. We propose exploring the following
options.

### Option I: Send on every init (with debounce)

Do exactly what server SDKs do: send once per `init()`, guarded by the same short debounce.

- **Benefits:** Easy and simple to implement and reason about. Identical mental model and code
  path to the server case; no sampling logic, no extra configuration. Every instance is
  represented.
- **Disadvantages:** Much higher overhead. Sentry has to ingest _much_ more data (one payload
  per page load / app launch / session, at client-traffic volumes), and it adds a request for
  users on every init.

### Option II: Sampling

Send the payload only for a random fraction of inits (e.g. **1%**, potentially configurable).
The intuition is that configuration is essentially **constant per release** — every instance of
the same release reports roughly the same options — so we do not need it from every init; a
small sample is enough to reconstruct the config for a release.

- **Benefits:** Much less overhead on both sides, while still capturing the configuration for
  each release given enough traffic.
- **Disadvantages:** Sampling is random, so it works better or worse depending on traffic
  volume — a high-traffic release is well covered, a low-traffic one (or a rarely-hit
  configuration) may be under-sampled or missed entirely. It also adds configuration surface and
  is harder to reason about and test than a deterministic approach.

### Serverless

Although serverless functions run "server" SDKs, they share the key constraints of client
SDKs: instances are **numerous and short-lived**, with an `init()` per invocation rather than
one long-lived process. We therefore expect similar trade-offs to apply, and the same
solutions explored here for client SDKs (e.g. sampling) **COULD** be applied to serverless
environments as well, rather than the plain debounced send-on-every-init used for long-lived
server processes.

## Storing

Once payloads arrive, we have to decide how much of this data we actually keep. Broadly there
are two options.

### Option 1: Store every record

Persist every payload we receive as its own record.

- **Benefits:** Complete history; nothing is lost, and we could in principle see every
  individual instance's config over time.
- **Disadvantages:** Very high storage cost and volume, especially for client/serverless traffic
  where near-identical payloads arrive constantly. The vast majority of records are duplicates
  that add no information.

### Option 2 (recommended): Deduplicate and store one record per configuration

Store one record per distinct configuration and discard the rest. The vast majority of incoming
payloads are duplicates, so dedup is what keeps this feature affordable. The question is what counts
as a "distinct configuration" — i.e. what we deduplicate by. We propose a **single dedup key with an
optional component**:

> **`release` + `environment` + `dist` + (optional) SDK-set options hash.**

#### The composite natural key (`release` + `environment` + `dist`)

This is the always-available baseline. Release alone is **not** sufficient — configuration can
legitimately differ across environments and builds within the same release (per-environment
options, per-deployment overrides, env-var-driven values) — so the minimum key is
`release` + `environment` + `dist`.

- It is **bounded and predictable** (roughly one record per tuple), **human-readable and directly
  queryable** ("show the config for release X in production"), **cheap** (a few stable top-level
  fields, no whole-payload processing), and every event already carries these fields.
- Its weakness is `release`: `environment` effectively always has a value (it defaults to
  `production`), `dist` is normally absent, so `release` is the load-bearing part — and it has **no
  default** and is frequently unset. When it is, the key degrades to roughly `environment` alone
  (almost always `production`), collapsing distinct configs into one bucket. It is also blind to
  differences _within_ a tuple: two instances sharing release+environment+dist but differing in some
  option are stored as one (first-seen) record, so genuine variation is silently lost.

The optional hash exists to address exactly that last weakness.

#### The optional SDK-set options hash

SDKs **MAY** additionally set the `options_hash` field on the `sdk_config` payload — a **hash of
their options that is stable across instances sharing the same configuration** (same config → same
hash; the hash changes when the config changes). When a payload carries this hash, **the server
includes it in the dedup key**; when it is absent, dedup falls back to the composite key alone.

Including the hash means two instances with the same release+environment+dist but genuinely
different options (different hash) are stored as **distinct records** — so within-release variation
and drift become visible instead of being collapsed into the first-seen config.

- **The hash is computed off the normalized `options`** — the serialized options block as defined
  in the [serialization rules](#options-serialization-rules) — which makes it deterministic and
  stable: it is **identical across instances that share a configuration** and **differs when the
  configuration differs**. It does not need to be comparable _across_ SDKs, so the specific hash
  algorithm is up to each SDK.
- **The hash is computed SDK-side, by design.** Otherwise, we cannot reliable relate events to their respective config.
- **If a hash is used, it MUST also be attached to every event the SDK produces**, so events can be
  correlated back to the exact config that produced them:
  - as an **attribute** on spans, logs, and other attribute-carrying items. We propose `sentry.config_hash` as a semantic attribute.
  - as a **context field** on error and transaction events. We propose `sdk_config.hash` as a new context with a single field for now.

#### Correlating an event to its config

This falls directly out of the dedup key:

- **Without a hash:** correlate via the composite key the event already carries
  (`release` + `environment` + `dist`). This is free and needs no event changes, but is only
  **bucket-level** — if config varied within the tuple, the event resolves to the bucket (a single
  first-seen record, or the set of stored variants), not necessarily the exact config that produced
  it.
- **With a hash:** correlation is **exact** — the event's stamped hash matches exactly one stored
  `sdk_config` record. This is the whole reason the hash must also live on events.

#### Trade-offs and caveats of the hash

- **Per-event overhead.** Stamping the hash adds a field to every event, at full event volume.
- **Timing.** The config is not fully settled the instant `init()` returns (debounce window,
  `applied` known late). The SDK must ensure the hash it stamps on events matches the config it
  reports — e.g. by hashing only config that is stable from `init()`, or by not stamping until the
  config has settled. Events emitted before that point may carry no hash (falling back to
  bucket-level correlation).
- **Sampling gaps.** For client/serverless SDKs we _may_ sample `sdk_config` (see Sending), so an
  event's hash can reference a config that was **never stored** — correlation then fails for exactly
  the instances we chose not to persist.

# Open Questions

- **What does standing up a new envelope item type actually require?** Introducing `sdk_config`
  is not just an SDK + storage change; it needs first-class handling in the ingest pipeline, and
  we need to enumerate what that entails before committing. At least:
  - **Relay / ingest support.** Registering the new item type, routing it to its own handler,
    and any validation/normalization (the `normalized_options` derivation lands here).
  - **Rate limiting.** Does `sdk_config` need its own rate-limit category, or does it share an
    existing one? How does rate limiting interact with the send cadence (debounced server sends,
    client sampling)? What is communicated back to the SDK (e.g. `429` / `Retry-After`) and how
    does the SDK back off?
  - **Payload / size limits.** What per-item and per-envelope size limits apply, and what happens
    when a config exceeds them — reject, or truncate (and if so, which flattened `options` keys to
    drop)?
  - **Data category, quota & billing.** Which data category does it map to for
    quotas/outcomes/billing? The intent is that this is supplementary telemetry, so it most
    likely should **not** be billed like events — but that needs to be decided explicitly.
  - **Outcomes / observability.** How are dropped or rejected `sdk_config` items recorded
    (outcomes, reasons) so we can see ingestion health for this new type?
- **Finalizing the dedup key.** (See [Storing](#storing) above.) We recommend
  `release` + `environment` + `dist` plus an optional SDK-set options hash, but the exact field set,
  the fallback for the common release-less case, and what SDKs should hash (and how they keep it
  stable) still need to be nailed down.

# Drawbacks

- **Risk of leaking sensitive data.** Configuration can contain secrets and PII — DSNs, auth
  tokens or custom headers in transport options, tunnel URLs, and user-meaningful values in
  options like `denyUrls`, `initialScope`, or `serverName`. Even with primitives-only
  normalization, we are shipping user configuration to Sentry, and redaction is imperfect. Any
  new field an SDK captures is a potential leak, so the capture surface must be curated
  carefully.
- **Ingestion and storage overhead.** This is a brand-new payload type sent at potentially very
  high volume (every init for client/serverless traffic). Even with sampling and dedup, it adds
  ingestion load, a new storage model, and server-side processing that did not exist before.
- **Data may be incomplete or misleading.** The techniques that keep volume down also reduce
  fidelity: client sampling can under-sample or miss low-traffic releases and rare
  configurations, and when no options hash is set, dedup keeps only the first-seen config per
  `release`+`environment`+`dist` bucket even when config actually varies within it. Decisions made
  on this data (e.g. deprecating an option that "looks unused") could be based on a
  non-representative picture.
- **Lossy representation of runtime options.** Reducing callbacks to `"[Function]"` tells us a
  `beforeSend`/`tracesSampler` exists but nothing about what it does. For audit-style use cases
  ("warn about confusing behavior") this is a hard limit — we can see that filtering is
  configured, not what it filters.
- **Ongoing maintenance burden.** The normalized schema (and any cross-SDK naming catalog) must
  be kept in sync with evolving options and integrations across every SDK and language. New
  options are invisible until each SDK is updated to capture them, so the dataset always lags
  the SDKs, and consistency across SDKs takes continuous effort.
- **Added SDK complexity and runtime cost.** Every SDK gains new machinery: debounced sending,
  flush-on-shutdown, opt-in per-integration `applied` tracking, normalization, and (for clients)
  sampling. This is more code, more surface for bugs, and some runtime overhead on every init.
- **Unresolved dedup identity.** Storage relies on a good key to deduplicate by. The composite key
  (`release`+`environment`+`dist`) is coarse when `release` is absent, and the finer-grained
  optional options hash is only as good as each SDK's hashing (and is not always present). Getting
  this wrong means either storing too much or collapsing genuinely different configurations
  together (see Storing).

# Not in scope / Follow-up work

This RFC focuses on capturing, transporting, and storing SDK configuration. The following are
explicitly out of scope here and left as follow-up work:

- **Actually using this data in product.** The downstream use cases from the Motivation
  (analytics, setup audits/warnings, showing data sources, configuration-over-time views, a UI
  to change configuration, etc.) are not designed here — they build on top of the data this RFC
  makes available.
- **Removing SDK metadata from error/transaction events.** Once `sdk_config` is the canonical
  home for SDK identity/integration metadata, it makes sense to stop duplicating it on every
  error/transaction event. This is not free, though: that metadata is currently searchable and
  used on events, so removing it requires a mechanism to backfill it onto events from the stored
  `sdk_config` (so events remain searchable/filterable by SDK, version, integrations, etc.).
  Designing that backfill is follow-up work.

