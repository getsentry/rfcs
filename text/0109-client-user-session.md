- Start Date: 2023-08-15
- RFC Type: feature
- RFC PR: #110
- RFC Status: draft

# Summary

Introduce, or officially define a user session concept for Sentry client side SDKs. Meaning decide how to name, create and propoagate unique IDs,
which are associated with an entire client side user session. Which is not tightly coupled to any specific product (Session Replay).

![image](https://github.com/getsentry/rfcs/assets/47563310/b1d52974-4c4f-424d-a2c4-509e0d670294)


# Motivation

Sentry user's monitoring client side use cases want to be able to observe all events associated with a user session of interest.
Whether that is due to one or more exceptions occuring in the flow, or performance problems, it is common that developers debugging a flow
would want to see all events from an individual user loading the page and navigating a site or mobile application views. 

They are frustrated because they want to be able to filter the data for a specific user in Discover, 
and the set of events available are incomplete.

# Proposals

**Example:**

1. A user is in Discover and tries to filter transactions by a user, `john@doe.com`, because this user reported a problem.
2. The events `AppStart` and `DownloadEditionMigration` appear, but still also need
3. the `graphQL call/query` that should happen within this set of interactions.

### Proposed Solutions:

1. A short term solution (do nothing): Use some unique identifiers from the user or SDK initialization to tag all events and make them
   searchable in discover
    
    > save us a lot of time if we were able to identify evens from that user
    > 
    
    Would the default `userId`  work in this case?
    
    > If you don't provide an `id` the SDK falls back to `installationId`, which the SDK randomly generates once during an app's installation.
    > 
    
    https://docs.sentry.io/platforms/android/enriching-events/identify-user/
    
    Setting any value like this as a tag would be indexed and then searchable in discover. A persistent unique userId set by the org,
    could allow to track all sampled “sessions” of the unique user. Which may be unecessary. A random ID for each session will allow
    to group just that session no specific relationship to the user.
    
    If this ID is to be used as well in DSC to associate other events via distributed tracing that would also need to be done manually
    by the user
    
    1. **con:** this will not influence any biases and there could still be missing events
    2. **con**: this would also include multiple app starts when using the `installationId`

2. Longer term solution: 
    1. react-native SDK
        1. SDK provides a way for users to generate a sessionID 
            1. could simple be a version of the initializationID
            2. could be experimental flag for now
            3. automatically propagated this in DSC
                1. session concept similar to SR with multiple traces connected to single trace
            4. consider a sampling option, 
                1. similar to SR that states if there is an error to have a higher sample rate for those user sessions
                2. potentially long txn times as a decider in client for deciding
            5. existing APIs around session may lead to confusion
            6. client side sampling:  SDK should ensure that if an event as part of a session included then all other events within
               that session are included as well
                1. identifying a unique session default experience, identifying by a particular user requires the user to decide with
                   tagging of a userID or email for example
            8. Always in reference to a user session
                1. can contain 1 or more traces
                2. a trace cannot contain more than 1 user session
            9. out of scope: replace/repair “release” sessions right away
                1. session replay 
                2. profiles existence
                3. guaranteeing that a session exists for a user calling support
