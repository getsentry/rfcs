- Start Date: YYYY-MM-DD
- RFC Type: feature / decision / informational
- RFC PR: <link>
- RFC Status: draft

# Summary

Reduce the number of profiles and replays dropped through dynamic sampling by
changing how trace sampling decisions are computed.

# Motivation

- Replays need traces, yet have low overlap with client-sampled traces on low
  sample rates
- Profiles have improved this by coupling client-side decision of profiles to
  traces (profiles sampled as subset of sampled traces)
- Both for profiles and replays, traces are dropped by server-side sampling.
- Creating bias eats away from DS budget, leads to lower quality traces

Objective:
- Increase affinity of replays to traces
- Maximize likelihood of generating traces with BOTH replays and profiles
- Minimize impact on DS (don't oversample)

"We don't oversample, as many profiles and replays are stored while DS still
operates at sample rates."

# Background

- DS is based on two components: (1) random number (2) cutoff percentage.
- Sampling multiple times with a different random number effectively multiplies
  the sample rate. Example: 10% x 10% = 1%. This is what happens to Replays
  today.
- Sampling multiple times with same random number means the sampling decision
  stays the same. This is how traces are sampled consistently without
  synchronization.
- If the sample rate changes, we observe an interesting effect:
    - Higher sample rate means no change. All previously sampled traces sampled
      again.
    - Lower sample rate: a top bracket is removed, so effectively the sample
      rate is „downgraded“.

# Coupled Sampling Decision

Couple the sample rate of replays to server-side DS by sharing the random number
via DSC. With this, the maximum number of traces with replays will be passed
through.

Generalization: Define as sparse data sample seed. Use the same random number
for profiles. This means, the lowest common sample rate of profiles + replays +
server DS always has fully enriched traces.

If sample rate is missing, sever applies DS like before.

## Sub-Trace Sampling

- Sparse data that is existentially bound to traces becomes a second sample
  decision after the trace sampling decision.
- Profiles follows this model already
- SDK change needed for Replays
- Replay sample rate is therefore based on trace-sample rate. Used to be
  different before (TODO double-check).

## Implications on client-side trace sampling

- DS model requires conventional double-sampling with decoupled seeds for client
  <> server sampling.
- Traces sample rate stays separate and receives its own seed.
- For replays, traces sample rate should be scoped to session, too. (would allow
  tracking UX journeys)

# Drawbacks

> Why should we not do this? What are the drawbacks of this RFC or a particular
> option if multiple options are presented.

- Sample seed determines server-side sampling. If a client tampers with the
  seed, we can significantly over/under sample.
- New client option for SDK config.
- Doesn't work for replays with errors.

# Unresolved questions

- Client SDK option
- Session sampling (see RFC 0109)
