- Start Date: 2024-08-27
- RFC Type: feature
- RFC PR: TODO
- RFC Status: draft

# Summary

This RFC proposes the implementation of versioned documentation for [Sentry Docs](https://docs.sentry.io). The goal is to provide users with access to documentation specific to different versions of a Sentry SDK. Currently, users only have access to the documentation of the latest version of a SDK.

# Motivation

- As of August 2024, downloads for the core JavaScript SDK are still roughly split up 50:50 between v7 and v8, where documentation is only available for v8.
- Reduce confusion and frustration for users that are trying to find documentation for their specific version.
- Reduce support requests / github issues regarding older versions.

# Options Considered

## 1 (preferred) - Nesting the version by appending the version to the platform path segment

The documentation would include the version number within the URL path (e.g., `docs.sentry.io/platform/javascript/v7/...`, `docs.sentry.io/platform/python/v1/...`). Omitting the version in the path would always point to the latest version. This approach integrates versioning directly into the existing URL structure, allowing users to easily switch between versions while supporting different versions for each SDK. Theoretically this would also allow different folder/file structures under each version. A possible approach would be to have a `versioned_docs` directory under each platform that serves the content for the different versions. This approach potentially introduces content-duplication.

## 2 - Keeping previous versions deployed under a subdomain

This approach would mean we trigger deployments under version specific branches (e.g. `js-v7`) and point a subdomain to it (e.g. `v7.docs.sentry.io`). Platform changes on the latest version would not be reflected in legacy versions (like styling, structure etc.)

The problem here is we would also need to include the platform in the subdomain for pointing to the correct documentation since the python version for example does not match the js version and is therefore likely not suitable for us.

## 3 - Appending the version to the URL

In this approach, the version number is appended to the URL, resulting in paths like `docs.sentry.io/platforms/javascript/some/nested/path/v7`. An advantage would be that versioning could be determined on a per page basis, but at the same time this introduces versioning in the nested page structures, making it difficult to maintain.

# Drawbacks (Assuming Option 1)

- Complex routing
- Content duplication
- User confusion (user might consume outdated information without being aware of it)
- (Potentially heavily) increased build time due to the number of added pages for each platform.
- Link management
- SEO - indexed versioned pages could potentially lead users to outdated information

# Unresolved questions

- How could the build process be optimized to not suffer from introducing versions? (e.g. SSR, ISR, ...)
- How can we make version switching intuitive from a UX perspective?
- Should versioned pages be indexed?
