* Start Date: 2022-09-29
* RFC Type: feature
* RFC PR: [#21](https://github.com/getsentry/rfcs/pull/21)

# Summary

This RFC details the proposal to add profiling instrumentation to the `sentry CLI`

# Motivation

We've recently added the support for profiling in the Rust SDK and we've been looking for a Sentry tool that we could use to dogfood it.

Apart from the point mentioned above, we can use this as an opportunity to improve the performance of `sentry-cli`, should we find any issue from the profiles data.

# Background

The `sentry-cli` was temporarily instrumented for a short period between April and May 2018 with different opting strategy (first opt-out and then opt-in).

As we're planning to re-introduce instrumentation by enabling profiling, we'll start collecting diagnostic data again, hence the need for this RFC.

# Options Considered

## Option 1: simple integration with no opting mechanism

Since we're not collecting user PII we could simply enable profiling without providing a chance to opt-in or opt-out.

**Pros**: we'd be sure to receive the data as there is no way to opt out of it. 

**Cons**: developers using it might not like the idea of diagnostic data being collected without their own approval.


## Option 2: opt-in

**Pros**: no automatic collection of diagnostic data without the explicit approval first (maximum transparency).

**Cons**: as it's often the case, most of the user will never opt-in and this might severely limit out chances to receive data .


## Option 3: opt-out

**Pros**: although users can still opt-out, by default profiling is enabled and this should give us a bigger pool and hence more data.

**Cons**: this is less "transparent" then the opt-in strategy as diagnostic data will be collected without explicit approval first. 

# Drawbacks/Impact

Here are listed the major concerns about potential drawbacks of profiling the `sentry-cli`

1. **program crashing**: while during our experimental tests (on Debian and MacOS) this didn't occur, therefore making us quite confident about the stability of the profiler, we haven't yet had the opportunity to test it across a wide range of hardware or Unix distributions so, this is a legitmate concern to take into account
2. **performane**: generally speaking, by adding instrumentation and enabling profiling we'd expect an overhead. This though should not represent a big problem for the following reasons:
    * **overhead no more than 5%**: we have a 5% max overhead for profiling across our SDKs implementations. The Rust profiler is no different and from our benchmark it turns out to be even less than that
    * **low traces_sample_rate**: we're planning to only sample 5% of the transactions/profiles
    * **non mission-critical** tool: this is not a mission critical backend service so, while we don't want it to crash or degrade its performance, a slight overhead would still be acceptable