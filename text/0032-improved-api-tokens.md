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
  - [Option #1](#option-1)
  - [Option #2](#option-2)
    - [Drawbacks](#drawbacks)
  - [Option #3](#option-3)
    - [Drawbacks](#drawbacks-1)
- [Unresolved questions](#unresolved-questions)

---

# Summary

Improve on Sentry's API token implementation to a more secure pattern. Our major goals for the improved API tokens are:

1. Using hashed values in the database
2. Only display the token once to the end user upon creation
   - ([#61941](https://github.com/getsentry/sentry/pull/61941))
3. Allow users to _name_ the tokens ([Tracking Issue #9600](https://github.com/getsentry/sentry/issues/9600))
   - [#58945](https://github.com/getsentry/sentry/pull/58945)
4. Use a predictable prefix and suffix to integrate with various secret scanning services (ex. Github's Secret Scanning)

# Motivation

## Why?

Sentry currently provides several strong options to secure a user's account, including SSO, SAML, and 2FA options.
However our approach to handling API tokens is not as mature. We have two major issues with the current API token implementation:

1. Tokens are stored as plaintext in the database, increasing the risk of exposure
2. Tokens are visible as plaintext in the Sentry UI

As a result, Sentry has to take extra steps to ensure the confidentially of API tokens (for example, [PR #39254](https://github.com/getsentry/sentry/pull/39254)).

## Expected Outcome

### User Experience

When a user creates an API token, they **have the option to provide it an arbitrary name** and **the actual token value is only displayed to them once**.

Existing API tokens, should be hashed and their original value discarded.

A notice in the Sentry UI should be presented to suggest the user rotate and generate a new token to gain the benefits of the improved version.

### Token Format

We need a predictable token format in order to integrate properly with secret scanning services. Our current format is a 64 character alphanumeric string. This is insufficient and
would likely produce a high amount of false positives in tooling like [TruffleHog](https://github.com/trufflesecurity/trufflehog), [detect-secrets](https://github.com/Yelp/detect-secrets),
[Github's Secret Scanning](https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning), etc.

The suggested pattern is `sntry[a-zA-Z]_[a-zA-Z0-9]{64}`. The character _after_ `sntry` will be used to identify the token type.

For example:

- `sntryu_a1b2c3...` - identifies a **user** API token
- `sntrya_a1b2c3...` - identifies an **API Application** token
- `sntrys_a1b2c3...` - identifies an **Organization Auth** token

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

Accidental credential leaks [happen](https://github.com/ChALkeR/notes/blob/master/Do-not-underestimate-credentials-leaks.md). Even though we provide several
tools for users to limit the storage of sensitive information in Sentry it can still happen.

Our support for various authentication methods (including 2FA, SSO, and SAML) helps mitigate access of potentially sensitive information, but API tokens cannot support these additional authentication gates.

We can help customers further protect their accounts and data by providing a means of auto-detecting leaked API tokens.

# Options Considered

## Option #1

This option strives to limit impact to the database by avoiding large bulk operations and maintain backwards compatibility. To do this we'll distribute the complete implementation over at least two releases.
This also allows for a smooth transition of self-hosted instances keeping pace with releases.

First, we will need to support naming and showing a mostly obfuscated token in the UI to help users identify them.

1. The frontend is updated to no longer display the token value for existing tokens. [#61941](https://github.com/getsentry/sentry/pull/61941)
2. Nullable `name` and `token_last_characters` fields are added to the `ApiToken` model.
   - New `ApiToken`s created should automatically have the `token_last_characters` populated based on an option.
     The option is required in order to properly test the upcoming backfill migration. [#62972](https://github.com/getsentry/sentry/pull/62972)
3. A backfill migration is created and ran to fill in the `token_last_characters` for all `ApiToken` entries. [#63342](https://github.com/getsentry/sentry/pull/63342)
4. Change the `ApiToken` serializer to send the `token_last_characters` in the response for use in the frontend. [#63473](https://github.com/getsentry/sentry/pull/63473)
5. Change the frontend to use the new `token_last_characters` value and show an obfuscated token in the UI. [#63485](https://github.com/getsentry/sentry/pull/63485)
6. Update the backend serializer for `ApiToken` to accept and return an optional `name` field.
7. Update the frontend to support creation of a token with a `name` and displaying of the `name` when listing tokens.

Second, we will need to secure the tokens. This involves four primary goals.

- Tokens are hashed in the database
- Newly created user auth tokens have the `sntryu_` prefix
- Newly created user API application tokens have the `sntrya_` prefix
- We encourage users in the UI via a notification/banner to recreate their tokens in order to get new ones with a prefix

1. Nullable `hashed_token` and `hashed_refresh_token` fields are added to the `ApiToken` model
2. The `save()` method on `ApiToken` is updated to calculate and store the token's SHA-256 hash in `hashed_token`.
3. Update the `UserAuthTokenAuthentication` middleware to:

   1. Caculate the SHA-256 hash and use the hash value for the table lookup on the `hashed_token` or `hashed_refresh_token` column.
   2. If the hash is not found, use the plaintext token for the table lookup on the `token` or `refresh_token` column.
   3. If it is a valid token that does not yet have a hashed value, hash it and update the respective `hashed_` columns for the entry in the database.

   > _This helps us avoid a large backfill migration in the future. As tokens are used, they'll be hashed and their corresponding
   > row will be updated. We will still need a backfill migration, but this allows a slow and safer transition to hashed tokens._
   >
   > _It's important to note that this does not update the token to the new prefixed format._

4. A notification/warning in the UI should be displayed recommending users recreate their tokens, resulting in the new token version.
5. New tokens are only displayed once at creation time to the user.
6. New tokens are created following the new format.
   - A Django migration will be needed to add fields: `hashed_token`, `version`, and `name`.
   - legacy tokens will be `version = 1` and new tokens `version = 2`
7. As old tokens are used, they are hashed and stored in the database.
   - This does not update the token to the new format.
   - The plaintext token value should be removed in this action.

**In the second release:**

1. As a Django migration, a bulk operation is executed to update all remaining legacy tokens in the database.
   - This operation will hash the legacy token value, store it in the database, and remove the plaintext value.
   - It does **not** update the token to the new format.

## Option #2

Instead of slowly generating the hashed token values over time of the legacy tokens (as in Option #1), we could generate a single migration that migrates the entire table to the end state.

### Drawbacks

- This is less than ideal because of the potential performance impact while the migration mutates each row in the table.
- Potential impact to self-hosted installs where this is a large amount of rows in the table.

## Option #3

To avoid the two different token versions, we could automatically prepend the prefix `sntryx_` (with `x` just being a placeholder here).
We would then follow a similar approach to Option #1 or Option #2 to generate the hashed values.

### Drawbacks

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
