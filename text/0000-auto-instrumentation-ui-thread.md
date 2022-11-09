* Start Date: 2022-11-08
* RFC Type: decision
* RFC PR: <link>
* RFC Status: -
* RFC Driver: [Roman Zavarnitsyn](https://github.com/romtsn)

# Summary

Add new `ui_thread` attribute to the `data` key-value map of the `Span` interface, indicating whether
an auto-instrumented span has run on the UI/Main thread.

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

## Making `ui_thread` attribute part of the protocol (Option 2)

Since this flag is only relevant to Frontent SDKs, and is only used to mark auto-instrumented spans, it was
decided against adding it to the common `Span` interface of the protocol.

# Drawbacks

The only drawback we found with this approach is that it works only for automatically created spans and
cannot be expanded to custom spans. However, given, that our auto-instrumentation offering is growing, this 
should not be a problem. Other potential detectors we could create for detecting performance issues:

* Network I/O on main thread
* Database operations on main thread
* Resources (images/audio/video) manipulation on main thread (e.g. decoding, resizing, etc.)

# Unresolved questions

* Should the `ui_thread` attribute be part of the protocol or just a new key in the data bag?
* How to properly fingerprint the File I/O performance issue? Do we need to provide a `caller_function`, which has 
performed the File I/O operation?
* (Out of scope) De-obfuscation/symbolication of the `caller_function`.
