- Start Date: 2024-02-06
- RFC Type: feature
- RFC PR: [#129](https://github.com/getsentry/rfcs/pull/129)
- RFC Status: approved

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

- From the SDK, we would send an envelope with the following items: `Replay`, `ReplayVideo` and `ReplayRecording`.
- The newly introduced item type, [`ReplayVideo`](https://github.com/getsentry/relay/blob/5fd3969e88d3eea1f2849e55b61678cac6b14e44/relay-server/src/envelope.rs#L115C5-L115C20), is used to transport the video data.
  The envelope item payload would consist of a single header line (`{"segment_id": 4}`), followed by a new line character (`\n`), followed by the raw video data.

- Additionally, it would be accompanied by an envelope item [`ReplayRecording`](https://github.com/getsentry/relay/blob/5fd3969e88d3eea1f2849e55b61678cac6b14e44/relay-server/src/envelope.rs#L113). The payload of this item consists of a header, e.g. `{"segment_id": 12}`, followed by a new line and the RRWeb JSON.
- The RRWeb JSON may start with a single event of type [`EventType.Meta`](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L8-L16), with viewport (screen) dimensions. The `EventType.Meta` event is usually present in the first segment of a replay, or whenever the view port or screen orientation changes.

    ```json
    {
      "type": 4,
      "timestamp": 1681846559381,
      "data": {
        "href": "",
        "height": 1920,
        "width": 1080
      }
    }
    ```

  > Note: these dimensions may be different than the video dimensions in case only part of the screen is captured.
    In that case, the following video event will have non-zero `data.payload.left` & `data.payload.top` fields (see below).

- The RRWeb JSON must contain a single event of type [`EventType.Custom`](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L8-L16), with `data.tag == 'video'`.
  This event must come at the first position in the array, or at the second position if the `EventType.Meta` event is present.
  If there's other data the UI needs, we can add it alongside the `type` to the `data` field. Because there's only a single `ReplayVideo` sent with a single `ReplayRecording`, there's a one-to-one mapping without further details necessary in the actual RRWeb JSON.

    ```json
    {
      "type": 5,
      "timestamp":1681846559381,
      "data": {
        "tag": "video",
        "payload": {
          "segmentId": 4,
          "size": 3440,
          "duration": 5000,
          "encoding": "whatever",
          "container": "whatever",
          "height": 1920,
          "width": 1080,
          "frameCount": 50,
          "frameRateType": "constant|variable",
          "frameRate": 10,
          "left": 0,
          "top": 0,
        }
      }
    }
    ```

    > Note: The format is based on [RRWeb Custom event type specification](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L53-L59).

## Other considered options

### Using the existing RRWeb canvas replay format (image snapshots)

It would be easy to implement this because the SDK already captures screenshots and with RRWeb being able to show them, there's not much to do. However, this would come with significantly larger data transfer size (compared to video), which should be kept as low as reasonably possible, considering this is currently aimed at mobile apps. Additionally, these images would need to be encoded in base64 so that they can be embedded in the RRWeb JSON.
