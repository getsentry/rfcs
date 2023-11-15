- Start Date: YYYY-MM-DD
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC addresses the high level metrics to span correlation system.

# Motivation

We believe the value in a good metrics solution is the correlation to traces and other signals.
This means that we need to store evidence of metric measurements on the spans.

There are two APIs related to metrics in an SDK.  The low-level `metrics` API which directly
throws a data point into a local aggregator, and a higher-level span-bound API that more
explicitly associates measurements with spans directly.  Because there are two APIs provided
we need to be careful setting customers on the path of success.

# Basics

For correlation purposes, measurements can be stored on the span within the `measurements`
data bag:

```json
{
  "span_id": "deadbeef",
  "op": "whatever",
  "metric": "my.span",
  "measurements": {
    "duration": { "value": 32.0, "unit": "millisecond" },
    "block_size": { "value": 1024, "type": "g" }
  }
}
```

The key `duration` here is special in that it is the "trivial" metric name.  Any
other measurement can be stored there.  The key of in the bag is concatenated to the
`metric` key of the span except for the `duration` case.  That means that in the above
case the metrics `custom/my.span` is emitted as distribution (the default) with
`32.0` as value and `custom/my.span.block_size` for instance as gauge.

# Trivial Correlations

These are correlations where a metric almost directly correlates to a span.

## Spans linked Timings

Per definition when a span is attributed with a `metric` name, it's duration is reported
as metric.  The tags associated with that metric are taken from the `metric_tags` parameter

```python
with start_span(description="something human readable", metric="my.span"):
    pass
```

The corresponding low-level API (`metrics.timing`) is supposed to automatically create a
span if tracing is enabled and no explict value is provided.  The following two examples
are equivalent:

```python
with metrics.timing("foo"):
    pass

with start_span(op="measurement", metric="foo"):
    pass
```

## Arbitrary Distributions

Distributions are relatively easy to attach to spans.  By definition we only permit
distributions (other than timing) to be associated with a span that itself is also
named with a `metric`.  For instance imagine the following code which processes a bunch
of spans:

```python
def process():
    message_buffer = recv()
    with start_span(metric="process.process-buffer") as span:
        for message in message_buffer:
            process_message(message)
        span.set_measurement("message-count", len(message_buffer))
```

This would

# API Proposal

If `metrics.timing` is used and there is no active span that already has a metrics attribute,
we automatically add a "measurement" span:

```python
with metrics.timing("foo"):
    pass
```

# Open Questions

* Metric vs span tags
