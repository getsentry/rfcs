* Start Date: 2022-09-08
* RFC Type: decision
* RFC PR: https://github.com/getsentry/sentry-cocoa/pull/2033

# Summary

This RFC proposes the inclusion of Swift demangle logic in the cocoa SDK, 
the same way symbolicator does.

# Motivation

We use class names as transaction names and transaction screen data, and the name
is not user friendly if we don't demangled it.

# Drawbacks

- By copying the demangle logic from Swift open source project, 
we increate the SDK binary by 46% (from 3MB to 4.4MB).
- We need to keep track in the Swift project to know when they
update the logic behind demangling.

# Alternatives

## Implement demangle algorithm ourselves 

We could try to create a logic ourself. The logic is a little complex, 
and we still need to keep track on any update in the Swift language.

## Demangled during ingestion

The ingestion is where we could do this server side, because we need the name
for dynamic sampling. But pushing it to server side it means the user needs to
deal with bad naming locally, like in 'beforeSend'. 
