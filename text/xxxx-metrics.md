- Start Date: YYYY-MM-DD
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC lays out the data model behind metrics in Sentry.  Metrics are time series
that can be pre-aggregated on the SDK side, optionally can be extracted from
transactions in relay and pop up in the product in different areas.

This RFC specifically extends our internal metrics infrastructure so that it can be
used as a stand-alone product and be emitted SDK side.

# Motivation

Sentry has an internal metrics system that is currently used to drive two product
surface areas: overall aggregates for performance and sessions.  Internally it is based
on data sketches which support counters, gauges, sets and distributions.  We want to
provide simple ways for SDKs to emit time series that logically also connect to existing
product surface areas.  This means that the concepts for metrics should relate to concepts
in traces so that a connection can be made.  We also recognize that certain measurements
cannot be associated logically with a trace which is why this RFC also covers those cases.

This RFC does not specify the motivation to build a metrics product, but the technical
decisions made to accomode the user experience for a metrics product.

# Basics

This introduces the basics of the metrics design.

## Metrics and Measurements

The term metric refers to any metric emitted in the system.  Measurements are subsets of
metrics which have a 1:1 relationship with a particular span.  As the system currently
only permits measurements on transactions most of the measurements today are thus
restricted to being attached to a transaction level span.  The exception to this rule
are span durations.  For more details about this refer to "Timing and Span Relationships"
below.  In principle a measurement can be emitted even if there is no transaction to attach
it to, as they are separate concepts. As an example the LCP measurement might fall outside
the scope of a transaction.  In that case we can still emit it as a metric, even if we
cannot attach it to a transaction.

Note that this RFC does not recommend or propose emission of metrics from clients
that are otherwise Relay extracted.  So while for instance LCP values and similar
vitals _could_ be sent via metrics in principle, it's not specified how this would
be accomplished.  As such no thought is spent on how the system would prevent double
counting yet.

## Trace Seeking

Metrics are referred to as "trace seeking".  This means that when a metric is emitted, the
SDK is expected to locate the active trace and pull in related information to that trace.
In some cases the issuance of such a metric can be detected to be a measurement in which
case the metric is directly attached to the correct location in the trace as well.  In all
cases however the tags associated with a metric are augmented by the current trace context.

The motivation here is that when looking at aggregated metrics within a certain time window
it should be possible to use these as an entry point to dive into other parts of the product
experience.  As an example by tagging metrics with the name of the current transaction and
release it's possible to narrow down the transactions to look at in the performance section
of Sentry.  Likewise by tagging metrics with releases it's possible to directly drive the
release health system.  When a measurement is emitted, directly correlation is possible in
that percentiles can be calculated from metrics timeseries data, and then the p95 or similar
can be taken as the lower bound for finding transactions or spans where that number is the
lower bound of that measurement.

```python
from sentry_sdk import metrics

# When the metrics is thrown into the aggregator, it's enhanced by the tags
# `release`, `environment` and `transaction` from the current trace.
with metrics.timing("my-expensive-operation", tags={"kind": "batch"}):
    # process the batch here.
    ...
```

## Units and Convertability

When metrics are emitted, units are sent alongside.  This means that the meaning of a number
is obvious and re-calculations are possible in the UI.  SDKs are expected to have reasonable
unit defaults for timings they are automatically emitting.  Units that are not understood by
the system are called "custom" units.  Units are always in singular form.

```python
metrics.distribution("upload.file_size", attachment.bytes, unit="byte")
metrics.gauge("cpu.pointer_size", CPU_POINTER_SIZE, unit="bit")
metrics.incr("processor.messages_processed", 1, unit="message")
```

## MRIs

Metrics are identified by their [metrics resource identifier](https://getsentry.github.io/relay/relay_metrics/struct.MetricResourceIdentifier.html).
It consists of type, namespace, metric name and unit.  On the SDK side in both
memory and in the transport the MRI does not play much of a role as it's encoded
in a more relaxed format.  Most importantly the namespace is implied as "custom"
for custom metrics.  The understanding of MRIs however is important as in the final
storage the metric is keyed by it's MRI in the system which means that the following
metrics are all different:

```
d:custom/endpoint.response_time@millisecond
d:custom/endpoint.response_time@second
g:custom/endpoint.response_time@second
```

For some metrics the idea is that some unification can take place later.  For
instance when an SDK sends seconds and another SDK version sends milliseconds
for the same unit, the system should later be able to unify them at query or
ingestion time.  This type of handling would not extend to custom or
incompatible types.

## Span Accounting

The plan is that spans in the `custom/` namespace are generally billed for in
one way or another.  Other metrics would be billed as part of other product
features.

# SDK Design

SDKs are expected to provide basic metric emission APIs modelled after common APIs inspired
by statsd.

## Aggregations

SDKs are expected to aggregate locally for windows of up to 10 seconds.  The aggregator shall be
running in the background and regularly flush out items.  Upon shutdown the SDK needs to ensure
that unflushed buckets are drained.  SDKs area also encouraged to ensure that the total aggregation
memory consumption is managed and flushes out buckets early if the memory consumption raises too high.

## Basic API

All metric functions are free standing topleve functions in a `metrics` module.  They all must accept
an optional `timestamp` which if not provided defaults to the current moment in time.  Likewise all
functions shall accept `tags` which is typically a dictionary.  More than one value per key is permitted
if represented as a list or tuple.  If the value is set to `none` or `null` or a similar sentinel value,
that tag is not emitted.  This functionality might not exist in languages which do not have naturally
nullable types.

The `key` of a metric is a metric name.  This is the raw metric name which is later encoded into the MRI.
Per policy if no slash is encoded it's emitted as a "custom" metric which is equivalent to prefixing it
with `custom/`. Note however that the SDK does not need to take care of this as the ingestion system has
this logic already implemented.  From the SDK side it's thus trivial to support custom and non custom
metrics.

* **incr**(*key*, *value* = `1.0`, *unit* = `"none"`, *tags* = `{}`, *timestamp* = `null`):
  Increments the given `counter` metric by the given value.  Counters are
  counted up or down on the SDK side within the rollup time window.  The aggregation state on the
  SDK side is a single float.

* **gauge**(*key*, *value* = `1.0`, *unit* = `"none"`, *tags* = `{}`, *timestamp* = `null`):
  Emits a gauge value.  For more information about gauges see the metric types.  On the SDK side
  the aggregation state is 5 counters (`last` with the most recently emitted value, `min` with the
  smallest value observed, `max` with the largest value observed, `sum` which is a float sum of
  the total sum of emitted values, `count` is a running counter of the number of values reported).

* **distribution**(*key*, *value*, *unit* = `"none"`, *tags* = `{}`, *timestamp* = `null`):
  Records a value for a distribution.  The aggregation state is a lis of all values encountered.
  This means that distributions are reduced to their quantiles only post emission.  This also means
  that in practical terms distributions are likely to be more expensive on the SDK side in terms of
  memory consumption than many other metric types and might cause early flushes.

* **set**(*key*, *value*, *unit* = `"none"`, *tags* = `{}`, *timestamp* = `null`):
  Reports a value as "ocurred".  The value is supposed to be a hashable primitive such as a string
  or integer.  On the SDK side these hashed values are recommended to be reduced via CRC32 to a
  32bit integer.  These sets can be used later to correctly sum up how many users / items / devices
  or similar were observed at a certain point or through a funnel.  Like distributions these can
  cause a significant overhead compared to gauges or couters as the aggregation state is a set.

* **timing**(*key*, *value*, *unit* = `"second"`, *tags* = `{}`, *timestamp* = `null`):
  This is a special form of a distribution that defaults to seconds or nanoseconds.  It records like
  a distribution but in some languages this might work with a context manager that takes the right
  timing itself.  If a specific overflow cannot be added, it's recommended that a suffix is added
  to the function or called `timed`.  For instance ``timing("foo", 1.0)`` would record a regular
  timing, but for instance ``timed("foo", 1.0, callback)`` would invoke the callback and measure it.
  For more information about `timing` see the section on span relationships below.

Motivating examples for a Python SDK:

```python

from sentry_sdk import metrics

def save_event(event):
    with metrics.timing("event_manager.save", tags={"platform": event.platform}):
        if not is_valid_event(event):
            metrics.incr("event_manager.invalid_event")
            return False
        ...

def toggle_early_adopter(org_id, value):
    if value:
        metrics.set("activated_early_adopter", org_id)
    ...
```

## Timing and Span Relationships

The `timing` and related measurements have a strong overlap with tracing.  In particular the
use of `metrics.timing` is in principle discouraged as similar in nature to the duration of
a span.  An SDK that sends at 100% sample rate will create an experience where the ingestion
system would be able to extract metrics from all spans.  However that opens the question of
how such metrics were to be grouped to create reasonable rollups.

A simplified way to reason about this is that the responsibility of grouping up spans into
metrics is the pure responsibility of relay.  As an example database queries are cleaned up
and grouped with complex logic provided by the ingestion system.  It would be unreasonable
to request SDKs to match that rollup and grouping behavior.

However not every span will create such a metric.  A simple way to approach this problem
would be to say that if a client wants a particular metric to be emitted for a span, that is
always considered a custom metric.  In such a case the rollup behavior is fully driven by
the client.  Sufficient evidence of that metric is retained with the span so that that
relationship can be established.

Example behavior:

```python
with start_span(
    description="process",
    op="task.spawn",
    emit_metric=True,
    metric_name="event_manager.process"
) as span:
    result = ...
    span.set_tag("success", result is not None and "true" else "false")
```

In this case the span emitted would retain information that there is a named metric `event_manager.process`
has a direct mapping to the span duration.  Internally the SDK (even if the span is not sampled!)
will record that metric as if `metrics.timing("event_manager.process", value=span.duration)` is called.

There are some concerns about the cardinality of span tags and how they can go with metrics.  For instance
today the product will liberally attach things such as SQL queries to spans.  That is not at all what we
want for metrics.  We want the tags that go with metrics to be already restricted on the client to be
lower cardinality for a better user experience.  One option would be to ask users to be explicit about
which tags should go with metrics by adding a flag to `set_tag` in that case:

```python
with start_span(
    description="process",
    op="task.spawn",
    emit_metric=True,
    metric_name="event_manager.process"
) as span:
    ...
    span.set_tag("platform", event.platform, add_to_metric=True)
```

## Other Metric Trace Relationships

For other metrics the relationship to traces is less obvious.  There are some examples where
taking measurements in regular intervals is already happening in the product today, but those
measurements are not yet linked up with traces well.  As an example memory measurements are
taking for profiles and session replays.  For such cases it would be nice to be able to also
take real metrics so that these kinds of correlations would become possible.  However for real
correlations it would be necessary to also attach information to traces when metrics are
emitted.  This could be envisioned as a timeline along a trace that plots the measurements
taken (eg: memory use at a certain point in time etc.).  Note that there is no requirement for
all metrics to be associated to a trace, even if they are likely to be part of the trace.

## Aggregation and Transmission

Metrics are emitted as an envelope item called `statsd` as it follows a format inspired by
statsd.  The associated data category is also called `statsd`.  There is currently no
method defined for how metrics are supposed to be counted, but this data category is used
to inform SDKs when an SDK is blocked from sending metrics.  This for instance can happen
if an account is not enabled for metrics.  In that case the SDK shall not send metrics
like it would do for any other rate limit.  Additionally however it could also leverage this
information to temporarily disable the aggregator.

The aggregator is a concept within an SDK which performs lossless aggregation.  It's
recommended for SDKs to perform two-level bucketing where the top level is the rounded
timestamp, and the second level are all the buckets within that timestamp.  That is
recommended as it allows an SDK to evict an entire bucket at once and send it to the
emission step.

SDKs should flush if a bucket is older than 10 seconds (rounded to full seconds) of it they
need to flush earlier because of memory pressure etc.

## Serialization Format

The serialization format for metrics is an envelope item called `statsd`.  It's permissible
for the system to emit a metric more than once though it's discouraged.  The format is
designed to allow relatively efficient submission of multi-value metrics such as
distributions.  For details about the submisson protocol refer the
[relay metrics documentation](https://getsentry.github.io/relay/relay_metrics/index.html).

For SDKs an important consideration is that the transmission format requires a certain amount
of sanitizing of values.  That is necessary as the protocol does not have a way to escape
special characters, so they need to be removed before serialization.  This is relevant for
both metric names, tag names and tag values.  It's recommended that a sequence
of unwanted characters are repaced by an underscore.  The sanitization that is
recommended is the following:

```python
_sanitize_key_re = re.compile(r"[^a-zA-Z0-9_/.-]+")
_sanitize_value_re = re.compile(r"[^\w\d_:/@\.{}\[\]$-]+", re.UNICODE)

def sanitize_key(value):
    return _sanitize_key_re.sub("_", value)

def sanitize_value(value):
    return _sanitize_value_re.sub("_", value)
```

A keen observer will note that the values permitted for tag values is much larger than for
some other metrics systems.  This is intentional as we want to be able to express some common
values there largely untransformed to permit correlation with other tag values.  In particular
most URL patterns for transactions should still work, same with sentry release names etc.

# Open Questions

* How does a metric indicate that it is also a measurement that should go into a trace or span?
* Do we want a protocol level indication that a transaction measurement should not be extracted
  because it's also in the aggregator on the client?
* 10 second aggregations on the client imply a certain delay for metrics to come in, is that okay?
  It means that metrics lag behind their 