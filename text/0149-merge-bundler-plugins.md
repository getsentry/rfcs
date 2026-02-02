- Start Date: 2026-01-23
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/149
- RFC Status: draft
- RFC Driver: [Charly Gomez](https://github.com/chargome)
- RFC Approver: JavaScript SDK Team

# Stakeholders

| Role                 | People                                    |
| -------------------- | ----------------------------------------- |
| Driver               | @chargome / JavaScript SDK Team           |
| Approver             | JavaScript SDK Team                       |
| Informed (potential) | Docs Team, Other SDK Engineering Managers |

# Summary

This RFC proposes merging the [sentry-javascript-bundler-plugins](https://github.com/getsentry/sentry-javascript-bundler-plugins) repository into the [sentry-javascript](https://github.com/getsentry/sentry-javascript) monorepo. This consolidation will unify versioning, reduce maintenance overhead, and improve the developer experience for both maintainers and users.

# Motivation

The bundler plugins (`@sentry/webpack-plugin`, `@sentry/vite-plugin`, `@sentry/rollup-plugin`, `@sentry/esbuild-plugin`) are tightly coupled to the Sentry JavaScript SDK. Maintaining them in a separate repository creates several pain points:

1. **Versioning complexity**: Independent release cycles make it difficult to ensure compatibility between SDK and plugins.
2. **Testing limitations**: Cannot easily test plugins against the actual SDK code they'll be bundling.
3. **Contributor friction**: Developers working on cross-boundary features need to context-switch between repositories.
4. **User confusion**: Users often file issues in the wrong repository.
5. **Duplicate infrastructure**: Separate CI/CD pipelines, release processes, and tooling configurations.

# Background

The bundler plugins were originally developed in a separate repository to allow independent versioning. The plugins are built on [unplugin](https://github.com/unjs/unplugin) and provide sourcemap upload, release creation/management, release injection, and React component display names for breadcrumbs and Session Replays.

## Current State

| Aspect          | sentry-javascript-bundler-plugins | sentry-javascript |
| --------------- | --------------------------------- | ----------------- |
| License         | MIT                               | MIT               |
| Current Version | v4.x                              | v9.x              |
| Test Framework  | Jest                              | Vitest            |
| Node.js Minimum | Node 16                           | Node 18+          |
| Monorepo Tool   | Nx                                | Nx/Lerna          |

**Packages to migrate:**
- `@sentry/bundler-plugin-core`
- `@sentry/webpack-plugin`
- `@sentry/vite-plugin`
- `@sentry/rollup-plugin`
- `@sentry/esbuild-plugin`

# Options Considered

## Option 1: Merge into sentry-javascript monorepo (Recommended)

Move all bundler plugin packages into the `sentry-javascript` repository. A two-phase approach (preparatory work in original repo, then final merge) reduces risk and allows changes to be tested in isolation.

## Option 2: Keep repositories separate

Maintain the current separate repository structure.

**Rejected because**: Does not address the core issues of versioning complexity, testing limitations, and contributor friction.

# Implementation Plan

## Prerequisites

- [x] Verify license compatibility (both MIT)
- [ ] Gather Webpack 4 usage statistics ([PR #857](https://github.com/getsentry/sentry-javascript-bundler-plugins/pull/857))

## Phase 1: Preparation (in sentry-javascript-bundler-plugins repo)

On a dedicated branch (e.g., `merge-prep`):

1. **Update dependencies**:
   - Bump minimum Node.js to 18+
   - Migrate unplugin to v2 (drops Node 16 and Webpack 4 support)
   - Bump Sentry CLI to v3
2. **Migrate tests from Jest to Vitest**
3. **Audit dependencies** for conflicts with sentry-javascript
4. **Publish final standalone version** with deprecation notice
5. **Merge prep branch to main** when ready for migration

## Phase 2: Migration to sentry-javascript

1. **Merge packages** into `sentry-javascript/packages/` while preserving git history (via `git subtree` or [git-filter-repo](https://github.com/newren/git-filter-repo))
2. **Integrate with monorepo** build system and CI
3. **Update `.craft.yml`** for new release targets

## Phase 3: Release

1. **Ship with sentry-javascript v11** to accommodate breaking changes
2. **Communication**: Deprecation notice on old repo, update documentation

## Phase 4: Post-Migration

1. **Archive** `sentry-javascript-bundler-plugins` with README pointing to monorepo

# Breaking Changes

Released with v11:

1. **Node.js 16 dropped** - Minimum version increased to 18+
2. **Webpack 4 dropped** (pending usage stats) - Required by unplugin v2; Webpack 5 was released 5+ years ago
3. **Version number jump** - Plugins jump from v4.x to v11.x to align with SDK

# Versioning Strategy

- **Major versions**: Released together with sentry-javascript majors
- **Minor/Patch versions**: Released together with sentry-javascript (all packages share same version)

# Future Considerations (Out of Scope)

Consolidate all plugins into a single `@sentry/bundler-plugins` package with subpath exports (e.g., `@sentry/bundler-plugins/webpack`). Would require aliasing to existing package names for backwards compatibility.

# Pros and Cons

## Pros

- Single source of truth for all JavaScript SDK tooling
- Consistent versioning and shared infrastructure
- Can test plugins with actual SDK code
- Reduced cognitive load for contributors
- Better triaging (users don't know about separate repo)

## Cons

- One-time migration effort
- Independent release cycles no longer possible without extra Craft configuration
- Larger monorepo
- Version jump from v4.x to v11.x may confuse users

# References

- [sentry-javascript-bundler-plugins repository](https://github.com/getsentry/sentry-javascript-bundler-plugins)
- [sentry-javascript repository](https://github.com/getsentry/sentry-javascript)
- [RFC 0086: Sentry Bundler Plugins API](https://github.com/getsentry/rfcs/blob/main/text/0086-sentry-bundler-plugins-api.md)
- [unplugin](https://github.com/unjs/unplugin)
