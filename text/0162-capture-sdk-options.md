- Start Date: 2026-09-21
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/162
- RFC Status: draft
- RFC Author: @mydea
- RFC Approver: 

# Summary

Today, we have very little visibility into which options a given Sentry SDK instance was configured
with. This RFC proposes that SDKs report their configuration (the options passed to `Sentry.init()`,
plus relevant derived and effective values) in a new `sdk_config` envelope item, so that Sentry can
store, surface, and act on it. Product features built on this data are future work.

# Motivation

A user reports missing transactions. Was tracing never enabled? Did a sample rate or
`beforeSendTransaction` drop them? Did something fail? Without the SDK configuration, we cannot tell.
With it, we can support:

- **Self-healing and support:** distinguish "never enabled", "enabled but filtered", and "failed".
- **Analytics and product decisions:** learn which options are used and which matter most, to guide
  docs, deprecations and removals in major versions, and investment.
- **Configuration-aware querying:** explain shifts in data with configuration changes, such as new
  filtering or sampling rules.
- **Setup audits and warnings:** suggest improvements and warn about confusing behavior given the
  settings.
- **Discoverability of data sources:** show every `Sentry.init()` that sends data into a project, with
  its configuration over time, and eventually allow changing configuration from the UI.

# Background

Sentry has no first-class record of SDK configuration. Two existing mechanisms come close:

- **The `sdk` object on error and transaction events** lists the SDK name, version, integrations, and
  packages, but not how the SDK is configured (sample rates, `beforeSend`, `sendDefaultPii`,
  `denyUrls`, transport and tracing options, …). It only arrives with events, so instances that send
  none, or whose events are all filtered, are invisible.
- **Client reports** count discarded events, which is unrelated to configuration. They are, however,
  a precedent for a standalone, non-event item that SDKs send on their own cadence and flush on
  shutdown.

<!-- Reference: Linear project
https://linear.app/getsentry/project/capture-sdk-options-js-08e8a89c71c9/overview -->

# Options Considered

## Option A (preferred): A dedicated envelope item

SDKs send the configuration in a standalone `sdk_config` envelope item, like client reports. This
decouples "how is this instance configured?" from "did it send an event?", and gives us a payload
that we can version, store, and analyze independently.

## Option B: Add the options to error events

Extend the `sdk` object on error and transaction events with the full options. This reuses the
existing transport, but configuration is only seen when events are sent, identical configuration is
re-sent with every event, and the data is mixed into the high-volume event stream, which makes
grouping and storing it harder.

# Proposed Design

## Payload

The item type is tentatively named `sdk_config` (alternatives: `sdk_metadata`, `sdk_options`), with
one language-agnostic schema for all SDKs, starting with JavaScript. Older Relay and self-hosted
versions discard unknown item types without affecting the rest of the envelope, so SDKs can send
`sdk_config` unconditionally.

SDKs send every field in this example except `normalized_options`, which Relay adds at ingestion:

```json
{
  "version": 1,
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
    "dataCollection.http.headers": false
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

The key fields (see [Appendix A](#appendix-a-payload-details) for all fields and exact rules):

- **`options`:** the **effective** configuration that the SDK runs with (after defaults, environment
  variables, and derived values), under native option names. Values are reduced to JSON primitives:
  nested objects become dot-notation keys, callbacks become `"[Function]"`, and integrations move to
  the `integrations` block.
- **`options_set_by_user`:** the keys that the user explicitly set in `init()`, to tell actual usage
  apart from defaults.
- **`integrations`:** the serialized options of each registered integration, plus an optional
  `applied` flag that records whether the integration took effect at runtime. For example, the Node
  SDK registers Express, Fastify, Koa, and more by default, but an app typically uses only one.
- **`options_hash`:** a required hash of the configuration (see [Storage](#storage)).
- **`normalized_options`:** a small catalog of options under canonical cross-SDK names (JS
  `tracesSampleRate` → `traces_sample_rate`), derived by Relay in the spirit of
  [0116-sentry-semantic-conventions](./0116-sentry-semantic-conventions.md).

The design keeps SDKs simple: they serialize their existing options object (e.g. JS
`client.getOptions()`), diff its keys against the `init()` argument, and ship no name mapping. New options are captured
automatically, one Relay implementation avoids inconsistent mappings across SDKs, and the catalog can
change, including for stored data, without SDK releases. Sending two option trees or wrapping every
value as `{ value, source }` would need more SDK bookkeeping. The cost is that converted values lose
their original form: for example, we cannot tell whether `integrations` was passed as a function (in
JS, only `integrations` and `stackParser` are affected).

Sensitive data is scrubbed primarily server-side. SDKs MAY also scrub values that they know to be
sensitive, but they do not guarantee fully scrubbed data.

## Sending

**Server SDKs** (Node, Python, Java, Go, …) send one payload per `init()` once the configuration has
settled, because values such as `applied` are only known after `init()` returns. Each SDK MAY choose
how to wait, for example with a short debounce (about 2 seconds) or a lifecycle hook. Short-lived
processes flush the payload on shutdown, and long-lived processes MAY re-send it at a slow interval
(e.g. hourly) in case a send was lost. [Appendix B](#appendix-b-sending-and-storage-details) has the
details.

**Client SDKs** (browser, mobile, desktop, gaming, …) call `init()` on every page load, app launch,
or session, so sending from every instance produces far more data. We propose exploring:

| Option                                                                                                            | Pros                                                       | Cons                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **I: Send on every `init()`**                                                                                     | Simple, same as server SDKs; every instance is represented | Much more data to ingest; an extra request per `init()`                                                                                              |
| **II: Sample** a fraction of `init()` calls (e.g. 1%), assuming configuration is essentially constant per release | Much less overhead                                         | Low-traffic releases and rare configurations may be missed; more configuration surface; harder to reason about and test                              |
| **III: Attach to the first outgoing envelope**; combinable with I or II, also usable by server SDKs               | No extra request; only instances that produce data report  | Harder to implement; the first envelope may leave before the configuration settles; instances that never send, e.g. misconfigured ones, never report |

**Serverless** functions run server SDKs but have one `init()` per short-lived invocation, like
clients, so client strategies such as sampling COULD apply to them.

## Storage

Storing every payload (**Option 1**) keeps a complete history, but mostly stores duplicates at a very
high cost. We recommend **Option 2: store one record per distinct configuration**, deduplicated by
**`options_hash` (primary) + `release` + `environment` + `dist` (fallback)**.

SDKs MUST compute `options_hash` from the serialized `options` and `integrations` blocks, and MUST
attach it to every event: as the proposed `sentry.config_hash` attribute on spans, logs, and other
items with attributes, and in a new `sdk_config.hash` context field on errors and transactions. The
hash links each event to its exact configuration and keeps configurations that differ within one
release separate.

If no stored record matches an event's hash (e.g. because the payload was lost or sampled out), or
the event has no hash, correlation falls back to `release` + `environment` + `dist`, which every
event already carries. The fallback resolves only to the records of that combination and is coarse
when `release` is unset.

# Drawbacks

- **Sensitive data:** configuration can contain secrets and PII (DSNs, tokens or headers in transport
  options, tunnel URLs, `denyUrls`, `initialScope`, `serverName`), and redaction is imperfect.
- **Overhead:** a new, potentially high-volume item (every `init()` for client and serverless
  traffic), a new storage model, and new server-side processing.
- **Incomplete or misleading data:** sampling and fallback correlation can give a non-representative
  picture, for example when deciding whether an option "looks unused".
- **Lossy callbacks:** `"[Function]"` shows that filtering is configured, not what it filters.
- **Maintenance:** the normalization catalog must track options across all SDKs.
- **SDK complexity:** delayed sending, flushing, `applied` tracking, serialization, and sampling add
  code and runtime cost on every `init()`.
- **Deduplication identity:** a poor hash or a missing `release` either stores too much or merges
  distinct configurations.

# Unresolved questions

- **Ingest requirements for a new item type:** Relay support (routing, validation, deriving
  `normalized_options`), rate limiting (own or shared category, interaction with the send cadence,
  `429`/`Retry-After` and SDK backoff), size limits (reject or truncate), data category, quota
  consumption, and billing (likely not billed like events), and outcomes for dropped items.
- **Deduplication key:** the exact fields, the fallback behavior, and what SDKs hash and how they keep
  the hash stable.
- **EAP storage:** EAP prefers a single top-level `attributes` field, which would mean storing blocks
  such as `options` as JSON-valued attributes that remain efficiently queryable. Whether to use EAP is
  decided with the storage design.
- **Item type name** and **client SDK send strategy** (Options I to III).

## Out of scope

- Product features built on this data (analytics, audits, data source views, configuration history,
  configuration UI).
- Removing SDK metadata from events. Events are searchable by it, so this first requires backfilling
  it onto events from stored `sdk_config` records.

# Appendix A: Payload details

**Fields**

- `version`: integer payload schema version, starting at `1` and independent of `sdk.version`. It is
  bumped only for changes that consumers must know about, so the server can select the right parser
  instead of guessing from the field set.
- `timestamp`: when the SDK sent the payload, used to order records and track changes. ISO 8601 or
  epoch seconds, following Sentry conventions.
- `sdk`: the same data as on events today; `sdk_config` becomes its canonical place. The `integrations`
  block captures integration information in more detail than the event's list of integration names;
  events keep their existing metadata for now (see [Out of scope](#out-of-scope)).
- `meta`: `release`, `environment`, `dist`, and runtime information, regardless of how they were set.
- `options_set_by_user`: uses the flattened keys of `options`; each key corresponds 1:1 to a key in
  `options`.
- `integrations`: each integration's options are nested under `options`, so they cannot collide with
  status keys. `applied` is `true` if the integration took effect (e.g. patched Express), `false` if
  not (e.g. its framework is absent), and omitted if unknown. It is opt-in, added where the signal is
  useful, such as framework integrations.
- `normalized_options`: entries are `{ "key": <native name>, "value": <effective value> }`; whether
  the user set an option is checked in `options_set_by_user`.
- `_other`: free-form, SDK-specific data; useful keys can later become first-class fields.

**Serialization rules** for `options` and each integration's `options`, which make the output
deterministic and consistent across SDKs:

1. Primitives are sent unchanged. Arrays stay arrays, with each element serialized by these same
   rules.
2. Nested objects are flattened: `dataCollection: { http: { bodies: true } }` becomes
   `"dataCollection.http.bodies": true`.
3. Functions become `"[Function]"`. SDKs MAY include the name (`"[Function: beforeSend]"`), but
   consumers must not rely on it.
4. The `integrations` option is omitted; its data is in the `integrations` block.
5. Other non-serializable values become type markers such as `"[SomeType]"`, following the SDK's
   existing normalization convention.

**Initial normalization catalog**, maintained alongside Relay and expected to grow. `release`,
`environment`, and `dist` are not included, because they are already in `meta`.

| Canonical key             | Meaning                     | Native names (JS → Python)                          |
| ------------------------- | --------------------------- | --------------------------------------------------- |
| `sample_rate`             | Error sample rate           | `sampleRate` → `sample_rate`                        |
| `traces_sample_rate`      | Tracing sample rate         | `tracesSampleRate` → `traces_sample_rate`           |
| `profiles_sample_rate`    | Profiling sample rate       | `profilesSampleRate` → `profiles_sample_rate`       |
| `send_default_pii`        | Whether default PII is sent | `sendDefaultPii` → `send_default_pii`               |
| `debug`                   | Debug logging enabled       | `debug` → `debug`                                   |
| `before_send`             | Whether the hook is set     | `beforeSend` → `before_send`                        |
| `before_send_transaction` | Whether the hook is set     | `beforeSendTransaction` → `before_send_transaction` |
| `before_send_span`        | Whether the hook is set     | `beforeSendSpan` → `before_send_span`               |
| `before_send_log`         | Whether the hook is set     | `beforeSendLog` → `before_send_log`                 |
| `ignore_spans`            | Span-ignore rules           | `ignoreSpans` → `ignore_spans`                      |
| `traces_sampler`          | Whether the hook is set     | `tracesSampler` → `traces_sampler`                  |
| `data_collection.*`       | All flattened sub-keys      | `dataCollection.*` → `data_collection.*`            |

# Appendix B: Sending and storage details

- **Waiting for settled configuration:** values known only after `init()` include `applied`, lazily
  registered integrations, and an asynchronously detected release or environment. The debounce MAY be
  configurable for setups that settle later. A lifecycle hook that guarantees settled options (e.g.
  after the first request, a post-init hook, or the first idle event loop) is preferable. The goal is
  one stable payload, not a stream of updates; later configuration changes are a separate concern.
- **Short-lived processes** (serverless, CLI) flush wherever they already flush events, and MAY reuse
  their client report flushing. If a process dies first, an equivalent instance will report.
- **Periodic re-send:** if Relay cannot guarantee that a `200` response means the payload was
  persisted, a single lost send would leave a long-running server without stored configuration.
- **Hash:** identical configurations produce identical hashes, and any change to the options, the
  registered integrations, their options, or `applied` changes the hash. Algorithms do not need to
  match across SDKs. The hash is computed SDK-side so that events can carry it.
- **Hash caveats:** it adds a field to every event. Because configuration settles after `init()`, the
  hash on events must match the reported configuration (e.g. by hashing only values that are stable
  from `init()`, or by stamping events only after settling), so early events may lack it. Payloads that
  were sampled out leave hashes without a stored record.
- **Fallback key:** `release` alone is insufficient, because configuration can differ by environment
  and build. The composite key is bounded, human-readable, and cheap, but `environment` defaults to
  `production` and `dist` is usually absent, so the key depends on `release`, which is often unset. It
  resolves to the first-seen record or to the set of stored variants.
