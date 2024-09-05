- Start Date: 2024-09-04
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/140
- RFC Status: draft

# Summary

As feature flags are evaluated in a customer's application we will collect those flags and their results, store them in-memory, and push the values to Sentry when an error occurs. The flags can be used to further understand what went wrong during the session.

# Motivation

To enable users to debug application errors with a complete picture of their application's state.

# Options Considered

We will collect flag evaluations and hold them in-memory.  On error event the flags will be placed into the `contexts` object on the `event` and sent to Sentry.

## Transport

The flags will be represented by this data structure during transport. The `flag` key is the name of the flag and the `result` key is the evaluation result returned by the customer's application.

```json
{
    "contexts": {
        "flags": [
            {"flag": "abc", "result": true},
            {"flag": "def", "result": false}
        ]
    }
}
```

## Public Interface

The SDK will expose one new public method `set_flag`.  Similar to `set_tag` or `set_user`, the `set_flag` method sets a key, value pair (representing the flag's name and its evaluation result) into an internal SDK structure. On error, that structure is serialized and appended to the event body as described in the previous section.

## Bounding Memory Usage and Transport Size

We will cap the number of flag evaluations to some fixed capacity (e.g. 100). Duplicate evaluations will update the existing entry rather than insert a new one. New unique evaluations will be appended to the data structure with the least recently accessed evaluation being dropped.

## Integrations

Integrations for feature flag SDKs will need to be written. There are many competing offerings and we'll want to provide integrations for. The main providers we want to initially target are: launchdarkly, unleash, split, and OpenFeature. The public SDK interface is available for those wishing to integrate with additional vendors.

The exact structure of an integration is undefined for the purposes of this document but each integration should call the `set_flag` SDK method on successful flag evaluation.
