- Start Date: 2023-02-01
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/71
- RFC Status: draft

# Summary

To make it easier to continue a trace over process boundaries (think of one program starting another one, like cron jobs)
It should be possible that the SDK on startup can fetch data from the environment variables (similar like we do when fetching trace context from http headers) and then create a "root transaction" that is attached to that trace and also continues the trace on outgoing requests.

# Motivation

The Sentry "Cron Monitors" feature suggests that one can add something like this to the crontab:

`10 * * * *   sentry-cli monitor run <monitor_id> -- python my_cron_job.py`.

The `sentry-cli` call starts a trace (so it is the head of trace) and the Sentry SDK in `my_cron_job.py` should connect it's transactions to that trace.

# Background

## Existing trace propagation mechanism

Trace propagation is: giving trace information from one service (the first service, or head of trace) to a second service, so that the second service can create transactions that are attached to the trace created in the first service.
In most cases the trace information is propagated through three HTTP headers (`sentry-trace`, `baggage` and `tracestate`).
A few integrations (for example job queues) use queue specific meta data fields for propagating trace information. (but those implementations only propagate `sentry-trace` and `tracestate`, NOT `baggage` so some information is lost here.)
The trace information can also be injected into rendered HTML as a <meta> HTML tag.

See Appendix A if you want to know how this works in the Python SDK.

# Options Considered

## Option A)

### Retrieving tracing information via environment variables:

When the SDK starts up it reads an environment variable `SENTRY_TRACING_USE_ENVIRONMENT` (defaults to `False`).
If `SENTRY_TRACING_USE_ENVIRONMENT` is set to `true` (or `true|True|TRUE|1|on|yes|y`) then the SDK reads the following environment variables:

- `SENTRY_TRACING_BAGGAGE`
- `SENTRY_TRACING_SENTRY_TRACE`
- `SENTRY_TRACING_TRACESTATE`

The environment variables contain the same strings that the respecitve HTTP headers would contain.
The SDK parses the string values from the environment variables and stores them in the current scope.
TODO: is the scope where this should live? Or just some local (or global) variable?

To successfully attach a transaction to an existing trace at least `SENTRY_TRACING_SENTRY_TRACE` must have data.

For dynamic sampling not to break, `SENTRY_TRACING_BAGGAGE` needs to include all information of the dynamic sampling context. The parsed baggage must not be changed.

When `SENTRY_TRACING_USE_ENVIRONMENT` is set to true during startup also a so called "Root Transaction" should be created automatically. It should include all the trace information from the scope and should be finished just before the process ends.

TODO: Maybe we should create a new transaction source for this kind of root transactions?

### Creating tracing information on process start up

If `SENTRY_TRACING_USE_ENVIRONMENT` is set to `true` and no information can be found in `SENTRY_TRACING_BAGGAGE`, `SENTRY_TRACING_SENTRY_TRACE` or `SENTRY_TRACING_TRACESTATE` then the current process is the head of trace and a dynamic sampling context should be created.

See [Unified Propagation Mechanism](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#unified-propagation-mechanism) for details.

See [Dynamic Sampling Context Payloads](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#payloads) to see what data needs to be included in the dynamic sampling context.

### Propagating/sending tracing information via environment variables:

The integrations that patch functions that are used for spawning new processes (`StdlibIntegration` in Python) should be changed so they grab the tracing information from the scope (if any) and set them in the environment variables (`SENTRY_TRACING_BAGGAGE`, `SENTRY_TRACING_SENTRY_TRACE`, `SENTRY_TRACING_TRACESTATE`) for the newly spawned process. The variable `SENTRY_TRACING_USE_ENVIRONMENT` should also be set to `true` so the receiving process is picking up the information.

# Drawbacks

TODO: Why should we not do this? What are the drawbacks of this RFC or a particular option if multiple options are presented.

# Unresolved questions

- TODO: What parts of the design do you expect to resolve through this RFC?
- TODO: What issues are out of scope for this RFC but are known?

# Appendix A

How trace propagation is working in the Python SDK right now:

When a request from another service is received a transaction is created. (So each request-response cycle is a transaction).
The process of creating a transaction that attaches to an existing trace received from the calling service is done as follows:

- data from the `baggage` header is parsed. If it contains values with a `sentry-` prefix the parsed baggage is frozen (marked as immutable).
- data from the `sentry-trace` header is parsed. (`trace_id`, `parent_span_id` and `parent_sampled`) If this header exists and contains values the parsed baggage from step is is frozen (marked as immutable).
- data from the `tracestate` header is parsed. (`sentry_tracestate` and `third_party_tracestate`).
- With all this information a new transaction is created.
- If an outgoing request is done this tracing information is attached to the request as HTTP headers, thus propagated.
- There are the options `propagate_traces` and `propagate_tracestate` that can turn off the propagation of traces (but not yet implemented in all integrations, so some integrations ignore them).

This should adhere to the [Unified Propagation Mechanism](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#unified-propagation-mechanism).

Currently every integration itself takes care of parsing tracing information and attaching it to Transactions or outgoing requests.
