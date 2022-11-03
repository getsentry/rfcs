* Start Date: 2022-11-02
* RFC Type: feature
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)
* RFC Status: -
* RFC Driver: [Dhiogo Ramos Brustolin](https://github.com/brustolin)

# Summary

Allow SDKs to send a textual representation of the application's UI view hierarch. 

# Motivation

Being able to see what the user was looking at is a good way to found out problems in the application. 
This RFC proposes a way to send information from the UI state of an application, known as "view hierarch".

# Proposal 

The proposal is to create a new [envelope item](https://develop.sentry.dev/sdk/envelopes/) in the form of a json representation of the UI elements. 
This is how the envelope item header should look like:

```json
{"type":"view_hierarch","length":...,"content_type":"application/json"}\n
```

And the envelope item payload will be a JSON array that contains a view hierarch for each available screen/window. 
This is how it should look like: 

```json
[
{
    "type": "element_class_name", 
    "identifier": "element_identifier",
    "children": [...], //An array of ui elements.
    "width": 100, 
    "height": 100,
    "depth": 100, //if 3D
    "x": 0,
    "y": 1,
    "z": 2, //if 3D.
    "visible": true|false,
    "alpha": 1,
    "{extra_properties}": "{property value}" //adicional information by platform
}
]
```

# Options Considered

- We could send the same information as attachment, but this impact on attachment quota. And also we need to rely on file name to determined whether an attachment is a view hierarch or not, this is a problem we already have with [screenshots](https://develop.sentry.dev/sdk/features/#screenshots).
- The view hierarch could be part of the Event, but because of the size limit, isn't recommended. 

# Drawbacks

- This can significantly increase the envelope size. 
- We've decided to not add the content of textfields, editables or labels because of PII.
    - We may evaluate an options to allow PII.