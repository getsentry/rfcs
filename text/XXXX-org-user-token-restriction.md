- Start Date: 2023-01-18
- RFC Type: feature
- RFC PR: -
- RFC Status: `draft`

# Summary

Provide an option to organization owners to disallow all user interaction with their organization that is using a user API token for authentication.

# Motivation

Sentry treats users and organizations as two separate entities. A user can be a part of multiple organizations.

An organization may have stricter requirements or a lower risk appetite compared to a user. We provide options for organizations to require SSO and 2FA to be enabled on a user account that wishes to interact with their organization. However, a user can authenticate with a personal API token, which inherently does not require controls like a 2FA prompt.

As a result, protecting the user API token lies solely on the user. Leaking secrets in source control, personal computers infected with malware, or vendor breaches can lead to these tokens being compromised, exposing an organization to increased risk in Sentry.

If a personal user API token is leaked, an organization owner does not have the ability to revoke the token and must coordinate with the user to do so -- further increasing the time an organization is potentially exposed.

# Solution

1. Add a toggle in the Organization Settings to deny use of personal API tokens for authentication against their organization.
2. Update authentication middleware to check for the targeted organization's preference.

# Drawbacks

- An organization upon enabling this may find some of their automation or integrations broken.

# Supporting Data

Secret or API token leaks are commonplace:

- [CircleCI's recent breach (Jan 2023)](https://circleci.com/blog/jan-4-2023-incident-report/)
- [Heroku and TravisCI token leaks](https://github.blog/2022-04-15-security-alert-stolen-oauth-user-tokens/)

# Related Work

- [Improved API Tokens](https://github.com/getsentry/rfcs/pull/32)

# Potential Future Work

- Allow organizations to require an SSO flow to authorize a user token before use.
