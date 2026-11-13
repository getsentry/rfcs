- Start Date: 2023-04-06
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

This specification proposes the keying / discovering of source maps via
the source hashes of the generated JavaScript files.  This is an alternative
lookup method to the proposed debug ID lookup.  It's there to support the
`CallSite.getScriptHash` browser API that Chrome and Edge already ship.

# Motivation

We want to make processing / SourceMap-ing of JavaScript stack traces more
reliable.  Our preferred solution for this involes unique Debug IDs but
supporting this requires bundler support as well.  On the other hand source
hashes for minified files are now possible to support in Chrome and Edge
without toolchain changes.

# Background

Looking up source maps and minified files by source hash is possible because Chrome and Edge support a [callsite script hash lookup](https://github.com/MicrosoftEdge/DevTools/blob/main/explainers/SourceHash/explainer.md).
For at least those browsers it would be possible to associate source maps
purely by that content hash in recent versions.

The hashes are available via the `Error.prepareStackTrace` API by invoking
the `getScriptHash` method on a call site object.  There is no fallback
possible for browsers not supporting script hashes.

The script hashes are documented to be SHA-256.

# Implementation

To support this the changes in our pipeline are limited.

## Protocol Changes

The `sourcemap` image type gains an additional key called `hashes` which
holds an object with hashes where each key corresponds to the name of a
hash algorithm and the value to the checksum in a format appropriate for
that hash.  Today only `sha256` is specified where the value is a SHA-256
hash in hexadecimal format:

```json
{
  "images": [
    {
      "type": "sourcemap",
      "code_file": "http://example.com/file.min.js",
      "hashes": {
        "sha256": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
      }
    }
  ]
}
```

## SDK Changes

On the SDK side we need to capture the content hashes of the referenced
frames and build up a map over time.  The easiest solution for this is to
maintain a growing list of hashes and to rely on `Error.prepareStackTrace`
to capture this:

```javascript
const scriptHashes = {};
const originalPrepareStackTrace = Error.prepareStackTrace;

// we use `Error.prepareStackTrace` exclusively for capturing the script hashes
// and we rely on `err.stack` parsing for the actual stack trace.  As documented
// getScriptHash() always returns a SHA-256 hash.
Error.prepareStackTrace = (err, callsites) => {
  for (var callsite of callsites) {
    if (!callsite.getScriptHash) {
      const filename = callsite.getFileName();
      if (!scriptHashes[filename]) {
        scriptHashes[filename] = callsite.getScriptHash();
      }
    }
  }
  return originalPrepareStackTrace ? originalPrepareStackTrace(err, callsites) : err.stack;
};
```

The SDK can then feed the script hashes into the sent image list as specified
above.

## Toolchain / Source Map Changes

For establishing the mapping from minified JavaScript to the source map, the
source map needs to gain a content hash entry.  As there is currently no
specification for how that mapping is supposed to be established, we would
reserve `x-sentry-file-hash-sha256` (header) and `x_sentry_fileHashSha256` (key):

```json
{
  "file": "foo.min.js",
  "x_sentry_fileHashSha256": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
}
```

Note that they use of the embedded key for now is likely discouraged for the
made up header as we do not plan on standardizing the file hashes.

To avoid re-calculating the SHA 256 hashes of the minified files constantly we
also want to add them to the manifest.  For this we could leverage the digest
header, with the small suboptimal situation that the HTTP digest spec uses
a base64 hash:

```json
{
  "files/_/_/foo.min.js": {
    "url": "~/foo.min.js",
    "type": "minified_source",
    "headers": {
      "digest": "sha-256=LXEWQrcmsEQBYnyp+6wy9chTD7GQPMTbAiWHF5IaSIE=",
      "sourcemap": "foo.min.map"
    }
  },
  "files/_/_/foo.min.map": {
    "url": "~/foo.min.map",
    "type": "sourcemap",
    "headers": {
      "x-sentry-file-hash-sha256": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
    }
  }
}
```

Upon uploading `sentry-cli` would establish the associations as today, but in addition
it would hash the file contents and add the necessary cross references into the
manifest.  In this case we can get away without any file rewriting and just associate
the hashes with the manifest instead.  Like with debug IDs we would require embedding
of sources into the source map.

## Sentry Mapping

On the Sentry side in addition to indexing by `debug_id` we add an additional database
index to record files indexed by it's SHA-256 content hash.  For potential future proofing
this table should allow definiting a different hash than SHA-256 in the future.

# Drawbacks

A drawback of this solution is that non-code changes in source files
will generate files with identical hashes.  Non-code changes for instance
can be whitespace or, more problematic, comments.  The risk of this happening
is assumed to be pretty low by the original spec authors.

This also relies on `Error.prepareStackTrace` being under Sentry's control
to capture the script hashes which might not always be possible.

# Future Direction

This proposal leverages existing developments in the source map ecosystem and some potential
improvements might be added at one point.

## Source File Hashes

There is [a pending proposal](https://github.com/source-map/source-map-rfc/issues/21) to add a
`sourcesHash` array to the source map to add SHA-256 hashes of source files to the source map
which could then be used to access sources.
