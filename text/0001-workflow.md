- Start Date: 2022-07-21
- RFC Type: informational
- RFC PR: -
- RFC Status: -

# Summary

This RFC describes the Sentry RFC process.

# Motivation

This document exists so that future RFC creators and editors have a workflow to go by. This workflow is inspired by
common RFC processes from the Open Source community (Rust RFCs, Python PEPs) but also our internal use of DACIs.

# RFC Type

The are three kinds of RFCs:

- a **feature** RFC is an RFC describing a new feature to Sentry, an SDK, the protocol, or something else that requires a decision to be made.
- a **decision** RFC is a DACI-style RFC that tries to capture a contended decision that requires circulation.
- an **informational** RFC is an RFC that provides guidelines, describes an issue, or states a longer-term plan that does not directly turn into implementation.

# RFC Status

- `draft`: this RFC is currently in draft state.
- `active`: this RFC is currently active, which means that the contents of the document reference the current state of affairs and are supposed to be followed.
  This status is used for RFCs that are informational or general guides.
- `implementation`: The RFC was discussed and is currently in a trail period of being implemented. Potential learnings will go into the RFC before it's finally approved. This step is optional and can be considered by the author as a forcing function to move forward.
- `approved`: the approver of an RFC approved the decision.
- `withdrawn`: the RFC was withdrawn. Typically such RFCs are not visible in the repository as the corresponding PRs are not merged unless they are withdrawn after being accepted.
- `replaced`: the RFC was later replaced by another RFC.

# RFC Creation Workflow

> You can use the RFC Creation script via `python new-rfc.py` to automate the steps below. You'll need python3 in your path, and the [gh cli installed](https://cli.github.com/) and [authed](https://cli.github.com/manual/gh_auth_login).

1. Create a new RFC document as a copy of `0000-template.md`.
2. Name it `XXXX-short-description.md` and commit it to a new branch.
3. Create a pull request against the `rfcs` repository. The number of the pull request then
   becomes the assigned RFC number filled into `XXXX`. Zero pad it out to 4 places for better sorting.
4. Pick an RFC type and write it down on your RFC text in the header.

If you are writing a DACI-style RFC, read "Instructions for running this Play" (10 mins) from
[Atlassian's Playbook](https://www.atlassian.com/team-playbook/plays/daci). Mention informed and contributors in the PR
description and assign the approver to the PR.

Comments are to be left on the text for suggestions and in the general GitHub pull request comment system.

# RFC Approval Process

Once the approver (can be a person or a TSC) approves the RFC it gets merged. At that point these things have to happen:

1. Ensure that the RFC PR link is filled in.
2. Ensure that the document is named after the PR number if it hasn't been yet.
3. Ensure the RFC is merged and shows up in `text`.
4. Ensure that a link to the RFC is added to the `README.md` file.

# RFC Withdrawal

RFCs do not need to run to completion. The creator can always withdraw (status `withdrawn`) the RFC, at which point the PR is closed. It can be reopened later.

RFCs that are `active` can be retried by setting the status to `replaced` or `withdrawn`. The former is to be used if another RFC has since replaced it.
Rather than doing that, it's typically better to edit and update the RFC instead (eg: informational RFCs are living documents).
