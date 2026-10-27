* Start Date: 2022-09-17
* RFC Type: feature
* RFC PR: 0010
* RFC Status: draft

# Summary

This RFC suggests a feature which introduces additional types of exceptions next to `mechanism.handled`.

# Motivation

Currently, exception which cause the running software to exit (the process died/hard crash) are marked as `handled: false`. This isn't enough for SDKs where an exception can be unhandled but at the same time doesn't cause the software to exit.

Sentry shows exceptions which aren't caught by the developer (unhandled) but also do not cause the software to exit in the same way as exceptions which are manually caught by the developer. This seems rather unintuitive and makes exceptions seem less severe than they are.

This issue impacts for example the [Dart/Flutter SDK](https://github.com/getsentry/sentry-dart/issues/456), the Unity SDK, the React Native SDK and possibly more.

Another issue is, that excpetions which don't cause the software to exit but are unhandled, are not considered in the [`session health` metric](https://develop.sentry.dev/sdk/sessions/).
Currently, the session would be marked as `errored` instead of `crashed`.

The attribute `thread.errored` was added in the past for similar reasons, but it got [reverted on Relay](https://github.com/getsentry/relay/pull/306) and [Android](https://github.com/getsentry/sentry-android/pull/187).

# Option 1 (recommended)

Based on the problem stated above, I propose to introduce the types of `handled`, `unhandled`, `process termination` (this is the same as the current `handled`, but rephrased to avoid confusion). I'm open for better phrasing of those types, but I'll stick to those names for the rest of the RFC. The meaning of those types is as follows:

- `handled`: The exception was recorded by a developer via `Sentry.capture*` method. May or may not be visually indicated by the Sentry user interface.
- `unhandled`: Indicates whether the exception was recorded automatically by Sentry through the use of a global exception handler or similar. This exception however didn't cause the software to exit, and the software will continue to be executed. This should be visualized in the Sentry user interface, they have a higher severity than the `handled` ones.
- `process termination`: The exception was recorded automatically by Sentry through the use of a exception handler or similar. The exception caused the software to terminate the execution. This should be visualized in the Sentry user interface. This is currently done by the `handled: false` flag in the [exception mechanism](https://develop.sentry.dev/sdk/event-payloads/exception/#exception-mechanism).

A user of Sentry should be able to 

- filter events on the issues page or discover for the newly introduces exception types (3 categories).
- highlight (similar to the unhandled label) events of the type unhandled and process termination.
- get alerted for events of the type unhandled and process termination separately.

Currently, there's an unhandled label on the issue's page but it's only highlighted for process termination errors (if `handled: false`).

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

In order to achieve backwards compatibility, in the absence of the `process_terminated` flag, the current behavior stays as is.
As soon as the `process_terminated` flag is present the bavior is as follows:

- `handled = false` and `process_terminated = false`: Exception is not handled by the user but didn't cause the software to terminate. Same as `unhandled` in the list above
- `handled = false` and `process_terminated = true`: Software terminated after an unhandled exception. Same as `process termination` in the list above
- `handled = true` and `process_terminated = false`: Exception was reported via `Sentry.capture*()` method. Same as `handled` in the list above.
- `handled = true` and `process_terminated = true`: Software was gracefully shut down after an handled exception. This should never happen and is invalid.

In the absence of the `handled` or its value being null, it's assumed to be `handled = true`. This is also the current behavior.

The introduction of the `process_terminated` flag enables the consideration of such exception types in the `session health` metric.

The [session protocol](https://docs.sentry.io/product/releases/health/#session-status) would need to change as well though, because there are only `errored` and `crashed` states.

# Option 2

This one is very similar to option 1, however instead of an additional flag, this introduces an enum for the different types.
Once again, the mechanism needs to be adapted:

```json
{
  "exception": {
    "values": [
      {
        "type": "Error",
        "value": "An error occurred",
        "mechanism": {
          "type": "generic",
          "exception_type": "handled|unhandled|process_termination", // <--- newly introduced field
        }
      }
    ]
  }
}
```

If the currently available `handled` flag is also present, the `exception_type` flag takes precedence. The `handled` flag however should become deprecated.

The introduction of the `exception_type` flag enables the consideration of such exception types in the `session health` metric.

# Option 3

Unhandled exceptions, which don't cause a process termination, are considered like exceptions which cause the process to terminate and are marked `handled: false`
That would however make it impossible to differentiate between those exception types in the `session health` metric, filters, alerts, etc.

# Approaches taken by other monitoring tools

- Crashlytics just differentiates between manually caught exceptions and unhandled exceptions, regardless of whether they cause the process to terminate.

# List of SDK to which this applies

This list might be incomplete

- [Flutter](https://github.com/getsentry/sentry-dart/issues/456)
- Browser SDKs
- Unity
- React Native
- .NET (UnobservedTaskException)

# Unresolved Questions

- Are there any other exception types next to the ones metioned in this RFC?
- When there's an unhandled exception, we'd automatically finish the transaction bound to the scope, but only if the app crashes (process termination)? See [issue](https://github.com/getsentry/develop/issues/443).
