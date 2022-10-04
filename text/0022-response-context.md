* Start Date: 2022-10-03
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/blob/rfc/response-context/text/0022-response-context.md
* RFC Status: draft
* RFC Driver: [Manoel Aranda Neto](https://github.com/marandaneto)

# Summary

Add `Response` interface that contains information on a HTTP response related to the event.

# Motivation

The [Request](https://develop.sentry.dev/sdk/event-payloads/request/) interface contains information on a HTTP request related to the event. However, there is no interface that contains information on a HTTP response related to the event. This RFC proposes a new interface called `Response` that contains information on a HTTP response related to the event.

The `Request` interface has a few limitations:
* Does not accept arbitrary fields, so unknown fields are dropped during ingestion such as `status_code`.
* Response `headers` are not dropped during data scrubbing, See [issue](https://github.com/getsentry/relay/issues/1501).
* Adding `Response` data in the `Request` interface is semantically wrong anyways.

This is necessary to implement the `Failed HTTP Client requests automatically result in Events` feature that is described in this [DACI](https://www.notion.so/sentry/Failed-HTTP-Client-requests-automatically-result-in-Events-f6c21d2a58ce4f2c889a823fd1da0044).

# Background

Since the `Response` metadata is PII sensitive, it should be properly mapped, documented and scrubbed.

# Supporting Data

See [Supporting data](https://www.notion.so/sentry/Failed-HTTP-Client-requests-automatically-result-in-Events-f6c21d2a58ce4f2c889a823fd1da0044#0ca951d5216742dbaab02f5fd33b8fb5) section in the [DACI](https://www.notion.so/sentry/Failed-HTTP-Client-requests-automatically-result-in-Events-f6c21d2a58ce4f2c889a823fd1da0044).

# Options Considered

## Option 1 (Preferred)

Adding a `Response` interface directly in the Event payload.

```json
{
  "response": {
    "method": "POST",
    "url": "http://absolute.uri/foo",
    "query_string": "query=foobar&page=2",
    "data": { // arbitrary fields
      "foo": "bar"
    },
    "cookies": "PHPSESSID=298zf09hf012fh2; csrftoken=u32t4o3tb3gg43; _gat=1;",
    "headers": {
      "content-type": "text/html"
    },
    "env": {
      "REMOTE_ADDR": "192.168.0.1"
    },
    "status_code": 500,
    "is_redirect": false,
    "response_body_size": 1000, // bytes
    "arbitrary_field": "arbitrary" // arbitrary and retained fields (either this or data)
  }
}
```

The `data` field is semantically different than the `Request#data`. The `Request#data` is the data that was sent to the server, while the `Response#data` is just arbitrary data that is attached to the response. The `Response#data` is not used for anything in the SDKs, but it is useful for the user to attach arbitrary data to the response.
We could rename to `other` or something else to avoid confusion.

## Option 2

Adding a `Response` interface in the [Contexts interface](https://develop.sentry.dev/sdk/event-payloads/contexts/).

```json
{
    "contexts": {
        "response": {
            "type": "response"
            // ...
  }
}
```

The content is the same as in Option 1.

## Option 3

Expand the `Request` interface adding the missing fields.
Data scrubbing should consider response headers when scrubbing.
If we do that, the `Request` docs should be ammended that it contains the `Response` data as well otherwise it's semantically wrong.

## Must have for all the options

A tag should be created for `url` and `status_code` fields, people should be able to search for events with a specific `url` or `status_code`, also to alert on specific `status_code`.

# Drawbacks

The `Response` interface is PII sensitive, so we need to be careful about how we scrub it.

The [Dart Dio HTTP Client](https://docs.sentry.io/platforms/dart/configuration/integrations/dio/) integration already adds the `Response` field in the `Contexts` interface, so in case we go with Option 1, we'd need to migrate the data to the new `Response` interface.

# Unresolved questions

* Should we rename `data` to `other` or something else to avoid confusion?
* Some fields from the `Response` should be the very same as the `Request` interface (such as `method`, `url`, ...), should we just omit them?
