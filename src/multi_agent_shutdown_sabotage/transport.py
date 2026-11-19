"""Adapt reference histories to Inspect's public model API.

Raw histories remain authoritative. Inspect cannot replay a user ``name`` or raw
malformed JSON arguments verbatim; see README fidelity notes.
"""

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

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
    StreamRetryEvent,
    StreamToolCallEvent,
)
from inspect_ai.tool import ToolCall, ToolInfo

from multi_agent_shutdown_sabotage.tools import TOOL_SCHEMAS


class TransportFidelityError(RuntimeError):
    """The provider did not expose raw tool arguments needed for faithful parsing."""


def inspect_history(history: list[dict[str, Any]]) -> list[ChatMessage]:
    """Convert one private history without mutating it or adding another agent's data."""
    messages: list[ChatMessage] = []
    for entry in history:
        role = entry["role"]
        content = entry.get("content", "")
        if role == "system":
            messages.append(ChatMessageSystem(content=content))
        elif role == "user":
            # Metadata preserves provenance, but is not a wire-level user name.
            metadata = {"reference_name": entry["name"]} if "name" in entry else None
            messages.append(ChatMessageUser(content=content, metadata=metadata))
        elif role == "tool":
            messages.append(ChatMessageTool(content=content, tool_call_id=entry["tool_call_id"]))
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
                calls.append(ToolCall(id=call["id"], function=fn["name"], arguments=args))
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
    raw: dict[str, str] = {}
    last_id: str | None = None

    async def capture(event: StreamEvent) -> None:
        nonlocal last_id
        if isinstance(event, StreamRetryEvent):
            raw.clear()
            last_id = None
        elif isinstance(event, StreamToolCallEvent):
            if event.id is not None:
                last_id = event.id
            if last_id is not None:
                raw[last_id] = raw.get(last_id, "") + event.arguments

    schemas = []
    for item in tools:
        function = TOOL_SCHEMAS[item]["function"] if isinstance(item, str) else item["function"]
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
            extra_body={"reasoning": {"enabled": True}},
            max_retries=3,
            stream_idle_timeout=180,
        ),
        cache=False,
        on_stream=capture,
    )
    choice = output.choices[0]
    message = choice.message
    content = message.text or None
    reasoning = None
    if isinstance(message.content, list):
        reasoning = "".join(c.reasoning for c in message.content if c.type == "reasoning") or None
    calls = message.tool_calls or []
    retained = []
    for call in calls[:1]:
        if call.id not in raw:
            raise TransportFidelityError(
                "Raw streaming arguments unavailable for tool call; cannot reproduce reference JSON parsing."
            )
        retained.append({"id": call.id, "name": call.function, "arguments": raw[call.id]})
    return Completion(
        content, reasoning, retained, max(0, len(calls) - 1), choice.stop_reason, output
    )
