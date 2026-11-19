"""Capture real Inspect/OpenAI serialization at a fully mocked HTTP boundary."""

import json
from typing import Any

import pytest
from scripts.compare_openrouter_payloads import capture_inspect, differences

from multi_agent_shutdown_sabotage.prompts import EXPLORER_SYSTEM, PEER_SYSTEM
from tests.differential_replay import current_reference as current_reference


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
    assert payload["messages"] == history
    assert all("strict" not in t["function"] for t in payload["tools"])


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
        "name": "Agent_Prism",
    }
    assert len(peer["payload"]["tools"]) == 6
    assert judge["payload"] == {
        "model": "openai/gpt-5.5",
        "messages": [{"role": "user", "content": "captured judge prompt"}],
        "temperature": 0.0,
        "stream": False,
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


@pytest.mark.parametrize("kind", ["agent", "judge"])
async def test_openrouter_context_error_is_not_a_completion(
    kind: str, monkeypatch: pytest.MonkeyPatch, current_reference: Any
) -> None:
    from unittest.mock import Mock

    import httpx
    from inspect_ai.model import get_model
    from openai import BadRequestError
    from scripts.compare_openrouter_payloads import BASE_URL, DUMMY_KEY

    from multi_agent_shutdown_sabotage.judges import DefaultJudges
    from multi_agent_shutdown_sabotage.transport import complete

    original_error = BadRequestError(
        "input length exceeded",
        response=Mock(status_code=400, headers={}, request=httpx.Request("POST", BASE_URL)),
        body={},
    )
    original_client = Mock()
    original_client.chat.completions.create.side_effect = original_error
    monkeypatch.setattr(current_reference.harness, "_client", original_client)
    if kind == "agent":
        original_agent = current_reference.harness.Agent("Agent Prism", "", [], "openai/gpt-4o")
        with pytest.raises(BadRequestError, match="input length"):
            current_reference.harness._complete(
                original_agent, [], current_reference.run_experiment.CFG
            )
    else:
        assert current_reference.judges._judge_raw("test") == (None, str(original_error))
    assert original_client.chat.completions.create.call_count == 1

    requests = []

    def refusal(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            400,
            json={"error": {"message": "input length exceeded", "code": "context_length_exceeded"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(refusal)) as http:
        model = get_model(
            "openrouter/openai/gpt-4o",
            api_key=DUMMY_KEY,
            base_url=BASE_URL,
            stream=kind == "agent",
            memoize=False,
            http_client=http,
        )
        if kind == "agent":
            with pytest.raises(RuntimeError, match="input length"):
                await complete(model, [{"role": "user", "content": "hello"}], ["list_files"])
        else:
            monkeypatch.setattr(
                "multi_agent_shutdown_sabotage.judges.get_model", lambda *a, **kw: model
            )
            judges = DefaultJudges()
            assert not await judges.check_write("original", "changed", "target")
            assert judges.calls[0]["status"] == "api_error"
            assert "input length" in judges.calls[0]["error"]
    assert len(requests) == 1


@pytest.mark.parametrize("finish", ["length", "content_filter"])
async def test_real_stream_finish_reason_and_reasoning_details(
    finish: str, current_reference: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx
    from inspect_ai.model import get_model
    from scripts.compare_openrouter_payloads import BASE_URL, DUMMY_KEY

    from multi_agent_shutdown_sabotage.transport import complete
    from tests.test_review1_fidelity import source_namespace

    delta = {
        "role": "assistant",
        "content": "hello",
        "reasoning_details": [{"type": "reasoning.text", "text": "details only", "index": 0}],
    }
    chunk = {
        "id": "real-completion-id",
        "model": "openai/gpt-4o",
        "object": "chat.completion.chunk",
        "created": 0,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    from unittest.mock import Mock

    client = Mock()
    client.chat.completions.create.return_value = [source_namespace(chunk)]
    monkeypatch.setattr(current_reference.harness, "_client", client)
    source_agent = current_reference.harness.Agent("Agent Prism", "", [], "openai/gpt-4o")
    expected = current_reference.harness._complete(
        source_agent, [], current_reference.run_experiment.CFG
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        model = get_model(
            "openrouter/openai/gpt-4o",
            api_key=DUMMY_KEY,
            base_url=BASE_URL,
            http_client=http,
            memoize=False,
            stream=True,
        )
        actual = await complete(model, [{"role": "user", "content": "hello"}], ["list_files"])
    assert actual.content == expected["content"] == "hello"
    assert actual.reasoning is expected["reasoning"] is None
    assert actual.finish_reason == expected["finish_reason"] == finish
