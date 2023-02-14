- Start Date: 2023-02-01
- RFC Type: feature
- RFC PR: https://github.com/getsentry/sentry-kafka-schemas/pull/2
- RFC Status: draft

# Summary

This RFC proposes introducing a centralized schema repository for the Kafka topics in use at Sentry. It provides mappings between the Kafka topics we are using to the encoding format and schemas for messages on that topic.

Topic registration and schema validation of messages will be optional for the foreseeable future.

# Motivation

Kafka is increasingly used as the message bus between services at Sentry. Kafka topics and their schemas are usually not internal to any one service, but part of the contract between services.

As Sentry grows, the number of message types and topics in use is exploding. We are marching further towards increasingly distributed ownership of data by product and infrastructure engineering teams. We have already seen an increase in the number of incidents related with invalid data and schema issues at Sentry. It is reasonable to expect this trend to continue as the number of topics, data types, teams and engineers contributing to Sentry grows.

The goals of the centralized schema repository are to:

- provide an explicit, single source of truth about how data in any given topic should look, and the contract that all consumers and producers of a topic must adhere to
- provide more stability by enforcing backward compatibility of changes via automation
- explicitly enumerate ownership of schemas
- make it easier for consumers to identify and reject bad messages without pausing the whole pipeline
- provide examples of messages for each schema type, which would help with writing consumer tests

# Supporting Data

Over the last quarter, we have seen many incidents related to schema disagreements at Sentry. Examples include the following: (note: inc numbers are internal to Sentry)

- Post process forwarder (INC-218)
- Snuba’s transactions consumer (INC-210)
- Super big consumers (INC-220)
- Replays consumer (INC-250, INC-281)

Many of these incidents are P1. Since messages are in order, an invalid message often halts consumers and requires manual intervention. This is disruptive to both Sentry engineers and our users (it takes us much longer to recover).

# Options Considered

### **Option A (preferred): Publish a library**

Schemas will be made available as a library for multiple programming languages (Python and Rust to start).

**Client usage example:**

```python
from sentry_kafka_schemas import get_schema

topic = "events"
schema = get_schema(topic)
# => {
# 	"type": "json"
# 	"version": 1,
# 	"schema": {
# 		"$schema": "http://json-schema.org/draft-07/schema#",
# 		"compatibility_mode": "backward",
# 		"type": "object",
# 		...
# 	}
# }

# Get a specific version of the schema
v1_schema = get_schema(topic, version=1)
```

**How schemas are stored:**

Topic data will be stored as yaml. For example:

```
topic: events
schemas:
    - version: 1
    compatibility_mode: backward
    type: json
    resource: events.schema.json
    - version: 2
    compatibility_mode: none
    type: avro
    resource: events_v2.avsc
```

In this example scenario, we decided to make a change to schemas on the “events” topic. The `events.schema.json` and `events_v2.avsc` files must be present.

**Compatibility modes:**

Each schema version defines it's compatibility mode. There will be 2 to start but more can be added if we want to change or tighten the rules.

- `none` - Any changes are allowed. Generally used if a feature is in dev to allow for fast iteration and breaking changes.
- `backward` - Allows adding optional fields, removing optional fields, and changing from optional to required and required to optional. Required field cannot be added at once, it must be split into 2 separate releases.

If `backward` is selected, CI in the schemas repository will ensure changes that are not allowed are not being introduced with a same version number

### **Option B (alternative, non-preferred option): Deploy a separate service**

No library is provided. Clients fetch data from the schemas service and need to know how to parse the schema from the response by themselves. The schemas service could either be built from scratch or we could deploy an existing open source implementation such as Confluent schema registry.

**Example usage:**

```bash
GET /schemas/events
GET /schemas/events?version=1
```

Or, using the Confluent schema registry API

```bash
GET /subjects/events/versions
GET /schemas/ids/123/schema

# Creating schemas. Unlike other options presented, schemas are not checked into code
POST /subjects/events/version/
{
    "schema": {"type": .........}
}
```

Unlike Option A, consumer and producer code should be updated automatically when a new version of the schemas service is deployed. This requires consumers and producers to frequently check for updates to the schema to stay in sync. If using the Confluent API, there are libraries to manage this. There are additional complexities of adding another service, like network access to the schema service and schema service capacity to figure out.

# Drawbacks

- We expect a significant performance hit if we were to validate every message in Python consumers (and producers). This has not yet been benchmarked for the various shapes of messages we process. Even with multiprocessing, we may have to sample or not validate in every scenario
- Additional step involved in making schema changes to Kafka topics
- Option B in particular adds quite a bit of additional overhead to Sentry’s infrastructure and would need to be shipped in all environments: all regions, open source, dev, CI and single tenant installations.
