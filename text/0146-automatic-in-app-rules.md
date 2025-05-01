- Start Date: 2025-05-01
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/146
- RFC Status: done

# Summary

For Java projects, when a code mapping is automatically created, also create an in-app stack trace rules to categorize the frames as in-app.

# Motivation

The majority of Java SDKs cannot determine if a frame is in-app or not and we depend on the customer's good will to add that information. In some cases, the customer would have to define dozens of rules by hand. Without in-app frames, Sentry's product lacks collapsed system frames, misses stack trace links and suspect commits.

# Supporting Data

There's 42% of Java projects with no issue with an in-app frame. Java projects with GitHub installed and automatic in-app generation only has 25% of projects with no issues with an in-app frame.

# Drawbacks

If the logic is not correct we may generate wrong in-app stack trace rules, however, the system allows for the customer to nullify the effects of the rule.

# Details

If a code mapping is generated for `com.example.foo` we generate an in-app rule for `stack.module:com.example.**`. This rule has one degree-less of specificity in order to match all packages across the board (e.g. `com.example.bar`).

This feature is build on top of [the derived code mappings system](0016-auto-code-mappings.md).

All logic for the creation of the rules can be found [here](https://github.com/getsentry/sentry/blob/4ce5da73a3896062636a214d384f439071741f89/src/sentry/issues/auto_source_code_config/task.py#L196-L200).
