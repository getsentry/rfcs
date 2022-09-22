- Start Date: 2022-09-22
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/13

# Summary

This RFC proposes new protocol fields to help with symbolicating .NET stack traces that use Portable PDBs internally for
symbolication.

# Motivation

To symbolicate a stack frame using a Portable PDB, we need the following data:

- IL Offset
- Method Index

Additionally, fetching a Portable PDB from an external Symbol server following the [SSQP specification](https://github.com/dotnet/symstore/blob/main/docs/specs/SSQP_Key_Conventions.md#portable-pdb-signature) needs to have:

- PDB File name
- PDB Id
- PDB Checksum

Currently the `SentryStackFrame` type of the `sentry-dotnet` SDK has an
[`instruction_offset` field](https://github.com/getsentry/sentry-dotnet/blob/57044ff52320c82cf1ca22cceee7125dfb9d1423/src/Sentry/SentryStackFrame.cs#L128-L135),
which is itself not yet documented on [`develop.sentry.dev`](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#frame-attributes).

# Background

The reason this decision or document is required. This section might not always exist.

# Options Considered

## Stack Trace Interface Extensions

We propose to add the following to the [Stack Trace Interface Frame Attributes](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#frame-attributes):

- `instruction_offset: Number`, as it is currently used by the `sentry-dotnet` SDK.
- `method_index: Number`.

The `instruction_offset` is defined as a JSON `Number`.
This instruction offset is fetched using the .NET [`StackFrame.GetILOffset`](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.stackframe.getiloffset)
method which returns a `Int32` type.

The `method_index` is a JSON `Number` for similar reasons.
The method index is derived from the .NET [`MemberInfo.MetadataToken`](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.memberinfo.metadatatoken)
field which also has type `Int32`. This `MetadataToken` is also using a format that encodes the actual method index as the lower 3 bytes (24 bits).

### Alternatives

WASM stack frames can also refer to the concept of a function index. An alternative would be to use a property named `function_index` for both.

## Debug Meta Interface Extensions

We propose to add the following to the [Debug Images Interface](https://develop.sentry.dev/sdk/event-payloads/debugmeta#debug-images):

- A new debug image type similar to the existing native image types.
- It should have a `type: "portable-pe"` attribute.
- A `debug_id: String` attribute with a `DebugId` that is parsed from the [CodeView Debug Directory Entry](https://github.com/dotnet/runtime/blob/main/docs/design/specs/PE-COFF.md#codeview-debug-directory-entry-type-2).
- A `debug_file: String` attribute with the corresponding PDB file path parsed from the same CodeView Entry.
- A `debug_checksum: String` attribute that is parsed from the [PDB Checksum Debug Directory Entry](https://github.com/dotnet/runtime/blob/main/docs/design/specs/PE-COFF.md#pdb-checksum-debug-directory-entry-type-19).

### Alternatives

- The proposed `"portable-pe"` spelling is modeled after the current `type: "pe"` usage.
- The current `type: "pe"` image is referencing a PDB file via its `debug_file` and `debug_id` attributes.
- An alternative spelling could be `"portable-pdb"`, `"portablepdb"` or `"ppdb"`.
- The `debug_checksum` attribute name has a similar reason. It is the checksum of the referenced debug file.

# Drawbacks

This increases the complexity and surface area of the Event Payload Interface. However all the proposed fields are
eventually necessary to offer symbolication for .NET stack traces based on debug data included in Portable PDB files.

# Implementation guidelines

The proposed fields need to be included and parsed in the following parts:

- The `sentry-dotnet` SDK.
- Relay
- Symbolicator

# Unresolved questions

- Bikeshed the `method_index` naming.
- Bikeshed the `"portable-pe"` naming.
- Do we have a link to documentation for why we need the checksum to do NuGet lookups?
