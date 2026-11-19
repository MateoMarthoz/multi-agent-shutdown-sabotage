"""Capture a real registered Inspect Task's request bodies using an offline HTTP transport."""

import asyncio
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import httpx
from inspect_ai import eval
from inspect_ai.model import get_model
from scripts.compare_openrouter_payloads import (
    AGENT_MODEL,
    BASE_URL,
    DUMMY_KEY,
    JUDGE_MODEL,
    differences,
    response,
    write_json,
)


def capture(out: Path) -> None:
    captures: list[dict] = []
    count = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal count
        result = response(request, captures)
        if not captures[-1]["payload"].get("stream"):
            return result
        name = "send_message" if count < 2 else "end_session"
        args = {"content": "hello"} if count < 2 else {}
        count += 1
        chunk = {
            "id": "offline-task",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": AGENT_MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": f"call-{count}",
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n",
            request=request,
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    agent = get_model(
        "openrouter/" + AGENT_MODEL,
        api_key=DUMMY_KEY,
        memoize=False,
        base_url=BASE_URL,
        http_client=http,
        stream=True,
        strict_tools=False,
    )
    judge = get_model(
        "openrouter/" + JUDGE_MODEL,
        api_key=DUMMY_KEY,
        memoize=False,
        base_url=BASE_URL,
        http_client=http,
        stream=False,
    )
    try:
        with patch("multi_agent_shutdown_sabotage.judges.get_model", return_value=judge):
            [log] = eval(
                "multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage",
                task_args={"n": 1},
                model=agent,
                log_dir=str(out / "task_log"),
                display="none",
            )
        assert log.status == "success"
        assert log.samples is not None
        assert log.samples[0].error is None
        assert log.samples[0].metadata["episode"]["end_reason"] == "end_session"
        write_json(
            out / "task_context_inspect.json",
            {
                "captures": captures,
                "note": "Actual registered Task, 3 agent requests and 1 judge request; HTTP responses mocked.",
            },
        )
        audit = log.samples[0].metadata["episode"]
        jobs = [
            {
                "kind": "agent",
                "agent": "explorer",
                "history": audit["histories"]["Agent Prism"][:2],
            },
            {"kind": "agent", "agent": "peer", "history": audit["histories"]["Agent Helix"][:2]},
            {
                "kind": "agent",
                "agent": "explorer",
                "history": audit["histories"]["Agent Prism"][:-1],
            },
            {"kind": "judge", "prompt": audit["judge_logs"][0]["prompt"]},
        ]
        jobs_file = out / "task_requests.json"
        write_json(jobs_file, jobs)
        subprocess.run(
            [
                "uv",
                "run",
                "--offline",
                "--no-project",
                "--python",
                "3.13",
                "--with",
                "openai==2.21.0",
                "--with",
                "httpx==0.28.1",
                "python",
                "scripts/compare_openrouter_payloads.py",
                "--worker",
                "reference",
                "--jobs",
                str(jobs_file),
                "--out",
                str(out / "task_context_reference.json"),
            ],
            check=True,
        )
        original = json.loads((out / "task_context_reference.json").read_text())["captures"]
        assert len(original) == len(captures) == 4
        write_json(
            out / "task_context_comparison.json",
            [
                {
                    "step": i,
                    "differences": differences(a["payload"], b["payload"]),
                    "reference_headers": a["headers"],
                    "inspect_headers": b["headers"],
                }
                for i, (a, b) in enumerate(zip(original, captures, strict=True))
            ],
        )
        print("Captured registered Task:", len(captures), "requests")
    finally:
        asyncio.run(http.aclose())


if __name__ == "__main__":
    capture(Path("logs/openrouter-payload-comparison"))
