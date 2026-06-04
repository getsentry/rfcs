- Start Date: 2026-04-28
- RFC Type: decision
- RFC PR: TBD
- RFC Status: draft
- RFC Driver: [Abdelrahman Awad](https://github.com/logaretm), [Dominik Buszowiecki](https://github.com/DominikB2014)
- RFC Approver: TBD

# Summary

Migrate web vitals (LCP, CLS, INP, FCP, TTFB) from spans to trace metrics in the Sentry JavaScript SDK.

Relay double-writes web vital spans as trace metrics (free) for a period of time (detailed below), then dashboards cut over to metrics-only queries. New major SDK releases emit web vitals as trace metrics natively, billed as metrics. Finally, Relay stops double writing and only converts spans from older SDKs to metrics. Billing details are covered [below](#cost-comparison) as we have some caveats to consider.

**Suggested timeline:**

The timeline here isn't sequential, as the work items can happen in parallel. But the over all goals to be met are dependent on the double-writing period duration.

Having said that, these are the work items with their own expected timelines:

- Double-write: 6 months, should be enough to build sufficient metrics history before dashboard cutover.
- Dashboard and product cutover: Given enough metrics has been collected from the double-write period, we can cut over to metrics-only queries.
- Single-write conversion: After the double-write period, we can stop double-writing and only convert spans from older SDKs to metrics.
- JS SDK emits web vitals as metrics natively: It can happen in the interim of the double-write, and it would reduce the cost of the double-write period.

# Motivation

Web vitals are measurements, not execution traces. The current span-based implementation carries structural overhead that doesn't serve the data:

- **Span overhead.** Current default browser tracing emits INP as a standalone web vital span and keeps LCP, CLS, FCP, and TTFB on the pageload transaction. With span streaming enabled, LCP and CLS also become web vital spans. The pageload span itself remains either way, so metrics only eliminate standalone web vital spans, not the pageload carrier. The savings depend on whether span streaming is enabled or not.
- **Cost to customers.** Metrics are cheaper per item, but produce 5 unsampled metric items per pageload while the pageload span remains. For some customers, metrics will be cheaper at a high enough sample rate (~34%) but more expensive than sampled spans at low sample rates. The tradeoff is cost vs 100% web vital coverage.
- **Metrics use-cases.** The browser does not have any OOTB metrics use-cases. By moving web vitals to metrics, it encourages metric adoption by customers.
- **Metrics are not SDK-sampled.** Metrics are not subject to trace sampling at either the SDK level. This means trace metrics capture 100% of emissions while still carrying `trace_id` for correlation.
- **Metrics lifecycle.** Metrics can be collected and sent at any time while still being trace connected. This can be critical for upcoming web platform features, specifically [Soft Navigation Web Vitals](https://developer.chrome.com/docs/web-platform/soft-navigations).

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

Replacing web vital spans with metrics here means we eliminate just the INP standalone span. But produce 5 metrics per pageload. So -1 span, +5 metrics.

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

Replacing web vital spans with metrics here means we eliminate the INP standalone span. But produce 5 metrics per pageload. So -1 spans, +5 metrics regardless of the span streaming mode.

## Payload size comparison

Measured from real SDK output. Both span and metric carry most of the same domain attributes, the only differences are the envelope structural fields:

- **Span has, metric doesn't (top-level):** `span_id`, `parent_span_id`, `start_timestamp`, `end_timestamp`, `is_segment`, `status`, `links`
- **Span has, metric doesn't (attributes):** `sentry.segment.name`, `sentry.segment.id`
- **Metric has, span doesn't (top-level):** `timestamp`, `type`, `unit`, `value`
- **Metric has, span doesn't (attributes):** `sentry.timestamp.sequence`

Keep in mind that this doesn't use the actual stored size, it uses the network bandwidth byte size.

| Item                             | As Span       | As Metric         | Delta                  |
| -------------------------------- | ------------- | ----------------- | ---------------------- |
| LCP                              | 1,874 B       | 1,634 B           | -240 B (12.8%)         |
| CLS                              | 1,552 B       | 1,324 B           | -228 B (14.7%)         |
| INP                              | 1,276 B       | 1,063 B           | -213 B (16.7%)         |
| TTFB                             | (on pageload) | 651 B             | +651 B                 |
| FCP                              | (on pageload) | 580 B             | +580 B                 |
| Pageload span (with vital attrs) | 1,532 B       | 1,274 B (without) | -258 B                 |
| **Total per pageload**           | **6,234 B**   | **6,526 B**       | **+292 B (4.7% more)** |

Per-item, metrics are ~213-240 B (13-17%) smaller than the equivalent span because they drop span structural fields. However, the total per-pageload overhead is **slightly larger** with metrics because FCP and TTFB, which currently ride free as attributes on the pageload span (~258 B combined), become standalone metric items (~1,231 B combined). The per-item savings on LCP/CLS/INP (~681 B) plus the pageload span shrinkage (~258 B) don't overcome the new standalone TTFB+FCP items.

The cost argument is not about bytes per pageload, it's about billing category and coverage. Metrics are billed at $0.50/GB vs per-span pricing, and are not SDK-sampled, so they capture 100% of emissions at any `tracesSampleRate`.

To calculate the span to metric ratio here, we have 2 relevant spans that are sent (pageload + INP), but only 1 standalone web vital span is eliminated. The migration produces 5 metrics per pageload. So at the same sample rate they are 5:1 (5 spans per pageload vs 1 metric per pageload), this can be skewed further by the user's own sample rate.

# Supporting Data

## Cost comparison

The cost analysis can be found in the [appendix](#appendix).

## Observed volume (warehouse data, April 2026)

Web vital spans are a significant volume category across a large number of organizations. The conversion is not 1:1, and the ratio depends on whether the SDK is using the current default behavior or streamed spans. Current default SDKs mostly produce INP standalone spans plus pageload measurements; streamed spans produce LCP, CLS, and INP as standalone spans plus FCP/TTFB on the pageload.

**95–96% of volume** flows through `auto.ui.browser.metrics` (the combined origin used by newer SDKs). Only INP consistently uses a dedicated origin (`auto.http.browser.inp`, ~4–5%). Dedicated `.lcp` / `.cls` origins are <0.1%.

## SDK version distribution (last 30 days)

| SDK major     | % of volume |
| ------------- | ----------- |
| v10 (current) | 46%         |
| v9            | 19%         |
| v8            | 19%         |
| v7            | 10%         |
| Unknown       | ~5%         |
| v6 and older  | ~1%         |

**Legacy tail implication:** 48% of web vital span volume comes from pre-v10 SDKs. v7 at 10% is non-trivial and likely sticky (pinned SDKs, older customers). Relay's span-to-metric conversion is not a short-term bridge and needs to be robust and long-lived, whether we decide to retire double-writing early or not. The conversion logic will exist for a few years.

## Pricing

Confirmed with product/billing, April 2026:

- **Spans (Team PAYG):** $0.0000020/span (5M–100M), $0.0000018/span (>100M). 5M included.
- **Trace Metrics (post-GA):** $0.50/GB. 5GB included. Confirmed at log parity pricing.
- **Per-emission cost:** Spans ~$2.00/1M. Metrics at $0.50/GB with measured avg ~1,050B/item ~$0.53/1M.

# Proposed Plan

We follow a phased rollout approach to lazily migrate web vitals to trace metrics, not retroactively.

## Double-write

Relay converts incoming web vital spans to trace metrics. Both the original span and the derived metric are written. Those metrics are **free** (not billed) during this phase. This builds a metrics backlog for the dashboard cutover and allows validation.

During that period, the team validates that metrics and spans agree and that they can drive the same insights and dashboards over the same period.

### How long to double-write?

It depends on how much we are willing to compromise and how much cost are we willing to absorb.

Suggested duration: 6 months. It's a significant amount of time, but it could be necessary to build sufficient metrics history before dashboard cutover. At the end of the double-write period, we should have 6 months of metrics data available which makes a hard cutover possible.

We can do shorter periods, but that creates gaps around the dashboard cutover point. For example, if we do a 30 day double-write, that means when dashboards cutover to metrics, customers won't be able to query any web vitals data >30 days old. Unless we allow dashboard to query mixed data from spans and metrics, which is not ideal.

The longer the double-write period, the less we need to compromise and the more we can keep the data consistent. We can also consider keeping it on forever if the costs are not too high. There is an estimation for that in the [appendix](#appendix).

### Relay conversion

The conversion hooks into Relay's span processing pipeline after normalization. These tables illustrate which metrics to be derived from which spans and how to map the attributes.

**v1 detection (current default + legacy/experimental standalone spans):**

_Note: v1 spans send out non-sentry standard attributes that carry additional information about the web vital, these need to be mapped to the new standardized attributes when available._

| Vital | Match                                                                                                       | Metric name              | Value source                                                                                                    | Unit          | Attributes                                                         |
| ----- | ----------------------------------------------------------------------------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------ |
| LCP   | `span.op == "pageload"` + `measurements.lcp` present, or legacy/experimental `span.op == "ui.webvital.lcp"` | `browser.web_vital.lcp`  | Pageload: `span.measurements["lcp"].value`; standalone: `span.events[0].attributes["sentry.measurement_value"]` | `millisecond` | Pageload `lcp.*` / standalone `lcp.*` -> `browser.web_vital.lcp.*` |
| CLS   | `span.op == "pageload"` + `measurements.cls` present, or legacy/experimental `span.op == "ui.webvital.cls"` | `browser.web_vital.cls`  | Pageload: `span.measurements["cls"].value`; standalone: `span.events[0].attributes["sentry.measurement_value"]` | `none`        | Pageload `cls.*` / standalone `cls.*` -> `browser.web_vital.cls.*` |
| INP   | `span.op == "ui.interaction.{click,hover,drag,press}"` + event named `inp`                                  | `browser.web_vital.inp`  | `span.events[0].attributes["sentry.measurement_value"]`                                                         | `millisecond` | _(none)_                                                           |
| FCP   | `span.op == "pageload"` + `measurements.fcp` present                                                        | `browser.web_vital.fcp`  | `span.measurements["fcp"].value`                                                                                | `millisecond` | _(none)_                                                           |
| TTFB  | `span.op == "pageload"` + `measurements.ttfb` present                                                       | `browser.web_vital.ttfb` | `span.measurements["ttfb"].value`                                                                               | `millisecond` | `ttfb.*` -> `browser.web_vital.ttfb.*`                             |

**v2 detection (streamed spans):**

| Vital | Match                                                                                                    | Metric name              | Value source                                      | Unit          | Attributes                                                                            |
| ----- | -------------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------- |
| LCP   | `span.op == "pageload"` + `browser.web_vital.lcp.value` attribute present                                | `browser.web_vital.lcp`  | `span.attributes["browser.web_vital.lcp.value"]`  | `millisecond` | `browser.web_vital.lcp.element`, `.id`, `.url`, `.size`, `.load_time`, `.render_time` |
| CLS   | `span.op == "pageload"` + `browser.web_vital.cls.value` attribute present                                | `browser.web_vital.cls`  | `span.attributes["browser.web_vital.cls.value"]`  | `none`        | `browser.web_vital.cls.source.1`, `.source.2`                                         |
| INP   | `span.op == "ui.interaction.{click,hover,drag,press}"` + `browser.web_vital.inp.value` attribute present | `browser.web_vital.inp`  | `span.attributes["browser.web_vital.inp.value"]`  | `millisecond` | _(none)_                                                                              |
| FCP   | `span.op == "pageload"` + `browser.web_vital.fcp.value` attribute present                                | `browser.web_vital.fcp`  | `span.attributes["browser.web_vital.fcp.value"]`  | `millisecond` | _(none)_                                                                              |
| TTFB  | `span.op == "pageload"` + `browser.web_vital.ttfb.value` attribute present                               | `browser.web_vital.ttfb` | `span.attributes["browser.web_vital.ttfb.value"]` | `millisecond` | `browser.web_vital.ttfb.request_time`                                                 |

**Output metric shape:**

```
TraceMetric {
  name: "browser.{vital}",          // e.g. "browser.web_vital.lcp"
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

During this period, the original span is already billed. The derived metric's billing outcome should be suppressed until we cut the dashboards over then we can either decide to bill them as metrics or keep them free.

## Dashboard cutover

Product should switch to metrics-only queries when ready. Given enough metrics has been collected from the double-write period.

**Areas that web vitals are present:**

- Web Vitals Dashboards (built by Sentry or cloned by customers)
- Customer Monitors/Alerts.
- Custom widgets.
- Trace view (as markers)

I checked if we can still do the same insights and dashboards with metrics only. Because metrics are correlated to spans, we can highlight the timing of the web vital on the span timeline by checking for the correlated web vital metrics for that span/trace. So I see no reason why we can't do the same insights and dashboards with metrics only.

## Disable double-write, single-write conversion

Double-write stops. Relay stops writing the original span for web vitals but continues converting web vital spans from older SDKs to metrics (single-write). The original span is no longer stored.

The goal is to converge on a single data source (metrics) for web vitals. Maintaining two parallel data paths (spans + metrics) indefinitely means two sets of queries, two dashboard implementations, and two mental models for the same data. Single-write eliminates that.

Performance scores (`score.lcp`, `score.cls`, etc.) are currently computed by Relay from raw vital values on the span. Once spans are dropped, score computation moves to the metrics pipeline, deriving scores from the same raw values on the trace metric instead.

At this point we stop absorbing the cost of the derived metrics. We can also keep double-writing on if the costs are acceptable.

### What stops working

When spans stop being written, anything querying the spans dataset for web vitals will silently stop returning data:

A non-trivial number of active alerts, saved Discover queries, and custom dashboard widgets reference web vital span measurements across a significant number of orgs. These won't error, they'll just quietly stop producing data. Customers may not notice immediately. We have a couple of options here:

One question to answer is: is it possible to **Migrate alerts and Discover queries to the metrics dataset?** We can provide auto-migrate known patterns (e.g. `measurements.lcp` -> `browser.web_vital.lcp`) or provide migration tooling. This depends if users make use of custom attributes on those spans or if they combine filters on other attributes on their saved queries.

### Provenance-based billing

Each converted metric carries a provenance or a meta attribute that determines how it's billed:

| Attribute              | Value              | Meaning                                    | Billed as                                                |
| ---------------------- | ------------------ | ------------------------------------------ | -------------------------------------------------------- |
| `sentry.metric.source` | `"span"`           | Relay converted this from a web vital span | Free during double-write, as Metric when cutover happens |
| `sentry.metric.source` | `"sdk"` or missing | SDK emitted this natively as a metric      | `DataCategory::TraceMetric`                              |

Relay sets `sentry.metric.source: "span"` on all converted metrics. The SDK omits the attribute on natively emitted metrics.

**Billing caveat for measurements that currently ride free on the pageload span:**

| SDK path           | Already billed as standalone span | Free on pageload today | Suppress billing for derived metrics |
| ------------------ | --------------------------------- | ---------------------- | ------------------------------------ |
| v1 current default | INP                               | LCP, CLS, FCP, TTFB    | LCP, CLS, FCP, TTFB, INP             |
| metrics-native SDK | none                              | none                   | none                                 |

Relay must suppress billing for any metric derived from a measurement that was not previously billed as a standalone span. Only new SDKs emitting all 5 vitals as native metrics (`sentry.metric.source: "sdk"`) should bill them as `DataCategory::TraceMetric`.

After the double-write period, we can either keep them free if the cost is not too high, or charge them as `DataCategory::TraceMetric` after communicating with customers, we have estimations of how much it would cost to bill them as `DataCategory::TraceMetric` in the [appendix](#appendix).

## SDK emits web vitals as metrics natively (v??)

This work item is independent of the double-write period. At somepoint the SDK will switch over to emitting web vitals as native metrics. The exact version depends on the product readiness for this switch.

The SDK will split the web vitals feature into its own integration, meaning the user has to specifically opt-in again for web vitals after the upgrade.

```js
import * as Sentry from "@sentry/browser";

Sentry.init({
  // ...
  integrations: [webVitalsIntegration()],
});
```

This means the user is aware of the breaking change, and is making an explicit decision to opt-in to the new behavior.

Ideally we would prefer to make in time to switch to metrics natively by default to avoid fragmenting the user-base, but we don't want to block or delay releases for this change.

This doesn't change the double-write duration, but it will reduce the cost we absorb during the double-write period. Customers upgrading to metrics natively will start paying for web vitals as metrics (billed as `DataCategory::TraceMetric`) once the metrics-native SDK behavior ships.

If the cutover date does not align with the SDK's next major release, we will have to handle it in one of two ways:

- Provide a fallback web vital integration that sends web vitals as spans (opt-out).
- Wait for a next major cycle to produce yet another breaking change.

Ideally it would be great if we can offer something temporary in the product that adapts the metric queries so that we can make the breaking change once in the next major release (v11) so we don't have to do it again or change behavior mid-release if we absolutely must.

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

It doesn't seem like querying mixed span/metric data is possible as some folks are suggesting.

## SDK-only, no Relay involvement

The SDK ships metrics natively in next available major as a breaking change. Customers upgrading are expected to understand the pricing implications. No Relay conversion will happen, the SDK will emit metrics natively.

We can have the new SDK traffic tagging projects with a `has_web_vitals_metrics` flag that is then used to switch over to metrics widget/dashboards/alerts/queries. This will benefit newer projects more since customers wouldn't have historical data to worry about.

In either case, the SDK will allow customers to opt-out and send spans instead of metrics.

**Pros:**

- No double-write cost absorbed by Sentry
- No Relay conversion logic to build or maintain
- Simpler overall: SDK emits metrics, customers are aware of billing implications and can choose to upgrade to the new SDK version.

**Cons:**

- Old SDKs never produce metrics, so their web vitals are only visible through the span query path. There is no single dataset that contains all web vital data.
- No convergence to a single data source without Relay conversion

## Do nothing

Keep web vitals as spans. No migration, no metrics conversion.

**Pros:**

- Nothing to do.

**Cons:**

- The browser platform has no metrics use-cases, limiting customer adoption of the metrics product.
- Web vitals continue to be sampled, customers will lose information on the web vital values, especially when soft navigation vitals are adopted.
- Customers may lose out on the reduced cost/coverage of web vitals as metrics, especially when soft navigation vitals are adopted.

# Unresolved questions

- **Downsampling model.** How does the metrics backend downsample beyond 30 days? Pre-aggregated percentile rollups (lossy for cross-window percentile queries) or retained distributions at lower time granularity (lossless)? This determines whether "p75 LCP over 90 days" on the metrics dashboard is accurate or approximate.
- **Early adopters of v11.** How do we handle the early adopters of v11? Is it possible to show them something until we can have a full cut over? This can help us make the permanant change in the next major.

# Appendix

- [Absorbed cost estimations and web vital analysis](https://www.notion.so/sentry/Web-Vitals-as-Metrics-Numbers-3568b10e4b5d80a8b802d1370a42c3e2)
