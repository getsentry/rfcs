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

We propose to use/add the following fields to the
[Stack Trace Interface Frame Attributes](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#frame-attributes)
that should be used to facilitate symbolication using Portable PDB files:

**`addr_mode: "rel:$idx"`**, _existing_, _required_

This re-uses the existing `addr_mode` field using relative indexing.
The index points into `debug_meta.images` protocol field and references a debug file
that contains the debug data necessary to symbolicate this stack frame.

**`instruction_addr: HexValue`**, _existing_, _required_

This re-uses the existing `instruction_addr` field and represents the
function-relative IL Offset and corresponds to the .NET [`StackFrame.GetILOffset`](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.stackframe.getiloffset) method.

**`function_id: HexValue`**, _new_, _required_

A new field that represents a unique identifier for this function _inside the referenced image_.
This is derived from the .NET [`MemberInfo.MetadataToken`](https://learn.microsoft.com/en-us/dotnet/api/system.reflection.memberinfo.metadatatoken).
This `MetadataToken` is encodes the metadata table in its most significant byte and the index into that table as the lower 3 bytes (24 bits).
The SDK should filter specifically for `MethodDef` tokens and only transmit the lower 3 bytes when it in fact is a `MethodDef` token.

### Open Questions:

- ~~How does WASM symbolication work? How is the concept of a _function index_ being used in WASM?~~
  - WASM has the context of `function_index`, though it is not useful for symbolication as the module relative instruction offset is enough to do DWARF lookups.
  - The WASM `function_index` would be useful to look up the function metadata in WASM format, which we do not use.
- ~~Should the `function_id` be a `HexValue`, or completely free-form?~~
  - We will restrict this to a `HexValue ` initially. We are free to relax that to `String` in the future if needed.
- ~~Should we decode the `MetadataToken` on the client? (filter for only `MethodDef`, and mask away the table id?)~~
  - Yes please. Since this is the functions ID, it should validate/decode that in the SDK.
- Should we introduce another `addr_mode` to call out "function-relative" addressing explicitly?

### Existing implementation

Currently the `SentryStackFrame` type of the `sentry-dotnet` SDK is currently using the
[`InstructionOffset` field](https://github.com/getsentry/sentry-dotnet/blob/57044ff52320c82cf1ca22cceee7125dfb9d1423/src/Sentry/SentryStackFrame.cs#L128-L135) to send the IL Offset.

## Debug Meta Interface

We propose to use/add the following fields to the
[Debug Images Interface](https://develop.sentry.dev/sdk/event-payloads/debugmeta#debug-images)
that should be used to facilitate symbolication using Portable PDB files:

**`type: "pe_dotnet"`**, _existing_ (new variant), _required_

A new _type_ of debug image that signifies a PE file that contains .NET IL and metadata, and has a .NET specific CodeView record (more below).

**`debug_id: DebugId`**, _existing_, _required_

The `DebugId` of the debug image. This is constructed from a CodeView record similar to the `debug_id` of a normal `"pe"` image,
with a small special case, more below.

**`debug_file: String`**, _existing_, _optional_

This is the filename (or full path) of the corresponding PDB debug file. This is optional when only relying on the sentry internal symbol
source, but is required when fetching symbols from external symbol servers.

**`debug_checksum: String`**, _new_, _optional_

This is the checksum of PDB debug file. The format should be `"${algorithm}:${hex-bytes}"`, for example `SHA256:0011aabb...`.
The algorithm and bytes are extracted from the
[PDB Checksum Debug Directory Entry](https://github.com/dotnet/runtime/blob/main/docs/design/specs/PE-COFF.md#pdb-checksum-debug-directory-entry-type-19).

**`code_file: String`**, _existing_, _optional_

The filename (or full path) of the executable (`.exe`, `.dll`) file.

**`code_id: String`**, _existing_, _optional_

An identifier for the executable derived from the `Timestamp` and `SizeOfImage` header values.
This value along with `code_file` can be used to look up the executable file on an external symbol server, however that functionality is not currently
used for .NET symbolication.

### Handling CodeView records

The `debug_id` value is extracted from a [CodeView Debug Directory Entry](https://github.com/dotnet/runtime/blob/main/docs/design/specs/PE-COFF.md#codeview-debug-directory-entry-type-2),
similar to the one that is already used for native symbolication.

The difference is in a special "Version Minor" value that says that the `Age` field of the CodeView record should not be used, and instead the last 4 bytes
of the 20 byte `debug_id` are taken from the `TimeDateStamp` field.

Looking up such files on an external symbol server is also different, as the last 4 bytes are masked by `FF`, and the server may require an additional
`SymbolChecksum` header.

Some files (such as the Windows version of `System.Reflection.Metadata.dll`) may have more than one CodeView record.
In the observed case, one record points to the Portable PDB file corresponding to the .NET portion of the file.
The other record points to a native PDB file which presumably contains native Debug Info related to a "Native Image".
That native PDB does not seem to be usable by our tools however. Trying to create a SymCache from it results in an empty cache.

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
PE: https://msdl.microsoft.com/download/symbols/system.reflection.metadata.dll/858257FE114000/system.reflection.metadata.dll
Portable PDB: https://msdl.microsoft.com/download/symbols/system.reflection.metadata.pdb/3183ede4e1eb4d0ca6a02937d1f72463FFFFFFFF/system.reflection.metadata.pdb
NI PDB: https://msdl.microsoft.com/download/symbols/system.reflection.metadata.ni.pdb/d9f6618dd9346123c7c2459c9645cf841/system.reflection.metadata.ni.pdb

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

Another example that rather fetches files from the Microsoft Symbol Server:

- https://msdl.microsoft.com/download/symbols/system.reflection.metadata.dll/858257FE114000/system.reflection.metadata.dll
- https://msdl.microsoft.com/download/symbols/system.reflection.metadata.pdb/3183ede4e1eb4d0ca6a02937d1f72463FFFFFFFF/system.reflection.metadata.pdb
- https://msdl.microsoft.com/download/symbols/system.reflection.metadata.ni.pdb/d9f6618dd9346123c7c2459c9645cf841/system.reflection.metadata.ni.pdb

</details>

# Drawbacks

This slightly increases the complexity and surface area of the Event Payload Interface. However all the proposed fields are
necessary to offer symbolication for .NET stack traces based on debug data included in Portable PDB files.

# Implementation

Support for these fields, or Portable PDB symbolication in general is being implemented in these parts of the pipeline:

- The `sentry-dotnet` SDK, something along these lines: https://github.com/getsentry/sentry-dotnet/pull/1785
- Relay: https://github.com/getsentry/relay/pull/1518
- Sentry-CLI: https://github.com/getsentry/sentry-cli/pull/1345
- Sentry: https://github.com/getsentry/sentry/pull/39610
- Symbolic: https://github.com/getsentry/symbolic/pull/696
- Symbolicator: https://github.com/getsentry/symbolicator/pull/883

# Unresolved questions

- ~~What should we do for PE files that have multiple CodeView Records?~~
  - Those come from Native Image (ngen) DLLs.
  - One of those records refers to a `.ni.pdb` in MSF PDB format.
  - The other one refers to a Portable PDB.
  - The MSF PDB does not seem to be usable via our native SymCache conversion.
  - The commendation is thus to simply filter for the `DebugDirectoryEntry.IsPortableCodeView` property.
