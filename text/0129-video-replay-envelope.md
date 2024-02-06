- Start Date: 2024-02-06
- RFC Type: feature
- RFC PR: [#129](https://github.com/getsentry/rfcs/pull/129)
- RFC Status: draft

# Summary

In order to capture video replays and present them to the user, we need:

- define how we transport the video data to the server
- define how we integrate the video data into the RRWeb JSON format
- how we combine multiple replay chunks to a single replay session

# Motivation

We need this to to capture replays on platforms where it's not possible/feasible to produce an HTML DOM (i.e. the native format supported by RRWeb).

<!-- # Supporting Data -->
<!-- Metrics to help support your decision (if applicable). -->

# Options Considered

If an RFC does not know yet what the options are, it can propose multiple options. The
preferred model is to propose one option and to provide alternatives.

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known?
