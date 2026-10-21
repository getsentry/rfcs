- Start Date: 2026-09-21
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/162
- RFC Status: draft
- RFC Author: @mydea
- RFC Approver:

# Summary

Sentry currently has very little visibility into which options a given SDK instance was configured
with. This RFC proposes that SDKs report their configuration (the options passed to `Sentry.init()`,
plus relevant derived and effective values) in a new `sdk_config` envelope item, so that Sentry can
store, surface, and act on it. Product features built on this data are future work.

# Motivation

A user reports missing transactions. Was tracing never enabled? Did a sample rate or
`beforeSendTransaction` drop them? Did something fail? Without the SDK configuration, there is no way to tell.
With it, Sentry can support:

- **Self-healing and support:** distinguish "never enabled", "enabled but filtered", and "failed".
- **Analytics and product decisions:** learn which options are used and which matter most, to guide
  docs, deprecations and removals in major versions, and investment.
- **Configuration-aware querying:** explain shifts in data with configuration changes, such as new
  filtering or sampling rules.
- **Setup audits and warnings:** suggest improvements and warn about confusing behavior given the
  settings.
- **Discoverability of data sources:** show every `Sentry.init()` that sends data into a project, with
  its configuration over time, and eventually allow changing configuration from the UI.
- **Onboarding:** confirm with certainty that the SDK setup succeeded, without asking users to send
  logs/metrics/spans/errors to verify it.

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
decouples "how is this instance configured?" from "did it send an event?", and yields a payload
that can be versioned, stored, and analyzed independently.

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

The payload is a single JSON object. Top-level fields mirror the existing event protocol, so Relay
can extract the queryable metadata from fixed paths, while `options` holds the SDK's native options
as-is. SDKs send everything in this example except `normalized`, which Relay adds at ingestion:

```json
{"type":"sdk_config","content_type":"application/json","hash":"9f2c1a7e"}
{
  "version": 1,
  "timestamp": 1790000000.0,
  "release": "my-app@1.2.3",
  "environment": "production",
  "dist": "42",
  "sdk": {
    "name": "sentry.javascript.node",
    "version": "10.0.0",
    "packages": [{ "name": "npm:@sentry/node", "version": "10.0.0" }]
  },
  "runtime": { "name": "node", "version": "20.11.0" },
  "options": {
    "release": "my-app@1.2.3",
    "sampleRate": 1.0,
    "tracesSampleRate": 0.2,
    "sendDefaultPii": true,
    "beforeSend": "[Function]",
    "denyUrls": ["/example\\.com\\/ignore/"],
    "dataCollection": { "httpBodies": ["incomingRequest"] }
  },
  "options_set_by_user": ["release", "tracesSampleRate", "sendDefaultPii", "beforeSend", "denyUrls"],
  "integrations": [
    { "name": "InboundFilters" },
    { "name": "Express", "applied": true },
    { "name": "Fastify" },
    { "name": "MyIntegration", "options": { "filter": "aaa", "shouldLog": "[Function]" } }
  ],
  "normalized": {
    "sample_rate": { "value": 1.0, "option": "sampleRate" },
    "traces_sample_rate": { "value": 0.2, "option": "tracesSampleRate" },
    "send_default_pii": { "value": true, "option": "sendDefaultPii" },
    "before_send": { "value": "[Function]", "option": "beforeSend" }
  }
}
```

The fields (see [Appendix A](#appendix-a-payload-details) for serialization and normalization):

- **`hash`** (item header): a required hash of the configuration (see [Storage](#storage)).
- **`version`:** the payload schema version.
- **`timestamp`:** when the configuration was captured, in seconds since the Unix epoch. Relay
  applies clock drift correction as for events, falls back to the receive time if it is missing or
  invalid, and uses it to set `first_seen` and `last_seen`.
- **`release`, `environment`, `dist`:** same as on events. Relay stores these as queryable columns.
- **`sdk`:** same shape as the `sdk` object on events (`name`, `version`, `packages`). Relay stores
  `name` and `version` as queryable columns.
- **`runtime`:** same shape as the `runtime` context on events (`name`, `version`).
- **`options`:** the **effective** configuration that the SDK runs with (after defaults, environment
  variables, and derived values), under native option names and with nesting kept. Values that also
  have a top-level field (e.g. `release`) MAY be included here as well. Option names should reflect
  the names a user would use to set the values.
- **`options_set_by_user`:** the option keys that the user explicitly set in `init()`, to tell actual
  usage apart from defaults. This should be best-effort - it MAY be incomplete if users add
  configuration in alternate paths or similar. If it is not possible to enumerate options
  automatically, SDKs MAY send a hand-picked subset of options here only.
- **`integrations`:** every registered integration, in registration order:
  - `name`: the integration name.
  - `applied` (optional): `true` if the SDK tracks the integration as actually applied at runtime.
    For example, the Node SDK registers Express, Fastify, Koa, and more by default, but an app
    typically uses only one.
  - `options` (optional): the serialized integration options. SDKs MAY decide which integration
    options are relevant to capture.
- **`normalized`:** a small catalog of options under canonical cross-SDK names (JS
  `tracesSampleRate` → `traces_sample_rate`), derived by Relay. `option` is the native option name,
  to allow display of the value in a way that makes sense for a user.

One new attribute is added to Sentry conventions, for linking telemetry to its configuration:

| Attribute                | Type   | Example      |
| ------------------------ | ------ | ------------ |
| `sentry.sdk_config.hash` | string | `"9f2c1a7e"` |

The design keeps SDKs simple: most SDKs can just serialize their existing finalized options object (e.g. JS
`client.getOptions()`), new options are captured automatically.
One Relay implementation avoids inconsistent mappings across SDKs, and the catalog can
change, including for stored data, without SDK releases.

One downside of this is that converted values lose their original form:
for example, it is not possible to tell whether `integrations` was passed as a function -
this should generally only affect a small subset of options (e.g. in JS, only `integrations` and `stackParser` are affected).

Sensitive data is scrubbed primarily server-side. SDKs MAY also scrub values that they know to be
sensitive, but they do not guarantee fully scrubbed data.

## Sending

SDKs send one payload per `init()` once the configuration has
settled, because values such as applied integrations are only known after `init()` returns. Each SDK MAY choose
how to wait, for example with a short debounce (e.g. 5 seconds) or a lifecycle hook. Short-lived
processes MAY flush the payload on shutdown. [Appendix B](#appendix-b-sending-and-storage-details) has the
details.

This applies to all kinds of SDKs. Records are [deduplicated server-side](#deduping) before storage.

**Server SDKs** (Node, Python, Java, Go, …) MAY re-send it at a slow interval
(e.g. hourly) in case a send was lost.

## Deduping

Because every `init()` sends a payload, most payloads do not need to be stored. They should be
deduplicated and discarded at ingestion time to avoid unnecessary processing cost.

Deduplication must keep database load as low as possible and avoid unnecessary reads and writes, so
it has to happen before storage. This could happen in different places:

**Relay**: Relay keeps hash keys and last-seen timestamps in a Redis or Memcached cache, and only
creates or updates records when needed.

**Kafka log compaction**: Alternatively, Relay pushes every config to Kafka and lets it handle deduplication.

## Retention

SDK config data should be kept for as long as the standard telemetry retention for a given project is (e.g. 30-90 days).
Importantly, data needs to be kept for 30-90 days _after it was last seen_, not after it was first seen.
For this purpose, we need to keep track of the `last_seen` field for all SDK config. It has to be updated e.g. once
every 24 hours - it does not have to be 100% accurate, only accurate enough to handle retention effectively.

## Rate Limiting

Ingested configs MUST be limited to avoid an unexpected explosion of records. For example, what happens if, for whatever reasons,
a client generates unique hashes for each instance (e.g. some randomness in some config value), thus sending thousands or millions of unique
configs in an hour?

Relay SHOULD apply a rate limit on the number of unique configs per project per hour. Config records above
the limit (e.g. **1000 configs/h**) are not created or updated.

Redis MAY track the set of config hashes per project for this, or we MAY use another mechanism to handle this.

## Storage

Storing every payload (**Option 1**) keeps a complete history, but mostly stores duplicates at a very
high cost. The recommended approach is **Option 2: store one record per distinct configuration**, deduplicated by
**`sentry.sdk_config.hash`.

SDKs MUST compute the hash from the serialized `options` and `integrations`, and MUST attach it
to every event: as the same `sentry.sdk_config.hash` attribute on spans, logs, and other items with
attributes, and in a new `sdk_config.hash` context field on errors and transactions. The
hash links each event to its exact configuration and keeps configurations that differ within one
release separate. The hash MAY be generated based off the full payload,
or from a subset if that makes more sense for an SDK.

The hash MUST NOT be put on other telemetry types if it has not yet stablized -
only a hash that matches a sent SDK config record MAY be attached to other events.
The hash MUST NOT change for a given client after it has been sent (even if options are changed later).

The hash also MUST be part of the envelope item header and Relay MUST reject any item without a hash.

If no stored record matches an event's hash (e.g. because the payload was lost or sampled out), or
the event has no hash, correlation MAY fall back to `release` + `environment` + `dist`, which every
event already carries. The fallback resolves only to the records of that combination and is coarse
when `release` is unset. It should use the newest matching config in this case.

The time a config entry was last seen must be kept in order to enable retention calculation.
This should be updated when a config is sent - not on every sent record, but e.g. every 24h,
to avoid unnecessary load on the database.

The new data type is free for end users and is not billed.
See [Appendix C](#appendix-c-volume-estimates) for estimations.

### What to store

In addition to the config itself (as JSON), the following queryable (meta-)data needs to be stored:

- `first_seen`: The date this config has been first sent (from `timestamp`).
- `last_seen`: The date this config has been last sent (from `timestamp`).
- `release`: The release associated with this config.
- `environment`: The environment associated with this config.
- `sdk_name`: The SDK name associated with this config.
- `sdk_version`: The SDK version associated with this config.
- `hash`: The hash/ID associated with this config (unique per project).

### Where to store

The data has the following access needs, which determine how and where to store it:

- Config itself is immutable. It will never be updated.
- Config should have a retention similar to other telemetry, so e.g. 30-90 days.
  - The retention needs to be measured based on when the config was last seen.
- In product, config may be queried as follows:
  - By hash key: When looking at telemetry (e.g. an issue), find the associated config for it.
  - By project/org: Find the latest config(s) for a given project (e.g. for onboarding)
  - By release/environment: Show config changes over time
  - By first_seen/last_seen dates
- Read patterns:
  - Config MAY be fetched for each issue/trace detail view (e.g. "Config that produced this error")
  - Config MAY be lazy-loaded on demand or MAY be eager loader for each detail view
  - Config MAY be queried on empty pages/during onboarding
- Analytics (e.g. in Hex) should be able to answer questions such as:
  - How many projects configure a given option?
  - What are average configured values (e.g. average sample rates, ...)
  - How many projects use the integration Y?
  - For projects using X/configuring Y, how many <do Z> (e.g. send spans, ...)

Options for storage are:

**EAP**:

- Pro: Easy to query (but trace_id could make it harder)
- Pro: Well suited for the expected sizes
- Pro: Cheaper than Postgres
- Con: Config is not really trace connected, which would lead to problems
- See [Appendix E](#appendix-e-eap-requirements) for more details on EAP requirements

**Postgres**:

- Pro: Easy to set up
- Pro: Easy to query
- Con: Payload sizes (~3kb configs) not a perfect match

**Postgres + Object Store**:

- Pro: Query via Postgres, keep full config in Object Store
- Pro: Well suited for the expected sizes
- Con: Additional complexity in keeping postgres/object store in sync

**Dedicated ClickHouse table**:

A dedicated table keyed on (project, hash) with TTL on last_seen.

- Pro: Handles dedup and retention natively
- Pro: Fast lookups
- Con: One-off tables (outside of EAP) is a de-emphasized pattern

**BigQuery**:

- Regardless of where data is stored for in-product use, it also needs to reach BigQuery so it can be accessed in Hex and similar tools.
- _TBD: How/when to move data over?_ It does not need to be live, e.g. 24h delay or similar would be fine.

See [Appendix C](#appendix-c-volume-estimates) for volume & cost estimates.

## Recommendation for Storage

Based on the reasearch and options above, the recommended solution is to store in **Postgres + Object Store**.

# Drawbacks

- **Sensitive data:** configuration can contain secrets and PII (DSNs, tokens or headers in transport
  options, tunnel URLs, `denyUrls`, `initialScope`, `serverName`), and redaction is imperfect.
- **Overhead:** a new, potentially high-volume item (every `init()` for client and serverless
  traffic), a new storage model, and new server-side processing.
- **Lossy callbacks:** `"[Function]"` shows that filtering is configured, not what it filters.
- **Maintenance:** the normalization catalog must track options across all SDKs.
- **SDK complexity:** delayed sending, flushing, applied integration tracking, serialization, and sampling add
  code and runtime cost on every `init()`.
- **Deduplication identity:** a poor hash or a missing `release` either stores too much or merges
  distinct configurations.

# Unresolved questions

- **Ingest requirements for a new item type:** Relay support (routing, validation, deriving
  normalized values), rate limiting (own or shared category, interaction with the send cadence,
  `429`/`Retry-After` and SDK backoff), size limits (reject or truncate), data category, quota
  consumption, and billing (likely not billed like events), and outcomes for dropped items.
- **EAP storage:** a new `TraceItemType` (sentry-protos, Snuba, Relay, Sentry search). EAP items
  expire after their retention period, so long-running processes must re-send within it. EAP could
  deduplicate via a deterministic `item_id` from the hash plus a bucketed `timestamp` (as preprod
  does), to be confirmed with the EAP team. Limits on attribute count and size per item.
- **Custom filtering:** Is SDK-side filtering (e.g. `beforeSendSdkConfig`) needed to allow manual PII stripping?

## Out of scope

- Product features built on this data (analytics, audits, data source views, configuration history,
  configuration UI).
- Removing SDK metadata from events. Events are searchable by it, so this first requires backfilling
  it onto events from stored `sdk_config` records.

# Appendix A: Payload details

For payload fields, see [Payload](#payload).

**Serialization rules** for `options` and integration `options`, which make the output
deterministic and consistent across SDKs:

1. Primitives, arrays, and nested objects are sent as JSON.
   a. An SDK MAY normalize specific options if it makes sense, e.g. stripping out user-specific paths, unstable options or similar.
2. Functions become `"[Function]"`. SDKs MAY include the name (`"[Function: beforeSend]"`), but
   consumers must not rely on it.
3. The `integrations` option is omitted; its data is in the top-level `integrations` field.
4. `undefined` values are omitted; `null` values are kept.
5. Other non-serializable values become their string form (e.g. `"/foo/i"` for a RegExp) or type
   markers such as `"[SomeType]"`, following the SDK's existing normalization convention.

**Initial normalization catalog**, maintained alongside Relay and expected to grow. `release`,
`environment`, and `dist` are not included, because they already have their own top-level fields.

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
| `data_collection`         | Data collection settings    | `dataCollection` → `data_collection`                |

# Appendix B: Sending and storage details

- **Waiting for settled configuration:** values known only after `init()` include applied integrations, lazily
  registered integrations, and an asynchronously detected release or environment. The debounce MAY be
  configurable for setups that settle later. A lifecycle hook that guarantees settled options (e.g.
  after the first request, a post-init hook, or the first idle event loop) is preferable. The goal is
  one stable payload, not a stream of updates; later configuration changes are a separate concern.
  This should be best-effort, it is understood that late config changes MAY not be correctly captured.
- **Short-lived processes** (serverless, CLI) flush wherever they already flush events, and MAY reuse
  their client report flushing. If a process dies first, an equivalent instance will report.
- **Periodic re-send:** Relay cannot guarantee that a `200` response means the payload was
  persisted. To accommodate this, as well as retention period dropping config after longer time periods,
  a single lost send would leave a long-running server without stored configuration.
- **Hash:** identical configurations produce identical hashes, and any change to the options, the
  registered integrations, their options, or the applied integrations changes the hash. Algorithms do not need to
  match across SDKs. The hash is computed SDK-side so that events can carry it.
- **Hash caveats:** it adds a field to every event. Because configuration settles after `init()`, the
  hash on events must match the reported configuration (e.g. by hashing only values that are stable
  from `init()`, or by stamping events only after settling), so early events may lack it. Payloads that
  were sampled out leave hashes without a stored record.
  The current hash should be put on other telemetry items, even if the sdk_config has not been sent yet.
  It is understood that this means that the final hash MAY differ from the one attached to early records.
  Those may be linked by fallback key only (see below).
- **Fallback key:** `release` alone is insufficient, because configuration can differ by environment
  and build. The composite key is bounded, human-readable, and cheap, but `environment` defaults to
  `production` and `dist` is usually absent, so the key depends on `release`, which is often unset. It
  resolves to the first-seen record or to the set of stored variants.

# Appendix C: Volume Estimates

- **2-3m** releases per day
  - Expected: about **5-10m** distinct SDK configs per day.
- **50b** sessions per day
  - May map roughly to **50b** SDK config envelopes sent per day.
- **300k** projects get data sent any given hour
  - For mobile, it is estimated that about **15-40** release/environment pairs are active per project at any given time
  - For JS, it is estimated to be **1-10** on average, as most users get upgraded to the latest version on reload.
  - Based on this, assuming an overall average of **20 active configs** per project, there would be **6m** SDK configs active per hour
- SDK config size examples:
  - JS Browser: ~1-3 KB
  - JS Node: ~1-4 KB
  - Based on this, 10m configs per day, each active for 30 days, would require storing about **900 GB** of SDK config
- Relay redis clusters currently cost ~5k USD/month (US region only), for project configs and rate limits.
  - An additional Redis instance for hash bookkeeping would cost about the same.
- EAP costs about **0.016 USD** per GB of logs storage, or **0.10 USD** per 1M spans
  - Based on this, EAP storage cost may be very low (<100 USD)
- Postgres cost about **51k USD/m** total, for about **60 TB** of data
  - Based on this, Postgres storage may be **~800 USD/m**
- Memcached cost is about **5K USD/m**
  - Cost of hash bookkeeping would thus be estimated to be low here too
- **200k** issue detail page views per day.
  - SDK config may be fetched **500k** times per day, if inflected to accomodate e.g. onboarding, other detail pages etc.

# Appendix D: Edge Cases

There are some edge cases to consider. Some may be resolved and others may be conciously not solved.

- SDK Config may be dropped when sent, thus telemetry may exist that has no corresponding config entry.
  - The product must work with missing data. It can differentiate between "old SDK, no config sent" and "config should exist, but is missing"
    via the existence of the hash attribute.

# Appendix E: EAP Requirements

If it is decided to use EAP for storage, here are some requirements this would entail:

- A new item type (protos, Relay, snuba, search)
- Daily re-sends from Relay to fake last-seen retention
- Newest-row dedup on every read
- First/last seen computed per query
- Hacking the trace_id so lookups don't turn into large scans (like it's not trace connected data, but we index on trace_id so that's our only lever to index)

Perf-wise, the closest analog today is `TraceItemDetails` which has single item lookup time of ~200ms p50 / 1.25s p99 with an index and a narrow window, so this would be similar or worse for larger windows. At the initial query volume that's fine, but if we ever wanted to query this heavily it could become real load.
