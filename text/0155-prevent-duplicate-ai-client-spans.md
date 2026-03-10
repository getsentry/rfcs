- Start Date: 2026-03-09
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/155
- RFC Status: draft

# Summary

Define a mechanism for avoiding duplicate AI Client Spans when agent libraries call instrumented model provider client libraries.

# Motivation

Many statistics displayed in the AI Agents Insights module are based on AI Client Spans. Statistics, including the total incurred cost, require all model calls to be instrumented with AI Client Spans exactly once. Model calls initiated by agents are always instrumented in agent libraries to support users of an agent library with a model provider not yet supported by the corresponding SDK. Conversely, "low-level" libraries of model providers are also instrumented with AI Client Spans to support users who call models outside of a supported agent framework.

Users of a supported agent framework with a supported model provider therefore generate two AI Client Spans, resulting in biased statistics in the AI Agents Insights module.

# Background

Generative AI libraries can be categorized into client and agent libraries. Client libraries like the `openai`, `anthropic` and `google-genai` Python packages are language-specific wrappers for calling the endpoints serving models from the respective providers. Agent libraries provide abstractions that trigger multiple model calls, and give users the ability to define tools. Examples of such libraries include the `openai-agents`, `langchain` and `pydantic-ai` Python packages.

Agent libraries typically provide an interface that lets the user define the code executed when an agent performs a model call. When these functions make use of an instrumented client library, two AI Client Spans are created. At the moment an API call to a model provider is triggered, the agent invocation call stack has the following structure:

```
Invoke agent
└── Agent library model call
    └── Client library model call
        └── API call
```

Some data exposed by the client library is not available at the agent's model abstraction level. For example, the concrete response model used to populate the `gen_ai.response.model` attribute is always available in the `openai` package, but never returned by the `Model` abstraction used by agents in the `openai-agents` package.

# Options Considered

- [Option 1: Global client library disabling](#option-1)
- [Option 2: Disabling agent library spans based on the request model](#option-2)
- [Option 3: Dropping AI Client Spans when the parent is an AI Client Span](#option-3)
- [Option 4: [Preferred] Dropping duplicate AI Client spans under a scope](#option-4)

## Option 1: Global client library disabling <a name="option-1"></a>

The solution automatically disables client library instrumentation when an agent library emits spans, unless the user explicitly overrides the behavior.

#### Pros

The solution is currently implemented by the SDKs.

#### Cons

Client libraries are used alongside agent libraries. A global mechanism that disables AI Client Spans for these libraries leads to under-reporting of AI Client Spans, and biases the statistics shown in the AI Agents Insights module.

Explicitly overriding the disabling mechanism results in the creation of two AI Client Spans when an instrumented agent calls an instrumented model provider. This also biases the statistics.

## Option 2: Disabling agent library spans based on the request model <a name="option-2"></a>

Maintain a global list that associates common request models, like `gpt-4-mini`, to their providers. Use the list to disable AI Client Spans in the instrumentation for the agent library when the provider corresponding to a request model is supported by the SDK.

#### Pros

More information used to populate the attributes of AI Client Spans is available in the client library than in the agent library abstraction.

#### Cons

There is no universal mapping from requested model to provider that stays up to date as new models are released. Old SDK versions must function with new models to avoid biasing the summary statistics in the AI Agents Insights module.

## Option 3: Dropping AI Client Spans when the parent is an AI Client Span <a name="option-3"></a>

The `start_span()` API attaches the new span as a child of an active span if present. The solution would check if the active span is an AI Client Span. If the active span is an AI Client Span, exit `start_span()` early instead of creating an AI Client Span.

#### Pros

The solution is the easiest to implement.

#### Cons

Disabling spans at the client library level results in a loss of information when the agent library's abstractions expose less information about model calls, and there is no mechanism to capture information from the client library.

Additionally, since the model abstraction used by an agent may contain user-defined code, there can be spans in between the AI Client Spans for the agent and client library. The parent-aware disabling only applies if there are no spans in between AI Client Spans in the trace hierarchy.

## Option 4: [Preferred] Dropping duplicate AI Client spans under a scope <a name="option-4"></a>

Use the existing SDK scope mechanism. There are two possible implementation depending on whether the SDK must capture information from client libraries that is not available in a supported agent framework. If information must be propagated, a new AI Client Scope class must be created. If not, a boolean flag can be added on the scope to indicate whether an AI Client Span has already be created while the scope has been active.

For the AI Client Scope solution, run the code that the agent uses to invoke a model under the AI Client Scope. If the current scope is an AI Client Scope when `start_span()` is invoked in the client library instrumentation, set AI Client Span attributes on the existing AI Client Span. Otherwise, create an AI Client Span before setting attributes on the span in the client library instrumentation.

For the boolean flag solution, add a boolean flag that is true precisely when an AI Client Span has been created within the scope. When `start_span()` is invoked in a client library and the flag is true, then `start_span()` must exit early. Otherwise, `start_span()` creates the span and sets relevant attributes.

#### Pros

Information that only exists at the client library level can be attached to the span created by instrumentation of the agent library. Information like the response model that was previously missing at the agent abstraction level is set on the agent library's AI Client Span.

#### Cons

The solution introduces complexity to the SDK. An integration would mutate the attributes set on a span created by another integration when the agent and client libraries are both instrumented.
