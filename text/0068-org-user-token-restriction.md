- Start Date: 2023-01-18
- RFC Type: feature
- RFC PR: -
- RFC Status: `draft`

# Summary

Provide an option to organization owners to disallow all user interaction with
their organization that is using a user API token for authentication.

# Motivation

Sentry treats users and organizations as two separate entities.
A user can be a part of multiple organizations.

An organization may have stricter requirements or a lower risk appetite
compared to a user. We provide options for organizations to require SSO and 2FA
to be enabled on a user account that wishes to interact with their organization.
However, a user can authenticate with a user API token, which inherently
does not require controls like a 2FA prompt.

As a result, protecting the user API token lies solely on the user.

Leaking secrets in source control, personal computers infected with malware, or
vendor breaches can lead to these tokens being compromised and exposes
an organization to increased risk.

If a user API token is leaked, an organization owner has two options:

1. Coordinate with the user to rotate their API token.
2. Remove the user from their organization.

An organization owner **cannot** delete another user's API token.

This also assumes the organization owner is made aware of the leaked token.
Currently, notification would only go to the user who owns the token.

# Proposed Solution

Owners should have more control on how user API tokens
interact with their organization.

In the majority of cases organization owners have requested the ability
to disallow interaction with their organization via a user API
token completely. These organizations typically follow our recommended
practice of using a custom integration for automation tasks.

**I'm proposing we add a toggle option under the organization settings
to disallow usage of user API tokens for authentication to their organization.**

## Pros

- Solves the concern for the majority of customers who are concerned about
  user API tokens
- Relatively simple implementation

## Cons

- Organization owners do not have a way to determine if
  their users are using personal API tokens
- An organization upon enabling this may find some of their automation
  or integrations broken

# Supporting Data

Secret or API token leaks are commonplace:

- [CircleCI's recent breach (Jan 2023)](https://circleci.com/blog/jan-4-2023-incident-report/)
- [Heroku and TravisCI token leaks](https://github.blog/2022-04-15-security-alert-stolen-oauth-user-tokens/)

# Related Work

- [Improved API Tokens](https://github.com/getsentry/rfcs/pull/32)

# Potential Future Work

- Allow organizations to require an SSO flow to authorize a user token before use.
- Instead of a simple on/off toggle, we could create a more complex _policy_ system
  allowing user API tokens to be used for certain scopes within an org
