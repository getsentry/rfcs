- Start Date: 2022-10-27
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/32
- RFC Status: draft

---

**Table of Contents**

- [Summary](#summary)
- [Motivation](#motivation)
  - [Why?](#why-)
  - [Expected Outcome](#expected-outcome)
    - [User Experience](#user-experience)
    - [Token Format](#token-format)
    - [Backend Token Hygiene](#backend-token-hygiene)
    - [Secret Verification Service](#secret-verification-service)
- [Background](#background)
- [Options Considered](#options-considered)
  - [Option #1](#option--1)
    - [`n+1`](#-n-1-)
    - [`n+2`](#-n-2-)
  - [Option #2](#option--2)
  - [Option #3](#option--3)
- [Drawbacks](#drawbacks)
  - [Option #2](#option--2-1)
  - [Option #3](#option--3-1)
- [Unresolved questions](#unresolved-questions)

---

# Summary

Improve on Sentry's API token implementation to a more secure pattern. We will have three major goals:

1. Using hashed values in the database
2. Only display the token once to the end user upon creation
3. Allow users to _name_ the tokens ([#9600](https://github.com/getsentry/sentry/issues/9600))
4. Use a predictable prefix to integrate with various secret scanning services (ex. Github's Secret Scanning)

# Motivation

## Why?

Sentry currently provides several strong options to secure a user's account, including SSO, SAML, and 2FA options. However our approach to handling API tokens is not as mature. We have two major issues with the current API token implementation:

1. Tokens are stored as plaintext in the database, increasing the risk of exposure
2. Tokens are visible as plaintext in the Sentry UI

As a result, Sentry has to take extra steps to ensure the confidentially of API tokens (for example, [PR #39254](https://github.com/getsentry/sentry/pull/39254)).

## Expected Outcome

### User Experience

When a user creates an API token, they **have the option to provide it an arbitrary name** and **the actual token value is only displayed to them once**.

Existing API tokens, should be hashed and their original value discarded.

A notice in the Sentry UI should be presented to suggest the user rotate and generate a new token to the new and improved version.

### Token Format

We need a predictable token format in order to integrate properly with secret scanning services. Our current format is a 64 character alphanumeric string. This is insufficient and would likely produce a high amount of false positives in tooling like [TruffleHog](https://github.com/trufflesecurity/trufflehog), [detect-secrets](https://github.com/Yelp/detect-secrets), [Github's Secret Scanning](https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning), etc.

The suggested pattern is `snty[a-zA-Z]_[a-zA-Z0-9]{64}`. The character _after_ `snty` will be used to identify the token type.

For example:

- `sntyu_a1b2c3...` - identifies a **user** API token
- `sntya_a1b2c3...` - identifies an **API Application** token

### Backend Token Hygiene

API tokens should be stored in the database with a cryptographically secure hash (minimum SHA-256). Salting is not necessary since these values are sufficient in length.

An additional column identifying the API token version will be added in order to correctly identify legacy API tokens.

### Secret Verification Service

In order to integrate with Github's Secret Scanning service, we will need to have an available service for them to submit potential matches to.

More details about Github's secret scanning program can be found [here](https://docs.github.com/en/developers/overview/secret-scanning-partner-program).

At a high-level, we will need to be able to:

- Receive a list of one or more potential tokens
- [Verify the signature of the request](https://docs.github.com/en/developers/overview/secret-scanning-partner-program#implement-signature-verification-in-your-secret-alert-service)
- Determine if the token is a true positive or a false positive
  - send this feedback back to Github
- Disable/revoke the compromised token
- Send a notification to the appropriate user

> :memo: This secret verification service is not an immediate need or a dependency of implementing the improved API tokens.

# Background

Accidental credential leaks [happen](https://github.com/ChALkeR/notes/blob/master/Do-not-underestimate-credentials-leaks.md). Even though we provide several tools for users to limit the storage of sensitive information in Sentry it can still happen.

Our support for various authentication methods (including 2FA, SSO, and SAML) helps mitigate access of potentially sensitive information, but API tokens cannot support these additional authentication gates.

We can help customers further protect their accounts and data by providing a means of auto-detecting leaked API tokens.

# Options Considered

## Option #1

The migration from the legacy tokens to the new tokens should be rolled out over X releases. This allows for a smooth transition of self-hosted instances keeping pace with the versions.

> With `n` being the current version.

### `n+1`

- Add a Django migration including the `hashed_token`, `name`, and `token_version` fields.
  - columns should allow `null` values for now.
- Remove displaying the plaintext token in the frontend, and only display newly created tokens once.
- Implement new logic to generate the new token pattern.
  - The `token_version` should be set as `2`.
- Implement a backwards compatible means of verifying legacy tokens. This should:
  - Verify the legacy token is valid/invalid.
  - If valid, hash the legacy token and store it in the table.
  - Remove the plaintext representation of the token in the table.
  - Mark the `token_version` as `1`.
- A notification/warning in the UI should be displayed recommending users recreate their tokens, resulting in the new token version.

The `n+1` Sentry version should run in production for sufficient time to update the majority of the rows in the database as the legacy tokens are _used_ by users.

### `n+2`

- Add a Django migration to generate the `hashed_token` value for any tokens in `sentry_apitoken` that do not already have a hashed value.
  - Rows matching this are legacy tokens that were not used during the transition period.
  - The `token_version` should be set to `1` for these rows.

## Option #2

Instead of slowly generating the hashed token values over time of the legacy tokens (as in Option #1), we could generate a single migration that migrates the entire table to the end state.

## Option #3

To avoid the two different token versions, we could automatically prepend the prefix `sntyx_` (with `x` just being a placeholder here). We would then follow a similar approach to Option #1 or Option #2 to generate the hashed values.

# Drawbacks

## Option #2

- This is less than ideal because of the potential performance impact while the migration mutates each row in the table. Potential impacts to self-hosted installs would be unknown as well.

## Option #3

- Users would not be able to benefit from the Github Secrets Scanning since they would still be using their 64 character alphanumeric string without the prefix.
- Authentication views/logic would become more complex with branching code to handle the with and without prefix cases.

# Unresolved questions

- How do we deploy the necessary changes for the backend and frontend separately and in a backwards compatible way?
- Implementation path for `APIApplication` secrets.
- Is there a downside to allowing `null` in the additional columns?
- What is the median time between token use?
  - _This value could be used to inform how long we wait between versions for the migration that will edit pending rows in the database._
- Do we want to support [API Keys](https://docs.sentry.io/api/auth/#api-keys) as well, even though they are considered a legacy means of authentication?
- Are there additional secret types we would like to apply this to?
- Should the secret verification service live within the monolith or run as a separate service entirely?
  - _Github [mentions that there could be large batches of secrets sent for verification](https://docs.github.com/en/developers/overview/secret-scanning-partner-program#create-a-secret-alert-service:~:text=Your%20endpoint%20should%20be%20able%20to%20handle%20requests%20with%20a%20large%20number%20of%20matches%20without%20timing%20out.). It might make sense to keep this as a separate service to avoid impact._
