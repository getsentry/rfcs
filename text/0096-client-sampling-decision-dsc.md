- Start Date: 2023-06-27
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC proposes the addition of a field to the `DynamicSamplingContext` that allows the head of the trace to propapagte whether it has sampled or not the transaction client side.

# Motivation

Relay has now the ability to tag incoming errors by looking at the trace header (aka dsc) and determine whether the trace connected to this error was fully sampled or not. This is useful to surface errors that belong to full traces on the product side, with the goal of improving user experience.

During development of tagging we realized that there is an edge case in which the system could misbehave. This happens when the head of the trace is sampled out on the client side but the DSC doesn't contain this information and when the server receives an error with that DSC, it will perform a sampling decision and maybe mark it as sampled. In this case, we will have a false positive, since the trace is not actually stored in its entirety but the error is tagged as if it was (e.g., `sampled = true` in the trace context).

# Solution

The solution to this problem would be to add a new field to the `DynamicSamplingContext` which will contain a boolean value marking whether or not the head of the trace was sampled out client side. This field will be used on:
- SDKs: to maintain a consistent client side sampling decision. If the head is sampled on the client, all the components of the trace will be sampled.
- Relay: to tag errors with the correct trace state. If the incoming error has in the dsc that the head was sampled out, we will mark `sampled = false` in the trace context.

To share the sampling decision, the new updated DSC will have a new field named `sampled`, like this:
```json
{
  "trace_id": "12345678901234567890123456789012",
  // Boolean to mark whether or not the head was sampled on the client, where true means that the head was kept.
  "sampled": true,
  ...
}
```

_The `sampled` field will be set only in case a transaction was started and was kept or dropped by the head of the trace. In all the other cases, the field should NOT be set._

# Connected issues

- https://github.com/getsentry/sentry/issues/51026
