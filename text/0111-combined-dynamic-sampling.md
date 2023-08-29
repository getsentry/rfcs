- Start Date: 2023-08-29
- RFC Type: feature
- RFC PR: <https://github.com/getsentry/rfcs/pull/111>
- RFC Status: draft

# Summary

Reduce the number of profiles and replays dropped through dynamic sampling by
changing how trace sampling decisions are computed.

# Motivation

Profiling and Replays are two Sentry features that heavily depend on connected
traces with transactions and spans. These spans provide vital debugging
information to the point where both features are considered incomplete without
an attached trace.

In practice, all of this data has to be sampled on the client (SDK) so that the
SDK does not incur too much overhead on the measured application and does not
saturate the network link to Sentry. For this, the SDK features three sample
rates:

1. `tracesSampleRate`: Defines the percentage of traces captured and sent to
   Sentry.
2. `profilesSampleRate`: Defines the percentage of **traces** for which a
   profile will be started and sent to Sentry.
3. `replaysSessionSampleRate`: Defines the percentage of **sessions** for which
   a replay will be started and sent to Sentry. Sessions usually outlive traces.

Since independent sample rates multiply, this creates a situation at low sample
rates for Replays where the overlap between sampled traces and sampled Replays
is too low. Since server-side sampling additionally drops traces, this leaves a
vanishingly small number of replays with traces stored.

Profiles have addressed this by coupling the client-side sample decision to
traces. The profile sample rate is a subset of the traces sample rate, so
profiling runs only in sampled traces. This ensures that 100% of profiles have a
trace attached. However, traces with profiles are still subject to server-side
sampling. Since the server-side sample decision is decoupled from the client,
the number of stored traces with profiles can still be too low, therefore.

Finally, there is no connection between sampled replays and sampled profiles. A
trace with a profile does not have a higher chance of having a replay captured
or vice versa.

# Objective

The goal of this RFC is to increase the affinity of replays and profiles to
stored (indexed) traces so that the likelihood of capturing traces with **both**
replays and profiles is maximized.

At the same time, the impact on effective dynamic sampling rates should be
minimized so that the number of stored events still closely tracks the target
fidelity.

# Background

Sampling on SDKs and the server is each based on two components:

1. A random number between `0.0` and `1.0`, called "sample seed".
2. A cutoff percentage, called "sample rate".

The sampler compares the seed to the rate: If the seed is lower, the data is
sampled, otherwise it is dropped.

Sampling can be performed multiple times in series, either with the same rate or
with different rates. The outcome of this depends primarily on how the sample
seed is handled:

- Using different seeds effectively multiplies the sample rates. For example
  _10% x 5% = 0.5%_. This is what happens between client-side and server-side
  sampling today.
- Reusing the same seed repeats the sampling decision. This is how dynamic
  sampling operates in ingestion without a need for synchronization between
  transactions or spans. The result is the lowest of all the applied sample
  rates.

The second option introduced above is also referred to as "coupled sampling",
since the sample decisions are coupled to each other. It can also be applied to
correlated data of different kinds each with their own sample rate. This creates
an interesting effect: Data sampled with the lower sample rate always has the
other kind of data available, since the decision is coupled.

![coupled-sampling](https://github.com/getsentry/rfcs/assets/1433023/5cf1dca7-b2af-42e2-83ca-231687b12e37)

# Coupled Sampling Decision

This RFC proposes to couple the client-side sample rates of sparse data
(profiles and replays) between each other and with server-side dynamic sampling:

1. When the trace starts, the SDK computes a sample seed for all sparse data.
2. Profiles and replays are recorded if their respective sample rates are higher
   than the sparse data sample seed.
3. The sparse data sample seed is placed on the DSC and propagated to all
   connected SDKs, as well as sent in Envelope headers to Sentry.
4. If available, Sentry uses the sparse data sample seed to compute the
   server-side dynamic sampling decision instead of the trace ID. If the seed is
   not present in the DSC, the sever applies dynamic sampling like before.

With this strategy, profiles and replays are sampled in common traces as much as
the sample rates permit, and dynamic sampling will prefer to store traces with
all data available.

## Sub-Trace Sampling

Sparse data that is existentially bound to traces is only collected if the trace
is sampled. Therefore, the SDK first always computes the trace sampling
decision. Only if that decision is positive, the SDK proceeds to check the
sparse sample seed against the respective sample rate. In practice, this makes
sample rates for spase data are "relative" to the traces sample rate.

Profiles already follow this model. To support coupled sampling for Replays, the
same shall be applied to sampling of Replay sessions: The replay sampling
decision should become coupled to the one of the trace, and the sample rate is
relative to the traces sample rate.

**TBD:** Decision on how to update SDK options.

## Implications on Trace Sampling

The trace sampling decision is intentionally **not** based off the sparse data
sample seed. SDKs continue to use the existing sampling and propagation strategy
for trace sampling decisions. The sample seed for traces does not have to be
synchronized between SDKs, since in this case the sampling decision suffices.

Keeping these seeds separate is important so that server-side dynamic sampling
still computes an independent sample decision for traces.

# Drawbacks

The sample seed directly determines the server-side sampling decision. If a
client tampers with the seed, the result can be significant over or under
sampling.

# Unresolved questions

1. How should the `replaysSessionSampleRate` SDK option be handled following
   this RFC? It can stay absolute, in which case the SDK must compute the factor
   to the traces sample rate. If it changes or a new option is introduced, users
   need to update their SDK options.
2. How should the `replaysOnErrorSampleRate` behave in comparison to the above?
3. Replays are sampled across entire sessions. See the [RFC
   0109](https://github.com/getsentry/rfcs/pull/109)) for a discussion on
   session sampling. If session sampling is adopted, the spare data sample seed
   should be propagated across the entire session.

# Discarded Options

- Creating a Replay bias constrains the ability to apply other forms of dynamic
  sampling, leads to lower quality traces, and in practice causes significant
  over-sampling.
