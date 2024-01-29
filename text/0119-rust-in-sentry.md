- Start Date: 2023-10-25
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/119
- RFC Status: draft

# Summary

Make it easier to use Rust code from Sentry/Python.

This is now live in the [`ophio`] repo. See the [Proposed Workflow](#proposed-workflow) section,
or the README of the [`ophio`] repo to learn how to create / publish / use these bindings.

# Motivation

We want to improve the adoption of Rust within the Sentry/Python codebase, making it easier to do so,
and removing some hurdles that make current Rust usage very annoying and brittle.

# Background

The current way we use Rust from Sentry/Python has a couple of downsides which we want to improve upon.

These include:

- Maintaining Python Bindings is itself a huge burden and cumbersome to do.
- Specifically, the introduction of the bindings predates the stable Python ABI.
- Publishing packages to PyPI means that we have to care about SemVer compatibility and public API.
- The publishing process itself to PyPI has seen an extremely high failure rate as of late.
- Getting a Rust dependency into Sentry/Python takes a long chain of publishes/updates and thus takes a long time.

We currently have Rust bindings in the form of the `symbolic` and `sentry-relay`,
where I believe both python package are built specifically for usage in Sentry, with very limited to no third-party usage.
In particular, Python `symbolic` contains a subset of the functionality the Rust crate provides,
and in other cases also exposes functionality that is not part of the Rust crate at all,
for the sole purpose of having Python bindings for that functionality (example: `proguard`).

# Options Considered

We settled on creating a "dumping group"

## Create a single Sentry-specific bindings package

With this approach, we would a single project/package that acts a Rust binding layer.
We would pull in only the Rust dependencies that we need, and only expose functionality to Python that we actually use.
It would also make it possible to move functionality from Python to Rust that does not make sense as a standalone
Rust crate.

- **pro**: Only pulling in the dependencies that are actually needed.
- **pro**: Only a single Python extension module to build / care about with fixed overhead.
- **pro**: Ability to move functionality from Python to Rust more fine-grained.
- **pro**: No need to ~maintain public PyPI packages and~ care about SemVer.
- **pro**: Simpler release / update flow. ~Ideally things would only require a single commit to `sentry`.~
- **con**: Setting up and maintaining a workflow in the Monolith repo that suits every developer might be more complex.

## Maintain crate-specific Python bindings

This approach is listed for completeness, I do _not_ advocate for it.
With this approach, each Rust crate we are interested in would have its own Python Bindings.

- **pro**: We have smaller more targeted crates/packages to maintain and to publish.
- **pro/con**: Both pro/con is that each crate/package is in charge of its own workflows.
- **con**: This would still suffer from the problems around having to maintain a public SemVer API.
- **con**: It would also rely on publishing to PyPI, and then updating that version within Sentry.
- **con**: Having multiple smaller Python extension modules will increased the fixed per-module overhead.
  In particular, each module would have its own bundled copy of the Rust `std`.

# Proposed Workflow

- Have a separate repo ([`ophio`]) for the Rust bindings, using PyO3 / maturin.
- Use the standard _release_/_publish_ workflow.
- Manually trigger publishes and [auto-approve](https://github.com/getsentry/publish/blob/main/.github/workflows/auto-approve.yml).
- The _publish_ workflow will publish to _public_ PyPI.
- The package will be public, but we will not have any SemVer obligations whatsoever.
- The internal PyPI mirror will automatically pick this up.
- Trigger the [bump-version] workflow to update this in Sentry.

Put even simpler:

- Get PR in [`ophio`] approved and merged.
- Trigger _release_/_publish_ workflow in [`ophio`].
- Either run [bump-version] workflow in [`sentry`], or open a PR that bumps the dependency version.

# Unresolved questions

- ~Can this live in the main `sentry` repo, or does it need to be a separate repo / project?~
- ~How would the developer workflow look like?~
- ~As in: Can Python-only developers just install pre-built binaries without the need to care about parts written in Rust at all?~

[bump-version]: https://github.com/getsentry/sentry/actions/workflows/bump-version.yml
[`ophio`]: https://github.com/getsentry/ophio
[`sentry`]: https://github.com/getsentry/sentry
