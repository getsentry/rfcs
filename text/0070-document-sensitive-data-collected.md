- Start Date: 2023-01-27
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/70
- RFC Status: draft

# Summary

We need an exact but concise documentation on what sensitive data our SDKs collect. This should be available in the SDKs documentation on docs.sentry.io and be specific to all the integrations that each SDK supports.

This RFC is related to [RFC-0062 Controlling PII and Credentials in SDKs](https://github.com/getsentry/rfcs/pull/62).

# Motivation

We collect a lot of data, and transparency creates trust. This documentation will make it easier for customers to choose Sentry because they know that their users data is in good hands.
It will also make it easier for our customers to be GDPR compliant. Companies that deal with data related to persons in the european union need to create a record of what data they are processing.
This documentation will make our customers lifes way easier while creating these records.
This will probably be a big selling point for larger customers.

# Background

After a data incident and a meeting with legal, we said that we need to take data issues to the next level.

# Options Considered

## A) Table in docs of each integration

Have a hand written (and maintained) table in the description that shows people in an easy to grasp way what data is collected. It also shows how the data collection is changed when certain options (like `sendDefaultPII`) are changed.

Here a example on how this could look like:
https://sentry-docs-git-antonpirker-python-fastapi-sensitive-data.sentry.dev/platforms/python/guides/fastapi/#data-collected

The elements in the table can be different for different kinds (frontend, backend, mobile) of SDKS.

Here a list of all sensitive data that is collected:

- HTTP Headers (`event.request.headers`)
- HTTP Cookies (`event.request.cookies`)
- HTTP Request Body (`event.request.data`)
- Log Entry Params (`event.logentry.params`)
- Logged in User (`event.user`)
- Breadcrumb Values (`event.breadcrumbs.values -> value.data`)
- Local vars in Exceptions (`event.exception.values -> value.stacktrace.frames -> frame.vars`)
- Span Data (`event.spans -> span.data`)

Pros:

- Easy understandable and nice to read documentation

Cons:

- Documentation need to be kept up to date with seperate PR in `sentry-docs` repo when changes to SDK are made
- Documentation for different versions of the SDK not solved yet

## B) Automatic documentation creation

If we go with _Option B)_ in [RFC-0062 Controlling PII and Credentials in SDKs](https://github.com/getsentry/rfcs/pull/62) we could add doc strings in the code of the implemented `EventScrubber` and then generate documentation from this code to render a table similar to the one in Option A) in this RFC.

Pros:

- Generated from code, so it should be always up to date
- Possible to render docs for different versions of the SDK

Cons:

- Doc strings in code need to be kept up to date.
- Need to write tooling for exporting doc string from all SDKs to be able to include the generated documentation into docs.sentry.io

## C) \*\*please suggest\*\*

If you have another idea on how to document this, please and an option here.

# Drawbacks

People tend to forget about documentation and then we end up with outdated documentation, which is kind of worse than having no documentation at all.

# Unresolved questions

- How do we guarantee, that the documentation stays up to date with the implementation?
- Do we need documentation tied to different versions of SDKs?
- We should probably add some checks in CI that make sure that code changes need to be documented as well?
