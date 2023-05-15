- Start Date: 2023-05-15
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This RFC Proposes an improved CI experience for uploading source maps, debug symbols,
and potentially other CI based operations by proposing a new way to get and manage
access tokens specifically for this environment.

# Motivation

Today there are two ways to get access tokens for use with sentry-cli:

1. per user access tokens
2. internal organization integrations

Either one are not great.  The per user token is easy to get access to (which is why
they are preferred in the docs still) but they run into the risk that a user departs
an organization and an integration stops working.  The organization integration flow
is complex and requires elevated privileges.  Either of those options have the additional
complexity that there are a lot of extra settings to get right when configuring the tools.
For instance the token itself does not know where it goes to, which requires organization
slug and project slug to be set.  All of this together means that the documentation does
not put a user on the path of success but requires multiple separate steps to get
everything in order.

# Background

We improved a lot of the inner workings of source maps and debug files at Sentry recently
but these efforts are held back by the complexity of getting the token.  The friction is
still too high for many customers to make the necessary investment into getting source maps
uploaded.  From a documentation writing and onboarding experience, it's also not clear with
the current system how the experience can be improved.

Additionally both Hybrid Cloud and Single Tenant would greatly benefit from automatically
routing to the right URLs.  Today the documentation is very quiet about how to get this
system to work on a single tenant installation and customers are often required to work
with CS to get source maps working.

# Technical Implementation

The motivation is to add a new kind of token to Sentry which are fundamentally per-organization
tokens, but with the ability to carry meta information that tools like sentry-cli can use to
improve the user experience.  These org level tokens can be created by anyone in the org, they
can be given additional restrictions, and they can carry meta information such as routing
data.  For the purpose of this document they are called **structural tokens**.

## Token Format

The proposed token format is undecided so far.  The goals of the token align generally with
both [Macaroons](http://macaroons.io/) and [Biscuit](https://www.biscuitsec.org).  Unfortunately
the former standard has never seen much attention, and the latter is pretty new and not
particularly proven.  Either system however permits adding additional restrictions to the
token which make them a perfect choice for the use in our pipeline.  Biscuits however seem
quite promising.  The idea of biscuits is that the token itself holds _facts_ which and
can be further constraints via _checks_ and they are checked against a datalog inspired
_policies_.

One of the benefits of having the tokens carry this data is that the token alone has enough
information available to route to a Sentry installation.  This means that `sentry-cli` or
any other tool _just_ needs the token to even determine the host that the token should be
sent against.

The token then gets a prefix `sntrys_` (sentry structure) to make it possible to
detect it by security scrapers.  Anyone handling such a token is required to check
for the `sntrys_` prefix and disregard it before parsing it.

It's unclear at the moment if Biscuit is a good choice.  There is an alternative where
instead of expressing everything in Biscuit tokens, the token gains a base64 encoded
JSON payload that the client can parse containing just the facts.

## Token Facts

Tokens in Biscuit contain facts.  Each fact can later be referenced by the policy and
further restrictions can be placed on the token.  For instance this is a basic set of
token facts for a token generated in the UI that has permissions to releases and
org read.

```javascript
site("https://myorg.sentry.io");
org("myorg");
project("myproject");
scope("project:releases");
scope("org:read");
```

Alternatively we we decide not to consider Biscuit the facts can be encoded into
a JSON structure.  Note that in this case we would not transmit the scopes.

```json
{
    "site": "https://myorg.sentry.io",
    "org": "myorg",
    "projects": ["myproject"]
}
```

Encoded the token would either be `sntrys_{encoded_bisquit}` or
`sntrys_{secret_key}.{base64_encoded_facts}` depending on the format chosen.  Alternatively
that JSON stucture could be encoded into a JWT token with sufficient restrictions.

## Transmitting Tokens

Tokens are sent to the target sentry as `Bearer` token like normal.  The server uses the
`sntrys_` prefix to automatically detect a structural token.

## Parsing Tokens

Clients are strongly encouraged to parse out the containing structure of the token and
to use this information to route requests.  The most important keys in the structure
are:

* `site`: references the target API URL that should be used.  A token will always have a
  site in it and clients are not supposed to provide a fallback.
* `org`: a token is uniquely bound to an org, so the slug of that org is also always
  contained.  Note that the slug is used rather than an org ID as the clients typically
  need these slugs to create API requests.
* `projects`: a token can be valid for more than one project.  For operations such as
  source map uploads it's benefitial to issue tokens bound to a single project in which
  case the upload experience does not require providing the project slugs.

## Token Issuance

The purpose of this change is to allow any organization member to issue tokens with little
overhead. As users can already issue tokens which shocking levels of access to any of the
orgs they are a member of there is a lot of room for improvement.

The proposed initial step is to only permit token issuance to support uploads and to permit
all users in the org to issue such tokens.  The tokens can be shown in the org's
"Developer Settings" page under a new tab called "Tokens".

Such simple token issuance can then also take place in wizards and documentation pages
This for instance would change this complex webpack config from the docs which requires
matching `org`, `project` and manually creating a sentry token:

```javascript
const SentryWebpackPlugin = require("@sentry/webpack-plugin");

module.exports = {
  devtool: "source-map",
  plugins: [
    new SentryWebpackPlugin({
      org: "demo-org",
      project: "demo-project",
      include: "./dist",
      // Auth tokens can be obtained from https://sentry.io/settings/account/api/auth-tokens/
      // and needs the `project:releases` and `org:read` scopes
      authToken: process.env.SENTRY_AUTH_TOKEN,
    }),
  ],
};
```

To a much more simplified version:

```javascript
const SentryWebpackPlugin = require("@sentry/webpack-plugin");

module.exports = {
  devtool: "source-map",
  plugins: [
    new SentryWebpackPlugin({
      authToken: "AUTO GENERATED TOKEN HERE",
      include: "./dist",
    }),
  ],
};
```

# Unresolved questions

- Is Biscuit a reasonable standard?  Do we want to give it a try?
  - Supporting Biscuit makes revocations more complex as tokens are somewhat malleable.
  - A benefit of Biscuits would be that they can be trivially temporarily restricted upon
    use which limits the dangers of some forms of token loss (eg: leak out in logs).

