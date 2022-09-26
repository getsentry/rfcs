* Start Date: 2022-07-21
* RFC Type: informational
* RFC PR: -
* RFC Status: -

# Summary

This RFC describes the Sentry RFC process.

# Motivation

This document exists so that future RFC creators and editors have a workflow to go by.  This workflow is inspired by
common RFC processes from the Open Source community (Rust RFCs, Python PEPs) but also our internal use of DACIs.

# Type

There are three types of RFCs:

* a **feature** RFC is a RFC describing a new feature to Sentry, an SDK, the protocol or something else that requires a decision to be made.
* a **decision** RFC is a [DACI](https://www.atlassian.com/team-playbook/plays/daci) style RFC that tries to capture a contended decision that requires circulation.
* an **informational** RFC is an RFC that provides guidelines, describes an issue or states a longer term plan that does not directly turn into implementation.

# Status

* `draft`: this RFC is currently in draft state.
* `active`: this RFC is currently active which means that the content of the document reference the current state of affairs and are supposed to be followed.
  This status is used for RFCs that are informational or general guides.
* `approved`: the approver of an RFC approved the decision.
* `withdrawn`: the RFC was withdrawn.  Typically such RFCs are not visible in the repository as the corresponding PRs are not merged unless they are withdrawn after accepted.
* `replaced`: the RFC was later replaced by another RFC.

# Workflow

1. Create a new RFC document as a copy of `0000-template.md`. Name it `XXXX-short-description.md` (number it one greater than the current max) and commit it directly to the `main` branch. Anyone can do this at any time. Publishing a new doc to `main` is the "request" in RFC.
1. Modify your RFC directly on `main` until other people care about it, then switch to PRs. PRs (or Issues, etc.) are the "comments" in RFC.
1. For non-informational RFCs, updating the RFC status to `approved` _must_ happen in a PR, with relevant parties signing off.

If you are writing a DACI style RFC, read "Instructions for running this Play" (10 mins) from
[Atlassian's Playbook](https://www.atlassian.com/team-playbook/plays/daci).  Mention informed and contributors in the RFC and have approver sign off on the `approved` PR.

Comments, discussion and suggestions should happen using GitHub issues and pull requests.


# Withdrawing

RFCs do not need to complete.  The creator can always withdraw (status `withdrawn`) the RFC. It can be reopened later.

RFCs that are `active` can be retired by setting the status to `replaced` or `withdrawn`. The former is to be used if another RFC has since replaced it.
Rather than doing that, it's typically better to edit and update the RFC instead (eg: informational RFCs are living documents).
