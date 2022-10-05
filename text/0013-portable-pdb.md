- Start Date: 2022-09-22
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/13

# Summary

This RFC proposes new protocol fields to allow symbolicating .NET stack traces that use Portable PDBs as debug files.

# Motivation

To symbolicate a stack frame using a Portable PDB, we need the following data:

- IL Offset
- Method Index

Additionally, in order to fetch a Portable PDB from an external Symbol server following the [SSQP specification](https://github.com/dotnet/symstore/blob/main/docs/specs/SSQP_Key_Conventions.md#portable-pdb-signature), it needs to have:

- PDB File name
- PDB Id
- PDB Checksum

## Example Symbolication Flow

In Pseudo-Code:

```
for each frame in the stack trace:
    - determine the debug image needed (eg via `addr_mode`).
    - fetch the portable pdb file (using its metadata: id, checksum).
    - symbolicate the frame via the portable pdb metadata:
        - look up the `MethodDebugInformation` table row (via `function_index`).
        - decode the `Sequence Points Blob` state machine up until `il_offset`.
        - ^ the above sequence points yield a "start line" and "document".
    - ^ the above symbolication can be simplified using a dedicated lookup format:
        - the cache format uses (function_index, il_offset) tuples as lookup key.
        - the cache format yields (file [language, name], line) tuples as result.
```

# Proposed Protocol Extensions

## Stack Trace Interface

We propose to add the following to the [Stack Trace Interface Frame Attributes](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#frame-attributes):

**`addr_mode: "rel:$idx"`**, _existing_

This re-uses the existing `addr_mode` field using relative indexing.
The index points into `debug_meta.images` protocol field and references a debug file
that contains the debug data necessary to symbolicate this stack frame.

**`instruction_addr: HexValue`**, _existing_

This re-uses the existing `instruction_addr` field and represents the
function-relative IL Offset and corresponds to the .NET [`StackFrame.GetILOffset`](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.stackframe.getiloffset) method.

**`function_id: HexValue`**, _new_

A new field that represents a unique identifier for this function _inside the referenced image_.
This is derived from the .NET [`MemberInfo.MetadataToken`](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.memberinfo.metadatatoken).
This `MetadataToken` is encodes the metadata table in its most significant byte and the index into that table as the lower 3 bytes (24 bits).

### Open Questions:

- How does WASM symbolication work? How is the concept of a _function index_ being used in WASM?
- Should we introduce another `addr_mode` to call out "function-relative" addressing explicitly?
- Should the `function_id` be a `HexValue`, or completely free-form?
- Should we decode the `MetadataToken` on the client? (filter for only `MethodDef`, and mask away the table id?)

### Existing implementation

Currently the `SentryStackFrame` type of the `sentry-dotnet` SDK is currently using the
[`InstructionOffset` field](https://github.com/getsentry/sentry-dotnet/blob/57044ff52320c82cf1ca22cceee7125dfb9d1423/src/Sentry/SentryStackFrame.cs#L128-L135) to send the IL Offset.

## Debug Meta Interface

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

# Appendix

## NuGet Symbol Server lookups

Fetching a Portable PDB from an external Symbol server following the [SSQP specification](https://github.com/dotnet/symstore/blob/main/docs/specs/SSQP_Key_Conventions.md#portable-pdb-signature) needs to have:

- PDB File name
- PDB Id
- PDB Checksum

The NuGet symbol server (`https://symbols.nuget.org/download/symbols/{query}`) requires the PDB checksum to be provided via a `SymbolChecksum` header.
If that header is not provided, the server will always respond with a `403` error code. Otherwise, it uses a `404` code when the symbol is not found, or `302` redirect when it is found.
Interestingly though, the server only checks the _existence_ of the header, not that the given checksum actually matches the file.

<details>
<summary>**Examples:**</summary>

```
> curl https://symbols.nuget.org/download/symbols/timezoneconverter.pdb/4e2ca887825e46f3968f25b41ae1b5f3FFFFFFFF/timezoneconverter.pdb -i
HTTP/2 403

> curl https://symbols.nuget.org/download/symbols/timezoneconverter.pdb/4e2ca887825e46f3968f25b41ae1b5f3FFFFFFFF/timezoneconverter.pdb -H "SymbolChecksum: SHA256:87a82c4e5e82f386968f25b41ae1b5f3cc3f6d9e79cfb4464f8240400fc47dcd79" -i
HTTP/2 302

> curl https://symbols.nuget.org/download/symbols/timezoneconverter.pdb/4e2ca887825e46f3968f25b41ae1b5f3FFFFFFFF/timezoneconverter.pdb -H "SymbolChecksum: invalid" -i
HTTP/2 302

> curl https://symbols.nuget.org/download/symbols/timezoneconverter.pdb/4e2ca887825e46f3968f25b41ae1b5f3/timezoneconverter.pdb -H "SymbolChecksum: SHA256:87a82c4e5e82f386968f25b41ae1b5f3cc3f6d9e79cfb4464f8240400fc47dcd79" -i
HTTP/2 404
```

The details of this header do not seem to be publicly documented, but can be traced by looking through the `symstore` code:

- PdbChecksum: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.FileFormats/PE/PEStructures.cs#L375
- PE Key: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.SymbolStore/KeyGenerators/PEFileKeyGenerator.cs#L75
- Portable PDB Key: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.SymbolStore/KeyGenerators/PortablePDBFileKeyGenerator.cs#L85
- Key Format: https://github.com/dotnet/symstore/blob/aa44862e5028cb7595bbd474da1d63e8c24bf718/src/Microsoft.SymbolStore/KeyGenerators/KeyGenerator.cs#L166-L177
- `SymbolChecksum` Header: https://github.com/dotnet/symstore/blob/8a7c47ac74302510f839cc2361ca591b6f4df542/src/Microsoft.SymbolStore/SymbolStores/HttpSymbolStore.cs#L112

</details>

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
