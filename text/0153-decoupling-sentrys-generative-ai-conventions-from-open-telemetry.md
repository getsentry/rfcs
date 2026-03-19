- Start Date: 2026-03-09
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/153
- RFC Status: draft

# Summary

Decouple Sentry semantic conventions for attributes on Generative AI spans from OpenTelemetry to improve the stability of Sentry SDKs. The proposed conventions broadly align with the current OpenTelemetry conventions, with some ill-defined and redundant attributes omitted.

The proposal also defines the types of spans SDKs are expected to emit for Generative AI systems, the operations those spans represent, and the attributes expected on each span type. It sets requirements to remove truncation and to stop capturing Generative AI spans not defined in this proposal. Finally, the document sketches how a typical agent application is manually instrumented.

# Motivation

Changing the semantics of attributes like `gen_ai.usage.input_tokens` invalidates data emitted by old SDK versions. In this example, the cost calculation performed downstream of the SDKs is based on conventions that were updated to align with OpenTelemetry. Changing the span attribute conventions, in this case, results in ill-formed cost estimates for users relying on old SDK versions.

# Background

OpenTelemetry semantic conventions for monitoring Generative AI systems are in development, are often underspecified, and frequently change. For example, the semantics of the `gen_ai.usage.input_tokens` attribute were ambiguous at the time Sentry added the attribute to the SDKs. Our decision to record input tokens excluding cached tokens became inconsistent with a [later update to OpenTelemetry's conventions](https://github.com/open-telemetry/semantic-conventions/commit/9d7d97ac117127662dafe3fd3094d5d660d6f3b7) that included cached tokens in the `gen_ai.usage.input_tokens` attribute.

The OpenTelemetry conventions for agent invocation spans are based on "simple" client spans. Agents are abstractions that can make multiple model calls and trigger tool calls. Frameworks like the Claude Agent SDK have a public API for changing the request model in successive model calls of an agent. While one API call to a model provider is parameterized by the model the user requests, agents, in general, do not have well-defined request or response models.

[OpenTelemetry's "Inference" span type](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md#inference) encapsulates diverse operations, including chat endpoints with structured roles and text completion endpoints without structured roles. The input and output formats depend on whether the endpoint uses roles such as "system", "user" and "assistant" or not.

Many OpenTelemetry attributes are redundant. A Generative AI application instrumented according to OpenTelemetry conventions sends the same information multiple times. An example is the redundancy between the `gen_ai.response.finish_reasons` attribute and finish reasons in the `gen_ai.output.messages` attribute. Storing information on multiple attributes results in inconsistencies.

# Options Considered

Keep Sentry Generative AI conventions aligned with OpenTelemetry.

#### Pros

There is no need to normalize OpenTelemetry spans received by the OTLP endpoint to a distinct Sentry format. By keeping SDKs tightly aligned with OpenTelemetry, Sentry avoids handling the accumulated drift as the OpenTelemetry Generative AI conventions evolve.

#### Cons

Tightly coupling to the OpenTelemetry Generative AI conventions requires renaming attributes or changing attribute semantics in the SDKs as the conventions evolve. These changes are disruptive to users of the SDKs, who expect stability across SDK versions.

# Proposed Spans

The proposal keeps and more narrowly defines 5 out of the 8 types of Generative AI spans currently created by SDKs. The Invoke Agent Span, AI Client Span, Text Completion Span, Embedding Span, and Execute Tool Span are defined in the section below, and their relationship to one another is described in the following paragraphs.

The Invoke Agent Span can be a parent of AI Client Spans, Text Completion Spans, Embedding Spans, and Execute Tool Spans. Similarly, the Execute Tool Span can be the parent of Invoke Agent Spans, AI Client Spans, Text Completion Spans, and Embedding Spans, since a tool call can be a function which invokes an agent or calls a model.
To invoke a tool, the model requests the tool call in its response. The agent executes the tool and provides the result as input to a subsequent model request. A typical trace in which an agent invokes a tool contains two AI Client Spans that are siblings of the Execute Tool Span. The structure is depicted below:

```
Invoke Agent
├── AI Client (requests tool call)
├── Execute Tool
└── AI Client (receives tool result)
```

The AI Client Span, Text Completion Span, and the Embedding Span represent precisely one request to a model provider. The spans cannot be the parent of an Execute Tool Span or an Invoke Agent Span. Generative AI spans in a trace may form subtrees such as the following:

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

AI Client Spans represent one request with structured roles to a provider handled by a single model without invoking tool calls. Tool call execution must not fall under AI Client Spans. A tool call request can be captured in the model's output or a tool call response can be captured by its input. Embedding and text completion requests to model providers are traced by other span types.

**Note**: The operation is more narrowly scoped than [OpenTelemetry's "client AI spans"](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md). The agent invocation span must be used for any operations which can involve multiple model calls or may invoke tools.

#### Meta Attributes

| Attribute | Required |
|---|---|
| `gen_ai.operation.name` | Required |
| `gen_ai.provider.name` | Required |

#### Conversation Attributes

| Attribute | Required |
|---|---|
| `gen_ai.conversation.id` | Required if state re-used in another trace |

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
| `gen_ai.tool.definitions` | Required if provided |
| `gen_ai.request.model` | Required if provided |
| `gen_ai.system_instructions` | Required if provided |

#### Output Attributes

| Attribute | Required |
|---|---|
| `gen_ai.output.messages` | Required |
| `gen_ai.response.id` | Required if in the model response |
| `gen_ai.response.model` | Required if in the model response |
| `gen_ai.response.finish_reasons` | Required if in the model response |
| `gen_ai.response.streaming` | Required |
| `gen_ai.response.time_to_first_token` | Required if streaming response |

#### Token Usage Attribute

| Attribute | Required |
|---|---|
| `gen_ai.usage.input_tokens` | Required |
| `gen_ai.usage.input_tokens.cached` | Required if in the model response |
| `gen_ai.usage.input_tokens.cache_write` | Required if in the model response |
| `gen_ai.usage.output_tokens` | Required |
| `gen_ai.usage.output_tokens.reasoning` | Required if in the model response |
| `gen_ai.usage.total_tokens` | Required |

## Text Completion Span

Text Completion Spans represent one request to a provider to complete an input string.

#### Meta Attributes

| Attribute | Required |
|---|---|
| `gen_ai.operation.name` | Required |
| `gen_ai.provider.name` | Required |

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
| `gen_ai.text_completion.input` | Required |
| `gen_ai.request.model` | Required if provided |

#### Output Attributes

| Attribute | Required |
|---|---|
| `gen_ai.text_completion.output` | Required |
| `gen_ai.response.id` | Required if in the model response |
| `gen_ai.response.model` | Required if in the model response |
| `gen_ai.response.finish_reasons` | Required if in the model response |
| `gen_ai.response.streaming` | Required |
| `gen_ai.response.time_to_first_token` | Required if streaming response |

#### Token Usage Attributes

| Attribute | Required |
|---|---|
| `gen_ai.usage.input_tokens` | Required |
| `gen_ai.usage.input_tokens.cached` | Required if in the model response |
| `gen_ai.usage.input_tokens.cache_write` | Required if in the model response |
| `gen_ai.usage.output_tokens` | Required |
| `gen_ai.usage.output_tokens.reasoning` | Required if in the model response |
| `gen_ai.usage.total_tokens` | Required |

## Embedding Span

Embedding Spans represent one request to a provider to encode input into numeric vector embeddings.

#### Meta Attributes

| Attribute | Required |
|---|---|
| `gen_ai.operation.name` | Required |
| `gen_ai.provider.name` | Required |

#### Agent Attributes

| Attribute | Required |
|---|---|
| `gen_ai.agent.name` | Required if provided |
| `gen_ai.pipeline.name` | Required if provided |

#### Input Attributes

| Attribute | Required |
|---|---|
| `gen_ai.embeddings.input` | Required |
| `gen_ai.request.model` | Required if provided |
| `gen_ai.request.encoding_formats` | Required if provided |

#### Output Attributes

| Attribute | Required |
|---|---|
| `gen_ai.response.id` | Required if in the model response |
| `gen_ai.response.model` | Required if in the model response |
| `gen_ai.embeddings.dimension.count` | Required |

#### Token Usage Attributes

| Attribute | Required |
|---|---|
| `gen_ai.usage.input_tokens` | Required |

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
| `gen_ai.tool.call.id` | Required if present |
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
| `gen_ai.system_instructions` | Required if provided |

#### Output Attributes

| Attribute | Required |
|---|---|
| `gen_ai.output.messages` | Required |

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

#### Meta Attributes

| Attribute | Required |
|---|---|
| `gen_ai.operation.name` | string |
| `gen_ai.provider.name` | string |

#### Conversation Attributes

| Attribute | Required |
|---|---|
| `gen_ai.conversation.id` | string |


#### Agent Attributes

| Attribute | Type |
|---|---|
| `gen_ai.agent.name` | string |
| `gen_ai.pipeline.name` | string |

#### Input Attributes

| Attribute | Type |
|---|---|
| `gen_ai.input.messages` | object |
| `gen_ai.text_completion.input` | string[] |
| `gen_ai.embeddings.input` | object |
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
| `gen_ai.text_completion.output` | string[] |
| `gen_ai.embeddings.dimension.count` | integer[] |
| `gen_ai.response.model` | string |
| `gen_ai.response.finish_reasons` | string[] |
| `gen_ai.response.id` | string |
| `gen_ai.response.streaming` | boolean |
| `gen_ai.response.time_to_first_token` | double |

#### Token Usage Attributes

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
| `gen_ai.tool.call.id` | string |
| `gen_ai.tool.name` | string |
| `gen_ai.tool.description` | string |
| `gen_ai.tool.type` | string |
| `gen_ai.tool.call.arguments` | object |
| `gen_ai.tool.call.result` | object |

# JSON Attributes

## gen_ai.input.messages

The input array contains items with a role, parts, and an optional name of the entity that created an item:
```json
[
    {
        "role": "user",
        "parts": [...],
        "name": "participant_identifier",
    },
    ...
]
```
The role should be "user", "assistant", or "tool". Assistant messages are model outputs, including tool call requests. The "tool" role is used for tool execution results passed back to a model. All other items that are not system instructions must use the "user" role.

The SDKs will map the provider's role names to the above set when the provider uses different names for roles that correspond to "user", "assistant", or "tool".
If the user provides an input item with an unexpected role, the SDK will not perform any conversion, and set the user-provided string as the role.

**Note**: Not all items will have a "user", "assistant", or "tool" role. SDKs must emit unexpected user-provided roles.

Allowed input part types will be recorded in the [AI Agents Insights module development guide](https://github.com/getsentry/sentry-docs/blob/master/develop-docs/sdk/telemetry/traces/modules/ai-agents.mdx).

Any content which will not be searched, such as binary image data, must be added as span attachments.

**Note**: SDKs currently truncate various Generative AI attributes and redact binary content. When Generative AI spans are emitted using the V2 span protocol, all truncation or redaction must have been removed. The V2 protocol is used by span-first SDKs.

Automatic instrumentation should avoid destructively trimming information, i.e., removing information that is not present on any other span. Instrumentation should also not unnecessarily duplicate the message history between successive model calls.
SDKs will therefore keep all input items starting with the **last** assistant message in the model input.

**Note**: There is no guarantee that the input items passed to a model that were not present in preceding model calls are the items starting with the last assistant message passed to a model. In a typical agent loop the invariant holds, as the history is updated and fed into subsequent model calls.

## gen_ai.embeddings.input

The attribute is a union discriminated by the type property. The type property is one of "text", "texts", "tokens", or "token_batches".

If the type is "text", then the value is a simple string, as in

```json
{
    "type": "text",
    "value": "Hello, world!",
}
```

If the type is "texts", the value is a string array, as in

```json
{
    "type": "texts",
    "value": ["First text", "Second text", "Third text"],
}
```

If the type is "tokens", then the value is an array of integers, as in

```json
{
    "type": "tokens",
    "value": [5, 8, 13, 21, 34],
}
```

Finally, if the type is "token_batches", then the value is a 2-dimensional array of integers, as in

```json
{
    "type": "token_batches",
    "value": [[5, 8, 13, 21, 34], [8, 13, 21, 34, 55]],
}
```

## gen_ai.tool.definitions

Tool definitions are represented as a JSON array with objects whose "name", "description" and "type" properties correspond to the attributes on Execute Tool Spans. The objects also have a "parameters" property, which maps parameter names to their type.

Each tool definition has a name, type, parameters, and an optional description:

```json
[
    {
        "name": "get_weather",
        "description": "Get the current weather for a given location.",
        "type": "function",
        "parameters": {
            "location": "string"
        }
    },
    ...
]
```

## gen_ai.system_instructions

System instructions are a flat list of parts identified by a "type" key:
```json
[
    {
        "type": "text",
        "content": "You are a helpful assistant.",
    },
    ...
]
```
System instructions can be represented with the same input part types as `gen_ai.input.messages`.

## gen_ai.output.messages

The output array contains items with a role, parts, and an optional name of the entity that created an item:
```json
[
    {
        "role": "assistant",
        "parts": [...],
    },
    ...
]
```
Each item in the array represents a candidate generation from the model, also referred to as a choice. All items are generated based on the same input.

**Note**: The [OpenTelemetry output schema](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-output-messages.json) includes a mandatory `finish_reason` property for each candidate generation. The `gen_ai.response.finish_reasons` attribute already records one finish reason per candidate response, and the Sentry conventions purposefully do not require duplicating finish reasons in the output array.

Allowed output part types will be recorded in the [AI Agents Insights module development guide](https://github.com/getsentry/sentry-docs/blob/master/develop-docs/sdk/telemetry/traces/modules/ai-agents.mdx).

## gen_ai.tool.call.arguments

Arguments are represented as a JSON object. Top-level keys correspond to tool call parameter names, and top-level values are the corresponding arguments. The arguments must be serialized as a primitive JSON value, JSON object, or JSON array:

```json
{
    "id": "1234",
    "complex_input": {...}
}
```

## gen_ai.tool.call.result

The tool call result must be serialized as the most appropriate JSON representation.

# Manual Instrumentation

Start with the following schematic example of an application in which an agent loop is built around successive calls to a chat API, and the agent has access to a tool.

```python
def chat(system_instructions, model_parameters, conversation_id, message_history):
    model_response = api_call(system_instructions, model_parameters, conversation_id, message_history)
    ...
    return model_response


def tool():
    ...


def agent_turn(system_instructions, model_parameters, conversation_id, message_history):
    new_messages = []

    response = chat(system_instructions, model_parameters, conversation_id, message_history)
    new_messages.append(response)    

    if has_tool_request(response):
        tool_output = tool(response)
        new_messages.append(tool_output)

    return new_messages

def agent_loop(system_instructions, model_parameters, conversation_id):
    message_history = []
    while True:
        new_messages = agent_turn(system_instructions, model_parameters, conversation_id, message_history)
        message_history += new_messages

        if terminal_condition(message_history):
            return message_history[-1]
```

The application can be instrumented as follows. Not all required attributes are set on each span. Instead, the code below focuses on the overall span hierarchy and a few illustrative attributes.

```python
from sentry_sdk.tracing import start_span

def chat(system_instructions, model_parameters, conversation_id, message_history):
    with start_span() as ai_client_span:
        # Meta attributes
        ai_client_span.set_attribute("gen_ai.operation.name", "chat")
        ...

        # Conversation attributes
        ai_client_span.set_attribute("gen_ai.conversation.id", conversation_id)
        ...

        # Agent attributes
        ai_client_span.set_attribute("gen_ai.agent.name", "example agent")
        ...

        # Configuration attributes
        ai_client_span.set_attribute("gen_ai.request.max_tokens", 16)
        ...

        # Input attributes
        messages = get_messages_starting_from_last_assistant_messages(message_history)
        ai_client_span.set_attribute("gen_ai.input.messages", messages)
        ...

        model_response = api_call(system_instructions, model_parameters, conversation_id, message_history)

        # Output attributes
        ai_client_span.set_attribute("gen_ai.response.model", model_response.response_model)
        ...

        # Token attributes
        ai_client_span.set_attribute("gen_ai.usage.input_tokens", model_response.input_tokens)
        ...


def tool():
    with start_span() as tool_span:
        # Agent attributes
        tool_span.set_attribute("gen_ai.agent.name", "example agent")
        ...

        # Tool attributes
        tool_span.set_attribute("gen_ai.tool.name", "example tool")
        ...


def agent_turn(system_instructions, model_parameters, conversation_id, message_history):
    new_messages = []

    response = chat(system_instructions, model_parameters, conversation_id, message_history)
    new_messages.append(response)    

    if has_tool_request(response):
        tool_output = tool(response)
        new_messages.append(tool_output)

    return new_messages

def agent_loop(system_instructions, user_input, model_parameters, conversation_id):
    message_history = [user_input]

    with start_span() as agent_span:        
        # Agent attributes
        agent_span.set_attribute("gen_ai.agent.name", "example agent")
        ...

        # Input attributes
        agent_span.set_attribute("gen_ai.input.messages", user_input)
        ...

        while True:
            new_messages = agent_turn(system_instructions, model_parameters, conversation_id, message_history)
            message_history += new_messages

            if terminal_condition(message_history):
                # Output attributes
                agent_span.set_attribute("gen_ai.output.messages", [message_history[-1]])
                ...

                return message_history[-1]
```
