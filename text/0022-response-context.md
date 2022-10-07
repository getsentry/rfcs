* Start Date: 2022-10-03
* RFC Type: feature
* RFC PR: [#22](https://github.com/getsentry/rfcs/pull/22)
* RFC Status: approved
* RFC Driver: [Manoel Aranda Neto](https://github.com/marandaneto)

# Summary

Add `Response` interface that contains information on a HTTP response related to the event.

# Motivation

The [Request](https://develop.sentry.dev/sdk/event-payloads/request/) interface contains information on a HTTP request related to the event. However, there is no interface that contains information on a HTTP response related to the event. This RFC proposes a new interface called `Response`.

The `Request` interface has a few limitations:
* Does not accept arbitrary fields, so unknown fields are dropped during ingestion such as `status_code`.
* Response `headers` are not dropped during data scrubbing, See [issue](https://github.com/getsentry/relay/issues/1501).
* Adding `Response` data in the `Request` interface is semantically wrong anyways.

# Background

This is necessary to implement the `Failed HTTP Client requests automatically result in Events` feature that is described in this [DACI](https://www.notion.so/sentry/Failed-HTTP-Client-requests-automatically-result-in-Events-f6c21d2a58ce4f2c889a823fd1da0044).

Since the `Response` metadata is PII sensitive, it should be properly mapped, documented and scrubbed.

The [Dart Dio HTTP Client](https://docs.sentry.io/platforms/dart/configuration/integrations/dio/) integration already adds the `Response` field in the `Contexts` interface.

# Supporting Data

See [Supporting data](https://www.notion.so/sentry/Failed-HTTP-Client-requests-automatically-result-in-Events-f6c21d2a58ce4f2c889a823fd1da0044#0ca951d5216742dbaab02f5fd33b8fb5) section in the [DACI](https://www.notion.so/sentry/Failed-HTTP-Client-requests-automatically-result-in-Events-f6c21d2a58ce4f2c889a823fd1da0044).

# Proposal (Namely Option 2)

The proposal is adding a `Response` interface in the [Contexts interface](https://develop.sentry.dev/sdk/event-payloads/contexts/).

By doing this, we can keep the `Request` interface as it is and we don't need to change the data scrubbing rules for the `Request` field.

Adding it as part of the `Contexts`, we get a lot for free such as retained arbitrary fields and back compatibility.

```json
{
  "contexts": {
    "response": {
      "type": "response",
      "cookies": "PHPSESSID=298zf09hf012fh2; csrftoken=u32t4o3tb3gg43; _gat=1;",
      "headers": {
        "content-type": "text/html"
      },
      "status_code": 500,
      "body_size": 1000,
      "arbitrary_field": "arbitrary" // arbitrary and retained fields for backwards compatibility when adding new fields
    }
  }
}
```

* `type`: `response` as `String`.
* `cookies`: Can be given unparsed as `String`, as `Dictionary`, or as a `List of Tuples`.
* `headers`: A `Dictionary` of submitted headers, this requires a special treatment in the data scrubbing rules.
* `status_code`: The HTTP status code, `Integer`.
* `body_size`: A `Number` (absolute/positive) indicating the size of the response body in bytes.

The `url`, `method`, `query_string`, `fragment`, `env` fields are not part of the `Response` interface and they should be set under the `Request` field, even if inferred from the HTTP response in case you don't have control over the HTTP Request object.

The `data` field won't be added to the `Response` interface, a phase 2 of this RFC will propose add Request and Response bodies are sent as attachments.

Fields that may contain PII:
* `cookies`
* `headers`

The PII rules should be similar to the [Request](https://develop.sentry.dev/sdk/event-payloads/request/) interface.

The difference is that `headers` contain response headers, such as this [issue](https://github.com/getsentry/relay/issues/1501).

## Must have

The fields `Request#url` and `Response#status_code` should be indexed, people should be able to search for events with a specific `url` and/or `status_code`, also to alert on them.

# Drawbacks

The `Response` interface is PII sensitive, so we need to be careful about how we scrub it.

# Appendix

## Removed Proposals

### Option 1

Adding a `Response` interface directly in the [Event payload](https://develop.sentry.dev/sdk/event-payloads/).

```json
{
  "response": {
    // ..
  }
}
```

This option is not chosen because it's not backwards compatible and we don't get a lot for free such as retained arbitrary fields and develop docs.

Also, the `Request` field may be soft deprecated in the future in favor of `Contexts#request`.

### Option 3

Expand the `Request` interface adding the missing fields.

Data scrubbing should consider response headers when scrubbing.

If we do that, the `Request` docs should be ammended that it contains the `Response` data as well otherwise it's semantically wrong.


This option is not chosen because PII rules would need to be changed, it's not backwards compatible and it's semantically wrong.
