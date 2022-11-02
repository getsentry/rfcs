* Start Date: 2022-11-02
* RFC Type: feature
* RFC PR: [#33](https://github.com/getsentry/rfcs/pull/33)

# Summary

Allow SDKs to send View hierarch of the application UI.

# Motivation

Being able to see what the user was looking at is a good way to found out problems in the application. 
This RFC proposes a way to send information from the UI state of an application, known as "view hierarch".

# Proposal 

The proposal is to create a new envelope item in the form of a json representation of the UI elements, like so: 

```json
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
```

# Options Considered

We could send the same information as attachment, but this impact on attachment quota.

# Drawbacks

This can significantly increase the envelope size. 