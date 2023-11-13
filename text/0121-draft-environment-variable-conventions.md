- Start Date: 2023-11-07
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/121
- RFC Status: draft

# Summary

We already expose certain environment variables that are consumed by SDKs, such as `SENTRY_DSN` and `SENTRY_RELEASE`.
To further ease usage, we should expose more options as such.
This RFC aims to find a set of conventions mainly aimed for server-side SDKs.

# Motivation

Changing the SDK configuration most often requires a re-deployment of the application. This can be cumbersome for small changes,
such as updating the `traces_sample_rate`. Given the rise in populairty of server-less or containerized deployments, where
most configuration hails from envrionment variables, we should strive to make this workflow less cumbersome for our users.

# Background

The Laravel SDK exposes the majority of its configuration as environment variables, making it a breeze to update the configuration of the SDK easily.
For a complete list of exposed variables, see https://github.com/getsentry/sentry-laravel/blob/9624a88c9cd9a50c22443fcdf3a0f77634b11210/config/sentry.php

# Options Considered

A first list of environment variables that all server sides SDKs should support could look like:

- `SENTRY_DSN`
- `SENTRY_RELEASE`
- `SENTRY_ENVIRONMENT`
- `SENTRY_SAMPLE_RATE`
- `SENTRY_TRACES_SAMPLE_RATE`
- `SENTRY_PROFILES_SAMPLE_RATE`
- `SENTRY_DEBUG`

Further additions could include but are not limited to:

- `SENTRY_TAGS_<tag-key>` - An environment variable of `SENTRY_TAGS_foo = "bar"` would result in a tag of `foo: bar` being attached to all events.

or SDK/framework-specific options, such as to control integrations or features

- `SENTRY_BREADCRUMBS_LOGS_ENABLED`
- `SENTRY_TRACE_MISSING_ROUTES_ENABLED`

# Drawbacks

TBD
