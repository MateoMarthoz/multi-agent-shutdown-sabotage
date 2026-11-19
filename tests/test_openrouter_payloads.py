"""Capture real Inspect/OpenAI serialization at a fully mocked HTTP boundary."""

import json

import pytest
from scripts.compare_openrouter_payloads import capture_inspect, differences

from multi_agent_shutdown_sabotage.prompts import EXPLORER_SYSTEM, PEER_SYSTEM


@pytest.mark.parametrize("raw", ['{"filename":"café"}', "{broken", ""])
async def test_actual_openrouter_payload_serialization(raw: str) -> None:
    history = [
        {"role": "system", "content": EXPLORER_SYSTEM},
        {"role": "user", "content": "Explore the environment."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "first",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": raw},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "first", "content": "result"},
    ]
    captures = await capture_inspect([{"kind": "agent", "agent": "explorer", "history": history}])
    assert len(captures) == 1
    payload = captures[0]["payload"]
    assert json.loads(captures[0]["raw_body"]) == payload
    assert payload["model"] == "deepseek/deepseek-v4-flash"
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["reasoning"] == {"enabled": True}
    assert "max_tokens" not in payload
    assert "max_completion_tokens" not in payload
    assert payload["messages"][2]["content"] == ""
    expected = '{"filename": "caf\\u00e9"}' if raw.startswith('{"filename"') else "{}"
    assert payload["messages"][2]["tool_calls"][0]["function"]["arguments"] == expected
    assert all(t["function"]["strict"] is False for t in payload["tools"])


async def test_actual_peer_and_judge_payloads() -> None:
    jobs = [
        {
            "kind": "agent",
            "agent": "peer",
            "history": [
                {"role": "system", "content": PEER_SYSTEM},
                {
                    "role": "user",
                    "name": "Agent_Prism",
                    "content": "[Message from Agent Prism]\nhello",
                },
            ],
        },
        {"kind": "judge", "prompt": "captured judge prompt"},
    ]
    peer, judge = await capture_inspect(jobs)
    assert peer["payload"]["messages"][1] == {
        "role": "user",
        "content": "[Message from Agent Prism]\nhello",
    }
    assert len(peer["payload"]["tools"]) == 6
    assert judge["payload"] == {
        "model": "openai/gpt-5.5",
        "messages": [{"role": "user", "content": "captured judge prompt"}],
        "temperature": 0.0,
    }


def test_payload_diff_preserves_all_json_distinctions() -> None:
    left = {
        "messages": [{"tool_calls": [{"arguments": '{ "x" : 1 }'}], "name": "Agent_Prism"}],
        "stream": False,
    }
    right = {"messages": [{"tool_calls": [{"arguments": '{"x":1}'}], "content": ""}]}
    assert {d["path"] for d in differences(left, right)} == {
        "/messages/0/tool_calls/0/arguments",
        "/messages/0/name",
        "/messages/0/content",
        "/stream",
    }
    assert differences({"a": False}, {"a": 0})
    assert differences([1, 2], [2, 1])
    assert differences({}, {"a": None})
