- Start Date: 2023-06-27
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC proposes the addition of a field to the `DynamicSamplingContext` that allows the head of the trace to propapagte whether it has sampled or not the transaction client side.

# Motivation

Relay has now the ability to tag incoming errors by looking at the trace header (aka dsc) and determine whether the trace connected to this error was fully sampled or not. This is useful to surface errors that belong to full traces on the product side, with the goal of improving user experience.

During development of tagging we realized that there is an edge case in which the system could misbehave. This happens when the head of the trace is sampled out on the client side but the DSC doesn't contain this information and when the server receives an error with that DSC, it will perform a sampling decision and maybe mark it as sampled. In this case, we will have a false positive, since the trace is not actually stored in its entirety but the error is tagged as if it was (e.g., `sampled = true` in the trace context).

# Options Considered

The solution to this problem would be to add a new field to the `DynamicSamplingContext` which will contain a boolean value marking whether or not the head of the trace was sampled out client side. This field will be used on:
- SDKs: to maintain a consistent client side sampling decision. If the head is sampled on the client, all the components of the trace will be sampled. (We need to decide whether the opposite will also hold true, since we might also want to keep certain transactions in a trace even though the head has been sampled out).
- Relay: to tag errors with the correct trace state. If the incoming error has in the dsc that the head was sampled out, we will mark `sampled = false` in the trace context.

# Unresolved questions

- TBD

# Connected issues

- https://github.com/getsentry/sentry/issues/51026
