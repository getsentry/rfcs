- Start Date: 2023-01-18
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/64
- RFC Status: draft

# Summary

The current RFC workflow requires authors to keep the RFC status updated in the text document. This is a fragile process that can introduce synchronization and even simple spelling errors. This RFC proposes relying on GitHub PR automation to dictate some of the happy path states, and using special text elements for the remaining states.

# Motivation

The current RFC workflow includes maintaining a status field in each document. Some of those statuses duplicate states that are better served by the process itself, ie, an RFC is considered to have a state of "draft" while it is still in PR, "approved" when the necessary stakeholders have approved the RFC PR, and "active" after the PR is merged.

Other states can be added in special call-out fields in RFC docs if and when they enter that state: "withdrawn" and "replaced", instead of being in the "RFC Status" field as it exists today, should instead be a header-type font with a warning icon like ⚠️ stating it was withdrawn or containing a link to the replacing RFC doc, appearing directly under the RFC metadata and before the Summary.

Relying on humans to follow a manual process always winds up leaking mistakes into production. [Here is an example](https://github.com/getsentry/rfcs/blob/7b6c373e560f1b4eca9a80059b60a222a4c8bcfa/text/0042-gocd-succeeds-freight-as-our-cd-solution.md?plain=1#L4) of a PR that has been merged, where it should be "active" status, but was left as "draft" when merged. It's often better to automate those kinds of things, and in this case, since GitHub has already automated the process of drafting (aka opening a PR), approving and merging proposals, we should use those as sources of truth to reduce errors.

# Drawbacks

- We may want to adopt a different process in the future instead of proposing RFCs via GitHub PR, for instance, using a GitHub wiki which does not have PRs, using a different repo host, or using a knowledge base product like Notion or JIRA
    - These are all unlikely scenarios, but if it happens, one could easily get the list of all RFC in `text/` and insert a status line of either withdrawn/replaced or active based on a simple text search.
