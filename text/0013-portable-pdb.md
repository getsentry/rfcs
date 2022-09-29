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

## NuGet Symbol Server

The NuGet symbol server (`https://symbols.nuget.org/download/symbols/{query}`) requires the PDB checksum to be provided via a `SymbolChecksum` header.
If that header is not provided, the server will always respond with a `403` error code. Otherwise, it uses a `404` code when the symbol is not found.

Examples:

```
> curl https://symbols.nuget.org/download/symbols/microsoft.maui.pdb/10f7f174e11949f587c4d0b617742d31FFFFFFFF/microsoft.maui.pdb -i
HTTP/1.1 403 Forbidden

> curl https://symbols.nuget.org/download/symbols/microsoft.maui.pdb/10f7f174e11949f587c4d0b617742d31FFFFFFFF/microsoft.maui.pdb -H "SymbolChecksum: SHA256:74f1f71019e1f5197c4d0b617742d31b515f041c4f62a41bfc25ebb05a7fbff3" -i
HTTP/1.1 404 Not Found
```

The details of this header do not seem to be publicly documented, but can be traced by looking through the `symstore` code:

- PdbChecksum: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.FileFormats/PE/PEStructures.cs#L375
- PE Key: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.SymbolStore/KeyGenerators/PEFileKeyGenerator.cs#L75
- Portable PDB Key: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.SymbolStore/KeyGenerators/PortablePDBFileKeyGenerator.cs#L85
- Key Format: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.SymbolStore/KeyGenerators/KeyGenerator.cs#L166-L177
- `SymbolChecksum` Header: https://github.com/dotnet/symstore/blob/8a7c47ac74302510f839cc2361ca591b6f4df542/src/Microsoft.SymbolStore/SymbolStores/HttpSymbolStore.cs#L112

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
- A `debug_checksum: String` attribute that is parsed from the [PDB Checksum Debug Directory Entry](https://github.com/dotnet/runtime/blob/main/docs/design/specs/PE-COFF.md#pdb-checksum-debug-directory-entry-type-19). The format for this attribute should be `${algorithm}:${hex-bytes}`, for example `SHA256:xxxx`.

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
- What should we do for PE files that have multiple CodeView Records?
