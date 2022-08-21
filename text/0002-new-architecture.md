* Start Date: 2022-07-21
* RFC Type: informational
* RFC PR: https://github.com/getsentry/rfcs/pull/2

# Summary

This document is a living piece that is updated with some collected thoughts on what likely projects
are over a multi year horizon to improve Sentry's underpinnings.

# Motivation

We are running into scaling limitations on our current infrastructure and as such some larger
decisions have to be made about the future of our codebase.  As we are talking about creating
more Sentry deployments in different regions and for smaller clusters, some of these problems
are becoming more pressing as they create complexity for each added installation.

# Expected Workstreams

This captures all expected streams of work that are in the scope of overhauling Sentry's
architecture.

## Processing Pipeline

These are long running concerns with the processing pipeline that should be addressed.

### Isolate Processing Pipeline out of Monolith

The celery tasks, event manager and related functionality used by the processing pipeline is living
alongside the rest of the Sentry code in the `sentry` monolith.  This means that it's quite chaotic
and many unintended cross dependencies are regularly introduced into the code base.  As some of the
processing pipeline wants to move out of the monolith for better scalability (in some extreme cases
even move out of Python as host language) it would be helpful by moving all of the processing pipeline
into a `sentry_pipeline` package.  It would be permissible for `sentry_pipeline` to import `sentry`
but not the other way round.

This will cause issues in the testsuite as the sentry test suite currently tries to create events
regularly and pragmatic solutions for this need to be found.

### Remove Pickle in Rabbit

We still use pickle as serialization format for Celery which means that it's not possible for code
outside of the Sentry monolith to dispatch tasks.  This is both an issue for the separation of
`sentry` and `sentry_pipeline` (as import paths are changing) as well as it causes problems for
dispatching and listening to tasks from Rust and other languages.

### Remove HTTP Polling to Symbolicator

The form of communication for event processing from the Python pipeline to Symbolicator (which is a
Rust service) involves polling the symbolicator from Celery Python workers.  This has shown many issues
in the past where the entire thing can tilt if the load on the symbolicators moves too far from the
load assumptions of the Python polling workers.  The correct solution would be for tasks to be directly
picked up by symbolicator.

### Remove Celery and RabbitMQ for Kafka

Our use of RabbitMQ is reaching the limits of what can be done with this system safely.  If we hit
disk our entire pipeline crawls to a grind and we're no longer able to keep up with the traffic.
As such we are already throttling how the events make it from kafka rabbit in extreme cases.  We are
however relying on RabbitMQ to deal with the large variance of task execution times in the symbolication
part of the pipeline.  For instance a JavaScript event can make it in the low milliseconds through
the entire pipeline whereas a native event can spend up to 30 minutes or more in the pipeline in very
extreme cases (completely cold caches against a slow symbol server).

It should however still be possible to move this to a Kafka model where batches of tasks are redistributed
to slower and faster topics.  For instance the processing of the task could be started and if it's not
finishing within a deadline (or the code already knows that this execution can't happen) it would be
dispatched to increasing slower topics.  With sufficient concurrency on the consumers this is probably
a good enough system for running at scale and with some modifications this might also work well enough
for single organization installations.

### Move Sourcemap Processing to Symbolicator

Our sourcemap processing system is running in a mix of Rust and Python code by fetching a bunch of data
via HTTP and from the database models to then send the data fetched into a Rust module for resolving.
This is generally quite inefficient but we are also running into limitations in the workers.  For instance
we rely exclusively on memcache for caches which means that we are limited by our cache size limitations.
Anything above the cache size is not processable which can cause a bad user experience for users depending
on very large source maps.

Symbolicator has a file system based caching system with GCS backing for rapid synching of new symbolicator
instances we could leverage.  Additionally symbolicator has a better HTTP fetching system than Sentry as
it's able to concurrencly fetch whereas the Sentry codebase is not.

Future feature improvements on the source map side might also demand more complexity in the processing side
which we are not currently considering given already existing scalability concerns on the existing workers.

## Python Monolith

These are changes to break up the monolith.  The goals here are largely that different teams can work largely
uninterrupted of each other, even on the monolith.  For instance in an ideal scenario changes to an integration
platform code do not necessarily have to run the entire Sentry testsuite on every commit.  Likewise UI code
ideally does not build the entirety of the Sentry UI codebase.

### Import Compartmentalization

As a first start imports in the Sentry codebase should be compartmentalized as much as possible.  Today we have
some catch all modules like `sentry.models` which import everything.  This means that it's hard for as to track
the actual dependencies from different pieces of code and also hides away circular imports.  One of the results of
this is that if you run a test against a single pytest module, you still pull in the entire codebase which already
takes a couple of seconds.  It also means that it's harder for test infrastructure code to analyze the minimal set
of dependencies that might need testing.

Likewise code in `sentry.utils` should most likely no longer import models etc.  Some of that code might event
move out of `sentry` entirely.

### Move Code from Getsentry to Senty

Currently quite a bit of code lives in `getsentry` for reasons of assumed convenience.  However this has created
the situation that it is quite easy to ship regressions because the changes in `getsentry` were not considered.
There is likely a whole range of code that does not need to live in `getsentry` and moving it to `sentry` would
make the testsuite more reliable, faster to run and catch more regressions early.

### Remove Pickle in Database

We still use pickled models in database code quite extensively.  This reliance on pickle makes it harder than
necessary to read and write from this outside of the main Python codebase.  Moving this to JSON will simplify the
handling of moving such code into environments where other code wants to access it.  We already require depickling
in the data pipeline for such cases.

### Phase out Buffers were Possible

Buffers as they exist today could in many cases be replaced by better uses of Kafka and clickhouse.  Some buffers are
not even as important any more for the product.  For instance the total counts for issues are already hidden from the
more prominent places in the UI.  The issue with buffers is that they are rather hard to scale, require the use of
pickle for the model updates and are hard to work with when it comes to filtering.  For instance we are able to give
you the total event count on an issue, but not when broken down by some of the filters that the UI wants to provide
(environment and release is possible, but any tag search will not able to give the right counts).

## Relay

Within relay some changes are likely to be necessary for continued to support of providing a stable service.  In
particular as more and more work moves into Relay certain risks that the current architecture is carrying need to
be addressed.  The goals here are horizontal scalability, the ability to route data more efficiently and to recover
from catastrophic failures.

### Traffic Steering

As we are now performing aggregations in Relay it's benefitial to be able to route traffic intelligently through the
layers.  For instance we can achieve much better aggregations by ensuring that data from related metrics keys are
forwarded to the same processing relays.

### Partial Project Options

Relays currently get one project config per project both via the HTTP protocol and by picking them up internally from
a redis key.  The size of this config package is exploding as more and more functionality is added.  There are many
benefits from splitting this up which should improve our ability to partially degrade service rather than the entire
project, reduce the pressure of redis and make updates faster.  For instance an experimental feature should ideally
gets its own config key and the inability to generate that config could still retain functionality for the rest of
the project.

### Separation of Traffic Classes

Relay currently forwards all envelopes to the next relay in chain the same.  There are however benefits by being able
to route sessions to different relays than for instance transactions or errors.  Particularly for future projects such
as session replays and profiling it would be nice to be able to route experimental features to a specific relay rather
than having to roll out the experimental support across the entire cluster of relays.

### Modularization in Relay

Clear up envelope processor to make it easier to add new items types etc and make it easier to add new functionality.
Today the massive envelope processor needs to be updated for every single item type added.  This opens many questions
about how different items should work on different layers of relay, how they are routed etc.  As we are adding more
item types this can turn more into a serverless function like internal API for adding item types that make it easier
to land new items.

### Relay Disk Buffer

Relays currently buffer all data in memory which means that if they go down, we lose data.  Instead relay ideally buffers
all its data additionally in a Kafka topic or on-disk storage that can make recovery from extended downtime possible.

### Partial Grouping Awareness in Relay

Today our grouping system really can only run in the tail end of the processing pipeline.  This makes it impossible for
us to perform certain types of filtering or grouping decisions in relay.  There is a range of issues that could already
be grouped quite accurately in Relay which would then permit us to do metrics extraction in relay or to perform efficent
discarding.

### Tail-based Sampling / Distributed Sampling Context Buffer

Relay is currently unable to perform tail based sampling or consistent sampling if the dynamic sampling context changes.
This could be remedied by extensive buffering or alternative approaches.  While a full tail based sampling approach is
likely to be quite costly, there might be hybrid approaches possible.

## Service Infrastructure

These are changes to the Sentry architecture to better support the creation of independent services.

### In-Monolith Service Compartmentalization

The Sentry monolith currently houses a range of small services that are however clustered together.  For instance the
processing pipeline really could be separated entirely from the rest of the System.  However the same is true for quite
a lot of different parts of the product.  For instance certain parts of the user experience are sufficiently idependent
in the UI code today already that they could turn into a separate service that just supplies UI views together with some
APIs.  While it's unclear if the existing experiences are worth splitting up into new services, it's probably likely that
we can at least structure their code so that we can reduce the total amount of pieces of code that need to be checked and
tested against changes.

In the ideal situation a change to the settings page of a project for instance does not need to run the UI tests for
performance views etc. unless the settings are in fact related to that component.

### Service Declarations

The biggest limiting factor today in creating new services is the configuration of these services.  When an engineer adds
a new service there is typically a followup PR against the internal ops repo to configure these services for the main
sentry installation.  Then there is some sort of ad-hoc workaround to make the whole thing work in local development, how
to make it work on a single tenant or self hosted installation.  Each new services undergoes a new phase of rediscovery how
suboptimal the rules and policies around scaling these services are.

Ideally we were able to describe the services in a config file (YAML?) which then can be consumed by deploy tools to
correctly provision and auto scale services.  This could either be a Sentry specific format or we adopt something that
has already been tested.

### Serverless Function Declarations for Consumers

The smallest unit of execution at Sentry is not a docker image but in fact a function.  We currently have no real serverless
setup but we have a few functions that are run as a kafka consumer, queue worker or similar.  Like services making these
scale is quite tricky and in some situations we need to needlessly spawn more processes and containers even though they
could be colocated.

## Data Store

These are abstract changes to the data store.  Largely this is not explored yet but some things are known.

### High Cardinality Metrics

As we are extracting metrics data from the existing transaction system we have effectively unlimited cardinality
in the data stream coming in.  The system currently applies various different attempts of dealing with this problem
where a lot of this is done on the Relay side.  This comes from the combination of the hard cardinality limited in
Relay but also by attempting to not generate high cardinality data in the clients.

However it's likely that we will be unable to reduce cardinality in the long run and the data model should ideally
be able to represent this high cardinality data.

## Client Pipeline

These are changes we expect in the protocl and client behavior.

### Push Config into Clients

Certain features such as dynamic sampling benefit of being able to push settings down to clients.  For instance to turn
on and off profiling at runtime it does not help us to discard unwanted profiles on the server, we want to selectively
turn on profiling.  Other uses for this are turning on minidump reporting for a small subset of users optionally.  This
requires the ability to push down config changes to clients periodically via relay.
