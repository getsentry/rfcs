* Start Date: 2022-07-21
* RFC Type: informational
* RFC PR: https://github.com/getsentry/rfcs/pulls/2

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

These are long running concerns with the processing pipeline that should be adressed.

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

### Traffic Steering

### Partial Project Options

## Service Infrastructure

### In-Monolith Service Compartmentalization

### Service Declarations

### Serverless Function Declarations for Consumers
