- Start Date: YYYY-MM-DD
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC addresses the high level metrics to span correlation system.

# Motivation

We believe the value in a good metrics solution is the correlation to traces and other signals.
This means that we need to store evidence of metric measurements on the spans.  These
measurements are automatically added when using the basic `metrics` API.

# Basics

Whenever a metrics API is used it operates in either span seeking or span creating mode.  Most
of the metrics APIs are span seeking which means that they record a measurement in relation
to that span.  Some APIs (such as `metrics.timing` when used with a code block) will instead
create a span and bind it.

```python
def process_batch(batch):
    processor = Processor()

    # This creates a span with op `timing_measurement`
    with metrics.timing("processor.process_batch"):
        for item in batch:
            success = processor.process_item(item)
            # This records an increment of 1
            metrics.incr("processor.item_processed", tags={"success": success})
        # This records a gauge
        metrics.gauge("processor.peak_memory_usage", processor.peak_memory_usage)
```

Each metric locally "aggregates" into something that represents a gauge and is persisted with
the closest span.  In the above case the following span gets recorded assuming a batch size of 5
where 3 succeed and two fail, the following measurements might be associated:

```json
{
    "span_id": "deadbeef",
    "op": "timing_measurement",
    "measurements": {
        "d:processor.process_batch@millisecond": [
            {
                "min": 421.0,
                "max": 421.0,
                "count": 1,
                "sum": 421.0
            }
        ],
        "c:processor.item_processed": [
            {
                "min": 1,
                "max": 1,
                "count": 3,
                "sum": 3,
                "tags": {"success": True}
            },
            {
                "min": 1,
                "max": 1,
                "count": 2,
                "sum": 2,
                "tags": {"success": False}
            }
        ],
        "g:processor.peak_memory_usage@megabyte": {
            {
                "min": 42.0,
                "max": 421.0,
                "count": 1,
                "sum": 421.0,
            }
        }
    }
}
```

Note that per-span all metrics (other than `sets` which are not yet accounted for) are
stored as gauges.  That means that despite the fact that `incr` was called 5 times, only
two gauges are stored.  The values of `min` and `max` are then useful for finding spans
within the search radius.  Likewise tags are stored per metric and might diverge from
the span tags.

In a way this implies that there are two aggregators: a global aggregator and a per-span
local gauge level minimal aggregator.

# Intended Correlations

The following correlations are useful for metrics to span queries:

## Spans linked Timings

When a code block is timed with `metrics.timing` (or potentially a span is named with the
`metric` parameter) it emits a distribution as timing.  That also binds and creates a span
and attached that metric directly as measurement.  In that case the tags for metrics
might also have to be explicitly recorded with `metric_tags` as parameter.

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

with start_span(op="timing_measurement", metric="foo"):
    pass
```

To find corresponding spans the `min` and `max` values on span measurements can be used
for correlation.

## Counters

Counters should be primarily seen as "events".  The existence of an `incr` on a span is
in fact the signal, more than the number is.  The reason for this is that things such as
throughput do not make a lot of sense.  The number of requests per second for instance
might be in the thousands, whereas each individual request only adds "1" to the counter.

However for finding interesting samples, the existence of a span that has that metric
in it (eg: `count > 0`) on the right tags might be sufficient.

On the other hand if `incr` is incremented multiple times, it might also be worth finding
the spans sorted by the highest `count` or highest total sum / max value.

# Open Questions

* Metric vs span tags
* Sets
* Sampling of measurements
* On span storage vs across span storage
