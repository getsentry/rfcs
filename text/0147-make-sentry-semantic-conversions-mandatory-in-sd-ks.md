- Start Date: 2025-05-08
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/147
- RFC Status: withdrawn

# Summary

We should make sure, that it is hard to add span attributes that are not listed in our Semantic Conversions.
This should make it impossible to just randomly add attributes that are not documented anywhere.

# Motivation

When every developer is adding random span attributes it leads to attribute names diverging between SDKs and we need to implement mappings in `relay` to make up for it.
This leads to `relay` needing to do more work to process events.

# Background

The AI insights module is a fairly new module, but SDKs already send the attributes in different ways.

# Supporting Data

[Metrics to help support your decision (if applicable).]

# Options Considered

## Option A: SentrySemConv Package

Whenever the semantic conversions are updated, packages for all our platforms are generated that are called "SentrySemConv" containing a enum kind of type that includes all the possible span attributes.

In the code we change the type of `set_attribute/setAttribute` to only allow the "key" to be of type SentrySemConf.

```python
# bad, not allowed:
span.set_attribute("ai.completion_tokens.used", 10)

# good, allowed:
import SentrySemConv
span.set_attribute(SentrySemConv.AI_COMPLETION_TOKENS_USED, 10)
```

The Sentry semantic conventions should be versioned for this. (See [Appendix A](#drawbacksappendix-a-versioning-for-semantic-conventions)) You will be not allowed to change the key of an attribute in the semantic conversion, you need to add a new attribute and deprecate the old one.

### Pros

- Makes it impossible to add random attributes to spans.
- Linter can show you when you use deprecated attributes.

### Cons

- More work when introducing a new attribute: You need to update the Sentry semantic conversions, before you can add a new attribute
- The SDK gets one new dependency: SentrySemConv

## Option B: Query semantic conversions on release of new SDK version.

Each SDK keeps a list of attributes used. When you want to do a release of the SDK a CI action is triggered that queries the semantic conversion repo. It checks if all the attributes that are used by the SDK are actually present in the semantic conversions.
If an attribute is not there, or is deprecated the CI fails. Preventing the SDK with random attributes being released.

For this we need to add an API to the semantic conversions page, to query for existing attributes (a simple page returning a JSON objects containing all attributes could suffice)

```python
# bad, not allowed:
span.set_attribute("ai.completion_tokens.used", 10)

# good, allowed:
from sentry_sdk import SemConv
span.set_attribute(SemConv.AI_COMPLETION_TOKENS_USED, 10)
```

### Pros

- Makes it impossible to add random attributes to spans.

### Cons

- Each SDK needs to implement a list of used attributes
- Each SDK needs to implement a CI action to check if those used attributes are existing in the semantic conventions.
- More work (because we need the JSON response in the semantic conventions page)

# Drawbacks

- It adds initial work for us.
- It also adds more workflow when doing a new SDK release that introduce a new attribute, because one needs to update the semantic conversions first.
s
# Appendix

## Appendix A: Versioning for Semantic Conventions

### Option A: Semantic Versioning ([major].[minor].[patch])

With this versioning we could have breaking changes in the semantic conventions (like renaming a attribute key).
That is probably overkill, and having breaking changes in this also not the best way. Cleaner would be to add new attributes and deprecate older verion.

### Option B: Simple verison numbers (v1, v2, v3, ...)

Easier to implement. One must make sure that there are never breaking changes released in a new version (so developer needs to make sure to deprecate old attributes and add new ones)
