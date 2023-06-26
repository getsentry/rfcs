- Start Date: 2023-06-22
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/106
- RFC Status: draft

# Summary

We want to come up with a way to support SourceMap processing or in particular access to files needed for SourceMap
processing that supports more customer use-cases, is correct, and is efficient to implement and scale.

# Motivation

We have found out that the move to non-indexed Artifact Bundles, and moving SourceMap processing to Symbolicator has
regressed some customer Stack Traces. We tracked those regressions down to not being able to resolve the files
needed for SourceMap processing via the current way we query for those files.

## Customer Use-Cases

Customers may be using our product in a wide variety of ways. While we might want to educate and push users to use
one particular way of using the product, which in this case may be _only upload a single bundle per release_, this
might not be feasible, and does not allow great freedom for customers. It is also not compatible with a direction
we might want to move in.

### Uploading disjoint Bundles for one release

Some customer projects consist of multiple independent technologies (buzzword: micro-frontend), frameworks and thus
build steps. One _release_ may have parts built in React, in Svelte _and_ Vue. These would thus generate multiple
_disjoint_ bundles per release.
Overlap between each bundle is minimal (for example polyfills) or there is no overlap at all.

We need to support a use-case where a customer _release_ is built from different parts, and multiple bundles make up
a single release.

### Overwriting existing files for one release

This is a use-case which we discourage on the one hand, but might eventually even extend (see next point).

Customers may hardcode a _release_ identifier somewhere in their codebase which is very infrequently updated/bumped.
However the customers CI may regularly build new bundles, and overwrite a previously existing bundle with a new build.

The assumption here is that such uploads have a high overlap, with a high number of identical files.

### Uploading without a release

It was suggested to allow bundle uploads without any kind of release.
Some bundlers and build systems are generating deterministic and unique file names. And there is no necessity to create
a _release_ to disambiguate files, as a changed file would get a new unique file name without collisions.

# Background

Sentry had a couple of iterations of how to deal with uploaded files, with different pros-cons and tradeoffs.

## Release Files

This refers to the `ReleaseFile` model. It is indexing individual files associated with a release.

- **pro**: Indexes individual files, and thus allows simple and fast lookup of individual files.
- **con**: Needs a `Release` object as foreign key.
- **con**: Indexing each individual file is believed to be expensive.

## Release Bundle / Artifact Index

Built on top of `ReleaseFile`s, this does not index each individual file, but rather maintains an index that is merged to.

- **pro**: There is a single index per release which references all included files.
- **pro**: Does not index individual files and thus puts less pressure on the DB.
- **con**: Lookups need to fetch and parse the index file.
- **con**: The index needs to be merged/updated when uploading new bundles.
- **con**: For disjoint / unique file names, the index will grow very large.
- **con**: Needs a `Release` object as foreign key.
- **con**: Can lead to "merge conflicts" with concurrent uploads touching the same index.

## Artifact Bundle

Built as the successor of Release Bundles, this has a separate index for `DebugId`s and supports expiration via database
partitioning.

- **pro**: Does not require a `Release` object.
- **pro**: Has a way to expire and remove unused bundles.
- **con**: Does not maintain an index and has limited support more than N bundles per release.

# Supporting Data

- We have seen customers that upload more than 200+ Bundles per release.
- We have also seen customers that upload up to 20.000 individual files per release.

One assumption that we have is that most of the files inside of bundles are never used.

- A big part of the SourceMap processing time spent in Symbolicator is related to accessing / decompressing individual
  files from bundles.

# Options Considered

It is crucial that we support the use-cases explained above, as the move to artifact bundles and processing in Symbolicator
has introduced regressions.

## Use existing Artifact Indexes

Early iterations of the `artifact-lookup` API made use of artifact indexes. This was later removed as the API endpoint
was not supposed to process large files. Downloading the artifact index to the API server, and performing lookups in
it was deemed to cause problems.

It was then replaced by just returning the _newest_ `N` release bundles. This has caused extreme load on the Database.
After investigation, we found out that sorting these release bundles by date was two orders of magnitude slower than
just returning `N` bundles unsorted. _Unsorted_ in this case would mean primary key order, which effective means
returning the _oldest_ `N` bundles.

Adding back support for artifact index lookups would temporarily solve the regression in SourceMap processing. However
this is based on release bundles and artifact indices which are in the process of being phased out.

- **pro**: Would allow querying / accessing the needed files.
- **con**: Requires downloading / querying the index on API servers.
- **con**: Based on deprecated technology that is in the process of being phased out.

## Using a replacement flat-file index

This would involve creating a replacement for artifact indexes based on the newer artifact bundles. Instead of a `JSON`
index, a flat-file format was proposed. However the exact format is rather an insignificant detail.

- **pro**: Would allow querying / accessing the needed files.
- **pro**: Would solve one pain-point of artifact indexes: No more `Release` object needed.
- **con**: Requires downloading / querying the index on API servers.
- **con**: Needs to re-create / replicate most of the artifact-index logic, and inherits all of its cons:
  - updating / merging the index on uploads
  - the index growing monotonically on disjoint uploads
- **con**: Automatic deletions (expired files) need to be taken into account when maintaining index.

## Index individual files in the Database

This would create a similar database table / index to `ReleaseFile`, but with different constraints.

- **pro**: Files individually indexed.
- **pro**: A database-based solution might be simpler than maintaining a separate index manually.
- **pro**: No `Release` object needed.
- **pro**: No need to download / process any index on API servers.
- **pro**: Would work well with auto-expiration / partitioning if implemented correctly.
- **con**: High load on Database and its indices.
- **con**: Might require a custom solution to better compress `release` and `url`, possibly by using some kind of interning.

The table could look something the following:

- org / project
- (optional) release + dist
- url
- date_added / touched
- artifact bundle id

## Hybrid Bundles / Individual files

The idea was brought up to only index individual files if the number of uploaded bundles per release exceeds a certain
threshold `N`.

This takes advantage of the fact that the downstream consumer (Symbolicator) will use the `manifest.json` index in
the returned `N` bundles, and no additional server-side index might be needed in that case.

- **mixed**: All the pros/cons of the above _individual files_, just with a lower number of indexed files.
- **pro**: No additional overhead for the one-bundle-per-release use-case.
- **pro**: The consumer (Symbolicator) side already has all the logic for dealing with `manifest.json` indices.
- **con**: Needs jobs and logic to backfill a per-file index if the threshold was exceeded.

## _Store_ individual files

Instead of just _indexing_ files individually and still referring to the bundle they are included in, it might be possible
to _store_ files themselves individually, possibly deduplicated by a content hash.

- **pro**: Solves file decompression performance of Symbolicator.
- **pro**: We _assume_ that most files inside of bundles are unused.
- **pro**: We _assume_ that a lot of files will not change across bundles (polyfills, dependencies, etc).
- **con**: We need a better way to store many small files.
- **mixed**: We have too little data validate assumptions about used files per bundle, duplicated files across bundles,
  complexity / cost of storing individual files, etc.

# Drawbacks

No matter which solution we choose, it comes with a significant implementation effort and potential cost in terms of
infrastructure for maintaining an index, either in a database or manually.

We also have to consider automatic expiration of unused files, bundles, indexes and releases.
