- Start Date: 2026-01-23
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/149
- RFC Status: draft
- RFC Driver: [Charly Gomez](https://github.com/chargome)
- RFC Approver: JavaScript SDK Team

# Stakeholders

| Role | People |
|------|--------|
| Driver | @chargome / JavaScript SDK Team|
| Approver | JavaScript SDK Team |
| Informed (potential) | Docs Team, Other SDK Engineering Managers |

# Summary

This RFC proposes merging the [sentry-javascript-bundler-plugins](https://github.com/getsentry/sentry-javascript-bundler-plugins) repository into the [sentry-javascript](https://github.com/getsentry/sentry-javascript) monorepo. This consolidation will unify versioning (shipping majors together), reduce maintenance overhead, and improve the developer experience for both maintainers and users.

# Motivation

The bundler plugins (`@sentry/webpack-plugin`, `@sentry/vite-plugin`, `@sentry/rollup-plugin`, `@sentry/esbuild-plugin`) are tightly coupled to the Sentry JavaScript SDK. Maintaining them in a separate repository creates several pain points:

1. **Versioning complexity**: Independent release cycles make it difficult to ensure compatibility between SDK and plugins.
2. **Testing limitations**: Cannot easily test plugins against the actual SDK code they'll be bundling.
3. **Contributor friction**: Developers working on cross-boundary features need to context-switch between repositories.
4. **User confusion**: Users often expect bundler plugins to live in the main SDK repository and file issues in the wrong place.
5. **Duplicate infrastructure**: Separate CI/CD pipelines, release processes, and tooling configurations.
6. **Triaging overhead**: Issues split across repositories complicates tracking and prioritization.

By merging the repositories, we can:

- Align bundler plugin versions with SDK versions (only shipping majors together)
- Test plugins with the actual SDK code they'll bundle
- Simplify the release process to a single Craft configuration
- Provide better tooling support (including LLM/AI context) for cross-boundary development
- Consolidate issue triaging with labels

# Background

The bundler plugins were originally developed in a separate repository (during hackweek) to allow independent versioning and release cycles. The plugins are built on [unplugin](https://github.com/unjs/unplugin) and provide:

- Sourcemap upload to Sentry
- Release creation and management
- Automatic release name discovery
- Release injection for automatic error association
- React component display names for breadcrumbs and Session Replays

## Current State

### sentry-javascript-bundler-plugins

| Aspect | Details |
|--------|---------|
| License | MIT |
| Current Version | v4.x |
| Testing Framework | Jest |
| Node.js Minimum | Node 16 |
| Monorepo Tool | Nx |
| Package Manager | Yarn |


### Packages

- `@sentry/bundler-plugin-core` - Shared bundler-agnostic functionality
- `@sentry/webpack-plugin` - Webpack 4 and 5 support
- `@sentry/vite-plugin` - Vite support
- `@sentry/rollup-plugin` - Rollup support
- `@sentry/esbuild-plugin` - esbuild support

### sentry-javascript

| Aspect | Details |
|--------|---------|
| License | MIT |
| Testing Framework | Vitest |
| Node.js Minimum | Node 18+ |
| Monorepo Tool | Nx/Lerna |
| Package Manager | Yarn |

## License

Both repositories use the **MIT license**. There is no license conflict for this merge.

# Options Considered

## Option 1: Merge into sentry-javascript monorepo (Recommended)

Move all bundler plugin packages into the `sentry-javascript` repository as part of the existing monorepo structure.

### Approach

1. Copy packages into `sentry-javascript/packages/` directory
2. Integrate with existing Nx build system
3. Migrate tests from Jest to Vitest
4. Unify versioning with SDK packages (majors released together)
5. Update Craft configuration to publish bundler plugin packages

### Versioning Strategy

- **Major versions**: Released together with sentry-javascript major versions
- **Minor/Patch versions**: Released together with sentry-javascript minor versions (streamlined for all packages in this repo)
- Initial merge should coincide with **v11 major release** to accommodate breaking changes (Node 16 drop)

### Package Publishing

Continue publishing existing package names for backwards compatibility:

- `@sentry/bundler-plugin-core`
- `@sentry/webpack-plugin`
- `@sentry/vite-plugin`
- `@sentry/rollup-plugin`
- `@sentry/esbuild-plugin`

### Future: Package Consolidation (Out of Scope)

In a future phase (not part of this RFC), consolidate all plugins into a single `@sentry/bundler-plugins` package with subpath exports:

```
@sentry/bundler-plugins/webpack
@sentry/bundler-plugins/vite
@sentry/bundler-plugins/rollup
@sentry/bundler-plugins/esbuild
```

This would require cross-publishing/aliasing to existing package names for backwards compatibility.

## Option 2: Keep repositories separate

Maintain the current separate repository structure.

**Rejected because**: Does not address the core issues of versioning complexity, testing limitations, and contributor friction.

# Implementation Strategy

## Prerequisites

- [x] Verify license compatibility (both MIT ✅)
- [ ] Gather Webpack 4 usage statistics to inform support decision
- [ ] Decide on Sentry CLI v3 migration timing (bundler-plugins issue https://github.com/getsentry/sentry-javascript-bundler-plugins/issues/825)

## Phase 1: Preparation

1. **Audit dependencies**: Review all bundler-plugin package dependencies for conflicts with sentry-javascript
2. **Document public APIs**: Ensure all public APIs are documented and compatibility is maintained
3. **Publish final standalone version**: Release final version from bundler-plugins repo with deprecation notice

## Phase 2: Migration

1. **Copy packages**: Move packages into `sentry-javascript/packages/` directory
   - Option A: Flat structure alongside other packages
   - Option B: Nested under `packages/bundler-plugins/` subdirectory (preferred?)

2. **Integrate with sentry-javascript's monorepo setup**: Adapt package configurations to match target repo's build system

3. **Migrate tests**: Convert Jest tests to Vitest
   - Update test configuration
   - Migrate Jest-specific APIs to Vitest equivalents
   - Ensure test coverage is maintained

4. **Update dependencies**:
   - Bump minimum Node.js version to 18+
   - Update unplugin to latest version
   - Remove Node 16 compatibility workarounds

5. **Configure CI**: Add bundler plugin jobs to GitHub Actions
   - Build bundler plugins in parallel job (doesn't impact overall CI time)
   - Integration tests with actual SDK code

## Phase 3: Publishing Configuration

1. **Update `.craft.yml`** for new release targets

2. **Version synchronization**: Configure packages to use SDK version numbers

3. **GitHub Actions**: Update release workflows to include bundler plugin packages

## Phase 4: Release

1. **Major version release**: First unified release as part of sentry-javascript v11

2. **Communication**:
   - Deprecation notice on old repository
   - Migration guide for users (anything to do here?)
   - Update documentation

## Phase 5: Post-Migration

1. **Archive repository**: Archive `sentry-javascript-bundler-plugins` with README pointing to monorepo
2. **Cleanup**: Remove any remaining references to old repository

# Potential Breaking Changes

This migration will introduce the following breaking changes (to be released with v11):

1. **Node.js 16 support dropped**: Minimum Node.js version increased to 18+
2. **Webpack 4 support dropped** (pending usage stats): Webpack 4 requires `NODE_OPTIONS=--openssl-legacy-provider` on Node 17+; Webpack 5 was released 5+ years ago
3. **Version number jump**: Plugin packages will jump from v4.x to v11.x to align with SDK versioning

# Known Drawbacks

1. **Larger monorepo**: Increases repository size and potentially CI times (mitigated by parallel jobs)
2. **Migration effort**: One-time cost to migrate packages, tests, and configuration
3. **Version number jump**: Users may be confused by jump from v4.x to v11.x
4. **Loss of independent releases**: Minor/patch releases tied to SDK schedule (unless Craft is configured otherwise)

# Pros and Cons Summary

## Pros

- Single source of truth for all JavaScript SDK tooling
- Consistent versioning across SDK and build tools
- Shared infrastructure (CI, linting, testing patterns)
- Easier to ensure compatibility between SDK and plugins
- Can test plugins with actual SDK code they'll bundle
- Reduced cognitive load for contributors
- Simpler dependency management
- Better triaging with labels (users don't know about separate repo)
- Shared context for LLMs when developing cross-boundary features
- All plugin code has minimal impact on repo size

## Cons

- Migration effort and potential breaking changes
- Independent release cycles no longer possible without extra Craft work
- Larger monorepo
- Risk of disrupting existing users during transition
- Increased complexity in the sentry-javascript repo

# Unresolved Questions

1. **Independent versioning**: Should we configure Craft to support independent minor/patch releases for bundler plugins, or tie everything to the SDK release schedule? Recommended: Same release cycle

2. **Webpack 4 support**: What are the current usage statistics? Should we drop support in v11, or maintain it with workarounds?

3. **Sentry CLI v3**: Should the Sentry CLI v3 migration (bundler-plugins issue bundler-plugins issue https://github.com/getsentry/sentry-javascript-bundler-plugins/issues/825) happen before or after the merge?

5. **SDK re-exports**: Should we re-export plugins from SDK packages in the future? This ships dev dependencies as prod dependencies, which users have complained about.

# References

- [sentry-javascript-bundler-plugins repository](https://github.com/getsentry/sentry-javascript-bundler-plugins)
- [sentry-javascript repository](https://github.com/getsentry/sentry-javascript)
- [RFC 0086: Sentry Bundler Plugins API](https://github.com/getsentry/rfcs/blob/main/text/0086-sentry-bundler-plugins-api.md)
- [unplugin](https://github.com/unjs/unplugin)