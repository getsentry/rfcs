- Start Date: 2023-04-20
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/87
- RFC Status: draft

# Summary

Sentry's ingestion runs through an Nginx proxy that rate limits requests per project, in order to protect our infrastructure from DoS / abuse. We set a fixed limit per project. We want to change this so our rate limits can bucket our different products into abuse limit categories.

Note while this RFC is public, the infrastucture we're referring to is getsentry (private) only, and any mention of specific customer issues should not be made in this spec / in the comments.

# Motivation

We want to plan about scaling Sentry in terms of traffic, and in terms of many different products. The current abuse limit is a hard cap, per project.

This worked well when Sentry had one product and ingestion facet, Errors, and decently when it introduced Sessions / Transactions. However, with the addition of Replays, and future products, this design is starting to impact our customers. This is because for Replays, we can make many requests per pageview, and take up a large percentage of the traffic alloted within the abuse limits. This is in addition to sessions, which makes one request per pageview, and often times transactions, which is one request per pageview.

The goal of the abuse limits is to protect our infrastructure, and for replays, the infrastructure (past relay) is designed to handle the type of scale beyond the current abuse limits. So if a customer **wants** to send that many replays, they should be able to, and this should not impact our other products limits.

Additionally, when these rate limits kick in they are not currently available on the stats page, which confuses both our customers and engineers, as it does not appear on the stats page at the moment.

# Background

The current abuse setup has been around for a long time. They are defined [here](https://github.com/getsentry/ops/blob/965ae4a36e134dfb3c56fff1c49dae1141663ed0/k8s/services/anti-abuse-pop/_values.yaml#L64).

# Supporting Data

There have been several customers that hit this rate limits, and we've had to work around these issues. It has caused a lot of confusion internally, as it is not well documented / well known within the company.

# Options Considered

## Option A:

Add information about the request to either the querystring, HTTP headers, or url-route, and use these in our Nginx config to do per-project rate limiting.

1. querystring: the querystring could contain a count of the envelope items. e.g. &session=1, &replay=1, &transaction=1, &error=1.
2. for HTTP headers, it could be the same except as a header. Not sure if CORS issues are a concern there.
3. url-route: We could define a different route for each envelope type, and re-write it in Nginx or add paths to Relay for each type. the URLs would be `/envelope-replays`, `/envelope-transactions`, etc. This would make the Nginx rules very straightforward.

## Option B:

Keep rate limits as they are, but attempt combine more items into single envelopes, and try to reduce the total RPS that each client makes to relay.

## Option C:

Simply increase our global rate limits, and rely more on Relay for the per-product rate limiting. Also attempt to make these rate limits show up in the stats page so there is more visibility into when this happens.

# Drawbacks

The relays downstream of the PoP are not provisioned per product, so therefore a risk of increasing the rate limit of one product impacting others is non-zero.
