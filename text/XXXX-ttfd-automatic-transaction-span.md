- Start Date: 2022-12-16
- RFC Type: feature
- RFC PR: <link>
- RFC Status: draft

# Summary

We want to provide a new span to the automatic ui transactions.
The ttfd (time-to-full-display) span is a way for the user to notify the sdk that a ui has been fully loaded.
That is, after all data is retrieved, either by database calls or rest apis, and set into the ui.
We would create a new span to the ui automatic transactions to measure it, for all screens of the application.
This rfc is mostly about how we should design the new api.

# Motivation

This is useful especially for mobile developers, but could also be useful for web.
There is no reliable way to automatically detect when a ui is fully drawn, as the "fully drawn" concept itself is dependant upon the developer.

# Background

We have to add a new api to the sdk to allow the user to notify that a ui was fully drawn.

# Options Considered

These options were considered for Android, but the same apply to other sdks, too.
1) Add a `SentryAndroid.reportFullyDrawn(Activity)` static method. We would start the span automatically when an Activity is being created and we would finish it when the api is called.
Pros: This resembles the system api `Activity.reportFullyDrawn()`, making it immediate to use.
Cons:
 - We need the activity this api is called for, and passing an Activity instance to an api is not ideal.
E.g. Activity A starts -> Activity B starts -> Activity A finishes loading data and the api is called.
At this point without the activity it was called on, we wouldn't know which span to finish, because the activity B would be at the top of the stack.
 - We need to add an api to `SentryAndroid`, instead of the `Sentry` class used everywhere else, due to Activity dependency.
 - This is not ideal for single activity apps, as it wouldn't work for fragments
 - If the user doesn't call the api, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.
2) Add a `Sentry.monitorFullyDrawn()` api. We would start the span automatically when an Activity is being created. 
This api would return the span or a custom object to allow the user to finish it autonomously.
Pros: We can flag the span when the api is called, so that if the user doesn't call the api, we know we can cancel it
Cons: 
- Returning the span would allow the user to perform "dangerous" operations. We could solve this by returning a stripped interface to allow only the `finish()` method, or an entirely custom object.
- If the user doesn't call the api, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span. 
3) Add a `Sentry.monitorFullyDrawn()` and a `Sentry.reportFullyDrawn(ISpan)` api. We would start the span automatically when an Activity is being created. 
This api would return a uid used by the other api to stop the span.
Pros: 
- We can flag the span when the api is called, so that if the user doesn't call the api, we know we can cancel it
- We don't return any "dangerous" object to the user
Cons: 
- We would add and force the user to use 2 apis
- If the user doesn't call the second api, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.

# Unresolved questions

- How long should the timeout be? The Facebook app developers consider a "bad start" a ttfd of 2.5 seconds or more, or an unsuccessful start. 
This is only for the first screen, as the other screens are usually faster.
https://android-developers.googleblog.com/2021/11/improving-app-startup-facebook-app.html
