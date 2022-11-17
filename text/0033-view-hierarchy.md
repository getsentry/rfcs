* Start Date: 2022-11-02
* RFC Type: feature
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
* RFC Status: -
* RFC Driver: [Dhiogo Ramos Brustolin](https://github.com/brustolin)

# Summary

Allow SDKs to send a textual representation of the application's UI view hierarchy. 

# Motivation

Being able to see what the user was looking at is a good way to find problems in an application. This RFC proposes a way to send information from the UI state of an application, known as "view hierarchy". Compared to screenshots the view hierarchy provides complementary information about the UI, e.g. relationships between UI widgets or additional attributes not visible on the screen.

Example View Hierarchies from PoC implementations:
* [Android](https://github.com/getsentry/sentry-java/pull/1998#issuecomment-1104806065)
* [iOS](https://github.com/getsentry/sentry-cocoa/pull/2044#issue-1329719543)
* [Flutter](https://github.com/ueman/sentry-dart-tools/blob/b850db587f0e099bed253d13055c88c03d536875/sentry_flutter_plus/lib/src/integrations/tree_walker_integration.dart)
* [Unity](https://github.com/getsentry/team-mobile/issues/64#issuecomment-1290868653)

# Proposal

Capture the view hierarchy in our mobile SDKs and convert it to a common JSON representation. Add it as an [attachment](https://develop.sentry.dev/sdk/envelopes/#attachment) to the envelope. The `attachment_type` is set to `"event.viewhierarchy"` and the `content_type` is set to the `"application/json"` mime-type.

The attachment payload is a JSON structure containing the view hierarchy, here's an example:
```json
{
    "rendering_system": "compose", // or android_view_system, apple_uikit, apple_swiftui, unity, flutter, ...
    "windows": [
        {
            "type": "com.example.ui.FancyButton",
            "identifier": "R.id.button_logout",
            "children": [], // nested elements
            "width": 100.0,
            "height": 100.0,
            "depth": 100.0, // if applies
            "x": 0.0,
            "y": 0.0,
            "z": 2.0, // if applies.
            "visible": true|false,
            "alpha": 1, // a float number from 0 to 1, where 0 means totally transparent, and 1 totally opaque.
            "{extra_properties}": "{property value}" // additional platform-specific attributes
        }
    ]
}
```

Some remarks on the example:
 * `windows`: contains all visible windows, on mobile it's typically just one or two (e.g. if a dialog is open)
 * `type`: The fully qualified widget class name, this name may be obfuscated on certain platforms (e.g. Android release builds with proguard enabled)
 * `children` nests all child UI widgets, which then builds up the whole UI tree

A typical Android/iOS view hierarchy for a single window consists of around 100-200 objects. Taking the attributes from the example above this generates a raw JSON file with a size of around 50KB. More complex view hierarchies for e.g. a Unity game may hold 1000-2000 objects, producing a JSON file of around 500KB.

## (De)obfuscation
As the view hierarchy may contain obfuscated attribute values (see `type` attribute in the example above) we need to process the attachment server-side, similar to what we already do for minidumps, [or profiles](https://github.com/getsentry/sentry/blob/cf71af372677487d7d0a7fd8ac9dd092f9596cf4/src/sentry/profiles/task.py#L350-L360).

# Options Considered
- Use a new envelope type instead of attachements: Whilst doable it's consideribly more work without adding any benefits. Using attachements has several advantages
    - Attachments are billable by default
    - We can immediately start sending and using this data, no need for large Relay updates
    - Less new code in the SDKs when compared to adding a new envelope item, so less hassle to maintain/test
    - We don't have to touch outcomes/rate limiting/processing code at all
    - We always can eventually migrate to a new envelope item type if we feel the need to, that option is still left open.
- The view hierarchy could be part of the Event, but because of the size limit, it is not recommended


# Drawbacks

- Increases event payload size
- We've decided to not add the content of textfields, editables or labels because of PII.
    - We may evaluate an options to allow PII.


## Initial Proposal
This is how the envelope item header should look like:

```json
{"type":"view_hierarchy","length":...,"content_type":"application/json"}\n
```

And the envelope item payload will be a JSON array that contains a view hierarchy for each available screen/window. 
This is how it should look like: 

```json
[
    {
        "type": "element_full_qualified_class_name", 
        "identifier": "element_identifier",
        "children": [...], //An array of ui elements.
        "width": 100, 
        "height": 100,
        "depth": 100, //if applies
        "x": 0,
        "y": 1,
        "z": 2, //if applies.
        "visible": true|false,
        "alpha": 1, //A float number from 0 to 1, where 0 means totally transparent, and 1 totally opaque.
        "{extra_properties}": "{property value}" //adicional information by platform
    }
]
```

This is just an example, each platform will define the required properties.

# Options Considered

- We could send the same information as attachment, but this impact on attachment quota. And also we need to rely on file name to determined whether an attachment is a view hierarchy or not, this is a problem we already have with [screenshots](https://develop.sentry.dev/sdk/features/#screenshots).
- The view hierarchy could be part of the Event, but because of the size limit, isn't recommended. 

# Drawbacks

- This can significantly increase the envelope size. 
- Obfuscation is a problem for custom UI controls, we'll probably need ingestion to de-obfuscate in the server side.
- We've decided to not add the content of textfields, editables or labels because of PII.
    - We may evaluate an options to allow PII.