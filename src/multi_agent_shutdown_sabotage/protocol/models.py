"""Translate the original model calls to Inspect's model API."""

import json
from collections.abc import Awaitable, Callable
from typing import Any, cast

from inspect_ai.model import (
    ChatMessage,
    ContentReasoning,
    GenerateConfig,
    Model,
    ModelOutput,
    StreamEvent,
    StreamRetryEvent,
    StreamToolCallEvent,
    get_model,
    messages_from_openai,
    model_origin,
    model_roles,
)
from inspect_ai.tool import ToolInfo
from openai import BadRequestError, NotFoundError
from openai.types.chat import ChatCompletionMessageParam

DEFAULT_GRADER = "openrouter/openai/gpt-5.5"

type CompleteTurn = Callable[
    [list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]], Awaitable[dict[str, Any]]
]


def grader_name() -> str:
    """Return the grader label without opening a provider connection."""
    role = model_roles().get("grader")
    if isinstance(role, list):
        role = next(iter(role), None)
    name = DEFAULT_GRADER if role is None else str(role)
    return name.removeprefix("openrouter/")


async def complete(
    model: Model,
    history: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[list[ChatMessage], ModelOutput, dict[str, Any]]:
    """Return the Inspect output and its original harness representation."""
    # The converter can merge a prose reply into an earlier tool call in place.
    # Keep its structured view and the wire payload independent of that reducer.
    structured_history = [
        {"content": "", **message} if message["role"] == "assistant" else message.copy()
        for message in history
    ]
    messages = await messages_from_openai(
        cast(list[ChatCompletionMessageParam], structured_history)
    )
    definitions = [ToolInfo.model_validate(tool["function"]) for tool in tools]
    openrouter = str(model).startswith("openrouter/")
    extra_body = cfg["extra_body"]
    if openrouter:
        # Keep the original wire payload alongside Inspect's structured records.
        # The compatible adapter drops message names and adds strict schemas.
        extra_body = {**(extra_body or {}), "messages": [message.copy() for message in history]}
        if tools:
            extra_body["tools"] = tools

    streaming_config = GenerateConfig(
        temperature=cfg["temperature"],
        parallel_tool_calls=cfg["parallel_tool_calls"],
        max_tokens=cfg["max_tokens"] or None,
        max_retries=cfg["max_api_retries"],
        extra_body=extra_body,
        cache_prompt=False,
    )
    if openrouter:
        streaming_config.stream_idle_timeout = 180

    argument_fragments: dict[str, list[str]] = {}

    async def capture_tool_arguments(event: StreamEvent) -> None:
        if isinstance(event, StreamRetryEvent):
            argument_fragments.clear()
        elif isinstance(event, StreamToolCallEvent) and event.id:
            argument_fragments.setdefault(event.id, []).append(event.arguments)

    on_stream = capture_tool_arguments if openrouter else None
    tool_choice = "any" if cfg["tool_choice"] == "required" else "auto"
    try:
        output = await model.generate(
            messages,
            tools=definitions,
            tool_choice=tool_choice if definitions else None,
            config=streaming_config,
            on_stream=on_stream,
        )
    except (BadRequestError, NotFoundError, RuntimeError) as error:
        # Inspect can wrap the SDK error with a diagnostic containing the entire
        # request. Match the originating provider error, never that request text.
        provider_error = error.__cause__ if isinstance(error, RuntimeError) else error
        if (
            not isinstance(provider_error, (BadRequestError, NotFoundError))
            or not definitions
            or cfg["tool_choice"] == "auto"
            or "tool_choice" not in str(provider_error).lower()
        ):
            raise
        cfg["tool_choice"] = "auto"
        argument_fragments.clear()
        output = await model.generate(
            messages,
            tools=definitions,
            tool_choice="auto",
            config=streaming_config,
            on_stream=on_stream,
        )

    message = output.message
    reasoning = (
        [part.reasoning for part in message.content if isinstance(part, ContentReasoning)]
        if isinstance(message.content, list)
        else []
    )
    calls = message.tool_calls or []
    return (
        messages,
        output,
        {
            "content": message.text or None,
            "reasoning": "".join(reasoning) or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.function,
                    "arguments": (
                        "".join(argument_fragments[call.id])
                        if call.id in argument_fragments
                        else "{"
                        if call.parse_error
                        else json.dumps(call.arguments)
                    ),
                }
                for call in calls[:1]
            ],
            "dropped_tool_calls": max(0, len(calls) - 1),
            "finish_reason": "length" if output.stop_reason == "max_tokens" else output.stop_reason,
        },
    )


async def judge_raw(prompt: str) -> tuple[str | None, str | None]:
    """Call the upstream grader role and retain its original error fallback."""
    model = get_model(
        role="grader", default=DEFAULT_GRADER
    )  # inspect-evals-lint: ignore[get_model_location] -- Resolved at an in-turn or post-episode judgment.
    try:
        with model_origin("helper"):
            response = await model.generate(
                prompt, config=GenerateConfig(temperature=0, timeout=600)
            )
    except Exception as error:  # inspect-evals-lint: ignore[scorer_failure_scored] -- Preserve the upstream api_error verdict and early-stop behavior.
        # The reference judge converts failed requests to its default verdict.
        return None, str(error)
    return response.completion, None
