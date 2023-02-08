- Start Date: 2023-02-01
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/71
- RFC Status: draft

# Summary

To make it possible to continue a trace over process boundaries (think of one program starting another one) For this to work we will use environment variables as the carrier. An SDK should be able to fetch tracing data from environment variables on `init()` to continue a trace started in another process.

# Motivation

The Sentry "Cron Monitors" feature suggests that one can add something like this to the crontab:

`10 * * * *   sentry-cli monitor run <monitor_id> -- python my_cron_job.py`.

The `sentry-cli` call starts a trace (so it is the head of trace) and the Sentry SDK in `my_cron_job.py` should connect it's transactions to that trace.

# Background

## Existing trace propagation mechanism

Trace propagation is: giving trace information from one service (the first service, or head of trace) to a second service, so that the second service can create transactions that are attached to the trace created in the first service.

In most cases we use HTTP as the carrier for trace information. The information is propagated through two HTTP headers (`sentry-trace` and `baggage`).

A few integrations (for example job queues) use queue specific meta data fields for propagating trace information. (but those implementations only propagate `sentry-trace` and maybe the legacy `tracestate` that will be rmeoved, but NOT `baggage` so some information is lost here.)

The trace information can also be injected into rendered HTML as a <meta> HTML tag.

See Appendix A if you want to know how this works in the Python SDK.

# Options Considered

## Option A)

### Retrieving tracing information via environment variables:

When the SDK starts up it reads an environment variable `SENTRY_TRACING_USE_ENVIRONMENT` (defaults to `False`).
If `SENTRY_TRACING_USE_ENVIRONMENT` is set to `true` (or `true|True|TRUE|yes|Yes|YES|y|1|on`) then the SDK reads the following environment variables:

- `SENTRY_TRACING_BAGGAGE` (similar to `baggage` HTTP header)
- `SENTRY_TRACING_SENTRY_TRACE` (similar to `sentry-trace` HTTP header)

The environment variables contain the same strings that the respecitve HTTP headers would contain.
The SDK parses the string values from the environment variables and stores. SDKs can decide where the what to store this tracing information.

To successfully attach a transaction to an existing trace at least `SENTRY_TRACING_SENTRY_TRACE` must have data.

For dynamic sampling not to break, `SENTRY_TRACING_BAGGAGE` needs to include all information of the dynamic sampling context. The tracing information parsed from this must not be changed.

When `SENTRY_TRACING_USE_ENVIRONMENT` is set to `true` during startup also a so called "Root Transaction" should be created automatically. It should include all the trace information from the parsed tracing information and should be finished just before the process ends.

TODO: Maybe we should create a new `transaction_info.source` for this kind of root transactions?

### Creating tracing information on process start up

If `SENTRY_TRACING_USE_ENVIRONMENT` is set to `true` and no information can be found in `SENTRY_TRACING_BAGGAGE` or `SENTRY_TRACING_SENTRY_TRACE` then the current process is the head of trace and a dynamic sampling context should be created.

See [Unified Propagation Mechanism](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#unified-propagation-mechanism) for details.

See [Dynamic Sampling Context Payloads](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#payloads) to see what data needs to be included in the dynamic sampling context.

### Propagating/sending tracing information via environment variables:

The integrations that patch functions that are used for spawning new processes (`StdlibIntegration` in Python) should be changed so they use the parsed tracing information (if any) and serialize it to the environment variables (`SENTRY_TRACING_BAGGAGE`, `SENTRY_TRACING_SENTRY_TRACE`) for the newly spawned process. The variable `SENTRY_TRACING_USE_ENVIRONMENT` should also be set to `true` so the receiving process is picking up the information.

## Option B) Passing tracing information via files

While initializing, SDK checks for environment variables: `SENTRY_TRACING_FILE_BAGGAGE` and `SENTRY_TRACING_FILE_SENTRY_TRACE`. Each of those variables might contain a file path that points to a file containing the tracing information.

For example, `SENTRY_TRACING_FILE_SENTRY_TRACE=/dir1/file1` indicates that `sentry-trace` value should be read from the file located at `/dir/file1`.

**Note**: the actual file object might also be, for example, a named pipe.

After the values are read from the files, the same considerations as in Option A apply.

Main differences from Option A:

* Using files, tracing information can be passed not only from a parent process to a child process, but also between processes that don't have direct parent-child relationships.
* Files used for transport can be updated by any other process (as far as filesystem permissions allow), and the SDK can technically re-read the file multiple times during the lifetime of the host application. However, I don't have a good use case for this right now.
* Message passing via files is generally more cumbersome and might have performance/reliability drawbacks, depending on the type of file (plain file, named pipe) and the backing filesystem.

# Drawbacks

Because the serialization format of the bagagge (and thus the dynamic sampling context) stays the same, just the carrier is a new one, it should be 100% compatible to other integrations and will not break dynamic sampling.

So: No drawbacks.

# Unresolved questions

- Should we create a new `transaction_info.source` for this kind of transactions that span one execution of a process?

# Appendix A

How trace propagation is working in the Python SDK right now:

When a request from another service is received a transaction is created. (So each request-response cycle is a transaction).
The process of creating a transaction that attaches to an existing trace received from the calling service is done as follows:

- data from the `baggage` header is parsed. If it contains values with a `sentry-` prefix the parsed baggage is frozen (marked as immutable).
- data from the `sentry-trace` header is parsed. (`trace_id`, `parent_span_id` and `parent_sampled`) If this header exists and contains values the parsed baggage from step is is frozen (marked as immutable).
- DEPRECATED and will be removed soon: data from the `tracestate` header is parsed. (`sentry_tracestate` and `third_party_tracestate`).
- With all this information a new transaction is created.
- If an outgoing request is done this tracing information is attached to the request as HTTP headers, thus propagated.
- There is the option `propagate_traces` that can turn off the propagation of traces (but not yet implemented in all integrations, so some integrations ignore them).

This should adhere to the [Unified Propagation Mechanism](https://develop.sentry.dev/sdk/performance/dynamic-sampling-context/#unified-propagation-mechanism).

Currently every integration itself takes care of parsing tracing information and attaching it to Transactions or outgoing requests.
