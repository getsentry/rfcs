* Start Date: 2022-09-28
* RFC Type: decision
* RFC PR: <link>

# Summary

This RFC proposes to require a frontend SDK to retain a trace that it continues
until the SDK naturally ends the user session.  This change is primarily to the
browser trace model to better support dynamic sampling and to create a more
coherent user experience.

# Motivation

Today there are two ways to start a trace: they can be started on the backend and then
continued on the client, or they can be started on the client.  In either case however
client SDKs are likely to create more traces that are disconnected to the backend trace
on page navigation or view changes.  This creates the situation that today the only sensible
way for dynamic sampling is to have traces started uniformly on the frontend project as
otherwise the dynamic sampling rules from both projects need to be modified (head trace
is where dynamic sampling rules apply).

The secondary motivation is that creating new traces on navigation also wipes out the
causal relationship to what happened before.  For instance it's more than possible that
before a client-side navigation the state of the application corrupted, but we lose that
trace relationship and a user has to manually piece it back together by for instance
listing all transactions created by a specific user ID.

# Background

We became aware of this problem in two ways recently:

1. Users want to sometimes create a transaction within another transaction.  Today there
   is no way to link these together for the purpose of dynamic sampling.  A separate RFC
   [0014](https://github.com/getsentry/rfcs/pull/14) is proposed to add an explicit way
   to carry forward the sampling context for a new transaction started after an already
   existing one.  It works by explicitly continuing the trace.  This solves part of this
   issue, but it leaves out the case where the sampling context naturally moves to another
   Sentry project.

2. We wanted to change our own tracing integration to start tracing on the server
   [Sentry PR #39349](https://github.com/getsentry/sentry/pull/39349) where this would
   require mirroring the sampling settings to another Sentry project and would also affect
   API requests detatched from user sessions.

# Supporting Data

The [honeycomb whitepaper on front-end observability](https://www.honeycomb.io/wp-content/uploads/2022/03/Front-end-Observability-Whitepaper-1.pdf)
recommends continung traces from the server until the natural end of the user Session:

> To accomplish this task, you will use the first event (page load) as the start of your trace and
> connect that first event to additional spans to build a full trace of the user session. Each span
> will represent a single thing that you want to track, such as a server request or a user click.

# Options Considered

There are multiple ways in which this problem can be addressed.

## Encouraged Root Trace Project and Session Long Traces

In the most trivial case the recommendation to customers would be to pick one project that
starts traces for real user sessions.  This could be *either* the frontend or backend, but it
should attempt to be consistent about it.  In either case the client SDK should *continue the
trace* until the browser tab naturally closes.

The consequences are that ``startTransaction()`` always anchors to the already open trace
and dynamic sampling context.  There can be an extra flag to force the start of a new trace
but that would be strongly recommended against.

## Alternative A: Detaching Sampling Project from Root Project

An alternative approach would be to allow a transaction to start again on the client but to
continue with the sampling context that came from the server.  In that case the root of the
trace is in fact the frontend for continued transactions after a page navigate, however the
sampling context is reused from the original server side request.

In this case the relationship of root project setting the dynamic sampling context would be
broken up and instead a transaction can explicitly pick up the sampling context of another
project but still issue disconnected traces.

## Alternative B: Trace to Trace Relationships

A potential alternative would be to continue the current project but allow a trace to annotate
itself as being the successor of another trace.  Our data model currently does not have a
trace to trace relationship but such a desire has come up before with session replays.  In that
case when a new trace starts on the client, it can annotate itself as the successor of a prior
trace and take over that sampling context.

# Drawbacks

Not addressing this issue might result in user confusion later as front-end user sessions
are likely to originate in different projects with different sampling rules.  However future
direction assumes that sampling will eventually happen adaptively in which case the user
confusion is less likely to be an issue.

# Unresolved questions

* This RFC does not attempt to address the issue of traces vs sessions for replays or other
  RUM like situations.
