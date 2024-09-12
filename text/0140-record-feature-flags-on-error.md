- Start Date: 2024-09-04
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/140
- RFC Status: draft

# Summary

As feature flags are evaluated in a customer's application we will collect those flags and their results, store them in-memory, and push the values to Sentry when an error occurs. The flags can be used to further understand what went wrong during the session.

# Motivation

To enable users to debug application errors with a complete picture of their application's state.

# Options Considered

We will collect flag evaluations and hold them in-memory. On error event the flags will be placed into the `contexts` object on the `event` and sent to Sentry.

## Transport

The flags will be represented by this data structure during transport. The `flag` key is the name of the flag and the `result` key is the evaluation result returned by the customer's application.

```json
{
  "contexts": {
    "flags": {
      "values": [
        { "flag": "abc", "result": true },
        { "flag": "def", "result": false }
      ]
    }
  }
}
```

## Public Interface

The SDK will expose one new public method `set_flag/2`. The method accepts the arguments `flag` (of type string) and `result` (of type boolean). Similar to `set_tag/2` or `set_user/1`, the `set_flag/2` method stores a flag, result pair on the isolation scope. On error, the isolation scope's flags are serialized and appended to the event body as described in the previous section.

Stateless, multi-tenanted applications, such as web servers, must isolate flag evaluations per request.

## Bounding Memory Usage and Transport Size

The number of flag evaluations must be capped to some fixed capacity (e.g. 100). When the capacity is reached the least recently evaluated flag should be dropped from the set. Duplicate flag evaluations may update their existing entry rather than insert a new one. In most contexts, it will make sense to update the existing entry. An LRU cache is recommended for these cases. If repeat flag evaluations are desired then a ring buffer may be used.

## Integrations

An integration should wrap, provide a hook, or otherwise intercept the calls made to a feature flagging SDK. The flag requested and the result returned must be stored within the Sentry SDK's internal state using the publicly available `set_flag/2` method.
