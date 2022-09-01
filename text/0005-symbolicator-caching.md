- Start Date: 2022-09-01
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/5

# Summary

This is a detailed description of the internal caching architecture of symbolicator.

# Motivation

We want to have a place where the high level infrastructure is written down in detail.
It should have a description of the intended workflow and the requirements that the solution should satisfy.

# Background

This document should inform any future changes to the underlying code, which right now is a bit convoluted.

# Supporting Data

We have seen that having long-lived caches is crucial to the performance and stability of our symbolication pipeline.
There were incidents related to not having enough caches available.

On the other hand we want to be confident to roll out changes that refresh caches in a timely fashion.

# Current architecture

TODO: maybe draft a mermaid diagram showing the control flow of how an event is processed, etc...

# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known?
