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

The item follows the EAP format, so it can be stored in EAP as a new
trace item type: a container with `items`, each with a `timestamp` and typed `attributes`. Existing
[Sentry conventions](https://getsentry.github.io/sentry-conventions/attributes/) are reused where
they fit; everything else lives under `sentry.sdk_config.*` in dot notation. SDKs send every
attribute in this example except `sentry.sdk_config.normalized.*`, which Relay adds at ingestion:

```json
{"type":"sdk_config","item_count":1,"content_type":"application/vnd.sentry.items.sdk-config+json"}
{
  "items": [
    {
      "timestamp": 1790000000.0,
      "attributes": {
        "sentry.sdk.name": { "type": "string", "value": "sentry.javascript.node" },
        "sentry.sdk.version": { "type": "string", "value": "10.0.0" },
        "sentry.sdk.packages": { "type": "array", "value": ["npm:@sentry/node@10.0.0"] },
        "sentry.sdk.integrations": {
          "type": "array",
          "value": ["InboundFilters", "Express", "Fastify", "Koa", "MyIntegration"]
        },
        "sentry.release": { "type": "string", "value": "my-app@1.2.3" },
        "sentry.environment": { "type": "string", "value": "production" },
        "sentry.dist": { "type": "string", "value": "42" },
        "process.runtime.name": { "type": "string", "value": "node" },
        "process.runtime.version": { "type": "string", "value": "20.11.0" },

        "sentry.sdk_config.version": { "type": "integer", "value": 1 },
        "sentry.sdk_config.hash": { "type": "string", "value": "9f2c1a7e" },

        "sentry.sdk_config.option.dsn": { "type": "string", "value": "https://<public-key>@o0.ingest.sentry.io/0" },
        "sentry.sdk_config.option.sampleRate": { "type": "double", "value": 1.0 },
        "sentry.sdk_config.option.tracesSampleRate": { "type": "double", "value": 0.2 },
        "sentry.sdk_config.option.sendDefaultPii": { "type": "boolean", "value": true },
        "sentry.sdk_config.option.beforeSend": { "type": "string", "value": "[Function]" },
        "sentry.sdk_config.option.denyUrls": { "type": "array", "value": ["https://example.com/ignore"] },
        "sentry.sdk_config.option.dataCollection.http.bodies": { "type": "boolean", "value": true },
        "sentry.sdk_config.options_set_by_user": {
          "type": "array",
          "value": ["dsn", "tracesSampleRate", "sendDefaultPii", "beforeSend", "denyUrls"]
        },

        "sentry.sdk_config.integration.Express.applied": { "type": "boolean", "value": true },
        "sentry.sdk_config.integration.Fastify.applied": { "type": "boolean", "value": false },
        "sentry.sdk_config.integration.MyIntegration.option.filter": { "type": "string", "value": "aaa" },
        "sentry.sdk_config.integration.MyIntegration.option.shouldLog": { "type": "string", "value": "[Function]" },

        "sentry.sdk_config.normalized.sample_rate": { "type": "double", "value": 1.0 },
        "sentry.sdk_config.normalized.sample_rate.original": { "type": "string", "value": "sampleRate" },
        "sentry.sdk_config.normalized.traces_sample_rate": { "type": "double", "value": 0.2 },
        "sentry.sdk_config.normalized.traces_sample_rate.original": { "type": "string", "value": "tracesSampleRate" },
        "sentry.sdk_config.normalized.send_default_pii": { "type": "boolean", "value": true },
        "sentry.sdk_config.normalized.send_default_pii.original": { "type": "string", "value": "sendDefaultPii" },
        "sentry.sdk_config.normalized.before_send": { "type": "string", "value": "[Function]" },
        "sentry.sdk_config.normalized.before_send.original": { "type": "string", "value": "beforeSend" }
      }
    }
  ]
}
```

The key fields (see [Appendix A](#appendix-a-payload-details) for more details on serialization and normalization):

- **`sentry.sdk.packages`:** the Sentry packages that make up the SDK, the same data as `sdk.packages`
  on events today. Each entry is `<name>@<version>`, where `name` is prefixed with its package
  registry as on events (`npm:@sentry/node@10.0.0`, `pypi:sentry-sdk@2.0.0`); consumers split on the
  last `@`.
- **`sentry.sdk_config.option.<key>`:** the **effective** configuration that the SDK runs with (after
  defaults, environment variables, and derived values), under native option names. Values are reduced
  to attribute types: nested objects become dot-notation keys, callbacks become `"[Function]"`, and
  integrations are covered by the integration attributes. Option names should reflect the names a
  user would use to set the values.
- **`sentry.sdk_config.options_set_by_user`:** the option keys that the user explicitly set in
  `init()`, to tell actual usage apart from defaults. This should be best-effort - it MAY be
  incomplete if users add configuration in alternate paths or similar. If it is not possible to
  enumerate options automatically, SDKs MAY send a hand-picked subset of options here only.
- **`sentry.sdk.integrations`:** lists every registered integration. Per integration,
  `sentry.sdk_config.integration.<name>.option.<key>` holds its serialized options, and an optional
  `sentry.sdk_config.integration.<name>.applied` records whether it took effect at runtime. For
  example, the Node SDK registers Express, Fastify, Koa, and more by default, but an app typically
  uses only one.
- **`sentry.sdk_config.hash`:** a required hash of the configuration (see [Storage](#storage)).
- **`sentry.sdk_config.normalized.<key>`:** a small catalog of options under canonical cross-SDK
  names (JS `tracesSampleRate` → `traces_sample_rate`), derived by Relay.
- **`sentry.sdk_config.normalized.<key>.original`:** the name that this property is called in the `options` (JS `tracesSampleRate`)
  to allow display of the value in a way that makes sense for a user.

New attributes to add to Sentry conventions:

| Attribute                                           | Type     | Example                                                          |
| --------------------------------------------------- | -------- | ---------------------------------------------------------------- |
| `sentry.sdk.packages`                               | string[] | `["npm:@sentry/node@10.0.0"]`                                    |
| `sentry.sdk_config.version`                         | integer  | `1`                                                              |
| `sentry.sdk_config.hash`                            | string   | `"9f2c1a7e"`                                                     |
| `sentry.sdk_config.option.<key>`                    | any      | `sentry.sdk_config.option.sampleRate=1.0`                        |
| `sentry.sdk_config.options_set_by_user`             | string[] | `["dsn", "tracesSampleRate"]`                                    |
| `sentry.sdk_config.integration.<name>.applied`      | boolean  | `true`                                                           |
| `sentry.sdk_config.integration.<name>.option.<key>` | any      | `...MyIntegration.option.filter="aaa"`                           |
| `sentry.sdk_config.normalized.<key>`                | any      | `...normalized.traces_sample_rate=0.2`                           |
| `sentry.sdk_config.normalized.<key>.original`       | string   | `sentry.sdk_config.normalized.sample_rate.original="sampleRate"` |

Reused as-is: `sentry.sdk.name`, `sentry.sdk.version`, `sentry.sdk.integrations`, `sentry.release`,
`sentry.environment`, `sentry.dist`, `process.runtime.name`, `process.runtime.version`.

The design keeps SDKs simple: most SDKs can just serialize their existing finalized options object (e.g. JS
`client.getOptions()`), new options are captured automatically.
One Relay implementation avoids inconsistent mappings across SDKs, and the catalog can
change, including for stored data, without SDK releases. 

One downside of this is that converted values lose their original form: 
for example, we cannot tell whether `integrations` was passed as a function - 
this should generally only affect a small subset of options (e.g. in JS, only `integrations` and `stackParser` are affected).

Sensitive data is scrubbed primarily server-side. SDKs MAY also scrub values that they know to be
sensitive, but they do not guarantee fully scrubbed data.

## Sending

We propose to send one payload per `init()` once the configuration has
settled, because values such as `applied` are only known after `init()` returns. Each SDK MAY choose
how to wait, for example with a short debounce (e.g. 5 seconds) or a lifecycle hook. Short-lived
processes MAY flush the payload on shutdown. [Appendix B](#appendix-b-sending-and-storage-details) has the
details.

We propose to do this for all kindes of SDKs - while client SDKs will send more redundant data than server SDKs,
the overall volume will still be low compared to e.g. metrics, spans or logs, and we'll server-side dedupe the records for storage.

**Server SDKs** (Node, Python, Java, Go, …) MAY re-send it at a slow interval
(e.g. hourly) in case a send was lost, and to account for data retention dropping old records for very long-lived processes.

## Storage

Storing every payload (**Option 1**) keeps a complete history, but mostly stores duplicates at a very
high cost. We recommend **Option 2: store one record per distinct configuration**, deduplicated by
**`sentry.sdk_config.hash` (primary) + `release` + `environment` + `dist` (fallback)**.

SDKs MUST compute the hash from the serialized option and integration attributes, and MUST attach it
to every event: as the same `sentry.sdk_config.hash` attribute on spans, logs, and other items with
attributes, and in a new `sdk_config.hash` context field on errors and transactions. The
hash links each event to its exact configuration and keeps configurations that differ within one
release separate. The hash MAY be generated based off the full `attributes` hash (minus the `sentry.sdk_config.hash` attribute), 
or from a subset if that makes more sense for an SDK.

If no stored record matches an event's hash (e.g. because the payload was lost or sampled out), or
the event has no hash, correlation falls back to `release` + `environment` + `dist`, which every
event already carries. The fallback resolves only to the records of that combination and is coarse
when `release` is unset. It should use the newest matching config in this case.

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
  normalized attributes), rate limiting (own or shared category, interaction with the send cadence,
  `429`/`Retry-After` and SDK backoff), size limits (reject or truncate), data category, quota
  consumption, and billing (likely not billed like events), and outcomes for dropped items.
- **EAP storage:** a new `TraceItemType` (sentry-protos, Snuba, Relay, Sentry search). EAP items
  expire after their retention period, so long-running processes must re-send within it. EAP could
  deduplicate via a deterministic `item_id` from the hash plus a bucketed `timestamp` (as preprod
  does), to be confirmed with the EAP team. Limits on attribute count and size per item.
- **Custom filtering:** do we need SDK side filtering, e.g. `beforeSendSdkConfig`, to allow manual PII stripping?

## Out of scope

- Product features built on this data (analytics, audits, data source views, configuration history,
  configuration UI).
- Removing SDK metadata from events. Events are searchable by it, so this first requires backfilling
  it onto events from stored `sdk_config` records.

# Appendix A: Payload details

For payload fields, see [Payload](#payload).

**Serialization rules** for option and integration option attributes, which make the output
deterministic and consistent across SDKs:

1. Primitives are sent unchanged. Arrays of one primitive type stay arrays; other arrays have each
   element converted to a string by these same rules.
   a. An SDK MAY normalize specific options if it makes sense, e.g. stripping out user-specific paths, unstable options or similar.
2. Nested objects are flattened: `dataCollection: { http: { bodies: true } }` becomes
   `sentry.sdk_config.option.dataCollection.http.bodies`.
3. Functions become `"[Function]"`. SDKs MAY include the name (`"[Function: beforeSend]"`), but
   consumers must not rely on it.
4. The `integrations` option is omitted; its data is in the `sentry.sdk.integrations` attributes.
5. `null` and `undefined` values are omitted, since attributes have no null type.
6. Other non-serializable values become type markers such as `"[SomeType]"`, following the SDK's
   existing normalization convention.

**Initial normalization catalog**, maintained alongside Relay and expected to grow. `release`,
`environment`, and `dist` are not included, because they already have their own attributes.

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
  This should be best-effort, it is understood that late config changes MAY not be correctly captured.
- **Short-lived processes** (serverless, CLI) flush wherever they already flush events, and MAY reuse
  their client report flushing. If a process dies first, an equivalent instance will report.
- **Periodic re-send:** Relay cannot guarantee that a `200` response means the payload was
  persisted. To accomodate this, as well as retention period dropping config after longer time periods,
  a single lost send would leave a long-running server without stored configuration.
- **Hash:** identical configurations produce identical hashes, and any change to the options, the
  registered integrations, their options, or `applied` changes the hash. Algorithms do not need to
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
