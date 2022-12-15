* Start Date: 2022-11-08
* RFC Type: decision
* RFC PR: [#36](https://github.com/getsentry/rfcs/pull/36)
* RFC Status: -
* RFC Driver: [Roman Zavarnitsyn](https://github.com/romtsn)

# Summary

Add new `blocked_main_thread` attribute to the `data` key-value map of the [`Span`](https://develop.sentry.dev/sdk/event-payloads/span/) interface, indicating whether an auto-instrumented span has run its entire duration on the UI/Main thread.

# Motivation

In order to expand our Performance Issues offering for mobile, we'd like to introduce a new attribute 
to the `Span.data` key-value map, indicating whether the span has run on the UI/Main thread, which may 
result in bad application performance, dropped frames, or even App Hangs/ANRs.

This attribute will be used to detect Performance Issues. As a proof-of-concept, we've decided to start
detecting File I/O operations on main thread as one of the common pitfalls in mobile development. Since
File I/O is an atomic operation and can't span across multiple threads, we can certainly say that it's
a performance issue, when we identify that it's running on the UI/Main thread from our instrumentation.

This attribute is also valid for any Frontend SDK.

# Background

Mobile and Desktop developers must be very aware of the UI Thread(s). It's a core part of developing 
user interfaces and a common source of bad user experience due to unresponsive UI.

File I/O operations on main thread is one of [the common causes](https://developer.android.com/topic/performance/vitals/anr#io-on-main) 
for slowing down mobile applications and worsening User Experience. They can result in dropped frames, or even worse, 
in App Hangs/ANR, which can happen if the UI/Main thread is blocked for more than 5 seconds. It is also easy to miss 
those operations, as they can be hidden under some third-party libraries/SDKs (e.g. image loading library, which does caching).

Since we already offer auto-instrumentation for File I/O operations on mobile platforms (Android, iOS, Dart),
it will be an easy win for us to start detecting Performance Issues by introducing a relatively small change
to the `Span.data` map.

[ANR documentation as part of Android Vitals](https://developer.android.com/topic/performance/vitals/anr).

# Proposal

Add two new attributes to the `data` key-value map of the [`Span`](https://develop.sentry.dev/sdk/event-payloads/span/) interface:

  1. `blocked_main_thread` - indicates whether the Span has spent its entire duration on the Main/UI thread.
  2. `call_stack` - contains the most relevant stack frames, that lead to the File I/O span. The stack frame should adhere to the 
  [`StackFrame`](https://develop.sentry.dev/sdk/event-payloads/stacktrace/#frame-attributes) interface. When possible, should only include `in-app` frames. 
  Used for proper fingerprinting and grouping of the File I/O performance issues.

An example of a File I/O span payload with the newly added attributes:
```json
{
  "timestamp": 1669031858.806411,
  "start_timestamp": 1669031858.712,
  "exclusive_time": 94.411134,
  "description": "1669031858711_file.txt (4.0 kB)",
  "op": "file.write",
  "span_id": "054ba3a374d543eb",
  "parent_span_id": "b93d2be92cd64fd5",
  "trace_id": "b2a33f3f79fe4a7c8de3426725a045cb",
  "status": "ok",
  "data": {
    "blocked_main_thread": true,
    "call_stack": [
      {
        "function": "onClick",
        "in_app": true,
        "lineno": 2,
        "module": "io.sentry.samples.android.MainActivity$$ExternalSyntheticLambda6",
        "native": false
      },
      {
        "filename": "MainActivity.java",
        "function": "lambda$onCreate$5$io-sentry-samples-android-MainActivity",
        "in_app": true,
        "lineno": 93,
        "module": "io.sentry.samples.android.MainActivity",
        "native": false
      }
    ],
    "file.path": "/data/user/0/io.sentry.samples.android/files/1669031858711_file.txt",
    "file.size": 4010
  },
  "hash": "8add714f71a52ef2"
}
```

## Symbolication

As the `call_stack` may contain obfuscated frames we need to symbolicate them server-side, similar to what we already do for 
[profiles](https://github.com/getsentry/sentry/blob/cf71af372677487d7d0a7fd8ac9dd092f9596cf4/src/sentry/profiles/task.py#L350-L360). 

To be able to symbolicate the `call_stack` which is part of the `Span` interface server-side, we have to start sending the `debug_meta`
information for transactions as well.

# Options Considered

## Detecting UI/Main thread for all Spans (Option 1)

The approach was to detect whether *any* span (including custom ones) has run on the UI/Main thread or not.
However, this turned out to be problematic, because we can't certainly say how much time a span spent on the
UI/Main thread vs other threads. The span might be started on the UI/Main thread, then perform a network
request on a background thread (a new child span), and then finished back on the UI/Main thread. It's unclear
whether this span should be marked as run on UI/Main thread or not.

This option would also require quite some changes in the protocol (e.g. having a map of threads with the start/end timestamp pairs)
as well as frontend changes.

This option has been decided against, due to potential high-complexity of the proper solution or just simply
infeasiable on some certain platforms.

## Making `blocked_main_thread` attribute part of the protocol (Option 2)

Since this flag is only relevant to Frontent SDKs, and is only used to mark auto-instrumented spans, it was
decided against adding it to the common `Span` interface of the protocol.

# Drawbacks

The only drawback we found with this approach is that it works only for automatically created spans and
cannot be expanded to custom spans. However, given, that our auto-instrumentation offering is growing, this 
should not be a problem. Other potential detectors we could create for detecting performance issues:

* Network I/O on main thread
* Database operations on main thread
* Resources (images/audio/video) manipulation on main thread (e.g. decoding, resizing, etc.)
