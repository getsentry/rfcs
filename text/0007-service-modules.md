* Start Date: 2022-08-31
* RFC Type: decision
* RFC PR: https://github.com/getsentry/rfcs/pull/7

# Summary

This RFC proposes a file structure for 'compartmentalized services' or 'domain
boundaries'. The concept of service boundaries was introduced in 0002, and this
document aims to provide more detailed guidelines for how 'services' in the
monolith would be structured as Python modules.

# Motivation

The sentry monolith continues to grow in scope as we build new product features.
As the application has grown the number of models, endpoints and tasks makes
understanding how the application is inter-connected more challenging. The
current code layout complicates optimizing CI, and impairs our ability to
clearly dilineate product boundaries within the monolith.

This RFC does not attempt to define what the boundaries and services within the
monolith should be. Nor does it attempt to describe the organization of
Typescript code.

# Background

Currently the Sentry monolith is organized as a single Django application that
follows a typical project layout organized by 'kind of class'. For example, all
models are co-located in a small number of directories, as are all endpoints and
serializers. While this repository layout has served us well, it is increasingly
hard to navigate as the application grows. At time of writing, we have:

* ~275 endpoint modules
* 115 model modules
* 105 serializer modules

Knowing how each of these classes are related to features in sentry is not
always obvious. A similar problem exists for tests as there is no way to easily
locate all the tests that need to be run when a model class changes.

# Proposed Python Structure

As sentry is a django application, we can leverage the
[Django-apps](https://docs.djangoproject.com/en/4.1/ref/applications/) to act as
a container for application services in the future. While not all services will
need all the features of Django Applications, many will.

## Django app structure

We'll use 'discover' as an example for the service modules

```
src/sentry/discover
    __init__.py
    app.py
    urls.py
    models/__init__.py
    models/discoversavedquery.py
    endpoints/discoverquery.py
    serializers/discoverquery.py
    tasks/deduplicate_things.py

tests/discover
    __init__.py
    models/test_discoversavedquery.py
    endpoints/test_discoverquery.py
    serializers/test_discoverquery.py
```

In addition to the Django related modules, celery tasks, consumers and any other
modules can be contained within a service. If a service doesn't provide
endpoints or use models it can still benefit from the proposed structure.

## Test location

Tests for a service would continue to live inside the top-level `tests`
directory. The `tests` tree would mirror continue to mirror the service + module
structure of the application code. Sharing naming conventions should make
running sub-sets of tests simpler to automate.

## Formal entry points to services

Service modules would use `__init__.py` to define the interface they present to
the rest of the Sentry monolith. Having the public interface of a service
formally defined limits the amount of entanglement the rest of the application
can create.

## Importing service internals is not allowed

An important change from the present application structure is that modules
outside of a service's scope would be *disallowed* from importing modules inside
a service. Modules outside of a service boundary may only import the top-level
service.

Disallowing cross-service internal imports could be enforced with the
[flake8-import-graph](https://pypi.org/project/flake8-import-graph/) extension.

# Options Considered

Another approach to this would be to put 'services' inside the directories of
each 'kind'. Again using discover as an example:

```
src/sentry
  endpoints/discover/discover_query.py
  models/discover/discoversavedquery.py
  serializers/discover/discoversavedquery.py
```

This approach dilutes the consistency benefits, and requires a significantly
more complex import graph rules. It also does not improve local development or
offer benefits to CI subsetting.

# Drawbacks

This approach will require moving **most** of the application source code
around. We currently store classpaths in several locations in the database. We
may need to use data migrations to update these paths or maintain aliases for
compatibility.

# Unresolved questions

* What 'services' would we need to add to the application?
* What do we do with models and logic that is shared by many endpoints/domains?
  Examples of this include rate limiting, and models like Organization, and
  Project? Should these be a single 'core' service? 
