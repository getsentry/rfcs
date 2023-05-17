* Start Date: 2023-05-17
* RFC Type: feature
* RFC PR: [#93](https://github.com/getsentry/rfcs/pull/93)
* RFC Status: draft
* RFC Driver: [Manoel Aranda Neto](https://github.com/marandaneto)

# Summary

Add `Request` and `Response` body to events.

This feature is opt-in by default due to PII concerns.

# Motivation

The [Request](https://develop.sentry.dev/sdk/event-payloads/types/#request) interface contains information on a HTTP request related to the event.

The `Request` contains the `data` field which is the request body. Can be given as string or structural data of any format.

The [Response](https://develop.sentry.dev/sdk/event-payloads/types/#responsecontext) interface contains information on a HTTP response related to the event.

However, the `Response` interface does not contain the `data` field which is the response body.

# Background

This is necessary to implement the [GraphQL Client Errors](https://www.notion.so/sentry/GraphQL-proposal-d6e5846f30434770903cf3af20bc2568) with syntax highlight.

The `Request` and `Response` bodies could contain PII.

Request body example (query language only):

```
query { 
  viewer { 
    login
  }
}
```

Response body example:

```json
{
  "data": {
    "viewer": {
      "login": "marandaneto"
    }
  }
}
```

A Request example with an error (query language only):

```
query { 
  viewer { 
    # note the removed `n` at the end
    logi
  }
}
```

Response body example:

```json
{
  "errors": [
    {
      "path": [
        "query",
        "viewer",
        "logi"
      ],
      "extensions": {
        "code": "undefinedField",
        "typeName": "User",
        "fieldName": "logi"
      },
      "locations": [
        {
          "line": 4,
          "column": 5
        }
      ],
      "message": "Field 'logi' doesn't exist on type 'User'"
    }
  ]
}
```

Using the `locations` and the request body (query language only), we can highlight the error in the request body.

```
query { 
  viewer { 
    # note the removed `n` at the end
    -> logi
  }
}
```

Request body example, full body (not only the query language):

```json
{
  "query": "{\n  viewer {\n    login\n  }\n}",
  "variables": {}
}
```

Request body example, full body (not only the query language):

```json
{
  "query": "{\n  viewer {\n    login\n  }\n}",
  "variables": {}
}
```

The Request body can also contain `variables`.

```json
{
  "query": "{\n  viewer {\n    login\n  }\n}",
  "variables": {
    "login": "marandaneto"
  }
}
```

Because of that, the `Request` and `Response` body should be sent to Sentry.

# Supporting Data

See [JIRA issues](https://www.notion.so/sentry/GraphQL-proposal-d6e5846f30434770903cf3af20bc2568?pvs=4#fd0b946340d947eb9bbaa320846ccd6a), not disclosing here because they could contain PII.

Related issues and discussions:

[GraphQL Support](https://github.com/getsentry/sentry/discussions/38913)

[Support for GraphQL errors](https://github.com/getsentry/sentry/issues/33723)

[Send request body for http client integrations and similar](https://github.com/getsentry/team-mobile/issues/41)

# Proposal (Option 1)

The proposal is adding a `data` field in the [Response](https://develop.sentry.dev/sdk/event-payloads/types/#responsecontext) interface.

By doing this, we can keep the `Request` interface as it is, we can copy the `data` scrubbing rules from the `Request` interface.

```json
{
  "contexts": {
    "response": {
      "type": "response",
      "status_code": 500,
      "body_size": 1000,
      "data": "...",
    }
  }
}
```

* `data`: Can be given as string or structural data of any format..

The `Response` interface keeps arbitrary fields, it is backwards compatible with the current implementation.

## Must have

The fields `Request#data` and `Response#data` could contain PII and they should run data scrubbing agressively.

[Session Replay](https://docs.sentry.io/platforms/javascript/guides/remix/session-replay/configuration/) already sends the request and response bodies, so we can use the same data scrubbing rules.

Since GraphQL is a well defined spec, we can also scrub the GraphQL fields.

Request example:

```json
{
  "query": "{\n  viewer {\n    login\n  }\n}",
  "variables": {
    "login": "marandaneto"
  }
}
```

Response example:

```json
{
  "data": {
    "viewer": {
      "login": "[Filtered]"
    }
  }
}
```

In this case, we only need to use the Request `variables` and its keys to scrub the Response `data`.

# Drawbacks

[Envelopes](https://develop.sentry.dev/sdk/envelopes) (Events) contain way lower [size limits](https://develop.sentry.dev/sdk/envelopes/#size-limits). The `data` fields could be large and it could be a problem.

SDKs should discard large and binary bodies by default, using the [maxRequestBodySize](https://docs.sentry.io/platforms/android/configuration/options/#max-request-body-size) and `maxResponseBodySize` (it'll be added) options.

The difference is that for GraphQL errors, this should be enabled by default.

# Appendix

## Removed Proposals

### Option 2

Add a new `graphql` interface to [Contexts](https://develop.sentry.dev/sdk/event-payloads/types/).

```json
{
  "contexts": {
    "graphql": {
      "type": "graphql",
      "data": "...",
    }
  }
}
```

We'd need to duplicate or still use some fields from the `Request` and `Response` interface.

Size limits would still be a problem.

### Option 3

Add a new envelope item for GraphQL.

```
{"event_id":"9ec79c33ec9942ab8353589fcb2e04dc"\n
{"type":"graphql","length":41,"content_type":"application/json"}\n
{"request":"foo","response":"bar"}
```

This would not be back compatible and must be added to all SDKs.

### Option 4

Add Request and Response bodies as attachments.

```
{"event_id":"9ec79c33ec9942ab8353589fcb2e04dc"\n
{"type":"attachment","length":10,"content_type":"application/json","filename":"request.txt"}\n
foo
{"type":"attachment","length":10,"content_type":"application/json","filename":"response.txt"}\n
bar
```

Attachments have to be special cased in Sentry, seems hacky, we do that with screenshots already.

# Unresolved questions

- Do we need to send the GraphQL scheme to Sentry in order to do data scrubbing properly?
- Should we send the Request and Response as different envelope items? (avoid the size limit)
- Should PII be scrubbed in the SDK instead?
  - The least SDKs have to do is to conform with the [Scrubbing Sensitive Data](https://github.com/getsentry/rfcs/blob/main/text/0038-scrubbing-sensitive-data.md) RFC.
