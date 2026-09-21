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

<!-- TODO: Propose one primary option and alternatives. Open questions to work through here:
- What exactly do we capture? (raw init options vs. effective/normalized config)
- How do we avoid capturing sensitive values (tokens, DSNs, PII in beforeSend, etc.)?
- How is it transported? (new envelope item type vs. attached to existing payloads vs.
  separate periodic "SDK config" report)
- How often is it sent? (once per init, on change, periodically)
- Where and how is it stored and deduplicated server-side?
- How do we represent non-serializable options (functions like beforeSend, integrations)?
- Cross-SDK consistency: this starts with JS, but the format should generalize. -->

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
