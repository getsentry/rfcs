- Start Date: 2022-11-21
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/38

# Summary

Make scrubbing of sensitive data (security related data (passwords, keys, et al) and personal identifiable information (PII)) in Sentry smarter.
This includes the SDK side (before we send data) and the Relay side (before we ingest data).

# Motivation

Currently, the scrubbing of sensitive data works but is not very smart. It can happen that sensitive data is leaked and ends up in our data storage.
It also can happen that scrubbing is too aggressive and too much data is removed, so the feature destroys value for the customer.

We want to have a smarter way of scrubbing sensitive data with a more fine grained control of what data is preserved and what data is scrubbed.

We do this to make sure we handle our users sensitive data with the respect it deserves.

# Background

A user complained that our data scrubbing did not remove sensitive data from an URL the users project made a HTTP request to. The sensitive data showed up in the span description in the Sentry UI.

# Supporting Data

(tbd)

# Conclusion

Not one option will be implemented but a combination of options:

1. The SDKs will try to save structured data where possible (Option B)
2. The SDKs will try to specify what kind of data is in `span.description` (and other places) as good as possible. (Can be done by more fine grained `span.op`s or applying OTel trace semantic convention to `span.data`. Needs to be speced out)
3. Relay uses data from 2.) to parse content fields and scrub sensitive data (Option C)
4. If there is no structured data (so 3.) is not possible) Relay applies a generic tokenizer that can extract key/value pairs from unstructured data and makes it easy to remove values from keys that are in a list of keys containing sensitive data. (Option D)

# Options Considered

### Status Quo:

- Right now most data scrubbing is done in Relay.
- There is a option `sendDefaultPII` in SDKs that may or may not remove some sensitive data before sending.
- In Relay fields have a "pii" attribute that can be `yes`, `no` or `maybe`:
  - `yes` means all the default data scrubbing Regexes are applied to the fields.
  - `maybe` means that the data scrubbing Regexes are not run by default. If the user has advanced data scrubbing set (in Sentry.io under: Project Settings > Security & Privacy > Advanced Data Scrubbing) those custom rules are applied to the field and if a rule matches the whole content of the field is removed.
  - `no` there is no possibility of data scrubbing for this field.
- The regexes for data scrubbing are defined [here](https://github.com/getsentry/relay/blob/92a4b349f271963a53c8a8278acb3d4d56f0dfe5/relay-general/src/pii/regexes.rs#L103-L274)
- Some regexes can just remove the sensitive part of the content (like IP and SSH keys regexes).
- Some of the regexes (like password regex) will remove the complete content of a field. This is because it is unstructured data. Relay does not know if the content is a SQL query, a JSON object, an URL, a Elasticsearch/MongoDB/whatever query in JSON format, or something else.

### Option A): Remove Sensitive Data in SDKs

At the time when SDKs set the data in an event, it knows what the data represents and can remove sensitive information. This way Relay has to beliefe that the SDK does the right thing and does not need to scrub data.

_Pros:_

-

_Cons:_

-

### Option B): Store data in a structured way in SDKs

The content should not be a simple string but structured data. The content could be a template string where all the sensitive values are removed plus a dictionary with the values to insert into the string.
Example `span.description` should be a string with named parameters in the format `select * from user where email=%(email)s;` or `POST /api/v1/update_password?new_password=%(new_password)s` and in `span.data` there should be `{"email": "test@example.com"}` or `{ "new_password": "123456" }` respectively.
Same goes for `breadcrumb.message/breadcrumb.data`, `logentry.message/logentry.params`, and `message.message/message.params`.

We need to identify all the fields we need to do this.

We should model this Option after how `Logentry` does this now.

Note: If we change the span.description then the hash for existing performance issues will be changed and existing performance issues will be recreated, so users would have duplicate performance issues in their list of issues. (Which we can just document in the CHANGELOG and everything should be fine.)

_Pros:_

- Relay would not have to reverse-engineer the semantics of the information supplied by the SDK.

_Cons:_

- Could be complex for nested JSON objects or for "Array of objects" kind of data.

### Option C): Relay identifies what kind of data is present and parses it.

Relay can try for each field to "guess" what kind of data it is. Guessing can be done by looking at what field in general we are guessing (field X has always a SQL query in it), or the span.op or other fields as well as the content itself. If the content is a SQL query, JSON object, Elasticsearch Query, GraphQL Query, URL, ... When Relay is certain that it knows the content is of a specific kind, it can then run a parser on it to be able to scrub values of sensitive fields.

An existing example for this is [parsing URL query parameters into a separate field](https://github.com/getsentry/relay/blob/c2e666d1728a2882b82e70fdbb02192c4cb0b50a/relay-general/src/store/normalize/request.rs#L29-L48), which Relay does when normalizing the [Request Interface](https://develop.sentry.dev/sdk/event-payloads/request/).

For the performance issue detection `sentry` does something similar:

- https://github.com/getsentry/sentry/blob/68e44ed3e8343a5e69d0b0a51ad65c02ae427cd0/src/sentry/spans/grouping/strategy/base.py#L186
- https://github.com/getsentry/sentry/blob/68e44ed3e8343a5e69d0b0a51ad65c02ae427cd0/src/sentry/spans/grouping/strategy/base.py#L142-L150

OpenTelementry has semantic conventions for tracing. A defined set of attributes set to the span describes the span data in more detail. We could borrow those semantic conventions and add them to `span.data` so that Relay can better parse the `span.description`: https://opentelemetry.io/docs/reference/specification/trace/semantic_conventions/

_Pros:_

-

_Cons:_

- Could be expensive to try multiple guesses before the right kind of data is identified. (Maybe its SQL? no. Maybe JSON? no. So it is a URL? yes.)

### Option D): Generic tokenization in Relay.

Have a generic tokenizer in Relay that can not parse full fledged SQL, but can extract key/value pairs out of almost everything. With this the values of keys with potential sensitive information can be removed.

_Pros:_

-

_Cons:_

-

### NEW! Option E): Improved regexes

Keep the logic on how data scrubbing is done right now, but improve the regexes to be more specific. Especially the "password regex" could be changed to the `auth` rule does ONLY match `auth` but NOT `author` or `authorize`.

With this we could add data scrubbing back to `span.description` (and potentially other fields that ware marked with `pii=maybe` right now).

_Pros:_

-

_Cons:_

-

# Drawbacks

(none)

# Unresolved questions

- We need to check with legal and/or security to make sure that the stuff we are planing is actually OK with existing laws and regulations
- We need to find all places in SDKs that sensitive data could be. Places we are targeting right now: `span.description/span.data`, `breadcrumb.message/breadcrumb.data`, `logentry.message/logentry.params`, and `message.message/message.params`, local variables, request bodies, response bodies, HTTP headers, cookies, ...
