- Start Date: 2026-09-21
- RFC Type: feature
- RFC PR: <link>
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

Ideas of what to eventually do with this data (not all in scope for this initial project):

- Analytics of which options are used, for decision-making about docs, deprecations, and majors.
- Flagging configuration changes that might affect trends over time when querying.
- Auditing `init()` setups to suggest helpful changes or warn about confusing behavior.
- Showing users a list of all the `Sentry.init()`s producing data into each project, so they
  can understand their data sources and any filtering/sampling/config that affects them.
- Showing changes to configuration over time.
- A UI for turning sources on and off and making configuration changes (e.g. via Seer PRs).
- A clear discoverability element — showing which data sources are configured to produce (and
  not produce) which telemetry types.

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

## Design principles

- **Primitives only.** The payload contains only JSON-serializable values: strings, numbers,
  booleans, `null`, arrays, and plain objects. No runtime constructs (functions, class
  instances, streams, etc.) ever appear literally.
- **Callbacks and other runtime values are reduced to markers.** We do not care about a
  callback's implementation, only that _a user-defined callback was set_. Any non-serializable
  value is normalized to a sentinel. We reuse the normalization convention SDKs already have
  (e.g. JS `normalize()` turning a function into `"[Function: name]"`). So
  `beforeSend: (event) => …` becomes `"beforeSend": "[Function]"` (optionally
  `"[Function: beforeSend]"`), a class instance becomes `"[SomeType]"`, and so on.
- **Faithful to the init config, and nested.** The `options` block mirrors the structure the
  user passed to `init()`, preserving nesting rather than flattening it.
- **Generic representation of integration options.** Integrations are user-configurable
  (`Sentry.myIntegration({ filter: 'aaa' })`), so we must capture their options generically —
  keyed by integration name, with their options normalized by the same rules. We do not need
  to understand any specific integration's options; we just record them.
- **Room for well-known metadata and for open-ended data.** Alongside the raw options there is
  space for well-known, structured metadata (SDK identity, release/environment, etc.) and a
  free-form bucket SDKs can use for anything not yet modeled.

## Proposed shape

```json
{
  "sdk": {
    "name": "sentry.javascript.node",
    "version": "10.0.0",
    "packages": [{ "name": "npm:@sentry/node", "version": "10.0.0" }],
    "integrations": {
      "InboundFilters": {},
      "ExpressIntegration": { "active": true },
      "FastifyIntegration": { "active": false },
      "KoaIntegration": {},
      "MyIntegration": {}
    }
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
    "beforeSend": "[Function]",
    "tracesSampler": "[Function]",
    "denyUrls": ["https://example.com/ignore"],
    "integrations": ["InboundFilters", "MyIntegration"]
  },

  "integration_options": {
    "InboundFilters": {},
    "MyIntegration": {
      "filter": "aaa",
      "shouldLog": "[Function]"
    }
  },

  "_other": {}
}
```

## Fields

- **`sdk`** — SDK identity metadata: `name`, `version`, and `packages`. This is the same
  information SDKs attach to error/transaction events today; **this RFC proposes moving it
  here** so it lives in one canonical place. It also carries the `integrations` map — the set
  of registered integrations plus their opt-in runtime status (see below). The configured
  _options_ of each integration live in the separate top-level `integration_options` block;
  the `sdk.integrations` map is about integration _identity and status_.
- **`meta`** — well-known, general metadata that we want first-class regardless of how it was
  set: `release`, `environment`, `dist`, and runtime/platform information (e.g. runtime name
  and version). These describe the instance producing data, complementing the raw `options`.
- **`options`** — a normalized snapshot of the configuration passed to `init()`, nested to
  mirror the user's input, with all values reduced to primitives per the rules above. The
  `integrations` init option is represented here as a list of names; the details live in the
  dedicated `integration_options` block to avoid duplicating (and bloating) the raw options.
- **`integration_options`** — a map of integration name → its normalized options. This is how
  we generically capture things like `MyIntegration({ filter: 'aaa' })` without understanding
  any specific integration. Integrations with no options serialize to `{}`.
- **`_other`** — a free-form, SDK-defined bucket for anything not covered by the well-known
  fields above. The leading underscore signals that this is arbitrary, unstructured data.
  Keeps the schema forward-compatible: SDKs can record additional data without a schema change,
  and useful keys can later be promoted to first-class fields.

## Reflecting which integrations are actually used

Knowing which integrations are _registered_ is not the same as knowing which are actually
_doing anything_. In the Node SDK, for example, a large set of integrations is added by
default (`ExpressIntegration`, `FastifyIntegration`, `KoaIntegration`, …), but a given app
typically uses only one of them. For analytics and audits we care about the difference
between "this integration is present because it ships by default" and "this integration is
actually instrumenting this app".

To capture this generically without enumerating every integration, `sdk.integrations` is a
map keyed by integration name, where the value is a small, **opt-in** status object:

- The **presence of a key** means the integration is registered/enabled.
- An optional **`active`** boolean means the integration determined at runtime whether it is
  actually in effect. `ExpressIntegration` sets `active: true` once it successfully patches
  Express; a defaulted integration whose target framework is absent can report
  `active: false`. An integration that reports nothing leaves its value as `{}` (`active`
  simply absent / unknown).

Key properties of this design:

- **Generic.** No integration-specific fields in the schema; any integration can contribute
  the well-known `active` signal (and we can add further opt-in status keys later).
- **Opt-in and non-exhaustive.** Integrations are not required to report status. We selectively
  push this into the integrations where the signal is valuable to us (e.g. the framework
  integrations), and leave the rest unreported.
- **Distinct from options.** This map carries identity/status only; configured options remain
  in the top-level `integration_options` block.

Note there is a timing implication: `active` is often only known slightly after `init()` (once
instrumentation runs), which influences _when_ the payload is sent or updated. This is
discussed in the send/store section.

## Cross-SDK naming

Option keys differ across SDKs (JS `tracesSampleRate` vs. Python `traces_sample_rate`). We
need to decide whether the payload uses each SDK's native option names as-is, or a canonical
cross-SDK naming so the server can compare the same option across languages. A canonical
catalog (in the spirit of [0116-sentry-semantic-conventions](./0116-sentry-semantic-conventions.md))
would make analytics far easier but requires each SDK to map its options; native names are
simpler but push normalization to the server. This is called out as an open question.

# Drawbacks

<!-- TODO: Why we might not want to do this — added payload/overhead, privacy considerations
around reporting configuration, maintenance cost of keeping the captured schema in sync with
SDK options, risk of leaking sensitive data. -->

# Unresolved questions

- What is the minimum viable set of options to capture for the initial project?
- What is the serialization format and how do we handle function/integration options?
- How do we prevent leaking secrets or PII contained in configuration?
- What is the transport and storage model, and how do we deduplicate across many clients?
- How does this generalize beyond JS to other SDKs?
