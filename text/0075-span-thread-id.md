- Start Date: 2023-02-15
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/75
- RFC Status: draft

# Summary

Enrich spans with thread id information.

# Motivation

As we have started to enrich profiling and performance UIs with data from the two products, we realized that we cannot precisely show what spans were executed on each thread (ex in profiling UI) or show what function frames were executed during a span (ex in performance UI). Having span thread id data would allow us to improve the user experience between the two products.

# Supporting Data

In profiling, we currently show the entire span tree regardless of what thread the user is viewing and in performance we default to showing the main thread. This is not very accurate and can lead to misleading our users.

Metrics:
No usage metrics, but this was requested by customers.

# Options Considered

- Add thread_id to spans
- Add thread_id and optional ended_thread_id (in case they differ) property to spans

# Drawbacks

Spans can span (pun not intended) different threads, so if we wanted better precision, we would probably need to track which thread a span was started and ended on.

Profiling already collects thread names, so the implementation between performance and profiling would have to be kept in sync - we add the risk of code falling out of sync between the two.

# Unresolved questions

- Are there other benefits to collecting this data?
- ???
