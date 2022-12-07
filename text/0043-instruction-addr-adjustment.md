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

# Proposed Protocol Extension

We propose to add the following field to the
[Stack Trace Interface Attributes](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#attributes):

**`instruction_addr_adjustment: "auto" | "all" | "all_but_first" | "none"`**, _new_, _optional_

This new attribute tells `symbolicator` if, and for which frames, adjustment of the `instruction_addr` is needed.

## Options and which one to use

**`"all_but_first"`**:

All frames but the first (in callee to caller / child to parent direction) should be adjusted.

SDKs should use this value if the stack trace was captured directly from a CPU context in a signal handler, or for
suspended threads.

**`"all"`**:

All frames of the stack trace will be adjusted, subtracting one instruction with (or `1`) from the incoming
`instruction_addr` before symbolication.

SDKs should use this value if frames were trimmed / skipped from the top either in the SDK itself, or a stack walker
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

1. Whichever frame happens to be "first" is most likely wrong when using the `"all_but_first"` strategy. Unless it is
   indeed a leaf frame. But that is pretty random.
2. Any other leaf frames that happen to be scattered around the "middle" of the long list of frames will be wrong.

I can see one way to fix this for profiling:

As profiling has more control over when and how stack traces are captured, it can move `instruction_addr` adjustment
into the SDK, and send already _correctly_ adjusted frames along with `instruction_addr_adjustment: "none"`.

Profiling most likely will use a profiling signal and capture the corresponding cpu context, or it will suspend threads
and capture their stack from the outside. In both cases, the leaf frame should _not_ be adjusted, but all non-leaf
frames should be. In this case it is fair to do a simple `- 1`, as the backend (Symbolicator) itself will make sure
that fixed-sized instruction sets are aligned to instruction addresses.

# Should we expose adjusted `instruction_addr`?

Symbolicator currently outputs the adjusted addresses back as `instruction_addr`. The un-adjusted value is still available
as the `instruction_addr` of the `raw_stacktrace` event property.

This is arguably an implementation bug that should be fixed?

It has previously caused confusion for customers who complain about "broken" (actually off-by-one) stack traces
compared to ones they capture / report through their own means.

# Unresolved questions

- Should we bikeshed the names a bit more? Armin has originally suggested `instruction_addr_heuristics` with a default
  `"magic"` value.
- Is the proposed solution to fix profiling appropriate?
- Should we indeed display non-adjusted "original" `instruction_addr` values in the UI?
- Related, if we want to display non-adjusted values in the UI, how can we achieve that if the SDKs send us
  pre-adjusted values? Is aligning to instruction width + add one instruction width enough in that case?
