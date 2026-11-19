"""Project private histories into Inspect and preserve their OpenRouter wire representation."""

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from inspect_ai.event import ModelEvent
from inspect_ai.log import transcript
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    GenerateConfig,
    Model,
    ModelOutput,
    StreamEvent,
    StreamReasoningEvent,
    StreamRetryEvent,
    StreamToolCallEvent,
    active_model_event_id,
)
from inspect_ai.tool import ToolCall, ToolInfo

from multi_agent_shutdown_sabotage.tools import TOOL_SCHEMAS


class TransportFidelityError(RuntimeError):
    """The provider did not expose raw tool arguments needed for faithful parsing."""


def check_openrouter_error(output: ModelOutput) -> None:
    """Recover hard failures converted to synthetic completions by Inspect."""
    # A successful OpenRouter chat completion carries the provider's response ID,
    # including when a real completion ends with content_filter.
    if output.response_id is None and output.stop_reason in {"model_length", "content_filter"}:
        raise RuntimeError(output.error or output.message.text or output.stop_reason)


def inspect_history(history: list[dict[str, Any]]) -> list[ChatMessage]:
    """Convert one private history without mutating it or adding another agent's data."""
    messages: list[ChatMessage] = []
    for entry in history:
        role = entry["role"]
        content = entry.get("content", "")
        if role == "system":
            messages.append(ChatMessageSystem(content=content))
        elif role == "user":
            # Inspect transcript projection. OpenRouter receives the original below.
            metadata = {"reference_name": entry["name"]} if "name" in entry else None
            messages.append(ChatMessageUser(content=content, metadata=metadata))
        elif role == "tool":
            # An off-schema send can return a non-string reply to the starting agent.
            display = content if isinstance(content, str) else json.dumps(content)
            messages.append(ChatMessageTool(content=display, tool_call_id=entry["tool_call_id"]))
        else:
            calls = []
            for call in entry.get("tool_calls", []):
                fn = call["function"]
                try:
                    args = json.loads(fn["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                # Inspect's ToolCall requires an object. Valid non-object JSON is
                # retained in the raw history; the reference loop may itself raise.
                calls.append(
                    ToolCall(
                        id=call["id"],
                        function=fn["name"],
                        arguments=args if isinstance(args, dict) else {},
                    )
                )
            messages.append(ChatMessageAssistant(content=content, tool_calls=calls or None))
    return messages


@dataclass
class Completion:
    """One normalized completion, with raw argument text for the retained first call."""

    content: str | None
    reasoning: str | None
    tool_calls: list[dict[str, Any]]
    dropped_tool_calls: int
    finish_reason: str
    output: ModelOutput


async def complete(
    model: Model, history: list[dict[str, Any]], tools: list[str] | list[dict[str, Any]]
) -> Completion:
    """Generate once; Inspect owns transport retries, never the activation budget."""
    openrouter = str(model).startswith("openrouter/")
    fragments: list[StreamToolCallEvent] = []
    reasoning_fragments: list[str] = []
    event_id = None

    async def capture(event: StreamEvent) -> None:
        nonlocal event_id
        if isinstance(event, StreamRetryEvent):
            fragments.clear()
            reasoning_fragments.clear()
        elif isinstance(event, StreamReasoningEvent):
            reasoning_fragments.append(event.reasoning)
        elif isinstance(event, StreamToolCallEvent):
            fragments.append(event)
            if openrouter:
                event_id = active_model_event_id()

    definitions = [TOOL_SCHEMAS[item] if isinstance(item, str) else item for item in tools]
    extra_body: dict[str, Any] = {"reasoning": {"enabled": True}}
    if openrouter:
        # OpenAI merges extra_body after serializing its typed request. Forward
        # the raw arrays to retain absent keys, user names and argument strings.
        extra_body.update(messages=deepcopy(history), tools=deepcopy(definitions))

    schemas = []
    for definition in definitions:
        function = definition["function"]
        schema = ToolInfo.model_validate(deepcopy(function))
        # ToolParams otherwise adds additionalProperties=False, absent upstream.
        schema.parameters.additionalProperties = None
        schemas.append(schema)
    output = await model.generate(
        input=inspect_history(history),
        tools=schemas,
        tool_choice="auto",
        config=GenerateConfig(
            temperature=1.0,
            parallel_tool_calls=False,
            reasoning_history="none",
            extra_body=extra_body,
            cache_prompt=False,
            max_retries=3,
            stream_idle_timeout=180,
        ),
        cache=False,
        on_stream=capture,
    )
    if openrouter:
        check_openrouter_error(output)
    choice = output.choices[0]
    message = choice.message
    content = message.text or None
    reasoning = None
    if openrouter:
        # The harness reads plain reasoning / reasoning_content deltas only.
        reasoning = "".join(reasoning_fragments) or None
    elif isinstance(message.content, list):
        reasoning = "".join(c.reasoning for c in message.content if c.type == "reasoning") or None
    calls = message.tool_calls or []
    retained = []
    for call in calls[:1]:
        arguments = _first_arguments(call, calls, fragments, event_id)
        retained.append({"id": call.id, "name": call.function, "arguments": arguments})
    return Completion(
        content,
        reasoning,
        retained,
        max(0, len(calls) - 1),
        "length" if openrouter and choice.stop_reason == "max_tokens" else choice.stop_reason,
        output,
    )


def _first_arguments(
    first: ToolCall,
    calls: list[ToolCall],
    fragments: list[StreamToolCallEvent],
    event_id: str | None,
) -> str:
    # Inspect's OpenAI stream reporter carries id and function forward by
    # source index, but does not expose the index itself. IDs can be reused.
    matching = [call for call in calls if call.id == first.id]
    if len(matching) > 1:
        if len(fragments) == len(calls) and all(
            (fragment.id, fragment.function) == (call.id, call.function)
            for fragment, call in zip(fragments, calls, strict=True)
        ):
            return fragments[0].arguments
        if sum(call.function == first.function for call in matching) == 1:
            same_id = [fragment for fragment in fragments if fragment.id == first.id]
            if any(f.function == first.function for f in same_id) and all(
                f.function is not None for f in same_id
            ):
                return "".join(f.arguments for f in same_id if f.function == first.function)
        # An OpenRouter ModelCall retains the SDK's index-assembled slots.
        # Match this exact generation; another sample or retry is never an oracle.
        indexed = _indexed_arguments(event_id, first)
        if indexed is not None:
            return indexed
        raise TransportFidelityError(
            "Repeated tool-call IDs with ambiguous fragments and no stream index"
        )

    parts: list[str] = []
    last_id = None
    for fragment in fragments:
        if fragment.id is not None:
            last_id = fragment.id
        if last_id == first.id:
            parts.append(fragment.arguments)
    if not parts:
        raise TransportFidelityError(
            "Raw streaming arguments unavailable for tool call; cannot reproduce reference JSON parsing."
        )
    return "".join(parts)


def _indexed_arguments(event_id: str | None, first: ToolCall) -> str | None:
    if event_id is None:
        return None
    log = transcript()
    event = next((e for e in reversed(log.history.resident_events) if e.uuid == event_id), None)
    if not isinstance(event, ModelEvent) or not event.call or not event.call.response:
        return None
    response: dict[str, Any] = event.call.response
    slot = response["choices"][0]["message"]["tool_calls"][0]
    function = slot["function"]
    if slot["id"] == first.id and function["name"] == first.function:
        raw = function["arguments"]
        if isinstance(raw, str):
            if raw.startswith("attachment://"):
                return log.attachments.get(raw.removeprefix("attachment://"), raw)
            return raw
    return None
