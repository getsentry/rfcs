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
  "timestamp": "2026-09-21T12:00:00Z",

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

- **`timestamp`** — when the payload was generated/sent by the SDK. We need to know when a
  configuration was reported, both to order records and to track configuration changes over
  time (e.g. "you changed your filtering rules in May"). Format follows the existing Sentry
  convention (ISO 8601 shown here; could equally be epoch seconds to match event `timestamp`).
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
  Fields in `options` should be **scrubbed server-side** for sensitive data (especially tokens
  and other secrets); notably, SDKs do **not** perform any client-side scrubbing of these values.
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

# Sending and Storing

This section covers question **b**: when the SDK emits the options payload, and how it is
handled server-side. When to send is **not one-size-fits-all** — it differs meaningfully
between SDK types. Broadly we distinguish **server SDKs** (Node, Python, Java, Go, …) from
**client SDKs** (browser, mobile, desktop, gaming, …), which have very different lifecycles.
We start with the server case; the client case is trickier and is covered next.

## Sending — Server SDKs

For server SDKs, the payload is sent **once, shortly after `init()`**, guarded by a short
**debounce delay**:

- **Debounced send after init.** Rather than sending synchronously at the end of `init()`, the
  SDK schedules the send after a short delay (default on the order of **2 seconds**). The delay
  lets the configuration **stabilize**: some values are not known at the exact moment `init()`
  returns — for example an integration's runtime `active` status (see "Reflecting which
  integrations are actually used"), lazily-registered integrations, or release/environment
  detected asynchronously. Debouncing collapses this settling period into a single payload that
  reflects the effective configuration rather than a half-initialized snapshot.
- **Configurable wait period.** The delay **MAY be configurable**. Each SDK should pick a
  sensible default based on **when the data it cares about becomes available** — an SDK that
  only detects framework instrumentation after the first request may want a longer default than
  one whose config is fully known almost immediately. Exposing it as an option lets specific
  setups tune it.
- **One payload per init.** The goal is a single, stable payload per SDK instance/init, not a
  stream of updates. If the config meaningfully changes later, that is handled as a separate
  concern (and mostly matters for long-lived processes); the common case is one send per
  process start.

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

### Option 2 (recommended): Deduplicate and store a single record

Store only **one** record per configuration and discard the rest. Because configuration is
essentially constant per release, we need a key to deduplicate by, and we suggest **release**:

- We store the **first** payload seen for a given release.
- All subsequent payloads for that **same** release are **discarded** (they are expected to be
  identical).
- When a payload arrives with a **new/different release**, we store that as the new record for
  that release.

This keeps storage bounded (roughly one record per release), matches the reality that config
changes track releases, and naturally gives us a per-release history of configuration over time.

**Open question — is `release` the right dedup key?** We need to verify that release is
sufficient to identify a distinct configuration. It may not always be: config can differ
_within_ the same release (e.g. environment-dependent options, feature flags, per-deployment
overrides, or code paths that call `init()` with different options), and release may be unset
in some setups. We may need a composite key (e.g. release + environment, or a hash of the
normalized options) or a different identifier altogether. This needs to be validated before
settling on release alone.

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
  configurations, and dedup-by-release keeps only the first-seen config per release even when
  config actually varies within a release. Decisions made on this data (e.g. deprecating an
  option that "looks unused") could be based on a non-representative picture.
- **Lossy representation of runtime options.** Reducing callbacks to `"[Function]"` tells us a
  `beforeSend`/`tracesSampler` exists but nothing about what it does. For audit-style use cases
  ("warn about confusing behavior") this is a hard limit — we can see that filtering is
  configured, not what it filters.
- **Ongoing maintenance burden.** The normalized schema (and any cross-SDK naming catalog) must
  be kept in sync with evolving options and integrations across every SDK and language. New
  options are invisible until each SDK is updated to capture them, so the dataset always lags
  the SDKs, and consistency across SDKs takes continuous effort.
- **Added SDK complexity and runtime cost.** Every SDK gains new machinery: debounced sending,
  flush-on-shutdown, opt-in per-integration `active` tracking, normalization, and (for clients)
  sampling. This is more code, more surface for bugs, and some runtime overhead on every init.
- **Unresolved dedup identity.** Storage relies on a good key to deduplicate by, and it is not
  yet clear that `release` (or any single field) is sufficient (see Storing). Getting this wrong
  means either storing too much or collapsing genuinely different configurations together.

