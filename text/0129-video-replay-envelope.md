- Start Date: 2024-02-06
- RFC Type: feature
- RFC PR: [#129](https://github.com/getsentry/rfcs/pull/129)
- RFC Status: draft

# Summary

In order to capture video replays and present them to the user, we need to define/decide:

- how to transport the video data to the server
- how to integrate the video data into the RRWeb JSON format
- how to combine multiple replay chunks to a single replay session

All of these influence one another and need to be considered together in a single RFC.

Note: SDK-side implementation that is currently being worked on relies on taking screenshots and encoding them to a video.
This is based on an evaluation where a video has much smaller size than a sequence of images (**TODO fix these: factor of X for 720p video**).

# Motivation

We need this to to capture replays on platforms where it's not possible/feasible to produce an HTML DOM (i.e. the native format supported by RRWeb). For example: mobile apps.

<!-- # Supporting Data -->
<!-- Metrics to help support your decision (if applicable). -->

# Options Considered

## Using a video, with EnvelopeItem:Attachment

- From the SDK, we should be able to use the existing envelope item type, [`attachment`](https://develop.sentry.dev/sdk/envelopes/#attachment) to transport the video data.
- Additionally, it would be accompanied with replay envelope item in RRWeb JSON format (**TODO link if any, see <https://github.com/getsentry/develop/issues/1144>**).
- To link to the video (attachment) file in the replay JSON, we could use a [`EventType.Custom`](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L8-L16). (**TODO how can we link to a specific attachment coming with the event?**).

## Other considered options

### Using the existing RRWeb canvas replay format (image snapshots)

It would be easy to implement this because the SDK already captures screenshots and with RRWeb being able to show them, there's not much to do. However, this would come with significantly larger data transfer size (compared to video), which should be kept as low as reasonably possible, considiering this is currently aimed at mobile apps. Additionally, these images would need to be encoded in base64 so that they can be embedded in the RRWeb JSON.

<!--
# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known? -->
