- Start Date: 2022-12-16
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/46
- RFC Status: draft
  
# Summary. 
  
We want to provide a new span to the automatic UI transactions.  
The TTFD (time-to-full-display) span is a way for the user to notify the SDK that the UI has been fully loaded.  
That is, after all data is retrieved, either by database calls or rest APIs, and set into the UI.  
We would create a new span to the UI automatic transactions to measure it, for all screens of the application.  
This rfc is mostly about how we should design the new API.  
  
# Motivation

This is useful especially for mobile developers, but could also be useful for web.  
There is no reliable way to automatically detect when UI is fully drawn, as the "fully drawn" concept depends on the developer.  
  
# Background. 
  
We have to add a new API to the SDK to allow the user to notify that the UI was fully drawn.  
Also, we need the user to specify the span to finish through a parameter, as it cannot be done automatically.  
E.g. Activity A starts -> Activity B starts -> Activity A finishes loading data and the API is called.  
At this point without the activity it was called on, we wouldn't know which span to finish, because the activity B would be at the top of the stack.  
  
# Options Considered
  
These options were considered for Android, but the same apply to other SDKs, too.  

## 1. Add a `SentryAndroid.reportFullyDrawn(Activity)` static method.
We would start the span automatically when an Activity is being created and we would finish it when the API is called.  
  
Pros:
- This resembles the system API `Activity.reportFullyDrawn()`, making it obvious how to use.  

Cons:
- We need the activity this API is called for, and passing an Activity instance to an API is not ideal.  
- We need to add an API to `SentryAndroid`, instead of the `Sentry` class used everywhere else, due to Activity dependency.  
- This is not ideal for single activity apps, as it wouldn't work for fragments.  
- If the user doesn't call the API, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.  


## 2. Add a `Sentry.monitorFullyDrawn()` API.

We would start the span automatically when an Activity is being created.  
This API would return the span or a custom object to allow the user to finish it autonomously.  
  
Pros:
- We can flag the span when the API is called, so that if the user doesn't call the API, we know we can cancel it.  

Cons:
- We don't depend on Activity, making it usable on other platforms, too.  
- Returning the span would allow the user to perform "dangerous" operations. We could solve this by returning a stripped interface to allow only the `finish()` method, or an entirely custom object.  
- If the user doesn't call the API, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.  
- We can't reliably map `Sentry.monitorFullyDrawn()` to the correct APM transaction, unless we force the user to call it in a specific callback, like `Activity.onActivityCreated()`.  

## 3. Add a `Sentry.monitorFullyDrawn()` and a `Sentry.reportFullyDrawn(UUID)` API.

We would start the span automatically when an Activity is being created.  
This API would return a UUID used by the other API to stop the span.  
  
Pros:
- We don't depend on Activity, making it usable on other platforms, too.  
- We can flag the span when the API is called, so that if the user doesn't call the API, we know we can cancel it.  
- We don't return any "dangerous" object to the user.  

Cons:
- We would add and force the user to use 2 APIs.  
- If the user doesn't call the second API, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.
- We can't reliably map `Sentry.monitorFullyDrawn()` to the correct APM transaction, unless we force the user to call it in a specific callback, like `Activity.onActivityCreated()`.  

## 4. Add `monitorFullyDrawn()` and `reportFullyDrawn()` to ISpan. 

The user gets access to the APM UI transaction by calling `Sentry.getSpan`, calls `span.monitorFullyDrawn()` and `span.reportFullyDrawn()`.  

Pros:
- We don't depend on Activity, making it usable on other platforms, too.  
- Correlate fully drawn to correct APM transaction.  
- User can add more spans via the same API Sentry.span.  
- Knowing when to wait for fully drawn.  

Cons:
- Extra APIs to call.  
- Keeping a reference of transaction.  

## 5. Add `reportFullyDrawn()` toISpan.

The user gets access to the APM UI transaction by calling `Sentry.getSpan`, and calls `span.monitorFullyDrawn()`.  

Pros:
- We don't depend on Activity, making it usable on other platforms, too.  
- Correlate fully drawn to correct APM transaction.  
- User can add more spans via the same API Sentry.span.  

Cons:
- Extra APIs to call.  
- Keeping a reference of transaction.
- Not knowing when to wait for fully drawn.

## 6. Hook into Android's new `FullyDrawnReporter`

We would use use a callback from that.  

Pros:
- Completely automatic and transparent to the user.  
- We would know the activity that was drawn, so we'd know the span to finish.  

Cons:
- Only available from `androidx.activity` library version 1.7, currently in alpha.  
- This is not ideal for single activity apps, as it wouldn't work for fragments.  
- Not knowing when to wait for fully drawn.  
  
# Unresolved questions
  
- How long should the timeout be? The Facebook app developers consider a "bad start" a ttfd of 2.5 seconds or more, or an unsuccessful start.  
This is only for the first screen, as the other screens are usually faster.  
https://android-developers.googleblog.com/2021/11/improving-app-startup-facebook-app.html
