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

Both are not great.  The per user token is easy to get access to (which is why
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
sent against.  This benefit also applies to JWT or PASETO tokens which can be considered
for this as well.  The RFC here thus proposes two potential options: A **Biscuit** token
format and a **JWT** token format.

A serialized token is added a custom prefix `sntrys_` (sentry structure) to make
it possible to detect it by security scrapers.  Anyone handling such a token is
required to check for the `sntrys_` prefix and disregard it before parsing it.  This
can also be used by the client side to detect a structural token if the client is
interested in extracting data from the token.

## Token Facts

We want to encode certain information into the tokens.  In Biscuit terms these are called
_facts_.  The following facts exist:

* `site`: references the target API URL that should be used.  A token will always have a
  site in it and clients are not supposed to provide a fallback.  For instance this
  would be `https://myorg.sentry.io/`.
* `org`: a token is uniquely bound to an org, so the slug of that org is also always
  contained.  Note that the slug is used rather than an org ID as the clients typically
  need these slugs to create API requests.
* `projects`: a token can be valid for more than one project.  For operations such as
  source map uploads it's beneficial to issue tokens bound to a single project in which
  case the upload experience does not require providing the project slugs.

### Biscuit Token Encoding

For biscuit tokens the following format could be used:

```javascript
site("https://myorg.sentry.io");
org("myorg");
project("myproject");
scope("project:releases");
scope("org:read");
```

Signed and encoded a biscuit token looks like `sntrys_{encoded_biscuit}`.

### JWT Token Encoding

For JWT the facts could be encoded as custom claims:

```json
{
    "iss": "sentry.io",
    "iat": 1684154626,
    "sentry_site": "https://myorg.sentry.io/",
    "sentry_org": "myorg",
    "sentry_projects": ["myproject"]
}
```

Encoded the token would either be `sntrys_{encoded_jwt}`.

## Transmitting Tokens

Tokens are sent to the target sentry as `Bearer` token like normal.  The server uses the
`sntrys_` prefix to automatically detect a structural token.  For existing tools that are
unaware of the structure behind structural tokens nothing changes.

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

An example of this with a JWT token:

```python
>>> import jwt
>>> tok = "sntrys_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzZW50cnkuaW8iLCJpYXQiOjE2ODQxNTQ2MjYsInNlbnRyeV9zaXRlIjoiaHR0cHM6Ly9teW9yZy5zZW50cnkuaW8vIiwic2VudHJ5X29yZyI6Im15b3JnIiwic2VudHJ5X3Byb2plY3RzIjpbIm15cHJvamVjdCJdfQ.ROnK3f72jGbH2CLkmswMIxXP1qZHDish9lN6kfCR0DU"
>>> jwt.decode(tok[7:], options={"verify_signature": False})
{
  'iss': 'sentry.io',
  'iat': 1684154626,
  'sentry_site': 'https://myorg.sentry.io/',
  'sentry_org': 'myorg',
  'sentry_projects': ['myproject']
}
```

## Token Issuance

The purpose of this change is to allow any organization member to issue tokens with little
overhead. As users can already issue tokens with shocking levels of access to any of the
orgs they are a member of there is a lot of room for improvement.

The proposed initial step is to only permit token issuance to support uploads and to permit
all users in the org to issue such tokens.  The tokens can be shown in the org's
"Developer Settings" page under a new tab called "Tokens".

Such simple token issuance can then also take place in wizards and documentation pages.

# How To Teach

Structural tokens change what needs to be communicated to users quite a bit.  In particular
less information is necessary for tools that are compatible with structural tokens.
This for instance would change this complex webpack config from the docs which requires
matching `org`, `project` and manually creating a sentry token today:

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

With structural tokens this can be changed to a much more simplified version which also
correctly handles Single Tenant:

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

There are however some cases where manual configuration would still be necessary:

* **Multi project tokens:** if a token contains more than one project, it's unclear if
  tools can handle this transparently.  In that case sentry-cli in particular is encouraged
  to fail with an error and ask the user to explicitly configure the slug of the project
  to use.
* **Legacy tools:** for tools not using sentry-cli but using the API directly, there might
  be a transitionary phase until the tool supports structural tokens.  In that case the
  documentation would need to point out the correct way to configure this.  The same applies
  to old installations of sentry-cli.

# Order of Execution

1. The most important piece is the new token.  As it behaves like any other token there is no
   immediate necessity for a tool to add support for structural tokens.
2. Add a user interface to issue these new tokens on an org level.
3. Add a user interface to issue these new tokens right from the documentation.
4. Add support for structural tokens to sentry-cli to allow `org` and `project` to be made optional.
5. Change documentation to no longer show `org` and `project` for tool config.

# Discussion

Addressing some questions that came up:

## Why not DSNs?

Originally the idea came up to directly use DSNs for uploads.  With debug IDs there is some
potential to enable this as most of the system is write once and most indexing is now based on
globally unique IDs.  However this today does not work for a handful of reasons:

1. Overwrites: DSNs are public and so someone who wants to disrupt a customer would be able to
   disrupt their processing by uploading invalid source maps or other broken files to a customer.
2. DSNs do not have enough routing information: while a DSN encodes some information, it's only
   possible to go from a DSN to the ingestion system but not the API layer.  A system could be
   added to relay to resolve the slugs and API URLs underpinning a DSN, but would reveal
   previously private information (the slugs) and requires a pre-flight to relay before making
   a request.
3. DSN auth would really only work for source map uploads and debug file uploads, it could not be
   extended to other CI actions such as codecov report uploads or release creation due to the
   abuse potential caused by public DSNs.
4. DSNs are limited to a single project and in some cases that might not be ideal.  In particular
   for frontend + backend deployment scenarios being able to use one token to manage releases
   across projects might be desirable.

## Why not PASETO?

PASETO as an alternative to JWT can be an option.  This should probably be decided based on what
has most support.  This proposal really only uses JWT for serialization of meta information, the
actual validation of the JWT tokens only ever happens on the server side in which case the system
can fully fall back to validating them based on what's stored in the database.

## Why Biscuit?

It's unclear if Biscuit is a great solution.  There is a lot of complexity in it and tooling support
is not great.  However Biscuit is a potentially quite exiting idea because it would permit tools
like sentry-cli to work with temporarily restricted tokens which reduces the chance of token leakage.
The complexity of Biscuit however might be so prohibitive that it's not an appealing choice.

# Unresolved questions

- Is Biscuit a reasonable standard?  Do we want to give it a try?
  - Supporting Biscuit makes revocations more complex as tokens are somewhat malleable.
  - A benefit of Biscuits would be that they can be trivially temporarily restricted upon
    use which limits the dangers of some forms of token loss (eg: leak out in logs).

