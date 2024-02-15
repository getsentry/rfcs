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
This is based on an evaluation where a video has much smaller size than a sequence of images.
Preliminary testing yielded about 5-7 KiB per video frame (300x651), compared to about 30 KiB for a JPEG image of the same resolution (70 % quality setting).

# Motivation

We need this to to capture replays on platforms where it's not possible/feasible to produce an HTML DOM (i.e. the native format supported by RRWeb). For example: mobile apps.

<!-- # Supporting Data -->
<!-- Metrics to help support your decision (if applicable). -->

# Options Considered

## Using a video, with EnvelopeItem:ReplayVideo

SDKs which support sending replay playback information as a video will use the new `ReplayVideo` envelope item type. The envelope item's payload is a msgpack-encoded value containing three keys.

1. The `replay_event` key. The value of this key is JSON bytes matching the protocol defined in [relay-event-schema](https://github.com/getsentry/relay/blob/master/relay-event-schema/src/protocol/replay.rs).
2. The `replay_recording` key. The value of this key contains three parts.
  1. Headers JSON. The headers must contain the `segment_id` value.
  2. A new-line character.
  3. RRWeb JSON bytes.
3. The `replay_video` key. The value of this key is raw video bytes.

An example payload is provided below (represented in Python syntax):

    ```python
    {
      "replay_event": b"{ ... }",
      "replay_recording": b'{"segment_id": 0}\n[{ ... }]',
      "replay_video": b'\x00\x00',
    }
    ```

In other languages (Rust for example) you might represent this as `HashMap<String, Vec<u8>>`.

The `segment_id` header on the `replay_recording` key is redundant as its also specified on the `replay_event` key. This is to preserve compatibility with other platform event types.

The RRWeb JSON provided on the `replay_recording` key may start with a single event of type [`EventType.Meta`](https://github.com/rrweb-io/rrweb/blob/8aea5b00a4dfe5a6f59bd2ae72bb624f45e51e81/packages/types/src/index.ts#L8-L16), with viewport (screen) dimensions. The `EventType.Meta` event is usually present in the first segment of a replay, or whenever the view port or screen orientation changes.

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
