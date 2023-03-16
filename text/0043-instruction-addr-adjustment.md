- Start Date: 2022-12-07
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/43
- RFC Status: draft

# Summary

This RFC introduces a new StackTrace Protocol field that controls adjustment of
the `instruction_addr` for symbolication.

# Motivation

To properly symbolicate the position / expression of the _call_, the `instruction_addr`
coming from the SDKs needs to be adjusted in some cases. The current adjustment that
we do does not allow for fine grained control and can lead to wrong symbolication results.

# Background

The `x86(-64)` `CALL` instruction pushes the return address (address immediately after the `CALL` instruction) on the stack.
Similarly, the `arm(64)` `BL` instruction copies the address of the next instruction into r14 (lr, the link register).

Therefore, the address recovered during stack walking for non-leaf frames is always the _return address_. Which according
to the descriptions above happens to be the next address after the function call.

In order to symbolicate the call-site itself, we adjust non-leaf frames by subtracting one instruction width, or `1` for
variable-length instruction sets such as `x86`.

This adjustment must not happen for leaf frames though, as they point to the exact instruction that caused a crashing
signal, or the instruction the thread was suspended on.

---

However, some client-side implementations may opt to trim frames from the top of the stack, for example to hide
implementation details of the stack walker itself.

This can also be the case when the stack capturing is not under direct control of the SDK, such as for the Unity SDK,
or the Rust SDK on some platforms.

Stack walker implementations may do that automatically, or offer parameters to skip frames from the top, such as
the Win32 [`CaptureStackBackTrace`](https://learn.microsoft.com/en-us/windows/win32/debug/capturestackbacktrace) function.

Apart from trimming stack frames, some implementations might even return already adjusted frames.

# Proposed Protocol Extension

We propose to add the following field to the
[Stack Trace Interface Attributes](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#attributes):

**`instruction_addr_adjustment: "auto" | "all" | "all_but_first" | "none"`**, _new_, _optional_

This new attribute tells `symbolicator` if, and for which frames, adjustment of the `instruction_addr` is needed.

## Options and which one to use

**`"all_but_first"`**:

All frames but the first (in callee to caller / child to parent direction) should be adjusted.

SDKs should use this value if the stack trace was captured directly from a CPU context in a signal handler or for
suspended threads.

**`"all"`**:

All frames of the stack trace will be adjusted, subtracting one instruction with (or `1`) from the incoming
`instruction_addr` before symbolication.

SDKs should use this value if frames were trimmed / skipped from the top either in the SDK itself, or in a stack walker
that is not under the control of the SDK.

**`"none"`**:

No adjustment will be applied whatsoever.

SDKs should use this value if the stack walker implementation has already applied an adjustment and the provided
`instruction_addr` values already point to the `CALL` instruction.

**`"auto"`** _(default)_:

Symbolicator will use the `"all_but_first"` strategy **unless** the event has a crashing `signal` attribute and the
Stack Trace has a `registers` map, and the instruction pointer register (`rip` / `pc`) does not match the first frame.
In that case, `"all"` frames will be adjusted.

## Profiling

The _Profiling Protocol_ needs a special mention here, as it uses a flat list of indexed frames to achieve better
deduplication of similar samples. In this case, profiling will send _all_ the frames as a single stack trace to symbolicator.
The property which frame was a leaf frame is completely lost in this process.

This is bad for two reasons:

1. Whichever frame happens to be _"first"_ is most likely wrong when using the `"all_but_first"` strategy. Unless it is
   indeed a leaf frame. But that is pretty random.
2. Any other leaf frames that happen to be scattered around the "middle" of the long list of frames will be wrong.

Profiling most likely will use a profiling signal and capture the corresponding cpu context, or it will suspend threads
and capture their stack from the outside. In both cases, the leaf frame should _not_ be adjusted, but all non-leaf
frames should be.

# Internal Symbolicator Protocol

The above `instruction_addr_adjustment` attribute will be used in the SDK -> Sentry protocol. The internal Sentry -> Symbolicator
protocol will add a per-frame attribute:

**`adjust_instruction_addr: Option<bool>`**, _new_

This is a _per-frame_ attribute which will do `instruction_addr` adjustment when set to `true`. The default depends on
the whole stack trace. If _any_ stack frame has an explicit value set, it will default to `Some(true)`. Otherwise it
defaults to `None`, which will apply the `"auto"` adjustment heuristic, keeping backwards compatibility to the current
implementation.

For example:

```rust
let default_adjustment = if frames.iter().any(|frame| frame.adjust_instruction_addr.is_some()) {
  Some(true)
} else {
  None
};

// ...

let instruction_addr_to_symbolicate = match frame.adjust_instruction_addr.or(default_adjustment) {
  Some(true) => todo!("use previous instruction addr"),
  Some(false) => instruction_addr,
  None => todo!("use existing heuristic"),
};
```

## Sentry Processor

The Sentry stack trace processor should transform the per-stack trace `instruction_addr_adjustment` flag into a
per-frame `adjust_instruction_addr` flag like so:

- `"auto"` / default: Do nothing.
- `"all"`: Add `adjust_instruction_addr: true` to the first frame, as every other frame will use `true` as default.
- `"all_but_first"`: Add `adjust_instruction_addr: false` to the first frame, as every other frame will use `true` as default.
- `"none"`: Add `adjust_instruction_addr: false` to every frame.

## Profiling Processor

The profiling product has tighter control over the quality of the stack traces and the methods with which they were obtained.
Assuming the stack traces were captured by suspending threads and walking from their CPU context, the top frame of each
stack trace would not need adjustment, but all the others would.

To make that work with the "indexed list of frames" approach of the profiling protocol, one way to solve this could be:

```rust
let mut all_frames = vec![/*...*/];

for idx in all_stack_traces.iter().flat_map(|frames| frames.first()) {
    all_frames[idx].adjust_instruction_addr = false;
}
```

# Should we expose adjusted `instruction_addr`?

Symbolicator currently outputs the adjusted addresses back as `instruction_addr`. The un-adjusted value is still available
as the `instruction_addr` of the `raw_stacktrace` event property.

This is arguably an implementation bug that should be fixed?

It has previously caused confusion for customers who complain about "broken" (actually off-by-one) stack traces
compared to ones they capture / report through their own means.

# Implementation

Support for this field needs to be added to different parts of the pipeline:

- Relay, to validate / forward this field to Sentry.
- Symbolicator, to apply the requested adjustment, and to possibly fix exposing adjusted `instruction_addr` values:
  https://github.com/getsentry/symbolicator/pull/948
- Sentry and Profiling event processors, to forward this flag to Symbolicator:
  https://github.com/getsentry/sentry/pull/42533
- Various SDKs to provide the appropriate flags if appropriate.

# Unresolved questions

- Should we bikeshed the names a bit more? Armin has originally suggested `instruction_addr_heuristics` with a default
  `"magic"` value.
- Should adjustment also be done for relative addresses?
- Should we indeed display non-adjusted "original" `instruction_addr` values in the UI?
- Related, if we want to display non-adjusted values in the UI, how can we achieve that if the SDKs send us
  pre-adjusted values? Is aligning to instruction width + add one instruction width enough in that case?
