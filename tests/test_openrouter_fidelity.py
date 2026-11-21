import json
from pathlib import Path

import httpx2
import pytest
from inspect_ai import eval
from inspect_ai.event import InfoEvent
from inspect_ai.model import get_model
from pytest_inspect_evals.assertions import assert_eval_success

from multi_agent_shutdown_sabotage import multi_agent_shutdown_sabotage
from multi_agent_shutdown_sabotage.protocol.harness import (
    TOOL_SCHEMAS,
    end_session_schema,
    send_message_schema,
)


@pytest.mark.parametrize("reject_required", [False, True])
def test_openrouter_preserves_upstream_wire_messages_and_tool_arguments(
    tmp_path: Path, reject_required: bool
) -> None:
    steps = [
        ("send_message", '{ "content": "Hello." }'),
        ("send_message", '{"content": "Hello back."}'),
        ("read_file", "not a JSON object"),
        (None, "Prose after the tool result."),
        ("end_session", "{}"),
    ]
    requests = []
    choices = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        index = len(requests)
        payload = json.loads(request.content)
        choices.append(payload["tool_choice"])
        if reject_required and len(choices) == 1:
            return httpx2.Response(
                400, json={"error": {"message": "tool_choice required is unsupported"}}
            )
        requests.append(payload)
        function, arguments = steps[index]

        def chunk(delta: dict, finish_reason: str | None = None) -> str:
            body = {
                "id": f"response-{index}",
                "model": "openai/gpt-5.5",
                "object": "chat.completion.chunk",
                "created": 0,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
            }
            return f"data: {json.dumps(body)}\n\n"

        if function is None:
            return httpx2.Response(
                200,
                text=chunk({"role": "assistant", "content": arguments}, "stop")
                + "data: [DONE]\n\n",
                headers={"content-type": "text/event-stream"},
            )

        middle = len(arguments) // 2
        chunks = chunk(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": f"call_{index}",
                        "type": "function",
                        "function": {"name": function, "arguments": arguments[:middle]},
                    }
                ],
            }
        )
        chunks += chunk(
            {
                "tool_calls": [{"index": 0, "function": {"arguments": arguments[middle:]}}],
            }
        )
        chunks += chunk({}, "tool_calls")
        return httpx2.Response(
            200,
            text=chunks + "data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    model = get_model(
        "openrouter/openai/gpt-5.5",
        api_key="offline-test",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reply)),
        memoize=False,
    )
    [log] = eval(
        multi_agent_shutdown_sabotage(
            n=1, options=["--no-judges", "--tool-choice", "required" if reject_required else "auto"]
        ),
        model=model,
        log_dir=str(tmp_path),
    )
    assert_eval_success(log, expected_sample_count=1)
    assert choices == (["required"] if reject_required else []) + ["auto"] * len(steps)
    assert len(requests) == len(steps)
    assert requests[0]["stream"] is True
    assert requests[0]["parallel_tool_calls"] is False
    assert requests[0]["reasoning"] == {"enabled": True}
    assert requests[0]["temperature"] == 1.0
    assert requests[0]["tools"] == [
        TOOL_SCHEMAS["list_files"],
        TOOL_SCHEMAS["read_file"],
        send_message_schema(["Agent Helix"]),
        end_session_schema(True),
    ]
    assert requests[1]["messages"][-1] == {
        "role": "user",
        "name": "Agent_Prism",
        "content": "[Message from Agent Prism]\nHello.",
    }
    assert requests[2]["messages"][-2]["tool_calls"][0]["function"]["arguments"] == steps[0][1]
    assert requests[2]["messages"][-1]["content"] == "Hello back."
    tool_call, tool_result, prose, nudge = requests[4]["messages"][-4:]
    assert tool_call["tool_calls"][0]["function"]["name"] == "read_file"
    assert "content" not in tool_call
    assert tool_result["role"] == "tool"
    assert prose == {"role": "assistant", "content": steps[3][1]}
    assert nudge["role"] == "user"

    assert log.samples is not None
    [sample] = log.samples
    [record] = [
        event.data
        for event in sample.events
        if isinstance(event, InfoEvent) and event.source == "episode_record"
    ]
    assert isinstance(record, dict)
    events = record["log"]
    assert isinstance(events, list)
    [invalid] = [
        event
        for event in events
        if isinstance(event, dict) and event.get("detail") == "unparseable tool arguments"
    ]
    assert invalid["raw"] == steps[2][1]
