* Start Date: 2022-09-26
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/19

# Summary

Proposal to add `beforeSendTransaction` to all SDKs.

# Motivation

For error events, `beforeSend` allows the user to make whatever changes they want to event data and to filter events however they want, which is useful for solving the cases where our built-in mechanisms for doing so don't correctly handle their particular use case. There is no such hook for transactions. Instead, users have to use `addGlobalEventProcessor` to add an event processor to the scope. This is less than ideal in a few ways:

- Ease of use (or lack thereof)
  - Nothing about `beforeSend` is obviously errors-only, so users assume it applies everywhere and try to use it for transactions.
  - Users have to learn two different ways to do effectively the same thing.
  - It forces users to write code in two separate places, which leads to potential redundancy if they want to act on any properties shared by error and transaction events.

- Lack of ultimate control over transaction events
  - Event processors happen in an unspecified order, and there's no guarantee a processor added by a user will run last. This means that an integration, for example, might change event data after the user's last chance to intervene.

(That last point is not _strictly_ true. As a last resort, a user could create a custom transport or could proxy events through their own servers, but both of those are pretty ugly, cumbersome workarounds.)

# Background

When transactions were introduced, the decision was made not to run them through `beforeSend` because they follow a slightly different schema, and therefore had the potential to break any existing `beforeSend` which relies on its input being a certain shape. It's unclear whether a transaction-specific `beforeSend`-type hook was discussed at the time.

# Supporting Data

Issues where this has come up:
- https://github.com/getsentry/sentry-docs/issues/5525
- https://github.com/getsentry/sentry-javascript/issues/4723
- https://github.com/getsentry/sentry-javascript/issues/5442
- https://github.com/getsentry/sentry-python/issues/1226

(and I'm sure many others)

# Options Considered

*Proposal*

Add `beforeSendTransaction` to all SDKs, which (as the name implies) would work exactly the same way `beforeSend` does, but would act upon transactions.

*Alternative*

In the next major of each SDK, start sending both errors and transactions through `beforeSend`.

*Comparison*

The main advantage the proposed `beforeSendTransaction` option has over the everything-goes-through-`beforeSend` option is that it's not a breaking change, and therefore doesn't need to wait for a major release to be introduced. (Non-breaking changes are also always less friction for the user, at least in the short run.)

The advantages the everything-goes-through-`beforeSend` option would have over the proposed `beforeSendTransaction` option are 1) all user code for filtering events and changing their data could live in one spot, and 2) we wouldn't be left with an option which is only for errors but doesn't say it's only for errors (similar to the current situation with `sampleRate` and `tracesSampleRate`). [EN: Reason number 2 actually makes me wish we _could_ go with the everything-goes-through-`beforeSend` option, but I recognize that avoiding user inconvenience has already pretty much won the day for `beforeSendTransaction`.]

# Drawbacks

Compared to doing nothing, the only drawbacks to either of the above options are the time and effort it will take to implement and document the changes.

# Unresolved questions

- Assuming we go with the `beforeSendTransaction` option, what all should go in the hint?
- Once we do this, should we deprecate `addGlobalEventProcessor` as a public API method?
- Are we happy with the `beforeSendTransaction` name, or are there better alternatives?
