- Start Date: 2024-07-05
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/137
- RFC Status: draft

# Summary

Today, Sentry SDKs will continue any trace they get via e.g. a `sentry-trace` header. However, it is possible to receive incoming traces from external organizations, in which case it is incorrect to continue the trace.

We should implement a way to avoid incorrectly continuing such a trace. The easiest way to do this is to restrict trace continuation to happen for the same Organization only.

# Motivation

Why are we doing this? What use cases does it support? What is the expected outcome?

# Background

The reason this decision or document is required. This section might not always exist.

# Supporting Data

[Metrics to help support your decision (if applicable).]

# Options Considered

If an RFC does not know yet what the options are, it can propose multiple options. The
preferred model is to propose one option and to provide alternatives.

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known?
