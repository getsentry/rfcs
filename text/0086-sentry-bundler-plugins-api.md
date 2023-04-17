- Start Date: 2023-04-13
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/86
- RFC Status: draft

# Summary

This RFC intends to discuss the future API of the [Sentry JavaScript Bundler Plugins](https://github.com/getsentry/sentry-javascript-bundler-plugins).

# Motivation

With the major bump to v2 of the bundler plugins, we have the opportunity to rethink the existing API that was orignially built on top of the [Sentry Webpack Plugin](https://github.com/getsentry/sentry-webpack-plugin).

Facts to consider when deciding on an API:

- The bump to v2 of unplugin will imply a major bump of the Sentry Webpack plugin and its switch to our unplugin based architecture.
- We recently introduced debug IDs as a source map resolving mechanism. This results in different needed options needed when running the plugins. Some options must be added, some removed.
- Releases are not a required parameter anymore for source maps upload.

As an additional thought: The new API should be seen as a "clean-slate" API - it's less about what has been and more about what the optimal API should look like.

# Supporting Data

- Debug ID RFC: https://github.com/getsentry/rfcs/blob/ab0f75567d95e247b5cc3f09c466b7254844e654/text/0081-sourcemap-debugid.md
- Debug ID changes related to the unplugin based Sentry bundler plugins: https://github.com/getsentry/sentry-javascript-bundler-plugins/issues/191

# Options Considered

The API generally only defines the options passed to the individual plugins. The options are the same for all bundlers.

For the sake of simplicity of this RFC, we will not decide on the JSdoc. All JSdoc below is just to illustrate what the options are used for.

Proposed API (TypeScript typedef):

```ts
interface Options {
  org?: string; // Can also be set via `env.SENTRY_ORG`
  project?: string; // Can also be set via `env.SENTRY_PROJECT`
  authToken?: string; // Can also be set via `env.SENTRY_AUTH_TOKEN`
  url?: string; // A way to configure self-hosted instances: unchanged
  headers?: Record<string, string>; // Headers added to every outgoing network request.
  debug?: boolean; // default: false - Whether to print debug information.
  silent?: boolean; // default: false - Whether to print anything at all.
  errorHandler?: (err: Error) => void; // when provided will swallow errors unless the provided function throws itself - By default any error will stop compilation to abort
  telemetry?: boolean; // default: true - whether to send telemetry to Sentry
  disable?: boolean; // default: false - just a quick way to entirely disable the plugin - purely for convenience

  // General configuration for source maps uploading - if not provided, source map uploading will be disabled
  sourcemaps?: {
    assets: string | string[]; // globs pointing to the javascript files that should be uploaded to Sentry with their source maps - these are the built assets and not the source files
    ignore?: string | string[]; // globs to exclude javascript files from being uploaded (will also not upload their source maps)
    rewriteSources?: (source: string) => string; // Hook to rewrite individual entries in the sourcemaps's `sources` field. By default, if not defined, the plugin will try to rewrite the entries to be relative to `process.cwd()`.
  };

  // General configuration for release creation and release injection - we decouple this from the debug ID source maps upload because they're technically not related anymore.
  // If not provided, this option will default to its default values.
  release?: {
    name?: string; // if not provided - Sentry CLI will try to guess a name (ie. git sha, cloud provider env vars, etc.)
    inject?: boolean; // default: true - whether to inject the release into bundles
    create?: boolean; // default: true - if set to `false` will not create a release in Sentry, no matter what other options are set - the release value will still be injected though.
    finalize?: boolean; // default: true
    dist?: string; // Can be used to segment releases further
    vcsRemote?: string; // default: 'origin' - Version control system remote name
    setCommits?: SetCommitsOptions;
    deploy?: DeployOptions;
    legacySourcemaps?: {
      // Pre-debugid way of uploading source maps - for users that for whatever reason cannot inject code into their bundles
      include: string | IncludeEntry | Array<string | IncludeEntry>;
      cleanArtifacts?: boolean; // default: false - Wether to delete artifacts previously uploaded to the release
    };
  };

  _experiments: {}; // whatever
}

// Identical to status-quo. See https://github.com/getsentry/sentry-webpack-plugin/blob/2b7d274a7355f0d27a431b2c20c37c9786bbe4cb/README.md for more information.
interface IncludeEntry {
  // ...
}

// Identical to status-quo. See https://github.com/getsentry/sentry-webpack-plugin/blob/2b7d274a7355f0d27a431b2c20c37c9786bbe4cb/README.md for more information.
interface SetCommitsOptions {
  // ...
}
```

Some removed options:

- `dryRun` - Current assumption is that this option is unnecessary:
  - Debug information can be printed with the `debug` option instead.
  - Executing the plugin is **very** low stakes. Releases and artifact bundles can be deleted with ease and without any lasting side-effects.
  - This option comes with maintenance effort that scales linearly with new features and there is a high chance implementing is overlooked for new features.
  - We introduce a `disabled` option instead that still is a convenient way of disabling the plugin without any continuous maintenance effort.
- `configFile`
  - Generally we would like to abstract away the fact that Sentry CLI is used under the hood.
  - The config file is very intransparent in combination with the plugin and generally not well documented. Let's remove this feature to lower maintenance burden.
- `injectReleasesMap` - Was used to support some micro frontends setups. This is not needed anymore with the introduction of debug IDs.
- `releaseInjectionTargets` - This was used to disable/enable release injection for a particular set of files. This is not really useful and cannot be used in all bundlers (esbuild). Additionally, for technical reasons we need to inject the release into every processed module anyhow (it will be deduped) so this option simply doesn't make a lot of sense anymore.

# Drawbacks

- Users will have to jump through a few hoops upgrading to the new Webpack plugin major just based on changing the options type. We have the theory that a good migration guide will solve most of this though.
- We are maintaining two systems of uploading source maps.

# Unresolved questions

- ~~Should the options we intend to remove really be removed or do we see use cases for them?~~
  - We remove `dryRun` for the reasons listed above
  - We remove `injectReleasesMap` for the reasons listed above
  - We remove `releaseInjectionTargets` for the reasons listed above
- ~~Should we remove environment variables and `.sentryclirc` as a means to configure the plugin?~~
  - We keep the env var configuration options because they aren't that high of a configuration effort, but we remove support for .sentryclirc
- ~~Should we deprecate the legacy source maps upload system entirely?~~
  - No. We think it still has its use cases so we keep it. Also self-hosted might still need this.
