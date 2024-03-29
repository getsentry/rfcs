- Start Date: 2023-10-23
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/118
- RFC Status: approved

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

## Option Chosen

On 2023-11-21, we decided to move forward with [4. Single Span Ingestion](#option-4), because single span ingestion will be available soon, and we strongly believe it's the future how SDKs will send spans to Sentry. Participants in the decision:

- Philipp Hofmann
- Karl Heinz Struggl
- Markus Hintersteiner
- Nar Saynorath
- Shruthilaya Jaganathan
- Pierre Massat

# Options Considered

### 1. Transactions as Carriers for Spans

The idea is to use transactions as carriers for measurements on mobile instead of trying to make the backend heavy concept work on mobile. There is no active "open" transaction, but we rather create transactions on-demand, whenever there is span data to send.
In Sentry, we need pick apart these special transactions (that we shouldn’t consider as such anymore, maybe use `transaction->transaction_info->source` to identify carrier transaction) and only use their content, which are the spans we measured. In short, we only use transactions to understand which Spans (measurements) should be aggregated.

Future considerations:
* How can we ensure that spans are packaged up efficiently, ultimately creating not to little and not too many web requests.
* As of now, some performance grouping is done based on transactions op and description. With this change, transactions will simply act as carriers, thus we need to ensure the span context has enough information that aggregation (e.g. by screen) can still be performed.
* Profiles are bound to transactions via a 1:1 mapping right now, we'd need to move towards a "continous profiling" model.

#### Pros

- We always get what we want when we want it
- Once we can ingest spans, it’ll be easy to switch.

#### Cons

- We need to change how we interact with transactions in the SDK and in the product.

### 2. One Transaction per Screen

Have one transaction per screen. This automatic transaction can be fully managed within the Sentry SDK. If no spans are generated an empty transaction would still be sent, as it contains slow/frozen frame metrics and ttid/ttfd data.

#### Pros

- There’s always a transaction running, which spans can be attached to
- There is no need for idle transactions anymore, as the lifetime matches a screen lifetime (a max deadline maybe still makes sense), making the overall behavior more predictable
- User interactions are modeled as spans instead of transactions, so they don’t interfere with transactions
- Slow and frozen frames could be added as child spans to the running transaction

#### Cons

- The transaction duration still makes no sense, as it’s length is determined by the time the screen was visible. Also probably needs a max timeout again too
- Any manually added / background work spans (e.g. a long running sync) could extend the transaction lifetime, which could result in overlapping transactions
- We need new (manual) APIs to track the current screen

### 3. Leave it as-is

Whilst being the least effort, this option doesn't add any value and we remain with all the drawbacks as outlined in the [background section](#background).

### 4. Single Span Ingestion <a name="option-4"></a>

Keep screen load transactions, and use single-span ingestion ([PR](https://github.com/getsentry/relay/pull/2620)) whenever the SDK creates an auto-generated span and sends it stand-alone to Sentry. To avoid multiple network requests, SDKs need to batch spans together; for example, send an envelope for every ten spans. The batch logic is still up for definition and is not the goal for this RFC. Instead, we are going to define this in an extra RFC.
We want to keep the screen load transactions as Mobile Starfish already relies on them, and we want to be backward compatible.

#### Pros

- Spans without transactions will not appear in the v1 performance product but only in Starfish. Therefore, no work on the v1 performance product is required.
- No idle timeout or wait-for-children logic is required.
- This solution is future-proof.

#### Cons

- Profiling won't work out of the box because profiles are bound to transactions.
