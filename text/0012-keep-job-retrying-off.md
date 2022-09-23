* Start Date: 2022-09-20
* RFC Type: informational
* RFC PR: [#12](https://github.com/getsentry/rfcs/pull/12)

# Summary

[eng-pipes] (our internal service for handling webhooks) attempts to
auto-retry GitHub actions builds for [getsentry] (internal sentry) for:

1. any job which fails the `ensure docker image` step
1. any failed required job on the primary branch

the latter was [recently disabled] when it was discovered it was broken and
was also blocking internal messaging.

the proposal is to remove this functionality entirely.

[eng-pipes]: https://github.com/getsentry/eng-pipes
[getsentry]: https://github.com/getsentry/getsentry
[recently disabled]: https://github.com/getsentry/eng-pipes/pull/323

# Motivation

1. dev-infra believes it is more important to improve job reliability
   rather than investing in a big-hammer retry which is more likely to lead to
   ignoring the actual problems
1. it would require significant investment to make it work properly
1. removing this feature removes complexity in `eng-pipes`

# Background

we've invested a lot recently into reducing flakiness of setup tasks:
- [using ghcr.io instead of dockerhub](https://github.com/getsentry/sentry/pull/38146)
- [using prebuilt wheels from internal pypi](https://github.com/getsentry/sentry/pull/38255)
- [caching volta / npm / yarn](https://github.com/getsentry/sentry/pull/36253)
- [pinning requirements](https://github.com/getsentry/sentry/pull/34879)
- [pinning github actions](https://github.com/getsentry/sentry/pull/37166)
- [fix caching infinite hangs](https://github.com/getsentry/sentry/pull/38096)

we also already have [5x retries for python tests] which we also believe is
too high but is generally a better retry mechanism than rerunning the whole
job.  in the future we'd like to reduce this as it _enables_ flaky tests as
much as it improves CI experience however that is out of scope for this rfc.

[5x retries for python tests]: https://github.com/getsentry/sentry/blob/e4725effe61e917edfa41eea6833383f31110827/.github/actions/setup-sentry/action.yml#L80

# Supporting Data

I cannot find any successful transactions of this feature in the [ENG-PIPES]
sentry project -- there are however (resolved) [failures].

[ENG-PIPES]: https://sentry.io/organizations/sentry/projects/eng-pipes
[failures]: https://sentry.io/organizations/sentry/issues/3584516283/?project=5246761

# Options Considered

the other option is to invest into fixing and supporting this functionality.

# Drawbacks

the main drawback is if this functionality actually worked it would
potentially improve CI experience

# Unresolved questions

* dev-infra agrees with this plan but wants to get input before moving forward
