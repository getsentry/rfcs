- Start Date: 2023-06-22
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/106
- RFC Status: draft

# Summary

We aim to develop a method to support SourceMap processing, particularly access to files necessary for SourceMap processing. This method should accommodate more customer use-cases, be accurate, and be efficient to implement and scale.

# Motivation

We have discovered that the transition to non-indexed Artifact Bundles and the moving of SourceMap processing to Symbolicator have caused some customer Stack Traces to regress. We traced these regressions back to our inability to resolve the files needed for SourceMap processing through our current method of querying for these files.

## Customer Use-Cases

Customers may use our product in a multitude of ways. Although we may want to guide and encourage users to use the product in a specific manner, such as _uploading only a single bundle per release_, this may not be practical and it restricts the customers' freedom. Furthermore, it may not align with the direction we wish to pursue.

We spent some time analyzing all the edge cases that our system permits and identified those we feel like are important to support.

### Uploading disjoint Bundles for one release

Some customer projects comprise multiple independent technologies, often referred to as micro-frontends, frameworks, and various build steps. A single release may include parts built in React, Svelte, and Vue. This would consequently generate multiple separate bundles per release. The overlap between each bundle is minimal, such as polyfills, or there might be no overlap at all.

_We need to accommodate a scenario where a customer release is constructed from different parts, and multiple bundles constitute a single release._

### Overwriting existing files for one release

This is a use-case that we discourage, but may eventually even expand upon (see the point about uploading without a release).

Customers might hardcode a _release_ identifier somewhere in their codebase, which is very seldom updated or bumped. However, the customer's CI may regularly build new bundles, overwriting a previously existing bundle with a new build.

_We need to accommodate a scenario in which a single release has an arbitrarily large set of highly joint bundles, that is, bundles with many files in common. We need to address this by being clear about the semantics of choosing the file used for processing._

### Uploading the same bundle for multiple releases

This use-case involves customers repeatedly uploading the same bundle, identified by its `bundle_id`, for multiple releases.

An instance where this might occur is if a customer has a Continuous Integration (CI) system that uploads two bundles with each iteration: one that varies arbitrarily with each release, and another that remains unchanged. The unchanged bundle is uploaded with the same `bundle_id` for each release. This action triggers our de-duplication mechanism, resulting in a one-to-many relationship between a bundle and its associated releases.

_We need to accommodate a scenario where a bundle can be accessed by multiple different releases._

### Uploading without a release

It was suggested to allow bundle uploads without any kind of release. Some bundlers and build systems are generating deterministic and unique file names. And there is no necessity to create a _release_ to disambiguate files, as a changed file would get a new unique file name without collisions.

_We need to accommodate a scenario in which a bundle can be directly indexed by a UUID, also known as a _`debug_id`_. This indexing doesn't require a release because each file will contain metadata that assists the processing pipeline in identifying the bundle containing all the necessary files for unminifying the stack trace._

# Background

Sentry has had several iterations of how to handle uploaded files, each with its own pros, cons, and trade-offs.

## Release Files

This refers to the `ReleaseFile` model, which indexes individual files associated with a release.

- **Pro**: It indexes individual files, allowing for simple and fast lookup of individual files.
- **Con**: It requires a `Release` object as a foreign key.
- **Con**: Indexing each individual file is considered to be costly.

## Release Bundle / Artifact Index

Built on top of `ReleaseFile`s, this doesn't index each individual file, but rather maintains an index that is merged into.

- **Pro**: There is a single index for each release which references all included files.
- **Pro**: It doesn't index individual files and thus puts less pressure on the database.
- **Con**: Lookups require fetching and parsing the index file.
- **Con**: The index needs to be merged or updated when new bundles are uploaded.
- **Con**: The merged index will overwrite files with identical names, providing 'last writer wins' semantics for error symbolication. This could potentially cause issues if the most recent bundle is deleted.
- **Con**: For disjoint or unique file names, the index will grow very large.
- **Con**: It requires a `Release` object as a foreign key.
- **Con**: It can lead to merge conflicts with concurrent uploads touching the same index.

## Artifact Bundle

Constructed as the successor of Release Bundles, this has a distinct index for `DebugId`s and supports expiration through database partitioning.

- **Pro**: It does not require a `Release` object.
- **Pro**: It provides a method to expire and remove unused bundles.
- **Con**: It does not maintain an index and has limited support for more than N bundles per release.

# Supporting Data

In order to revise the indexing mechanism for bundles, we have gathered some data to support our proposals and guide technical decisions:

- We have observed customers uploading more than 200 bundles per release.
- We have also observed customers uploading up to 20,000 individual files per release.
- We have found that approximately 23% of release/distribution pairs have more than one bundle connected to them.
- We have seen customers associating a bundle with approximately 2000 releases.

# Assumptions

During the technical discussions for the new indexing system, we have made some assumptions:

- Most of the files inside of bundles are never used.
- The most recent uploads have more likelihood of being used by incoming errors.
- Most of the edge cases we're trying to solve can be reduced in magnitude by providing more education to our users.

# Options Considered

It is crucial that we support the use cases explained above, as the transition to artifact bundles and processing in Symbolicator has introduced regressions.

## Use existing Artifact Indexes

Early iterations of the `artifact-lookup` API utilized artifact indexes. However, this was later removed because the API endpoint was not designed to process large files. Downloading the artifact index to the API server and performing lookups in it was considered problematic.

The solution was to replace it by simply returning the newest `N` release bundles. This, however, resulted in extreme load on the database. Upon investigation, it was discovered that sorting these release bundles by date was two orders of magnitude slower than just returning `N` bundles unsorted. In this context, 'unsorted' refers to the primary key order, which effectively means returning the oldest `N` bundles.

Reintroducing support for artifact index lookups could temporarily resolve the regression in SourceMap processing. However, this relies on release bundles and artifact indices, which are currently being phased out.

- **Pros**: This would allow for the querying and accessing of the necessary files.
- **Cons**: It requires downloading or querying the index on API servers. It also relies on a deprecated technology that is in the process of being phased out.

## Using a replacement flat-file index

This would involve creating a replacement for artifact indexes based on the newer artifact bundles. Instead of a JSON index, a flat-file format has been proposed. However, the exact format is a relatively insignificant detail.

- **Pro**: This would allow querying or accessing the necessary files.
- **Pro**: This would address one major issue with artifact indexes: there would be no more need for a `Release` object.
- **Con**: This would require downloading or querying the index on API servers.
- **Con**: This would need to recreate or replicate most of the artifact-index logic, and it would inherit all of its cons:
  - Updating or merging the index upon uploads.
  - The index growing monotonically on disjoint uploads.
- **Con**: Automatic deletions (expired files) need to be considered when maintaining the index.

## Index individual files in the Database

This would create a database table or index similar to `ReleaseFile`, but with different constraints.

- **Pro**: Files are individually indexed.
- **Pro**: A database-based solution might be simpler than maintaining a separate index manually.
- **Pro**: No `Release` object is needed.
- **Pro**: There is no need to download or process any index on API servers.
- **Pro**: This would work well with auto-expiration or partitioning if implemented correctly.
- **Con**: There could be a high load on the database and its indices.
- **Con**: This might require a custom solution to better compress `release` and `url`, possibly by using some kind of interning.
- **Con**: The number of writes in the table could significantly exceed the number of reads, leading to substantial growth in its size and indices.

## Hybrid Bundles / Individual files

The idea was proposed to index individual files only if the number of uploaded bundles per release surpasses a certain threshold `N`.

This capitalizes on the fact that the downstream consumer, Symbolicator, will utilize the `manifest.json` index in the returned `N` bundles, and there may not be a need for an additional server-side index in that scenario.

- **Mixed**: This has all the advantages and disadvantages of the above-mentioned _individual files_, but with a smaller number of indexed files.
- **Pro**: There is no additional overhead for the one-bundle-per-release use case.
- **Pro**: The consumer side, Symbolicator, already possesses all the logic for dealing with `manifest.json` indices.
- **Con**: It requires jobs and logic to backfill a per-file index if the threshold is exceeded.

## Store individual files

Instead of merely indexing files individually while still referring to the bundle they are included in, it might be feasible to store the files themselves individually, potentially deduplicated by a content hash.

- **Pro**: This solves the file decompression performance issue of Symbolicator.
- **Pro**: We assume that most files within bundles are unused.
- **Pro**: We assume that many files will not change across bundles (polyfills, dependencies, etc).
- **Con**: We need a more efficient method to store numerous small files.
- **Mixed**: We have insufficient data to validate assumptions about the usage of files per bundle, duplicated files across bundles, and the complexity/cost of storing individual files, etc.

# Implementation history

Two separate approaches were developed and considered in this time.

## Database Indexing

This approach is described above as _Index individual files in the Database_.

The solution involved creating a table called `ArtifactBundleIndex`, which would contain a `url` and an `artifact_bundle_id` associated with that URL.

This table would be populated upon upload, and once the threshold was reached, the system would begin indexing. In our production case, the threshold was set to `1`, indicating that the system would start indexing as soon as a second bundle was uploaded to the same release. The contents of both bundles would then be added to the table.

We tried several implementations of this indexing, initially with a de-duplication mechanism both in-memory and in-database. This allowed us to keep the table size relatively small, especially in cases of highly joint bundles. However, this approach led to problems when users deleted bundles that were last indexed, and we had to start re-indexing older bundles. This process presented both technical complexity and infrastructure load.

After some testing, we decided to remove the de-duplication feature and simply insert all the files each time. This change resulted in a significant increase in the table size. In approximately one week, the table gained 40 million rows, which raised concerns about its size and lookup scalability, even though auto-expiration could potentially keep this number steady.

On the lookup end, the system would use a release/dist to first identify the bound bundle ids, and then search for the specific url for each bundle, using last writer wins semantics for resolving possible url conflicts. This lookup mechanism involves several joins, and depending on the cardinality of the associations of the release/dist pair, performance could vary significantly.

The limiting factor here seemed to be the size and the query performance of the main index.

## Improved Flat File Indexing

This approach is similar to the _Using a replacement flat-file index_ listed above, but tries to improve upon some of the shortcomings.

- The index is not being queried on the API servers, but it is being processed directly in Symbolicator.
- The index format itself is being adapted to support bundle removals.

The concept is to index each uploaded bundle based on the triple `project_id, release, dist`, where `release` and `dist` are considered `""` for debug IDs upload. This is done under the presumption that this is the triple in an incoming error, which can help the system determine where to potentially look for SourceMaps.

The indexes stored for each triple would be formatted as `.json` files. As a result, the database will scale in relation to the number of bundles uploaded to different projects and releases. The schema of the database will contain the triple and a link to the `.json` file.

The file could have a format like, though the format is not finalized yet:

```json
{
  "bundles": [
    { "bundle_id": "bundle_1" },
    { "bundle_id": "bundle_2" },
    { "bundle_id": "bundle_3" }
  ],
  "files_by_url": {
    "~/url/in/bundle": [1, 0]
  },
  "files_by_debug_id": {
    "5b65abfb-2338-4f0b-b3b9-64c8f734d43f": [2]
  }
}
```

In practice, we will store debug IDs and URL indexes separately. Specifically, all debug IDs will be stored in the index identified by the triple `project_id, "", ""`, while the URLs will be identified by the standard triple `project_id, release, dist`.
The rationale for this division is to better allow `DebugId`-based lookups for events that are lacking a proper `release`.

The creation of this index will be performed _asynchronously_ after a bundle has been uploaded. It will be protected against concurrent access through a _retry mechanism_ (there may be a need to better define concurrency semantics if we find that retries during high contention lead to task starvation). The indexing operation to be implemented will be both _idempotent_ and _commutative_, as we will establish a total order of bundles by timestamp and ID. This facilitates a simpler design for the asynchronous execution of indexing tasks.

The most recent _per-release_ index containing indexed `URL`s, and the most recent _per-project_ containing `DebugId`s will be sent
directly to Symbolicator with each event to be processed.
This will improve caching on the Symbolicator side, and avoid frequent round-trips to the `artifact-lookup` API.

Symbolicator will then use the downloaded indexes to perform lookups. Since each index represents a 1:1 relationship with the files bound to the triple `project_id, release, dist`, the system will easily handle cases where a release has multiple bundles or a bundle has multiple releases. In the case of a bundle with multiple releases, the system will create duplicate indexes. The triple identifier will differ, but since the indexes are within a single file, we are not overly concerned about scalability. The primary goal of indexing is to quickly bisect the locations to look for when resolving a specific stack trace.

Deletions will be more complex with this system, as we don't have any consistency guarantees offered by the database. Currently, our idea is to perform a repair on read, but this is something we will investigate once the scalability of the indexing has been evaluated with a write-only implementation.

Such a system also has an additional benefit. In the index, we will maintain an ordered list of bundles that had that specific URL.
This means that the index is consistent even when considering bundle deletions.
