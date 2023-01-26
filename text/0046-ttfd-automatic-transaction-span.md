- Start Date: 2022-12-16
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/46
- RFC Status: draft
  
# Summary 
  
We want to provide a new span to the automatic UI transactions.  
The TTFD (time-to-full-display) span is a way for the user to notify the SDK that the UI has been fully loaded.  
That is, after all data is retrieved, either by database calls or rest APIs, and set into the UI.  
We would create a new span to the UI automatic transactions to measure it, for all screens of the application.  
This RFC is mostly about how we should design the new API.  
  
# Motivation

This is useful especially for mobile developers, but could also be useful for web.  
There is no reliable way to automatically detect when UI is fully drawn, as the "fully drawn" concept depends on the developer.  
  
# Background. 
  
We have to add a new API to the SDK to allow the user to notify that the UI was fully drawn.  
Also, we need the user to specify the span to finish through a parameter, as it cannot be done automatically.  
E.g. Activity A starts -> Activity B starts -> Activity A finishes loading data and the API is called.  
At this point without the activity it was called on, we wouldn't know which span to finish, because the activity B would be at the top of the stack.  
# Final Decision
  
We decided to go with the simplest API possible, from the end user perspective.  
We are going to add a single new API `Sentry.reportFullDisplayed()`, which will find the last active screen load transaction and finish the `time-to-full-display` span.  
The active screen load transaction needs to wait for a to-be-defined timeout if the user calls this API.  
We still have to evaluate all the edge cases.  
  
Since we are going to wait for the user to call the manual API, we are going to make it opt-in, otherwise unaware users would have their transactions take much longer without immediate causes.
  
Furthermore, we will evaluate if the SDKs should automatically finish the `time-to-full-display` span, as it would greatly push adoption, but with a lot of possible false positives.  
This consideration will be evaluated after getting feedbacks (or complains) from the users and after checking the feature adoption.  
  
We are keeping the considered options as a reference.  
  
  
## Options Considered

* [2. Sentry.monitorFullDisplay() with Span](#option-2)
* [4. monitorFullDisplay on ISpan](#option-3)
  
Options removed:  
* [1. SentryAndroid.reportFullyDrawn(Activity)](#option-1)
* [3. Sentry.monitorFullDisplay() with UUID](#option-3)
* [5. reportFullDisplay() on ISpan](#option-5)
* [6. reportFullDisplay on ISpan with Option](#option-6)
* [7. Hook into Android's `FullyDrawnReporter`](#option-7)
  
These options were considered for Android, but the same apply to other SDKs, too.  


## 2. Sentry.monitorFullDisplay() with Span <a name="option-2"></a>

Add a `Sentry.monitorFullDisplay()` API. We would start the span automatically when an Activity is being created.  
This API would return the span or a custom object to allow the user to finish it autonomously.  
  
## Pros

- We don't depend on Activity, making it usable on other platforms, too.  
- We can flag the span when the API is called, so that if the user doesn't call the API, we know we can cancel it. 

### Cons
 
- Returning the span would allow the user to perform "dangerous" operations. We could solve this by returning a stripped interface to allow only the `finish()` method, or an entirely custom object.  
- If the user doesn't call the API, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.  
- We can't reliably map `Sentry.monitorFullDisplay()` to the correct APM transaction, unless we force the user to call it in a specific callback, like `Activity.onActivityCreated()`.  


## 4. monitorFullDisplay on ISpan <a name="option-4"></a>

Add `monitorFullDisplay()` and `reportFullDisplay()` to ISpan. The user gets access to the APM UI transaction by calling `Sentry.getSpan`, calls `span.monitorFullDisplay()` and `span.reportFullDisplay()`.  

### Pros

- We don't depend on Activity, making it usable on other platforms, too.  
- Correlate fully drawn to correct APM transaction.  
- User can add more spans via the same API Sentry.span.  
- Knowing when to wait for fully drawn.  

### Cons

- Extra APIs to call.  
- Keeping a reference of transaction.
  
## Removed Options

## 1. SentryAndroid.reportFullyDrawn(Activity) <a name="option-1"></a>

Add a `SentryAndroid.reportFullyDrawn(Activity)` static method. We would start the span automatically when an Activity is being created and we would finish it when the API is called.

### Removal reason

- The name of the api should be closer to `reportTimeToFullDisplay()`, losing the only pro.

### Pros

- This resembles the system API `Activity.reportFullyDrawn()`, making it obvious how to use.

### Cons

- We need the activity this API is called for, and passing an Activity instance to an API is not ideal.  
- We need to add an API to `SentryAndroid`, instead of the `Sentry` class used everywhere else, due to Activity dependency.  
- This is not ideal for single activity apps, as it wouldn't work for fragments.  
- If the user doesn't call the API, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.  


## 3. Sentry.monitorFullDisplay() with UUID <a name="option-3"></a>

Add a `Sentry.monitorFullDisplay()` and a `Sentry.reportFullDisplay(UUID)` API. We would start the span automatically when the SDK creates an auto-generated transaction.  
This API would return a UUID used by the other API to stop the span.

### Removal reason

- Returning a span could be more useful to the end user, making [option 2](#option-2) better then this.

### Pros

- We don't depend on Activity, making it usable on other platforms, too.
- We can flag the span when the API is called, so that if the user doesn't call the API, we know we can cancel it.
- We don't return any "dangerous" object to the user.

### Cons

- We would add and force the user to use 2 APIs.
- If the user doesn't call the second API, we would have a span that runs forever. We would have to add a timeout to automatically cancel the span.
- We can't reliably map `Sentry.monitorFullDisplay()` to the correct APM transaction, unless we force the user to call it in a specific callback, like `Activity.onActivityCreated()`.


## 5. reportFullDisplay on ISpan <a name="option-5"></a>

Add `reportFullDisplay()` toISpan. The user gets access to the APM UI transaction by calling `Sentry.getSpan`, and calls `span.reportFullDisplay()`.

### Removal reason

- Add an API to all ISpan objects could be confusing.  
- Not knowing when to wait for fully drawn, making [option 4](#option-4) better then this.  

### Pros <a name="option-5-pros"></a>

- We don't depend on Activity, making it usable on other platforms, too.  
- Correlate fully drawn to correct APM transaction.  
- User can add more spans via the same API Sentry.span.  

### Cons <a name="option-5-cons"></a>

1. Extra APIs to call.  
2. Keeping a reference of a transaction.
3. Not knowing when to wait for fully drawn.


## 6. reportFullDisplay on ISpan with Option <a name="option-6"></a>

Same as Option 5. but with an option wether to wait for calling `reportFullDisplay` or not.
The SDK would wait for a configurable timeout for the user to call `reportFullDisplay`. If the user doesn't call the API the SDK adds a `ui.load.full_display` span with `deadline_exceeded`, and finishes the auto-generated transaction.
If the user calls `reportFullDisplay` and the option wether to wait for calling `reportFullDisplay` or not is disabled, the SDK does nothing.

### Removal reason

- A timeout should always be present, to avoid transactions running indefinitely due to user's error.  
- Same reasons of [option 5](#option-5).  

### Pros

- [Same Pros as option 5](#option-5-pros)
- Knowing when to wait for fully drawn when option enabled.

### Cons

1. [Cons 1-2 of option 5](#option-5-cons)


## 7. Hook into Android's `FullyDrawnReporter` <a name="option-7"></a>

We would use use a callback from that.  

### Removal reason

- Not knowing when to wait for fully drawn.  
- Would work only on Android, and not even for single activity apps.  

### Pros 

- Completely automatic and transparent to the user.  
- We would know the activity that was drawn, so we'd know the span to finish.  

### Cons

- Only available from `androidx.activity` library version 1.7, currently in alpha.  
- This is not ideal for single activity apps, as it wouldn't work for fragments.  
- Not knowing when to wait for fully drawn.  
- Only works on Android.
  
# Unresolved questions
  
- How long should the timeout be? The Facebook app developers consider a "bad start" a ttfd of 2.5 seconds or more, or an unsuccessful start.  
This is only for the first screen, as the other screens are usually faster.  
https://android-developers.googleblog.com/2021/11/improving-app-startup-facebook-app.html
