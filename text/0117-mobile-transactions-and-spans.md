- Start Date: 2023-10-23
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/117
- RFC Status: draft

# Summary

This RFC proposes to adapt the way transactions and spans are generated and sent on mobile platforms. In the recent light of [the performance API revamp](0101-revamping-the-sdk-performance-api.md) and the mobile starfish efforts we aim to provide a way of aggregating span data on a screen level.

# Motivation

For mobile starfish we want to be able to aggregate span data on a screen level. Metrics like TTID, TTFD, slow & frozen frames are especially useful if they can be grouped by screen, giving more actionable insights into the fast and slow parts of an app.

# Background

As of now the way transactions are created has several drawbacks:

1. Missing root transaction: We automatically create transactions whenever an Activity (Android) or ViewController (iOS) is created, but they idle-timeout after 3s. This means we sometimes end up in situations where we can’t attach spans to a transaction as there's no running transaction.

2. Multiple automatic transaction sources: We automatically start transactions for activities, user interactions and navigation events. These different sources are racing against each other as there can only be one transaction running (if a transaction is already running, a new one won’t be started), making it hard to predict the overall behavior.

3. Automatic vs. manual transactions: Any user-created transaction potentially breaks the behavior of the existing automatic-transaction generation, since there can only be a single transaction on the scope.

4. Transaction durations are sometimes pointless: As they’re based on idle transaction. Any relevant or even non-relevant child span can influence the transaction duration.

# Options Considered

### 1. Transactions as Carriers for Spans (preferred approach)

The idea is to use transactions as carriers for measurements on mobile instead of trying to make the backend heavy concept work on mobile. There is no active "open" transaction, but we rather create transactions on-demand, whenever there is span data to send.
In Sentry, we need pick apart these special transactions (that we shouldn’t consider as such anymore, maybe use `transaction->transaction_info->source` to identify carrier transaction) and only use their content, which are the spans we measured.

TBD:
* How can we ensure that spans are packaged up efficiently, ultimately creating not to little and not too many web requests.
* As of now, some performance grouping is done based on transactions op and description. With this change they will simply act as carieers, so we need to ensure the span context has enough information that aggregation (e.g. by screen) can still be performed.
* Profiles are right now captured based on transaction start signals, we need to find a reliable way to keep the remaining functionality.


**Pros**

- We always get what we want when we want it
- Once we can ingest spans, it’ll be easy to switch.

**Cons**

- We need to change how we interact with transaction in the SDK and in the product

### 2. One Transaction per Screen

Have one transaction per screen. This automatic transaction can be fully managed within the Sentry SDK. If no spans are generated an empty transaction would still be sent, as it contains slow/frozen frame metrics and ttid/ttfd data.

**Pros**

- There’s always a transaction running, which spans can be attached to
- There is no need for idle transactions anymore, as the lifetime matches a screen lifetime (a max deadline maybe still makes sense), making the overall behavior more predictable
- User interactions are modeled as spans instead of transactions, so they don’t interfere with transactions
- Slow and frozen frames could be added as child spans to the running transaction

**Cons**

- The transaction duration still makes no sense, as it’s length is determined by the time the screen was visible. Also probably needs a max timeout again too
- Any manually added / background work spans (e.g. a long running sync) could extend the transaction lifetime, which could result in overlapping transactions
- We need new (manual) APIs to track the current screen

### 3. Leave it as-is

Whilst being the least effort, this option doesn't add any value and we remain with all the drawbacks as outlined in the [background section](#background).
