- Start Date: 2026-02-27
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/152
- RFC Status: draft
- RFC Author: @supervacuus
- RFC Approver: 

# Summary

This RFC proposes a mechanism for SDKs to mark stack frames as already symbolicated on the client side, so that the backend (processing/symbolicator) can skip symbolication for those frames. This avoids wasted symbolicator resources, prevents false-positive "missing debug symbols" errors in the UI, and gives SDKs a first-class way to indicate that a frame's symbol and associated module/image should be treated at face value and not considered missing.

# Motivation

When an SDK symbolicates a native stack frame on the client (e.g., because the debug symbols are available locally but not on the server), the backend currently has no way to know this. Processing and symbolicator still attempt to symbolicate every native frame. This leads to two concrete problems:

1. **Wasted resources:** Symbolicator attempts symbolication for frames that are already fully resolved, consuming resources unnecessarily. This might be an operational non-issue, and I only add it for completeness.

2. **Incorrect and misleading UI errors:** When symbolicator cannot find debug symbols for an already-symbolicated frame, it sets `symbolicator_status: "missing"` and surfaces an error telling the user to upload the debug symbols for the associated module. In most cases, this is **by design**: users typically do not want to add symbol tables or debug information to their deployment artifacts and usually release a stripped artifact and separately upload debug information once per release to Sentry. In such a setup, the client cannot symbolicate anyway, and a `missing` status is sensible feedback. However, there are situations where the opposite is true: the symbols exist only on the client device (e.g., system libraries on end-user devices), and there is no realistic chance of collecting them upfront. The user sees a broken-looking stack trace and a confusing call-to-action that doesn't apply. 

This problem is not theoretical. It already manifests today in at least two concrete scenarios:

- **Tombstone / native crash reporting**: Native SDKs that symbolicate system library frames on-device before sending the event. The backend cannot distinguish these from unsymbolicated frames and flags them as broken since it cannot find any symbol information in its stores. On Android in particular, we usually have both situations: native user libraries will be packaged stripped and `Symbolicator` must resolve associated frames (i.e., the UI warning is sensible if symbol/debug-info is missing), but system and framework libraries usually will be symbolicated on-device and `Symbolicator` won't have access to data to further enrich the stack frame. In that case, the UI error is misleading and inactionable to the user.
- **.NET SDK**: The .NET SDK resolves function names, file paths, and line numbers locally using portable PDB metadata. When these frames arrive at the backend, symbolicator still attempts to process them. Because the user hasn't uploaded PDB files to Sentry (the SDK already handled this), every frame returns `symbolicator_status: "missing"` and the UI shows a misleading symbolication error banner. This is tracked in [getsentry/sentry#97054](https://github.com/getsentry/sentry/issues/97054).

![Screenshot symbols rendered as missing although symbolicate](./0152-missing-symbols-screenshot.png)
![Screenshot of images missing although no action required](./0152-missing-modules-screenshot.png)

# Background

## How `symbolicator_status` works today

After symbolicator processes an event, each native frame receives a `symbolicator_status` stored in `frame.data`. The status values include:

- `"symbolicated"`: symbolicator successfully resolved the frame.
- `"missing"`: symbolicator could not find the required debug symbols.
- `"unknown"`: symbolicator could not process the frame for other reasons.

This status is set exclusively by the backend during processing. It currently cannot be influenced by SDKs.

Relevant code: [`sentry/lang/native/processing.py`](https://github.com/getsentry/sentry/blob/422487ea4acad23710cd1fe5392a5b684e09c2e4/src/sentry/lang/native/processing.py#L129-L131)

## Frame handling in processing

The native frame handler in `processing.py` iterates over all frames and unconditionally sends them through symbolicator. There is already a code path that exits frame handling early when certain conditions are met:

[`processing.py` L378-L379](https://github.com/getsentry/sentry/blob/422487ea4acad23710cd1fe5392a5b684e09c2e4/src/sentry/lang/native/processing.py#L378-L379): this early-exit is what we want to trigger for SDK-symbolicated frames, accepting them at face value without attempting further symbolication.

## Existing workarounds

### Hard-coded exceptions in the monolith

A `FIXME` in `processing.py` adds a special case for .NET, which never had debug images before but can send fully symbolicated events from the SDK. This was added to prevent false symbolication errors when .NET started sending debug images. The `FIXME` tag indicates this was not considered the right long-term approach.

Notably, the .NET SDK has since evolved to **send debug images** (with `type: "pe_dotnet"`), because this enables symbolicator to fetch source context via the Microsoft symbol server and SourceLink. Once debug images are present, however, the FIXME's original precondition ("no debug images -> skip") no longer triggers. Symbolicator now sees debug images, attempts to resolve symbols for *all* frames, including user-code frames that the SDK already symbolicated locally, and marks them as `"missing"` because the PDB was never uploaded. This is exactly the scenario reported in [getsentry/sentry#97054](https://github.com/getsentry/sentry/issues/97054): the FIXME handled the old .NET world correctly, but the SDK outgrew the workaround.

Relevant code: [`processing.py` L149-L158](https://github.com/getsentry/sentry/blob/422487ea4acad23710cd1fe5392a5b684e09c2e4/src/sentry/lang/native/processing.py#L149-L158)

See also: [getsentry/sentry#46955](https://github.com/getsentry/sentry/issues/46955): "Remove error banner for non-app symbols"

### Third-party library detection

There is a `is_known_third_party()` check that suppresses missing-symbol errors for recognized system libraries (e.g., iOS system frameworks). This is a denylist approach and does not scale to arbitrary platforms or deployments.

### Passing `symbolicator_status` from the SDK

In theory, an SDK could set `symbolicator_status` directly on the frame's `data` dict. Since `data` is part of the stacktrace `Frame` and falls into relay's untyped "other" catch-all ([`relay-event-schema/.../stacktrace.rs` L200-202](https://github.com/getsentry/relay/blob/55c59cf75d3c35bbbb66df14072d147eca056bd7/relay-event-schema/src/protocol/stacktrace.rs#L200-L202)), it would technically be forwarded. However, using untyped catch-all fields for regular SDK usage is explicitly frowned upon and for good reason.

## Scope

This RFC focuses on the **stack trace display and symbolication** aspect of the problem. Specifically: how can an SDK tell the backend "this frame is already symbolicated, don't try again"? It is also assumed that any solution to misattributing "missing symbols" should also rectify attributing associated modules in the debug-meta as missing. The scope intentionally does **not** cover source context fetching: even if a frame is marked as symbolicated, the backend may still want to fetch source files for inline source context display.

## Affected components

This is a cross-cutting concern that touches:

- **SDKs**: All native code handling SDKs (sentry-native, sentry-java/Android NDK, sentry-dotnet, (maybe sentry-cocoa), and downstream dependants + any future SDK performing client-side native symbolication).
- **Relay / ingestion**: The frame schema needs to either gain a new typed field or explicitly allow SDKs to set existing fields.
- **Processing (monolith)**: `sentry/lang/native/processing.py` needs to honor the new signal and skip symbolication for marked frames.
- **Symbolicator**: May need awareness of the flag if processing delegates the decision.
- **UI**: Should stop showing misleading "missing symbols" errors for frames that are intentionally client-symbolicated.

# Options Considered

## Option A: New typed frame attribute: `symbolicated` (currently preferred)

Add a new boolean field `symbolicated` (or similar, can be renamed on the server to `client_symbolicated`, analog to `in_app` -> `client_in_app`) to the frame schema in relay. When set to `true`, processing skips symbolication for that frame and treats it as already resolved. We might also make this an enum to give the client finer-grained control over the level of frame enrichment, but I currently see no immediate scenario.

**Changes required:**

- **relay-event-schema**: Add `symbolicated: bool` to `Frame` (typed, not catch-all).
- **SDKs**: Set `symbolicated: true` on frames the SDK has symbolicated.
- **processing.py**: Check `symbolicated` early in frame handling; if `true`, set `symbolicator_status` to `"symbolicated"` (or a new value like `"client_symbolicated"`) and skip further processing.
- **UI**: No changes needed if we reuse `"symbolicated"` status. If we introduce a new status value, the UI may want to render it distinctly. But we might be able to remove special cases.

### Pros

- Clean, explicit, typed, and no abuse of catch-all fields.
- Can be adopted incrementally by different SDKs.
- Clear contract between SDK and backend.
- Minimal risk of side effects on existing flows.
- Allows removal of special-case(s) in UI. 

### Cons

- Requires a relay schema change.
- New attribute that all parts of the pipeline need to be aware of.

## Option B: Infer from existing frame data (heuristic)

If a frame already has a resolved `function` name (and optionally `filename`, `lineno`) when it arrives from the SDK, processing could skip symbolication. The logic would be: "if the raw frame has a symbol name, don't attempt to re-symbolicate."

**Changes required:**

- **processing.py**: Add a check early in frame handling: if `function` is already present and non-empty, skip symbolication and mark as symbolicated.

### Pros

- No SDK changes required. Works immediately with existing data.
- No schema changes in relay.
- Simplest possible implementation.

### Cons

- Fragile heuristic: a frame might have a `function` from partial client symbolication but still benefit from server-side enrichment (source context, inline frames, demangling).
- Risk of breaking existing workflows where the backend intentionally re-symbolicates client-provided function names (e.g., to add source context or correct demangling).
- Doesn't distinguish between "SDK intentionally symbolicated this" and "SDK sent a partial/best-guess symbol name."
- The .NET `FIXME` is a concrete example of this approach's fragility: a server-side heuristic that worked initially but silently broke when the SDK evolved to send debug images (see Background). Any new heuristic is susceptible to the same drift.

## Option C: Allow SDKs to set `symbolicator_status` directly

Let SDKs explicitly set `symbolicator_status: "symbolicated"` (or a new value) in `frame.data`. Relay would need to explicitly allow this field from SDKs rather than treating it as backend-only.

**Testing has shown that SDK-set values in `frame.data.symbolicator_status` are discarded or overwritten by the backend during processing.** This means Option C is not viable without changes to either relay (to stop stripping/ignoring the field) or processing (to check for an existing value before overwriting).

**Changes required (if pursued despite the above):**

- **relay-event-schema**: Make `symbolicator_status` a recognized field that SDKs may set, and ensure it is not stripped during ingestion.
- **processing.py**: Check if `symbolicator_status` is already set before overwriting it with symbolicator's result.
- **SDKs**: Set `data.symbolicator_status` on symbolicated frames.

### Pros

- Reuses existing infrastructure: no new field needed.
- Processing already checks this field; minimal backend changes.

### Cons

- Blurs the line between SDK-set and backend-set status, making debugging harder.
- Using catch-all fields for regular SDK usage is not desirable.
- If the field is later moved or renamed during a schema cleanup, SDK behavior breaks silently.
- Tested and confirmed not to work today: SDK-set values are discarded/overwritten in the backend.

# Unresolved Questions

- How are the associated debug-meta images being resolved? If a frame is marked as "client-symbolicated" and thus doesn't show a "missing symbol" warning, images that are missing, but whose associated frames are entirely "client-symbolicated", shouldn't be marked as an error either (but should still be listed). Should this be resolved on the client (with a tag similar to the frame)? Or should this be resolved in native processing?
- Are there workflow interactions between symbolication, line-number, and source lookup that would be prevented by the presented approach?
- What is the interaction with demangling? If an SDK provides a mangled C++ symbol, should the backend still demangle it even if the frame is marked as client-symbolicated?
- Should the UI distinguish between server-symbolicated and client-symbolicated frames (e.g., a subtle indicator), or treat them identically?
- Naming: `symbolicated`, `client_symbolicated`, `sdk_symbolicated`, `symbolication_source`, or something else?

# Related Issues and Prior Art

- [getsentry/sentry#97054](https://github.com/getsentry/sentry/issues/97054): "UI shows symbolication error without indication of what to do about it" (.NET scenario)
- [getsentry/sentry#46955](https://github.com/getsentry/sentry/issues/46955): "Remove error banner for non-app symbols"
- `FIXME(swatinem)` in [`processing.py` L149-158](https://github.com/getsentry/sentry/blob/422487ea4acad23710cd1fe5392a5b684e09c2e4/src/sentry/lang/native/processing.py#L149-L158): Hard-coded .NET exception
- `is_known_third_party()` in [`processing.py`](https://github.com/getsentry/sentry/blob/422487ea4acad23710cd1fe5392a5b684e09c2e4/src/sentry/lang/native/processing.py) - Denylist-based workaround
- Relay frame schema catch-all: [`relay-event-schema/.../stacktrace.rs` L200-202](https://github.com/getsentry/relay/blob/55c59cf75d3c35bbbb66df14072d147eca056bd7/relay-event-schema/src/protocol/stacktrace.rs#L200-L202)
