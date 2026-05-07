- Start Date: 2026-04-28
- RFC Type: decision
- RFC PR: TBD
- RFC Status: draft
- RFC Driver: [Abdelrahman Awad](https://github.com/logaretm), [Dominik Buszowiecki](https://github.com/DominikB2014)
- RFC Approver: TBD

# Summary

Migrate web vitals (LCP, CLS, INP, FCP, TTFB) from spans to trace metrics in the Sentry JavaScript SDK. It's a multi-phase approach to ensure we end up with single data source for web vitals and avoid introducing any billing changes for our customers.

Relay double-writes web vital spans as trace metrics (free) for a period of time (detailed below), then dashboards cut over to metrics-only queries. New major SDK releases emit web vitals as trace metrics natively, billed as metrics. Finally, Relay stops double writing and only converts spans from older SDKs to metrics, billed as spans, no customer sees a billing change at any phase.

**Suggested timeline:**

The timeline here isn't sequential, as the work items can happen in parallel. But the over all goals to be met are dependent on the double-writing period duration.

Having said that, these are the work items with their own expected timelines:

- Double-write: 6 months, should be enough to build sufficient metrics history before dashboard cutover.
- Dashboard and product cutover: Given enough metrics has been collected from the double-write period, we can cut over to metrics-only queries.
- Single-write conversion: After the double-write period, we can stop double-writing and only convert spans from older SDKs to metrics.
- JS SDK emits web vitals as metrics natively: It can happen in the interim of the double-write, and it would reduce the cost of the double-write period.

# Motivation

Web vitals are measurements, not execution traces. The current span-based implementation carries structural overhead that doesn't serve the data:

- **Span overhead.** Current default browser tracing emits INP as a standalone web vital span and keeps LCP, CLS, FCP, and TTFB on the pageload transaction. With span streaming enabled, LCP and CLS also become web vital spans. The pageload span itself remains either way, so metrics only eliminate standalone web vital spans, not the pageload carrier.
- **Cost to customers.** Per-item, metrics are ~3.8× cheaper than spans ($0.53/1M vs $2.00/1M). However, the migration adds items: current default has 2 spans per pageload (INP + pageload), v11 has 4 (INP + LCP + CLS + pageload), while metrics always produce 5 items + 1 pageload span. The net cost depends on sample rate. At `sampleRate: 1.0`, v11 with metrics (~$450/mo at 100M pageloads) is 38% cheaper than v11 spans ($730) but 22% more expensive than current default spans ($370). At low sample rates (≤0.1), metrics cost more in absolute terms (~$270 vs $30-$70) because they are unsampled — but they capture 100% of web vitals vs 10%. See the cost comparison table below for the full matrix.
- **Metrics use-cases.** The browser does not have any OOTB metrics use-cases. By moving web vitals to metrics, it encourages metric adoption by customers.
- **Transaction+Span Schema Deprecation.** The v2 span protocol is in the works and will deprecate the transaction+span schema (v1). Span streaming becomes the default in v11, so this RFC has to account for both the current v1 default and the v11 streamed-span default.
- **Metrics are not SDK-sampled.** Metrics are not subject to trace sampling at either the SDK level. This means trace metrics capture 100% of emissions while still carrying `trace_id` for correlation. This works well with the cost model.


All costs below are Team PAYG at $0.0000020/span (≤100M), $0.0000018/span (>100M), $0.50/GB metrics. 5M spans and 5GB metrics included free. 100M actual pageloads/month.

**Items per pageload:**
- Current default: 1 standalone web vital span (INP) + 1 pageload span = 2 spans
- v11 streamed: 3 standalone web vital spans (INP + LCP + CLS) + 1 pageload span = 4 spans
- v11 with metrics: 1 pageload span (sampled) + 5 metrics (unsampled). Metrics are not subject to `tracesSampleRate`.

| Mode | `sampleRate: 1.0` | `sampleRate: 0.25` | `sampleRate: 0.1` |
|---|---|---|---|
| **Current default** | **~$370** (100%) | **~$90** (25%) | **~$30** (10%) |
| **v11 streamed spans** | **~$730** (100%) | **~$190** (25%) | **~$70** (10%) |
| **v11 with metrics** | **~$450** (100%) | **~$300** (100%) | **~$270** (100%) |

_How the "v11 with metrics" row is calculated: metrics cost is fixed at ~$260 (500M items × ~1,050B = ~525 GB, 5 GB free, 520 GB × $0.50). The pageload span still exists and is sampled, adding ~$190 at 1.0, ~$40 at 0.25, ~$10 at 0.1. Total = metrics + pageload spans._

**Key observations:**
- At `sampleRate: 1.0`, metrics (~$450) are 38% cheaper than v11 streamed spans ($730) but 22% more expensive than current default ($370). The v11 span doubling (200M → 400M) is the main cost driver that metrics avoid.
- At `sampleRate: 0.25`, metrics (~$300) cost more than either span mode ($90 / $190) in absolute terms, but capture 100% of web vitals vs 25%.
- At `sampleRate: 0.1`, metrics (~$270) cost 4-9× more than spans ($30 / $70), but capture 10× the data. Customers at low sample rates chose that rate to save money — metrics shift web vitals to 100% coverage at a fixed cost regardless of sample rate.
- The pageload span is not eliminated in any scenario. It continues to carry navigation timing, resource spans, and other non-vital data.

# Background

## Current state

Web vitals are emitted via two code paths in the browser SDK, depending on SDK version and span streaming:

### Transaction+span schema (v1, current default, will be deprecated)

Current default v1 behavior sends two relevant spans for the page: the pageload transaction and the INP standalone web vital span. LCP, CLS, FCP, and TTFB are measurements on the pageload transaction unless the standalone LCP/CLS experiments are enabled.

Legacy or experimental v1 standalone LCP/CLS spans use `span.addEvent()` to attach the vital value as a measurement:

```
Span {
  op: "ui.webvital.lcp",
  origin: "auto.http.browser.lcp",
  exclusive_time: 0,
  start_timestamp == timestamp,  // zero duration
  attributes: {
    "lcp.element": "body > img",
    "lcp.url": "https://example.com/img.png",
    "lcp.size": 28500,
    "lcp.loadTime": 1234.5,
    "lcp.renderTime": 1234.5,
    "sentry.pageload.span_id": "...",
    "sentry.report_event": "pagehide",
  },
  events: [{
    name: "lcp",
    attributes: {
      "sentry.measurement_value": 1234.5,   // the actual LCP value
      "sentry.measurement_unit": "millisecond",
    }
  }]
}
```

For v1 standalone web vital spans, the vital value lives inside a span event using `sentry.measurement_value` / `sentry.measurement_unit`. Attribute names use flat keys like `lcp.element`, `lcp.size`. For the current default pageload path, LCP/CLS/FCP/TTFB values live in `event.measurements` on the pageload transaction.

### Streamed spans (v2, already implemented)

Streamed spans embed the vital value directly as a span attribute:

```
Span {
  op: "ui.webvital.lcp",
  origin: "auto.http.browser.lcp",
  exclusive_time: 0,
  attributes: {
    "browser.web_vital.lcp.value": 1234.5,    // value is a direct attribute
    "browser.web_vital.lcp.element": "body > img",
    "browser.web_vital.lcp.url": "https://example.com/img.png",
    "browser.web_vital.lcp.size": 28500,
    "browser.web_vital.lcp.load_time": 1234.5,
    "browser.web_vital.lcp.render_time": 1234.5,
    "sentry.transaction": "/my/page",
    "sentry.pageload.span_id": "...",
    "user_agent.original": "Mozilla/5.0 ...",
  }
}
```

Key differences from v1: the value is a first-class attribute (`browser.web_vital.{vital}.value`) instead of nested in a span event. Attribute names use the `browser.web_vital.*` namespace instead of flat `lcp.*` keys. The `sentry.transaction` route name and `user_agent.original` are included directly.

INP uses `ui.interaction.{click,hover,drag,press}` as the op (not `ui.webvital.inp`). FCP and TTFB do not have dedicated streamed spans. In streamed mode they are attributes on the pageload span; in non-streamed mode they are measurements on the pageload transaction.

## Payload size comparison

Measured from real SDK output (streamed span mode, realistic attributes including release, environment, user agent, route name, LCP element tree, CLS sources). Both span and metric carry the exact same domain attributes — the only differences are the envelope structural fields:

- **Span has, metric doesn't (top-level):** `span_id`, `parent_span_id`, `start_timestamp`, `end_timestamp`, `is_segment`, `status`, `links`
- **Span has, metric doesn't (attributes):** `sentry.segment.name`, `sentry.segment.id`
- **Metric has, span doesn't (top-level):** `timestamp`, `type`, `unit`, `value`
- **Metric has, span doesn't (attributes):** `sentry.timestamp.sequence`

| Item | As Span | As Metric | Delta |
|---|---|---|---|
| LCP | 1,874 B | 1,634 B | -240 B (12.8%) |
| CLS | 1,552 B | 1,324 B | -228 B (14.7%) |
| INP | 1,276 B | 1,063 B | -213 B (16.7%) |
| TTFB | (on pageload) | 651 B | +651 B |
| FCP | (on pageload) | 580 B | +580 B |
| Pageload span (with vital attrs) | 1,532 B | 1,274 B (without) | -258 B |
| **Total per pageload** | **6,234 B** | **6,526 B** | **+292 B (4.7% more)** |

Per-item, metrics are ~213-240 B (13-17%) smaller than the equivalent span because they drop span structural fields and `sentry.segment.*` attributes. However, the total per-pageload overhead is **slightly larger** with metrics because FCP and TTFB, which currently ride free as attributes on the pageload span (~258 B combined), become standalone metric items (~1,231 B combined). The per-item savings on LCP/CLS/INP (~681 B) plus the pageload span shrinkage (~258 B) don't overcome the new standalone TTFB+FCP items.

The cost argument is not about bytes per pageload — it's about billing category and coverage. Metrics are billed at $0.50/GB vs per-span pricing, and are not SDK-sampled, so they capture 100% of emissions at any `tracesSampleRate`.

This is not straightforward to calculate because there are two ratios:

- Current default: 2 relevant spans are sent (pageload + INP), but only 1 standalone web vital span is eliminated. The migration produces 5 metrics per pageload.
- Streamed spans / v11 default: 4 relevant spans are sent (pageload + INP + LCP + CLS), but only 3 standalone web vital spans are eliminated. The migration still produces 5 metrics per pageload.

# Supporting Data

## Observed volume (warehouse data, April 2026)

Web vital spans are a significant volume category across a large number of organizations. The conversion is not 1:1, and the ratio depends on whether the SDK is using the current default behavior or streamed spans. Current default SDKs mostly produce INP standalone spans plus pageload measurements; streamed spans produce LCP, CLS, and INP as standalone spans plus FCP/TTFB on the pageload.

Volume is declining MoM (~6-10%) while org count is growing. Per-org standalone web-vital emission is shrinking, consistent with SDK-side sampling improvements in newer versions.

**95–96% of volume** flows through `auto.ui.browser.metrics` (the combined origin used by newer SDKs). Only INP consistently uses a dedicated origin (`auto.http.browser.inp`, ~4–5%). Dedicated `.lcp` / `.cls` origins are <0.1%.

## SDK version distribution (last 30 days)

| SDK major | % of volume |
|---|---|
| v10 (current) | 46% |
| v9 | 19% |
| v8 | 19% |
| v7 | 10% |
| Unknown | ~5% |
| v6 and older | ~1% |

**Legacy tail implication:** 48% of web vital span volume comes from pre-v10 SDKs. v7 at 10% is non-trivial and likely sticky (pinned SDKs, older customers). Relay's span-to-metric conversion is not a short-term bridge and needs to be robust and long-lived.

## Pricing

Confirmed with product/billing, April 2026:

- **Spans (Team PAYG):** $0.0000020/span (5M–100M), $0.0000018/span (>100M). 5M included.
- **Trace Metrics (post-GA):** $0.50/GB. 5GB included. Confirmed at log parity pricing.
- **Per-emission cost:** Spans ~$2.00/1M. Metrics at $0.50/GB with measured avg ~1,050B/item ~$0.53/1M.

## Cost projection

See the cost comparison table above. Summary of item count changes per pageload:

| Mode | Spans per pageload | Metrics per pageload | Net item change |
|---|---|---|---|
| Current default → metrics | 2 (INP + pageload) → 1 (pageload remains) | 0 → 5 | -1 span, +5 metrics |
| v11 streamed → metrics | 4 (INP + LCP + CLS + pageload) → 1 (pageload remains) | 0 → 5 | -3 spans, +5 metrics |

FCP and TTFB currently ride for free on the pageload span (~258 B combined as attributes). As metrics they become separate billable items (~651 B and ~580 B respectively). This makes total per-pageload bytes ~4.7% larger with metrics: the per-item savings on LCP/CLS/INP (~681 B) plus pageload span shrinkage (~258 B) don't overcome FCP and TTFB becoming standalone items (~1,231 B). The pageload span itself continues to exist; we extract measurements from it, not replace it.

Note: these numbers reflect already-sampled volume. The true event count (pre-sampling) would be significantly higher.

# Proposed Plan

We follow a phased rollout approach to lazily migrate web vitals to trace metrics, not retroactively.

## Double-write

Relay converts incoming web vital spans to trace metrics. Both the original span and the derived metric are written. Those metrics are **free** (not billed) during this phase. This builds a metrics backlog for the dashboard cutover and allows validation.

During that period, the team validates that metrics and spans agree and that they can drive the same insights and dashboards over the same period.

### How long to double-write?

It depends on how much we are willing to compromise and how much cost are we willing to absorb.

Suggested duration: 6 months. It's a significant amount of time, but it's necessary to build sufficient metrics history before dashboard cutover. At the end of the double-write period, we should have 6 months of metrics data available and won't need to compromise and have mixed span/metric data in the web vital/performance score dashboards.

We can do shorter periods, but that creates gaps around the switchover point. For example, if we do a 30 day double-write, that means when dashboards cutover to metrics, customers won't be able to query any web vitals data >30 days old. Unless we allow dashboard to query mixed data from spans and metrics, which is not ideal.

The longer the double-write period, the less we need to compromise and the more we can keep the data consistent.

### Relay conversion

The conversion hooks into Relay's span processing pipeline after normalization, gated on an org-level feature flag (`Feature::WebVitalSpanToMetricConversion`).

These tables illustrate which metrics to be derived from which spans and how to map the attributes.

**v1 detection (current default + legacy/experimental standalone spans):**

_Note: v1 spans send out non-sentry standard attributes that carry additional information about the web vital, these need to be mapped to the new standardized attributes when available._

| Vital | Match | Value source | Unit | Attributes |
|---|---|---|---|---|
| LCP | `span.op == "pageload"` + `measurements.lcp` present, or legacy/experimental `span.op == "ui.webvital.lcp"` | Pageload: `span.measurements["lcp"].value`; standalone: `span.events[0].attributes["sentry.measurement_value"]` | `millisecond` | Pageload `lcp.*` / standalone `lcp.*` -> `browser.web_vital.lcp.*` |
| CLS | `span.op == "pageload"` + `measurements.cls` present, or legacy/experimental `span.op == "ui.webvital.cls"` | Pageload: `span.measurements["cls"].value`; standalone: `span.events[0].attributes["sentry.measurement_value"]` | `none` | Pageload `cls.*` / standalone `cls.*` -> `browser.web_vital.cls.*` |
| INP | `span.op == "ui.interaction.{click,hover,drag,press}"` + event named `inp` | `span.events[0].attributes["sentry.measurement_value"]` | `millisecond` | _(none)_ |
| FCP | `span.op == "pageload"` + `measurements.fcp` present | `span.measurements["fcp"].value` | `millisecond` | _(none)_ |
| TTFB | `span.op == "pageload"` + `measurements.ttfb` present | `span.measurements["ttfb"].value` | `millisecond` | `ttfb.*` -> `browser.web_vital.ttfb.*` |

**v2 detection (streamed spans / v11 default):**

_Note: Span streaming is the v11 default. This changes the eliminated span count from 1 standalone web vital span per pageload today to 3 standalone web vital spans per pageload in v11._

| Vital | Match | Value source | Unit | Attributes |
|---|---|---|---|---|
| LCP | `span.op == "ui.webvital.lcp"` | `span.attributes["browser.web_vital.lcp.value"]` | `millisecond` | `browser.web_vital.lcp.element`, `.id`, `.url`, `.size`, `.load_time`, `.render_time` |
| CLS | `span.op == "ui.webvital.cls"` | `span.attributes["browser.web_vital.cls.value"]` | `none` | `browser.web_vital.cls.source.1`, `.source.2` |
| INP | `span.op == "ui.interaction.{click,hover,drag,press}"` + `browser.web_vital.inp.value` attribute present | `span.attributes["browser.web_vital.inp.value"]` | `millisecond` | _(none)_ |
| FCP | `span.op == "pageload"` + `browser.web_vital.fcp.value` attribute present | `span.attributes["browser.web_vital.fcp.value"]` | `millisecond` | _(none)_ |
| TTFB | `span.op == "pageload"` + `browser.web_vital.ttfb.value` attribute present | `span.attributes["browser.web_vital.ttfb.value"]` | `millisecond` | `browser.web_vital.ttfb.request_time` |

**Output metric shape:**

```
TraceMetric {
  name: "browser.{vital}",          // e.g. "browser.lcp"
  type: "distribution",
  unit: "millisecond",              // "none" for CLS
  value: <extracted value>,
  trace_id: span.trace_id,
  span_id: span.span_id,
  timestamp: span.timestamp,
  attributes: {
    "sentry.transaction": ...,
    "user_agent.original": ...,
    "sentry.pageload.span_id": ...,
    // Detail attributes normalized to v2 namespace
    "browser.web_vital.{vital}.*": ...,
    // Provenance
    "sentry.metric.source": "span",
  }
}
```

Whether these metrics are queryable by the customer during the migration is not yet decided. On one hand, it might cause confusion, on the other hand, it might be useful to have the metrics available for the customer to query during the migration.

### Making derived metrics free during double-write

During this period, the original span is already billed. The derived metric's billing outcome is suppressed by setting. The outcomes pipeline should already support per-item suppression.

## Dashboard cutover

Dashboards switch to metrics-only queries. Given enough metrics has been collected from the double-write period, we can cut over to metrics-only queries.

I checked if we can still do the same insights and dashboards with metrics only. Because metrics are correlated to spans, we can highlight the timing of the web vital on the span timeline by checking for the correlated web vital metrics for that span/trace. So I see no reason why we can't do the same insights and dashboards with metrics only.

## Disable double-write, single-write conversion

Double-write stops. Relay stops writing the original span for web vitals but continues converting web vital spans from older SDKs to metrics (single-write). The original span is no longer stored.

The goal is to converge on a single data source (metrics) for web vitals. Maintaining two parallel data paths (spans + metrics) indefinitely means two sets of queries, two dashboard implementations, and two mental models for the same data. Single-write eliminates that.

Performance scores (`score.lcp`, `score.cls`, etc.) are currently computed by Relay from raw vital values on the span. Once spans are dropped, score computation moves to the metrics pipeline, deriving scores from the same raw values on the trace metric instead.

At this point we stop absorbing the cost of the derived metrics.

### What stops working

When spans stop being written, anything querying the spans dataset for web vitals will silently stop returning data:

A non-trivial number of active alerts, saved Discover queries, and custom dashboard widgets reference web vital span measurements across a significant number of orgs. These won't error, they'll just quietly stop producing data. Customers may not notice immediately. We have a couple of options here:

- **Migrate alerts and Discover queries to the metrics dataset.** Auto-migrate known patterns (e.g. `measurements.lcp` → `browser.lcp`) or provide migration tooling.
- **Gate the single-write conversion on a feature flag.** Keep double-write running longer to give customers time to migrate their alerts and Discover queries to the metrics dataset before spans are dropped.

The longer the double-write period is, the more time we have to migrate the alerts and Discover queries to the metrics dataset.

### Provenance-based billing

Each converted metric carries a provenance or a meta attribute that determines how it's billed:

| Attribute | Value | Meaning | Billed as |
|---|---|---|---|
| `sentry.metric.source` | `"span"` | Relay converted this from a web vital span | `DataCategory::Span` |
| `sentry.metric.source` | `"sdk"` or missing | SDK emitted this natively as a metric | `DataCategory::TraceMetric` |

Relay sets `sentry.metric.source: "span"` on all converted metrics. The SDK sets `sentry.metric.source: "sdk"` (or omits the attribute, defaulting to `"sdk"`) on natively emitted metrics.

This ensures:

- Old SDKs sending spans -> Relay converts -> billed as `Span` -> no billing change
- New SDKs sending metrics -> billed as `TraceMetric` -> customer opted in via upgrade

**Billing caveat for measurements that currently ride free on the pageload span:** The set of vitals that are free today depends on the SDK code path. With the current default (v1, no span streaming), LCP, CLS, FCP, and TTFB are all measurements on the pageload transaction — only INP is a standalone billed span. With streamed spans (v11 default), LCP and CLS become standalone billed spans, so only FCP and TTFB remain free on the pageload span. When Relay extracts free-riding measurements as separate metrics, naively billing those as `DataCategory::Span` would charge customers for items they were not paying for before (4 items for v1 SDKs, 2 items for v2/streamed SDKs). To preserve the "no billing change" guarantee, Relay must suppress billing on any metric derived from a measurement that was not a standalone span. In practice: for v1 SDK traffic, suppress billing on LCP, CLS, FCP, and TTFB metrics derived from the pageload span; for v2/streamed SDK traffic, suppress billing on FCP and TTFB only. Only new SDKs emitting all 5 vitals as native metrics (`sentry.metric.source: "sdk"`) should be billed as `DataCategory::TraceMetric`.

## SDK emits web vitals as metrics natively (v11)

This work item is independent of the double-write period. Span streaming is the v11 default, so v11 emits LCP, CLS, and INP as web vital spans unless the SDK changes to emit web vitals as metrics natively.

Exact details of the SDK change are TBD, since we still have to decide how much friction we want to introduce to the SDK upgrade process. This also has a span-count implication: before v11/current default, switching to metrics eliminates the INP standalone span while keeping pageload; in v11, switching to metrics eliminates INP, LCP, and CLS standalone spans while keeping pageload. Depending on the timing of the metrics migration relative to the v11 release, we either:

- **Metrics-native SDK work ships after v11 span streaming is already default**: v11 emits LCP, CLS, and INP as streamed spans until the metrics-native change lands. After that, the SDK emits web vitals only as metrics natively.
- **Metrics-native SDK work ships with v11**: The SDK can emit web vitals only as metrics natively from the first v11 release. This avoids introducing the streamed LCP/CLS/INP span shape as the steady-state default for web vitals.

Ideally the second scenario is the best case. This still doesn't change the double-write duration, but it will reduce the cost we absorb during the double-write period. Customers upgrading to v11 will start paying for web vitals as metrics (billed as `DataCategory::TraceMetric`) once the metrics-native SDK behavior ships, which is expected since they opted into the new SDK version.

### Billing summary

| Phase | Old SDKs v1 (spans, no streaming) | Old SDKs v2 (streamed spans) | New SDKs (v11+, metrics) |
|---|---|---|---|
| Double-write | Billed as spans, derived metrics free (outcome suppressed). LCP/CLS/FCP/TTFB derived metrics also free (were free measurements on pageload). | Billed as spans, derived metrics free (outcome suppressed). FCP/TTFB derived metrics also free (were free measurements on pageload). | N/A |
| Post-double-write | Relay converts to metrics, `sentry.metric.source: "span"` → billed as `DataCategory::Span`. LCP/CLS/FCP/TTFB billing suppressed (were previously free on pageload span). | Relay converts to metrics, `sentry.metric.source: "span"` → billed as `DataCategory::Span`. FCP/TTFB billing suppressed (were previously free on pageload span). | N/A |
| v11+ | Relay converts to metrics, billed as spans. LCP/CLS/FCP/TTFB billing suppressed. | Relay converts to metrics, billed as spans. FCP/TTFB billing suppressed. | `sentry.metric.source: "sdk"` → all 5 vitals billed as `DataCategory::TraceMetric` |

No customer experiences an unexpected billing change at any phase.

# Alternatives considered

## Relay single-write with query-side fallback

Instead of double-writing, Relay converts web vital spans to metrics from day one (single-write only, no span is stored). The query layer reads both the spans dataset (for historical data predating the conversion) and the metrics dataset, merging results during the transition. After spans age out of retention (~13 months), dashboards switch to metrics-only queries.

**Pros:**

- No double-write cost absorbed by Sentry
- No long double-write period needed to build metrics history
- Converges to a single dataset (metrics) once old spans age out of retention
- Old SDKs are still covered since Relay converts their spans to metrics

**Cons:**

- Query layer must merge results from two datasets with different schemas, which adds complexity to every dashboard, alert, and Discover query that touches web vitals
- Cross-dataset queries may have different performance characteristics and edge cases (e.g. different retention, downsampling behavior)
- Dual-query logic needs to be maintained for ~13 months until historical spans age out

This approach trades double-write cost for query-layer complexity. It may be simpler overall and is worth exploring with the databrowsing team.

## SDK-only, query-side fallback, no Relay involvement

The SDK ships metrics natively in v11 as a breaking change. Customers upgrading are expected to understand the pricing implications. No Relay conversion, no double-write. Dashboards query both the spans and metrics datasets.

**Pros:**

- No double-write cost absorbed by Sentry
- No Relay conversion logic to build or maintain
- Simpler overall: SDK emits metrics, dashboards query both datasets, done

**Cons:**

- Query layer must merge results from two datasets with different schemas
- Dual-query logic may need to be maintained indefinitely. Pre-v11 SDKs (currently 48% of volume) will continue sending spans, and many customers will never upgrade. The query layer must support both datasets as long as old SDKs are in the wild
- Old SDKs (pre-v11) never produce metrics, so their web vitals are only visible through the span query path. There is no single dataset that contains all web vital data
- No convergence to a single data source without Relay conversion

## Do nothing

Keep web vitals as spans. No migration, no metrics conversion.

**Pros:**

- Nothing to do.

**Cons:**

- The browser platform has no metrics use-cases, limiting customer adoption of the metrics product.
- Customers may lose out on the reduced cost of web vitals as metrics, especially if they adopt soft navigation.  

# Unresolved questions

- **Downsampling model.** How does the metrics backend downsample beyond 30 days? Pre-aggregated percentile rollups (lossy for cross-window percentile queries) or retained distributions at lower time granularity (lossless)? This determines whether "p75 LCP over 90 days" on the metrics dashboard is accurate or approximate.
- **Early adopters of v11.** How do we handle the early adopters of v11? Do we prepare the metric dashboards for them and show it once they have enough metrics data?
