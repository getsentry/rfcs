- Start Date: YYYY-MM-DD
- RFC Type: feature / decision / informational
- RFC PR: <link>
- RFC Status: draft

# Summary

One of the systems that Sentry internally operates today is an abstract concept referred
to as "file store".  It consists of a postgres level infrastructure to refer to blobs and
a go service also called "file store" which acts as a stateful proxy in front of GCS to
deal with latency spikes, write throughput and caching.

This RFC summarizes issues with the current approach, the changed requirements that go
into this system and proposes a path forward.

# Motivation

Various issues have ocurred over the years with this system so that some decisions were
made that over time have resulted in new requirements for filestore and alternative
implementations.  Replay for instance operates a seperate infrastructure that goes
straight to GCS but is running into write throughput issues that file store the Go service
solves.  On the other hand race conditions and complex blob book-keeping in Sentry itself
prevent expiring of debug files and source maps after a period of time.

The motivation of this RFC is to summarize the current state of affairs, work streams that
are currently planned are are in motion to come to a better conclusion about what should be
done with the internal abstractions and how they should be used.

# Background

blah

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
