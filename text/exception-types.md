* Start Date: 2022-09-14
* RFC Type: feature
* RFC PR: -
* RFC Status: draft

# Summary

This RFC suggests a feature which introduces additional types of exceptions next to `unhandled`.

# Motivation

Currently, exception which cause the running software to exit are marked as `unhandled: true`. This isn't enough for SDKs where an exception can be unhandled but at the same time doesn't cause the software to exit.

Sentry shows exceptions which aren't caught but also do not cause the software to exit in the same way as exceptions which are manually caught by a developer. This seems rather unintuitive and makes exceptions seem less severe than they are.

This issue impacts for example the [Dart/Flutter SDK](https://github.com/getsentry/sentry-dart/issues/456), the Unity SDK, the React Native SDK and possibly more.

Another issue is, that excpetions which don't cause the application to exit but are uncaught, are not considered in the [`session health` metric](https://develop.sentry.dev/sdk/sessions/).

# Proposal

Based on the problem stated above, I propose to introduce the types of `handled`, `unhandled`, `process termination` (this is the same as the current `unhandeld`, but rephrased to avoid confusion). I'm open for better phrasing of those types, but I'll stick to those names for the rest of the RFC. The meaning of those types is as follows:

- `handled`: The exception was recorded by a developer via `Sentry.capture*` method. May or may not be visually indicated by the Sentry user interface.
- `unhandled`: Indicates whether the exception was recorded automatically by Sentry through the use of a global exception handler or similar. This exception however didn't cause the software to exit, and the software will continue to be executed. This should be visualized in the Sentry user interface.
- `process termination`: The exception was recorded automatically by Sentry through the use of a exception handler or similar. The exception caused the software to terminate the execution. This should be visualized in the Sentry user interface. This is currently done by the `unhandled` flag in the [exception mechanism](https://develop.sentry.dev/sdk/event-payloads/exception/#exception-mechanism).

In order to propagate those exception types, the exception mechanism needs to be adapted:

```json
{
  "exception": {
    "values": [
      {
        "type": "Error",
        "value": "An error occurred",
        "mechanism": {
          "type": "generic",
          "handled": true,
          "process_terminated": false // <--- newly introduced field
        }
      }
    ]
  }
}
```

In order to achieve backwards compatibility, in the absence of the `process_termination` flag, the current behavior stays as is.
As soon as the `process_terminated` flag is present the bavior is as follows:

- `handled = true` and `process_terminated = true`: Software was gracefully shut down after an handled exception
- `handled = true` and `process_terminated = false`: Exception is not handled by the user but didn't cause the software to terminate. Same as `unhandled` in the list above
- `handled = false` and `process_terminated = true`: Software terminated after an unhandled exception. Same as `process termination` in the list above
- `handled = true` and `process_terminated = false`: Exception was reported via `Sentry.capture*()` method. Same as `handled` in the list above.

In the absence of the `handled` or its value being null, it's assumed to be `handled = true`.


The introduction of the `process_terminated` flag enables the consideration of such exception types in the `session health` metric.

I'm guessing this affects data ingestion layer, but since I'm not familiar with that part, I can't comment on the impact theses changes would have on that.

# Other options considered

Unhandled exceptions, which don't cause a process termination, are considered like exceptions which cause the process to terminate.
That would however make it impossible to differentiate between those exception types in the `session health` metric.

# Approaches taken by other monitoring tools

- Crashlytics just differentiates between manually caught exceptions and unhandled exceptions, regardless of wether they cause the process to terminate.

# Unresolved Questions

- Which SDKs would profit from this RFC? Is it the majority, a good chunk of it, or just the minory?
- Are there any other exception types next to the ones metioned in this RFC?
