- Start Date: 2026-03-09
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/153
- RFC Status: draft

# Summary

Decouple Sentry semantic conventions for attributes on Generative AI spans from OpenTelemetry to improve the stability of Sentry SDKs. The proposed conventions broadly align with the current OpenTelemetry conventions, with some ill-defined attributes removed.

The proposal also defines the types of spans SDKs are expected to emit for Generative AI systems, the operations those spans represent, and the attributes expected on each span type. Finally, it proposes a plan to stop capturing Generative AI spans not defined in this proposal.

# Motivation

Changing the semantics of attributes like `gen_ai.usage.input_tokens` invalidates data emitted by old SDK versions. In this example, the cost calculation performed downstream of the SDKs is based on conventions that were updated to align with OpenTelemetry. Changing the span attribute conventions, in this case, results in ill-formed cost estimates for users relying on old SDK versions.

# Background

OpenTelemetry semantic conventions for monitoring Generative AI systems are in development, are often underspecified, and frequently change. For example, the semantics of the `gen_ai.usage.input_tokens` attribute were ambiguous at the time Sentry added the attribute to the SDKs. Our decision to record input tokens excluding cached tokens became inconsistent with a [later update to OpenTelemetry's conventions](https://github.com/open-telemetry/semantic-conventions/commit/9d7d97ac117127662dafe3fd3094d5d660d6f3b7) that included cached tokens in the `gen_ai.usage.input_tokens` attribute.

The OpenTelemetry conventions for agent invocation spans are based on "simple" client spans. Agents are abstractions that can make multiple model calls and trigger tool calls. Frameworks like the Claude Agent SDK have a public API for changing the request model in successive model calls of an agent. While one API call to a model provider is parameterized by the model the user requests, agents, in general, do not have well-defined request or response models.

# Options Considered

Keep Sentry Generative AI conventions aligned with OpenTelemetry.

#### Pros

There is no need to normalize OpenTelemetry spans received by the OTLP endpoint to a distinct Sentry format. By keeping SDKs tightly aligned with OpenTelemetry, Sentry avoids handling the accumulated drift as the OpenTelemetry Generative AI conventions evolve.

#### Cons

Tightly coupling to the OpenTelemetry Generative AI conventions requires renaming attributes or changing attribute semantics in the SDKs as the conventions evolve. These changes are disruptive to users of the SDKs, who expect stability across SDK versions.

# Proposed Spans

The proposal keeps and more narrowly defines 3 out of the 6 types of Generative AI spans currently created by SDKs. The Invoke Agent Span, AI Client Span, and Execute Tool Span are defined in the section below, and their relationship to one another is described in the following paragraphs.

The Invoke Agent Span can be a parent of both AI Client Spans and Execute Tool Spans. Similarly, the Execute Tool Span can be the parent of both Invoke Agent Spans and AI Client Spans, since a tool call can be a function which invokes an agent or calls a model.
To invoke a tool, the model requests the tool call in its response. The agent executes the tool and provides the result as input to a subsequent model request. A typical trace in which an agent invokes a tool contains two AI Client Spans that are siblings of the Execute Tool Span. The structure is depicted below:

```
Invoke Agent
├── AI Client (requests tool call)
├── Execute Tool
└── AI Client (receives tool result)
```

The AI Client Span represents precisely one request to a model provider. The span cannot be the parent of an Execute Tool Span or an Invoke Agent Span. Generative AI spans in a trace may form subtrees such as the following:

```
Invoke Agent
├── AI Client
├── Execute Tool
│   └── (no child Generative AI spans)
├── Execute Tool
│   └── AI Client
├── Execute Tool
│   └── Invoke Agent
│       └── ...
└── AI Client
```

Attributes on the proposed spans are grouped into categories, and their types are specified in the "Proposed Attributes" section.

## AI Client Span

AI Client Spans represent a single request to a provider handled by one model and not involving tool calls.

**Note**: The operation is more narrowly scoped than [OpenTelemetry's "client AI spans"](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md). The agent invocation span must be used for any operations which can involve multiple model calls or may invoke tools.

#### Agent Attributes

| Attribute | Required |
|---|---|
| `gen_ai.agent.name` | Required if provided |
| `gen_ai.pipeline.name` | Required if provided |

#### Configuration Attributes

| Attribute | Required |
|---|---|
| `gen_ai.request.max_tokens` | Required if provided |
| `gen_ai.request.seed` | Required if provided |
| `gen_ai.request.frequency_penalty` | Required if provided |
| `gen_ai.request.presence_penalty` | Required if provided |
| `gen_ai.request.temperature` | Required if provided |
| `gen_ai.request.top_p` | Required if provided |
| `gen_ai.request.top_k` | Required if provided |

#### Input Attributes

| Attribute | Required |
|---|---|
| `gen_ai.input.messages` | Required |
| `gen_ai.request.model` | Required if provided |
| `gen_ai.system_instructions` | Required if provided |

#### Output Attributes

| Attribute | Required |
|---|---|
| `gen_ai.response.id` | Required if in the model response |
| `gen_ai.response.model` | Required if in the model response |
| `gen_ai.response.finish_reasons` | Required if in the model response |
| `gen_ai.response.streaming` | Required |
| `gen_ai.response.time_to_first_token` | Required if streaming response |

#### Token Usage

| Attribute | Required |
|---|---|
| `gen_ai.usage.input_tokens` | Required |
| `gen_ai.usage.input_tokens.cached` | Required if in the model response |
| `gen_ai.usage.input_tokens.cache_write` | Required if in the model response |
| `gen_ai.usage.output_tokens` | Required |
| `gen_ai.usage.output_tokens.reasoning` | Required if in the model response |
| `gen_ai.usage.total_tokens` | Required |

## Execute Tool Span

Describes tool executions.

#### Agent Attributes

| Attribute | Required |
|---|---|
| `gen_ai.agent.name` | Required if provided |
| `gen_ai.pipeline.name` | Required if provided |

#### Tool Attributes

| Attribute | Required |
|---|---|
| `gen_ai.tool.name` | Required |
| `gen_ai.tool.description` | Required if provided |
| `gen_ai.tool.type` | Required |
| `gen_ai.tool.call.arguments` | Required |
| `gen_ai.tool.call.result` | Required |

## Invoke Agent Span

An agent for the purposes of these conventions is an abstraction that can make multiple model calls, using data from earlier calls to inform subsequent calls, and may invoke tools. A typical agent provides the history of inputs and outputs from previous model calls in subsequent calls.

**Note**: Many attributes in the [OpenTelemetry conventions for Invoke Agent Spans](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-agent-spans.md) are ill-defined for agents that call multiple models in the course of their execution. Attributes that depend on a specific model, such as token usage attributes, are therefore not meaningful in this context and have been omitted from the proposed Sentry conventions.

#### Agent Attributes

| Attribute | Required |
|---|---|
| `gen_ai.agent.name` | Required if provided |
| `gen_ai.pipeline.name` | Required if provided |

#### Input Attributes

| Attribute | Required |
|---|---|
| `gen_ai.input.messages` | Required |
| `gen_ai.tool.definitions` | Required if provided |
| `gen_ai.system_instructions` | Required if provided |

#### Output Attributes

| Attribute | Required |
|---|---|
| `gen_ai.output.messages` | Required |
| `gen_ai.response.finish_reasons` | Required if provided |

# Deprecating Spans

Agent creation, handoff and workflow spans will be removed from the SDKs with this proposal. The spans are to be removed at the latest in the next major release of the Python and JavaScript SDKs.

Agent creation spans are currently emitted when instrumenting LangGraph with either SDK. The current instrumentation wraps a graph compilation in LangGraph, which creates the template from which agents are created. The agent creation spans currently emitted by the SDK are semantically misaligned with OpenTelemetry, which defines such spans to represent agent creation rather than graph compilation.

Handoff spans are only created by the Python SDK's instrumentation for OpenAI Agents. In the `openai-agents` package, handoffs are implemented by responding to a tool call request in the model's output. The dedicated handoff span will be replaced by an Execute Tool Span.

Workflow spans are not documented by either OpenTelemetry or the [AI Agents Insights module development guide](https://github.com/getsentry/sentry-docs/blob/master/develop-docs/sdk/telemetry/traces/modules/ai-agents.mdx), and only captured by the OpenAI Agents Python instrumentation. The span currently associates multiple agents running in the same workflow together. In the future, an agent that performs a handoff will appear as the parent of an Execute Tool Span, which itself will be the parent of the Invoke Agent Span for the agent which is handed off to.

The current `openai-agents` span tree of the form

```
transaction: "{entry_agent.name} workflow" (e.g. "primary_agent workflow")
└── Invoke Agent "invoke_agent primary_agent"
    ├── AI Client
    └── gen_ai.handoff
└── Invoke Agent "invoke_agent secondary_agent"
    └── AI Client
```

will change to

```
Invoke Agent "invoke_agent primary_agent"
├── AI Client
└── Execute Tool
    └── Invoke Agent "invoke_agent secondary_agent"
        └── AI Client
```

where the secondary agent's Invoke Agent Span continues after the primary agent's Invoke Agent Span has finished.

# Proposed Attributes

The attribute definitions follow the [OpenTelemetry definitions](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-agent-spans.md) at the time this proposal is accepted. If an attribute is not included, its definition is provided by the [AI Agents Insights module development guide](https://github.com/getsentry/sentry-docs/blob/master/develop-docs/sdk/telemetry/traces/modules/ai-agents.mdx).

#### Agent Attributes

| Attribute | Type |
|---|---|
| `gen_ai.agent.name` | string |
| `gen_ai.pipeline.name` | string |

#### Input Attributes

| Attribute | Type |
|---|---|
| `gen_ai.input.messages` | object |
| `gen_ai.request.model` | string |
| `gen_ai.tool.definitions` | object |
| `gen_ai.system_instructions` | object |

#### Configuration Attributes

| Attribute | Type |
|---|---|
| `gen_ai.request.max_tokens` | integer |
| `gen_ai.request.seed` | integer |
| `gen_ai.request.frequency_penalty` | double |
| `gen_ai.request.presence_penalty` | double |
| `gen_ai.request.temperature` | double |
| `gen_ai.request.top_p` | double |
| `gen_ai.request.top_k` | integer |

#### Output Attributes

| Attribute | Type |
|---|---|
| `gen_ai.output.messages` | object |
| `gen_ai.response.model` | string |
| `gen_ai.response.finish_reasons` | string[] |
| `gen_ai.response.id` | string |
| `gen_ai.response.streaming` | boolean |
| `gen_ai.response.time_to_first_token` | double |

#### Token Usage

| Attribute | Type |
|---|---|
| `gen_ai.usage.input_tokens` | integer |
| `gen_ai.usage.input_tokens.cached` | integer |
| `gen_ai.usage.input_tokens.cache_write` | integer |
| `gen_ai.usage.output_tokens` | integer |
| `gen_ai.usage.output_tokens.reasoning` | integer |
| `gen_ai.usage.total_tokens` | integer |

#### Tool Attributes

| Attribute | Type |
|---|---|
| `gen_ai.tool.name` | string |
| `gen_ai.tool.description` | string |
| `gen_ai.tool.type` | string |
| `gen_ai.tool.call.arguments` | object |
| `gen_ai.tool.call.result` | object |

# Unresolved questions

Attributes with the `object` type follow specific JSON schemas. Their transport format and detailed schemas are not defined by this proposal. Unless explicitly defined otherwise in a future proposal, they must conform to the OpenTelemetry schemas for the respective attributes.
