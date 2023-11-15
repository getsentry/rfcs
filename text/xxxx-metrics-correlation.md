- Start Date: YYYY-MM-DD
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC addresses the high level metrics to span correlation system.

# Motivation

WRITE ME

# API Proposal

If `metrics.timing` is used and there is no active span that already has a metrics attribute,
we automatically add a "measurement" span:

```python
with metrics.timing("foo"):
    pass
```

# Open Questions

* How does a metric indicate that it is also a measurement that should go into a trace or span?
* Do we want a protocol level indication that a transaction measurement should not be extracted
  because it's also in the aggregator on the client?
* 10 second aggregations on the client imply a certain delay for metrics to come in, is that okay?
  It means that metrics lag behind their 