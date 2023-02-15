* Start Date: 2022-11-23
* RFC Type: feature
* RFC PR: -
* RFC Status: draft

# Summary

Enhance stack traces and profiles with module name.

# Motivation

Standardize 3rd party/vendor code detection across SDK's

# Problem

Frames in Sentry stack traces contain an `in_app` field which serves as a flag to indicate if a frame belongs to "user" defined code. This means that by definition, we do not know if an error originated from inside a 3rd party dependency or not as some SDK's mark that as 3rd party code.

# Impact on our product

quoting @armenzg
> Currenly, the issue details page loads the first stacktrace frame that is marked as in-app. On Python, stack traces are marked as in-app for both the customer's code as well as 3rd party libraries, thus, the customer in some cases will be loading the frame for a 3rd party library rather that their own code. In such cases, stacktrace links will fail since they cannot link 3rd party libraries with the source code for that library. As of one hour ago you can see the impact of 3rd party modules on the issue details page when showing stack trace links (see https://sentry.io/organizations/sentry/discover/results/?id=17731&project=1&statsPeriod=45m). Notice that in_app being False (aka 3rd party modules) has a success rate of 0%.


SDK related code
- Node.js: https://github.com/getsentry/sentry-javascript/blob/master/packages/utils/src/stacktrace.ts#L172
- Python: https://github.com/getsentry/sentry-python/issues/1754
- Go: https://github.com/getsentry/sentry-go/blob/64b90ef9fbe4aaaf3a30a6fc170e931940c6f258/stacktrace.go#L295
- Php: https://github.com/getsentry/sentry-php/blob/510dd816bf33f5f1322d564b6a562bfc422b265f/src/FrameBuilder.php#L117
- Ruby: https://github.com/getsentry/sentry-ruby/blob/4d712af25de31fc05f65db4c4f2d89bcaf193002/sentry-ruby/lib/sentry/backtrace.rb#L89
- (feel free to add more)

# Proposal #1: add a frame type enum field

# Trade offs
For some languages,  


# RFC Status

* `draft`: this RFC is currently in draft state.
* `active`: this RFC is currently active, which means that the contents of the document reference the current state of affairs and are supposed to be followed.
  This status is used for RFCs that are informational or general guides.
* `approved`: the approver of an RFC approved the decision.
* `withdrawn`: the RFC was withdrawn.  Typically such RFCs are not visible in the repository as the corresponding PRs are not merged unless they are withdrawn after being accepted.
* `replaced`: the RFC was later replaced by another RFC.

# RFC Creation Workflow

1. Create a new RFC document as a copy of `0000-template.md`.
2. Name it `XXXX-short-description.md` and commit it to a new branch.
3. Create a pull request against the `rfcs` repository.  The number of the pull request then
   becomes the assigned RFC number filled into `XXXX`.  Zero pad it out to 4 places for better sorting.
4. Pick an RFC type and write it down on your RFC text in the header.

If you are writing a DACI-style RFC, read "Instructions for running this Play" (10 mins) from
[Atlassian's Playbook](https://www.atlassian.com/team-playbook/plays/daci).  Mention informed and contributors in the PR
description and assign the approver to the PR.

Comments are to be left on the text for suggestions and in the general GitHub pull request comment system.

# RFC Approval Process

Once the approver (can be a person or a TSC) approves the RFC it gets merged.  At that point these things have to happen:

1. Ensure that the RFC PR link is filled in.
2. Ensure that the document is named after the PR number if it hasn't been yet.
3. Ensure the RFC is merged and shows up in `text`.
4. Ensure that a link to the RFC is added to the `README.md` file.

# Related issues

- https://github.com/getsentry/sentry-python/issues/1754
# RFC Withdrawal

RFCs do not need to run to completion.  The creator can always withdraw (status `withdrawn`) the RFC, at which point the PR is closed.  It can be reopened later.

RFCs that are `active` can be retried by setting the status to `replaced` or `withdrawn`.  The former is to be used if another RFC has since replaced it.
Rather than doing that, it's typically better to edit and update the RFC instead (eg: informational RFCs are living documents).
