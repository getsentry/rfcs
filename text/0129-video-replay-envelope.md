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

## Using a video, with EnvelopeItem:ReplayVideo

- From the SDK, we would send a new envelope with the following items: `Replay`, `ReplayVideo` and `ReplayRecording`.
- The newly introduced item type, [`ReplayVideo`](https://github.com/getsentry/relay/blob/5fd3969e88d3eea1f2849e55b61678cac6b14e44/relay-server/src/envelope.rs#L115C5-L115C20) is used to transport the video data.
  The envelope item would consist of a single header line (JSON), followed by a new line and the raw video data.
  - The header should contain at least the following metadata:

    ```json
    {
      "segment-id": 4,
      "size": 3440,
      "duration": 5000,
      "encoding": "whatever",
      "container": "whatever",
    }
    ```

- Additionally, it would be accompanied by an item [`ReplayRecording`](https://github.com/getsentry/relay/blob/5fd3969e88d3eea1f2849e55b61678cac6b14e44/relay-server/src/envelope.rs#L113), containing a header, e.g. `{"segment_id": 12}`, followed by a new line and the RRWeb JSON.
  - The RRWeb JSON must start with an event of type [`EventType.Custom`](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L8-L16), containing the type `video`.
  There must only be a single video custom event in the RRWeb JSON.
  If there's other data the UI needs, we can add it alongside the `type` to the `data` field. Because there's only a single `ReplayVideo` sent with a single `ReplayRecording`, there's a one-to-one mapping without further details necessary in the actual RRWeb JSON.

    ```json
    {
      "type": 5,
      "timestamp":1681846559381,
      "data": {
        "tag": "video",
        "payload": {
          "segment-id": 4,
          "size": 3440,
          "duration": 5000,
          "encoding": "whatever",
          "container": "whatever",
          "v-size": 1920,
          "h-size": 1080,
          "frame-count": 50,
          "frame-rate-type": "constant|variable",
          "frame-rate": 10,
        }
      }
    }
    ```
    > Note: The format is based on [RRWeb Custom event type specification](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L53-L59).

## Other considered options

### Using the existing RRWeb canvas replay format (image snapshots)

It would be easy to implement this because the SDK already captures screenshots and with RRWeb being able to show them, there's not much to do. However, this would come with significantly larger data transfer size (compared to video), which should be kept as low as reasonably possible, considering this is currently aimed at mobile apps. Additionally, these images would need to be encoded in base64 so that they can be embedded in the RRWeb JSON.

<!--
# Drawbacks

Why should we not do this? What are the drawbacks of this RFC or a particular option if
multiple options are presented.

# Unresolved questions

- What parts of the design do you expect to resolve through this RFC?
- What issues are out of scope for this RFC but are known? -->
