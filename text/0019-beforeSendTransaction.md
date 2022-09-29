* Start Date: 2022-09-26
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/19

# Summary

Proposal to make `beforeSend` (or a similar method) work for transactions (and possibly other payload types in the future) in all SDKs.

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

_(Revised after preliminary discussion in https://github.com/getsentry/rfcs/pull/19)_

### **Option 1**

_(Original proposal, demoted to one option of several after discussion)_

Add `beforeSendTransaction` to all SDKs, which (as the name implies) would work exactly the same way `beforeSend` does, but would act upon transactions.

Pros:
- Not a breaking change, so less pain for customers in the short run.
- Not a breaking change, so no need to wait for a major release to implement it.

Cons:
- Increased API surface.
- Code that acts on shared event properties (tags, contexts, etc) would need to be duplicated between `beforeSend` and `beforeSendTransaction`.
- Unclear/non-parallel naming when considered alongside `beforeSend`. (`beforeSendTransaction` is a clear name, but `beforeSend` is not - it really ought to be `beforeSendError`; similar problem to current confusion with `sampleRate` and `tracesSampleRate`.)
- Future payload types (replays, profiles, etc) would need their own methods. Where does it end?

### **Option 2**

In the next major of each SDK, start sending both errors and transactions through `beforeSend`.

Pros:
- `beforeSend` has a seemingly-universally-applicable name, so the most intuitive thing for users is to have it fulfill its implied role and apply universally.
- Future payload types could  be added without introducing new init options/versions of the method.

Cons:
- Potentially breaking change for everyone, even people not using tracing, because old assumptions about `beforeSend` input schema would no longer hold. (We could maybe work around this by just surrounding our `beforeSend` call with a `try-catch` and returning the event untouched if things go sideways.)

### **Option 3**

Like option 2, except `beforeSend` doesn't change and instead we create a new universal method to take its place.

Pros:
- Not a breaking change, so less pain for customers in the short run.
- Not a breaking change, so no need to wait for a major release to implement it.

Cons:
- What would we call it? The most logical name given other option names (`beforeBreadcrumb`, `beforeNavigate`, etc) is already taken.
- What would happen to `beforeSend`? Either we'd eventually either: 1) deprecate and remove it, which just kicks the breaking-change can down the road, or 2) keep it around in perpetutity, which isn't great either, because it would probably continue to confuse people (both by providing a less-functional way to do what the new method does and by _still_ not being named `beforeSendError`).

### **Option 4**

_(Listed for the sake of completeness, and not a bad idea in and of itself, but by general consensus probably not the right option here)_

Implement lifecycle hooks for transactions (and possibly replays, profiles, etc in the future)

Pros:
- Granular control
- Depending on how we do it, might line us up with OTel.

Cons:
- Significantly bigger footprint than other options, not only in terms of work to build it but also documentation, support, and bundle size.
- Would act primarily on `Transaction` objects whereas we're trying to match `beforeSend`'s ability to act on finalized events.

# Drawbacks

Compared to doing nothing, the only drawbacks to any of the above options are the time and effort it will take to implement and document the changes. (In other words, the idea of giving people `beforeSend`-like powers over transactions doesn't have any notable drawbacks on its own.)

# Unresolved questions

- If we go with the `beforeSendTransaction` option, what all should go in the hint? Are we happy with the `beforeSendTransaction` name, or are there better alternatives?
- If we go with a new universal method, what should we call it? What should happen to `beforeSend` afterwards?
- Once we do this, should we deprecate `addGlobalEventProcessor` as a public API method? (Not inherently a part of this change, but something that was spoken of in the past but then backed away from because event processors were the workaround to the problem this RFC is trying to solve.)
