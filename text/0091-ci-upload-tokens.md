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
data. For the purpose of this document they are called **structural tokens**. 

## Token Format

We use a custom token format based on base64 encoding.

```
PREFIX_FACTS_SECRET
```

Concretely, a token would look like this:

```
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
```

* `PREFIX`: `sntrys_` - this is static and helps to identify this is a Sentry token.
* `FACTS`: A base64 encoded JSON string of the facts.
* `SECRET`: A random secret part for the token. We may use `b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")`, but this is an implementation detail. 

A serialized token is added a custom prefix `sntrys_` (sentry structure) to make
it possible to detect it by security scrapers.  Anyone handling such a token is
required to check for the `sntrys_` prefix and disregard it before parsing it.  This
can also be used by the client side to detect a structural token if the client is
interested in extracting data from the token.

The purpose of the secret is that the resulting token is not guessable. It should be a randomly generated string that is different for each token.

## Token Facts

We want to encode certain information into the tokens.  The following attributes are defined:

* `iat`: Timestamp when the token was issued.
* `url`: references the root domain to be used. A token will always have a
  url in it and clients are not supposed to provide a fallback. This value can be found in `settings.SENTRY_OPTIONS["system.url-prefix"]`. Some APIs are only available on this URL, not on the region URL (see below). e.x. `https://sentry.io/`. 
* `region_url`: The domain that the organization's API endpoints are available on. This value can be found in `organization.links.regionUrl`. e.x.  `http://us.sentry.io`. 
* `org`: a token is uniquely bound to an org, so the slug of that org is also always
  contained. Note that the slug is used rather than an org ID as the clients typically
  need these slugs to create API requests.

These facts are encoded in the JWT as custom claims:

```json
{
    "iat": 1684154626,
    "region_url": "https://eu.sentry.io/",
    "url": "https://sentry.io/",
    "org": "myorg"
}
```

Encoded the token then is be `sntrys_{encoded_facts}_secret`.

## Token Storage

Tokens are stored in the database in hashed form, not in plain text. 
In addition, we store the last 4 characters of the token in plain text in order to help with identification of tokens.
We also allow to define a `name` for a token for easier identification,
however this may often be auto-generated when e.g. creating a token from the docs or other places.

## Transmitting Tokens

Tokens are sent to the target sentry as `Bearer` token like normal.  The server uses the
`sntrys_` prefix to automatically detect a structural token.  For existing tools that are
unaware of the structure behind structural tokens nothing changes.

## Parsing Tokens

Clients are strongly encouraged to parse out the containing structure of the token and
to use this information to route requests.  For the keys the following rules apply:

* `url` & `region_url`: references the target API URL that should be used.  A token
  will always have a site in it and clients are not supposed to provide an
  automatic fallback.
* `org`: a token is uniquely bound to an org, so the slug of that org is also always
  contained.  Note that the slug is used rather than an org ID as the clients typically
  need these slugs to create API requests.

An example of parsing the token content with python:

```py
def parse_token(token: str):
    if not token.startswith("sntrys_") or token.count('_') != 2:
        return None

    payload_hashed = token[7:token.rindex('_')]
    payload_str = b64decode((payload_hashed).encode('ascii')).decode("ascii")
    return json.loads(payload_str)
```

## Token Issuance

The purpose of this change is to allow any organization member to issue tokens with little
overhead. As users can already issue tokens with shocking levels of access to any of the
orgs they are a member of there is a lot of room for improvement.

The proposed initial step is to only permit token issuance to support uploads and to permit
all users in the org to issue such tokens.  The tokens can be shown in the org's
"Developer Settings" page under a new tab called "Tokens".

Such simple token issuance can then also take place in wizards and documentation pages.

The generated token itself is only visible after creation. Users cannot see the token again later.

## Token Revocation

Tokens cannot be deleted, but only revoked (=soft deleted). Only managers & owners may revoke tokens. 
Users may be able to delete tokens they created regardless of their role. 

## Editing Tokens

Only the `name` of the token may be updated after it was created. Any user may update any tokens name. 
You cannot update the scope(s) of a token after it was issued.

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
      url: "https://sentry.io/",  // defaults to sentry.io
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
      project: "demo-project",
      include: "./dist",
    }),
  ],
};
```

Some manual configuration remains as we still want ask users to provide the slug
of the project explicitly to allow cross-org token issuance by default.

Additionally **legacy tools** will require more configuration.  For tools not
using sentry-cli but using the API directly, there might be a transitionary
phase until the tool supports structural tokens.  In that case the documentation
would need to point out the correct way to configure this.  The same applies to
old installations of sentry-cli.

# Order of Execution

1. The most important piece is the new token.  As it behaves like any other token there is no
   immediate necessity for a tool to add support for structural tokens.
2. Add a user interface to issue these new tokens on an org level.
3. Add a user interface to issue these new tokens right from the documentation.
4. Add support for structural tokens to sentry-cli to allow `org` to be made optional.
5. Change documentation to no longer show `org` & `url` for tool config.

# Discussion

Addressing some questions that came up:

## Project Bound Tokens

It would be possible to restrict tokens to a single project (or some projects).  At a later
point this might still be interesting when the tokens become more potent.  For now these
tokens can only be used to upload files which means that the damage that one org member
can do against projects they are not a member of are limited.  As such we are willing to
accept the risk of issuing tokens across the entire org.

This also means that tools will still require the project slug to be provided for operations
that are project bound.  Today most of these operations are project bound, but we might want
to investigate ways to bring most of these operations to the org level so that over time this
information can be removed.

For instance for debug files there is no good reason why these files are not uploaded to
org level to begin with.  For source maps the situation is a bit more complex due to the
optional nature of debug IDs.  However in an increasing number of cases uploads should
again be possible to the org level.

The benefit of a cross-org token is that this token can then later be used against other
projects in the same pipeline without having to re-issue the token.  For instance a CI job
that first only uploads the frontend source maps might later want to do release creation
for the backend as well.  Having an overly restricted token would make this a more painful
change.

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

## Why not JWT?

We initially set out to try to use JWT as a format. However, since we are not interested in signing the tokens (which is a fundamental concept of JWT), this lead to problems. Skipping signing means we have to use `algorithm='none'`, which is not very well supported. When using this algorithm, the resulting tokens always end in `.`, as the final part would be based on the key, which is missing. Having a trailing `.` after each token is an unnecessary error source (users may not copy it, ...). We _could_ try to handle this when decoding, but this would still make this technically invalid JWT. 

Since we do not need signing/verification of the token client side, we decided against using JWT as a format.

## Why not PASETO?

PASETO as an alternative to JWT can be an option.  This should probably be decided based on what
has most support.  This proposal really only uses JWT for serialization of meta information, the
actual validation of the JWT tokens only ever happens on the server side in which case the system
can fully fall back to validating them based on what's stored in the database.

## Why Not Biscuit?

It's unclear if Biscuit is a great solution.  There is a lot of complexity in it and tooling support
is not great.  However Biscuit is a potentially quite exiting idea because it would permit tools
like sentry-cli to work with temporarily restricted tokens which reduces the chance of token leakage.
The complexity of Biscuit however might be so prohibitive that it's not an appealing choice.

## Why not include the Project?

We decided to only encode the org-reference into the token, not the project. This allows CI to extend usage to new/other projects without having to issue a new token. In the future, we may allow to also bind tokens to project(s). But for now, all tokens are org-wide.