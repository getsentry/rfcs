- Start Date: 2023-01-17
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/62
- RFC Status: approved
- RFC Driver: [Neel Shah](https://github.com/sl0thentr0py/)

# Summary

Proposals for new SDK-side configs/APIs to exhaustively control both PII (Personally Identifiable Information) and security credentials that are sent to Sentry.

# Motivation

As we get larger orgs with privacy, security and GDPR concerns using Sentry, it becomes more and more important to solve these use cases well with proper abstractions.  
We've also had incidents in the past where we got collateral flak publicly for breaches / leaks on self-hosted instances.

Controlling data exposed or collected on any SDK in a centralized and consistent manner with full transparency would be the goal of this RFC.

I will also make the case for (optionally) distinguishing between PII and Security semantics.  
Security credentials should **never** be sent to Sentry, while PII would be left as a choice for the user.

# Background

## Existing PII handling mechanisms

Currently, PII is mainly stripped in Relay along with some ad-hoc logic of what data to include in each (SDK, language, integration) combination.

### Relay

Relay implements a [`PiiProcessor`](https://github.com/getsentry/relay/blob/37f965b9747fd00ba4f3b01be378279bb6704687/relay-general/src/pii/processor.rs#L55) that scrubs
the event payload recursively for things it can identify including emails, creditcards, IP addresses, SSNs, etc.  
The configuration format is documented [here](https://develop.sentry.dev/pii/) and a full list of the current builtin rules can be found [here](https://github.com/getsentry/relay/blob/37f965b9747fd00ba4f3b01be378279bb6704687/relay-general/src/pii/builtin.rs#L34).

While we should continue doing server-side scrubbing in any case, having more control on the SDK is still desired by users who want to be completely sure
that no sensitive data ever leaves their application and crosses the network.

### SDKs

#### `send_default_pii`

The Unified API has a boolean config `send_default_pii` that is used ad-hoc in various integrations to conditionally add certain fields to the event payload.  
Each (SDK, language, integration) combination internally uses this flag to optionally add sensitive data such as headers, cookies or user login data.  
Thus, each integration author has to decide what data is potentially sensitive and the user has no further control on what is included.  
PII handling is also missing in many SDKs in performance related logic such as database span recording integrations.

The following table will illustrate usage examples from various SDKs highlighting various problems with the current way of doing things.

| SDK        | Integration             | Links                                                                                                                                                                                               | Remarks                                                                      |
| ---        | ---                     | ---                                                                                                                                                                                                 | ---                                                                          |
| python     | WSGI                    | [cookies](https://github.com/getsentry/sentry-python/blob/de84c4c7d65830e91f3af8555ebb1f7385a2d7cc/sentry_sdk/integrations/_wsgi_common.py#L63-L64)                                                 | all cookies including session are included which is a security issue         |
| python     | WSGI                    | [headers](https://github.com/getsentry/sentry-python/blob/de84c4c7d65830e91f3af8555ebb1f7385a2d7cc/sentry_sdk/integrations/_wsgi_common.py#L18-L27)                                                 | hardcoded sensitive headers list                                             |
| python     | sql spans & breadcrumbs | [params](https://github.com/getsentry/sentry-python/blob/de84c4c7d65830e91f3af8555ebb1f7385a2d7cc/sentry_sdk/tracing_utils.py#L169-L179)                                                            | not using `send_default_pii` but custom config                               |
| javascript | httpclient              | [cookies, headers](https://github.com/getsentry/sentry-javascript/blob/7316b850988df64467a7052082db84461f8a2cd2/packages/integrations/src/httpclient.ts#L136-L154)                                  | no control in which cookies and headers                                      |
| ruby       | request interface       | [headers](https://github.com/getsentry/sentry-ruby/blob/bbfb6514d95adda77676d4a0823924e789db0909/sentry-ruby/lib/sentry/interfaces/request.rb#L84-L104)                                             | random hardcoded lists                                                       |
| android    | okhttp                  | [headers](https://github.com/getsentry/sentry-java/blob/9b6c37f33376556ce0f66e526541a04e9e3aa60f/sentry-android-okhttp/src/main/java/io/sentry/android/okhttp/SentryOkHttpInterceptor.kt#L223-L242) | no headers at all if `send_default_pii` false, filter sensitive even if true |

As demonstrated by the collection above, each SDK does slightly different things and the decisions on what is gated behind `send_default_pii` are mostly left to the integration authors.  
The user can merely choose to follow the author's implementation with this flag but not really be sure if and what data is leaking without reading the integration source, which is an undesirable state of affairs.


#### `before_send` and `add_event_processor`

In cases where users are not happy with `send_default_pii`, we suggest using either `before_send` for errors or `add_event_processor` for all events for controlling PII on the final event payload.  
This, while it works in theory has several problems:

* there is an ordering problem when a user's added global event processor runs before some other event processor added by an integration, thus not giving the user the actual final event
  * there are [documented **unsupported** use cases](https://github.com/getsentry/sentry-python/issues/1226#issuecomment-978806984) here such as the user never being able to remove a certain request header since the headers are actually added [after](https://github.com/getsentry/sentry-python/blob/de84c4c7d65830e91f3af8555ebb1f7385a2d7cc/sentry_sdk/integrations/wsgi.py#L306-L325) the user's event processor runs
  * this will be partially fixed by `before_send_transaction` but I still believe PII scrubbing is a key concern that should not be shoe-horned into catch-all callbacks that run at the end
* writing either of these callbacks requires the user to know the whole event schema which even our own SDK devs don't know fully

# Options Considered

The high-level proposal is to introduce a new `config.event_scrubber` with a default implementation that users can tweak with a simple `denylist` in most cases.  
The end-user only cares about hiding certain information quickly, so a single list is the ideal interface.  
Anything more complex than that is asking them to think about things they don't care about.  
The advanced user can still override the implementation (similar to custom transports) if they wish to do so by using their own class implementation.


```python
# ===========================================================================
# event_scrubber.py

DEFAULT_DENYLIST = ["password", "HTTP_COOKIE"]

class EventScrubber:
    def __init__(self, denylist=None):
        self.denylist = DEFAULT_DENYLIST if denylist is None else denylist

    def scrub_event(self, event):
        # type: (Event) -> Event
        # ... scrubbing logic discussed below
        return event


# ===========================================================================
# client.py

def capture_event(self, event):
    # ... existing logic
    if not config.send_default_pii:
        scrubbed_event = event_scrubber.scrub_event(event)

    new_event = before_send(scrubbed_event)
    # ... existing logic


# ===========================================================================
# usage

sentry_sdk.init(
    send_default_pii=False,
    event_scrubber=EventScrubber(denylist=["custom_sensitive_field"]),  # has default impl
)
```

The actual scrubbing logic can be implemented in two ways with trade-offs outlined below.

## A: Walk whole tree

```python
class EventScrubber:
    def scrub_list(self, l):
        for i, v in enumerate(l):
            if isinstance(v, dict):
                l[i] = self.scrub_dict(v)
            elif isinstance(v, list):
                l[i] = self.scrub_list(v)
          return l

    def scrub_dict(self, d):
        for k, v in d.items():
            if k in self.denylist:
                d[k] = "[Filtered]"  # Use `AnnotatedValue` here for _meta
            elif isinstance(v, dict):
                d[k] = self.scrub_dict(v)
            elif isinstance(v, list):
                d[k] = self.scrub_list(v)
        return d

    def scrub_event(self, event):
        return self.scrub_dict(event)
```

Here we would walk the whole event dict and whenever we encounter a key from the denylist, we would replace the value with `[Filtered]`.
We can optionally annotate the values so that the UI is transparent about the filtering.  
This allows a centralized place to scrub stuff regardless of where in the SDK it originates from.

This basically mirrors what relay does but with comparatively less complexity in how we scrub.  
Relay does a bunch of regex matching and such which would be a lot of added complexity to add to each SDK.

Note that the actual implementation of this recursion might have differences based on platform and the typing of `Event`. The above is just pseudo-code.  

## B: Scrub pre-defined set of interfaces

Instead of recursing through the whole payload, we can also manually keep track of interfaces we expect to see PII in and just scrub those.  
The advantage here is that it also acts as a form of self-documentation for sources of leakage.  
The implementation in this case would look something like the following.

```python
class EventScrubber:
    def scrub_dict(self, d):
        for k, v in d.items():
            if k in self.denylist:
                d[k] = "[Filtered]"

    def scrub_event(self, event):
        if "request" in event:
            if "headers" in event["request"]:
                self.scrub_dict(event["request"]["headers"])  # or event.request.headers if you have interfaces in your language

        if "spans" in event:
            for span in event["spans"]:
                if "data" in span:
                    self.scrub_dict(span["data"])

        # ... all other such fields exhaustively
        return event
```

For completeness, here's a list of interfaces from `sentry-python` currently potentially leaking PII.

* `event.request.headers`
* `event.request.cookies`
* `event.request.data`
* `event.logentry.params`
* `event.user`
* `event.breadcrumbs.values -> value.data`
* `event.exception.values -> value.stacktrace.frames -> frame.vars`
* `event.spans -> span.data`

## (Optional) C: Add separate security denylist

A related proposal is to split the `denylist` into `pii_denylist` and `security_denylist` where stuff in `security_denylist` is **always** scrubbed
irrespective of `send_default_pii` and stuff in `pii_denylist` is only scrubbed if `send_default_pii` is `False`.

# Drawbacks

* Option A: we add one more pass through the event object which adds some non-trivial computational overhead
* Option B: we need to keep track of possible sources of PII leakage in each SDK
  * the user cannot easily add new sources of leakage without writing a custom class

# Unresolved questions

* What parts of the design do you expect to resolve through this RFC?
  * Decide on one of the two scrubber implementations
  * Decide if we want to differentiate security and PII

* What issues are out of scope for this RFC but are known?
  * More advanced scrubbing such as regex detection within a value is out of scope

# Conclusion

For implementation of the scrubber, we will go with Option B since a recursive Option A seems infeasible in most SDKs.  
The first MVP will be done in `sentry-python` and we will also include Option C (separate always-on security denylist) for now.  
If the implementation has too much complexity, we can debate again during code review and simplify.  
Once `sentry-python` is shipped with a scrubber, develop docs will be updated and other high prio SDKs can port the implementation.

