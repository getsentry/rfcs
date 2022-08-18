* Start Date: 2022-08-18
* RFC Type: decision
* RFC PR: https://github.com/getsentry/rfcs/pull/4

# Summary

This RFC proposes a preliminary refactoring of the Sentry monolith in order
to support later compartmentalization into services by eliminating mass
re-exports in `sentry.app` and `sentry.models`.  The goal is to make the
dependency tree easier to understand in order to break it into separate
services by making modules the boundary of our dependencies.

In other words we want to be able to say that if module A depends on module B
it depends on the entirey of it.  Today this is violated by a `sentry.app`
and `sentry.models`.

# Motivation

Sentry's CI and even local testing times are quickly increasing through the
code size in Sentry.  We run pretty much all tests at all times as we are not
able to determine which change is going to require which code to run.  The
solution in parts to this will likely be to compartmentalize Sentry into smaller
services.  Today drawing these service boundaries however is relatively tricky
because a lot of code within Sentry is deeply intertwined.

This also in parts shows up in import times.  To run a single test file for a
utils module (`test_rust.py`) pytest will spend 0.2 seconds in test execution vs
2 seconds in import time.  While imports are so far acceptable, the bigger issue
caused by it is that it increases the total amount of surface that we need to
consider for test execution.

The main motivator however is the inability to draw boundaries within Sentry
today.  For instance today `sentry.http` pulls in `sentry.models` (to import
`EventError` to access a constant) which pulls in _all_ database models.
`sentry.http` itself is needed by `sentry.utils.pytest.sentry` and some other
places.  Because all models are imported, not just the model declarations are
imported but a lot of the application.  For instance via the
`sentry.models.identity` the `sentry.analytics` system is pulled.
`sentry.models.integrations` will pull in the entire integration platform code
including `sentry.pipeline` which drags in the entire incidents system, API
helpers and more.  `sentry.models.organizationmember` pulls in `sentry.app`
which then pulls in `tsdb`, `buffer`, `nodestore` etc.

While it's undoubtedly true that today many of these imports will happen anyways
as we are globally configuring sentry in the tests, getting imports under control
will let us slowly break the Sentry monolith into distinct services in an easier
and more controlled manner.

Making these imports however explicit enables us to better understand the real
dependencies through imports.  Today we cannot use import tracking to see the
real dependencies because they are obfuscated through the mass re-exports.

# Background

This proposal came out of the desire to attempt to isolate the processing
pipeline out of the majority of the Sentry codebase.  The end goal for that is
to be able to perform important changes to the event processing pipeline in
isolation of the rest of the code base to reduce the time spent in CI for
important changes to it.

As such all code related to the processing pipeline should be moved into a clear
structure and have a largely independent test setup (think moving all of processing
related logic to `sentry.services.processing` or `sentry_processing` for better
enforcability).

# Options Considered

the proposal is to require developers to import models from the declaring model
instead of the re-import.  that means rather than to import
`from sentry.models import User` the developer is required to import
`from sentry.models.user import User` instead.  This has a few benefits:

1. People are less likely to accidentally use imports out of the `sentry.models`
  module that exist today but were unintentional.  As an example we have seen
  users of `from sentry.models import Any` because vscode adds auto imports from
  the first seen module and it happens that we accidentally re-export the `Any`
  type from `sentry.models` rather than `typing`.
2. It becomes easier to understand what is declared where when not using IDEs.
  In particular some of the constants which are currently imported from the
  `sentry.models` module can be hard to pinpoint to (eg: where is `sentry.models.ONE_DAY`
  coming from?)
3. We can start enforcing isolation on the module level to enable 
  compartmentalization with lints.

# Rollout Plan

The implementation of the migration path is a multi stage process:

1. fully canonicalize all the imports from `sentry.app` and `sentry.models`
   in `getsentry` and prevent the introduction of future through a lint.  After
   this point all changes can be seen locally to `sentry`.
2. fully canonicalize all the imports from `sentry.app` in `sentry`.
3. remove the re-exports in `sentry.app`.
4. gradually canonicalize the imports of models from the `sentry` codebase.
5. eliminate the re-exports of models in `sentry.models`.

# Drawbacks

The drawback of this change is that imports become more verbose:

Before:

```python
from sentry.models import Integration, OrganizationIntegration, Organization, \
    OrganizationMember, User
```

After:

```python
from sentry.models.integrations import Integration, OrganizationIntegration
from sentry.models.organization import Organization
from sentry.models.organizationmember import OrganizationMember
from sentry.models.user import User
```

# Outside of Scope / Unresolved Questions

This RFC does not yet set out a plan for the actual comparmentalization.  The goal
is to start enabling the ability to use the module boundary to track and visualize
dependencies.

Out of scope is also the eliminiation of further star re-exports.  The majority of
other star re-exports we have are somewhat contained within modules which are already
largely self contained modules.  As an example `sentry.identity` has a lot of star
exports from the different identity modules (`github`, `slack`, `google` etc.).  As
we are likely going to consider this to be a self contained piece of code there is
only limited benefit of changing this.

However poventially we want to be more specific about re-exporting in modules by
being explicit about what is being re-exported to make code discovery easier and to
avoid accidentaly mis-imports such as pulling in types from `sentry.models`.
