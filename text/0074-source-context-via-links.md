- Start Date: 2023-02-15
- RFC Type: feature
- RFC PR: <https://github.com/getsentry/rfcs/pull/74>
- RFC Status: draft

# Summary

In situations where a source code link and a line number is available for a frame, present the link in the UI and show
the source code surrounding the line.

# Motivation

The source context is currently composed of three [`Frame` attributes](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#frame-attributes):

- `context_line` - Source code in filename at `lineno`.
- `pre_context` - A list of source code lines before `context_line` (in order) – usually [`lineno - 5:lineno`].
- `post_context` - A list of source code lines after `context_line` (in order) – usually [`lineno + 1:lineno + 5`].

Showing a source code context and a link to it (e.g. to GitHub) currently works only if the source code itself is
available during symbolication, thus the attributes are filled in at that time, or if they were already sent with the event by the SDK.

There are, however, situations where we do have a URL where the source code resides, but not the contents (without downloading it), for example:

- Portable-PDB source-link (.NET, see [this `symbolic` issue](https://github.com/getsentry/symbolic/issues/735))
- Debuginfod servers (we don’t support these yet)
- SourceMaps (either embedded sourcesContent or using individual source files)
- via a repository integration in combination with associated commit

In these cases, the actual source code is not necessary to do symbolication (as opposed to source maps and other types of obfuscated source containers) but it is useful for end-user
when evaluating the issue in the UI.

## Related GH feature requests

- [Extend stack-trace linking UI](https://github.com/getsentry/sentry/issues/35608)
- [Support stack trace linking when stack frames do not contain line context.](https://github.com/getsentry/sentry/issues/44015)

# Options Considered

## A | Download the source code during symbolication

One option is to download the source code from its link at the time the event is symbolicated, filling the context-related
`Frame` attributes for each stacktrace frame, while the event is being processed.

### Pros

- Reuses existing fields (changes only needed in the `Symbolicator`).
- Sources surrounding the frame line are then stored in the database, enabling [search-by-code](https://github.com/getsentry/sentry/issues/3755).
- May be possible to do server-side authentication (based on project/org configuration) - this would complicate the solution & caching though, as opposed to only supporting publicly available sources.

### Cons

- Downloads all frame sources even though the event/frame may never be viewed by a user.
- Adds potentially tens of requests for each symbolicated event that has a source link - as many as there are in the stack trace.

## B | Add a source-link to the `Frame` and let the UI handle it

Another option is to extend `Frame` attributes with a new field, e.g. `source_link` and let UI download the source code
as needed or just display the link.

### Pros

- No overhead on the server for loading sources in situations where the event/frame wouldn't be shown.
- Requests to fetch the source code, if any, are made by the user browser, thus avoiding potential quota limits.

### Cons

- Sources not available in the database -> can't [search-by-code](https://github.com/getsentry/sentry/issues/3755).
- Accessing private sources may be problematic. We could still show the source link, though.

# Unresolved questions

- Neither approach is a clear winner, any suggestions?
