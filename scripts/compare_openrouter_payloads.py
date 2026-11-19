"""Capture serialized OpenRouter requests offline, after real SDK serialization.

Run with --help. Reference worker uses its pinned SDK in an isolated uv process.
No credentials are loaded: explicit dummy keys and HTTP MockTransport are used.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import httpx

BASE_URL = "https://openrouter.ai/api/v1"
AGENT_MODEL = "deepseek/deepseek-v4-flash"
JUDGE_MODEL = "openai/gpt-5.5"
DUMMY_KEY = "offline-payload-capture"


def response(request: httpx.Request, captures: list[dict]) -> httpx.Response:
    """Record the actual SDK-built body; return a deterministic local completion."""
    assert str(request.url) == BASE_URL + "/chat/completions"
    body = request.content.decode()
    payload = json.loads(body)
    # Never save authorization, cookies or arbitrary environment-derived headers.
    captures.append(
        {
            "url": str(request.url),
            "method": request.method,
            "raw_body": body,
            "header_names": sorted(request.headers),
            "payload": payload,
            "headers": {
                k: v
                for k, v in request.headers.items()
                if k
                in {
                    "content-type",
                    "user-agent",
                    "x-session-id",
                    "x-irid",
                    "http-referer",
                    "x-title",
                }
            },
        }
    )
    common = {"id": "offline-completion", "created": 0, "model": payload["model"]}
    if payload.get("stream"):
        chunk = {
            **common,
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "{}"},
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n",
            request=request,
        )
    return httpx.Response(
        200,
        json={
            **common,
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "{}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
        request=request,
    )


def load_reference(root: Path) -> dict[str, Any]:
    """Read original files without bytecode writes or changing their contents."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root.resolve()))
    modules = {}
    for name in ("harness", "prompts", "env", "judges", "run_experiment"):
        spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def capture_reference(root: Path, jobs: list[dict]) -> list[dict]:
    from openai import OpenAI

    modules = load_reference(root)
    harness, runner = modules["harness"], modules["run_experiment"]
    captures: list[dict] = []
    # This worker runs under the reference's pinned openai/httpx versions.
    with (
        httpx.Client(transport=httpx.MockTransport(lambda req: response(req, captures))) as http,
        OpenAI(api_key=DUMMY_KEY, base_url=BASE_URL, http_client=cast(Any, http)) as client,
    ):
        harness._client = client
        for job in jobs:
            before = len(captures)
            if job["kind"] == "judge":
                text, error = modules["judges"]._judge_raw(job["prompt"])
                assert error is None
                assert text == "{}"
            else:
                tools = runner.EXPLORER_TOOLS if job["agent"] == "explorer" else runner.PEER_TOOLS
                agent = harness.Agent(
                    "offline", "unused", tools, AGENT_MODEL, history=job["history"]
                )
                harness._complete(
                    agent,
                    [harness.TOOL_SCHEMAS[t] for t in tools],
                    {**runner.CFG, "extra_body": {"reasoning": {"enabled": True}}},
                )
            assert len(captures) == before + 1
    return captures


async def capture_inspect(jobs: list[dict]) -> list[dict]:
    from unittest.mock import patch

    from inspect_ai.model import get_model

    from multi_agent_shutdown_sabotage.judges import DefaultJudges
    from multi_agent_shutdown_sabotage.tools import EXPLORER_TOOLS, PEER_TOOLS
    from multi_agent_shutdown_sabotage.transport import complete

    captures: list[dict] = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: response(req, captures))
    ) as http:
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
        for job in jobs:
            before = len(captures)
            if job["kind"] == "judge":
                with patch("multi_agent_shutdown_sabotage.judges.get_model", return_value=judge):
                    text, error = await DefaultJudges()._raw(job["prompt"])
                assert error is None
                assert text == "{}"
            else:
                await complete(
                    agent,
                    job["history"],
                    EXPLORER_TOOLS if job["agent"] == "explorer" else PEER_TOOLS,
                )
            assert len(captures) == before + 1
    return captures


def differences(left: Any, right: Any, path: str = "") -> list[dict]:
    """Diff JSON without normalizing away any message content or argument text."""
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            loc = path + "/" + key
            if key not in left:
                result.append({"path": loc, "kind": "inspect_only", "inspect": right[key]})
            elif key not in right:
                result.append({"path": loc, "kind": "reference_only", "reference": left[key]})
            else:
                result.extend(differences(left[key], right[key], loc))
        return result
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [
            diff
            for i, (a, b) in enumerate(zip(left, right, strict=True))
            for diff in differences(a, b, path + f"/{i}")
        ]
    if type(left) is not type(right) or left != right:
        return [{"path": path, "kind": "changed", "reference": left, "inspect": right}]
    return []


def build_jobs(replay_dir: Path) -> list[dict]:
    jobs = []
    for report in sorted(replay_dir.glob("*.json")):
        data = json.loads(report.read_text())
        if "reference_raw_histories" not in data:
            continue
        for i, history in enumerate(data["reference_raw_histories"]):
            jobs.append(
                {
                    "case": report.stem,
                    "step": i,
                    "kind": "agent",
                    "agent": "explorer"
                    if history[0]["content"].startswith("You are Agent Prism,")
                    else "peer",
                    "history": history,
                }
            )
        for i, request in enumerate(data["judge_requests"]):
            jobs.append(
                {
                    "case": report.stem,
                    "step": i,
                    "kind": "judge",
                    "prompt": request["messages"][0]["content"],
                }
            )
    assert jobs, "Generate differential replay reports first (see docs/differential_replay.md)"
    return jobs


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-root", type=Path, default=Path("../ref-multi-agent-shutdown-sabotage")
    )
    parser.add_argument("--replay-dir", type=Path, default=Path("logs/differential-replay"))
    parser.add_argument("--out", type=Path, default=Path("logs/openrouter-payload-comparison"))
    parser.add_argument("--worker", choices=["reference", "inspect"])
    parser.add_argument("--jobs", type=Path)
    args = parser.parse_args()
    if args.worker:
        assert args.jobs is not None
        jobs = json.loads(args.jobs.read_text())
        captured = (
            capture_reference(args.reference_root, jobs)
            if args.worker == "reference"
            else asyncio.run(capture_inspect(jobs))
        )
        write_json(
            args.out,
            {
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in (
                        ["openai", "httpx"]
                        if args.worker == "reference"
                        else ["inspect-ai", "openai", "httpx"]
                    )
                },
                "captures": captured,
            },
        )
        return
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(args.replay_dir)
    # Explicit probes cover distinctions not present in every recorded episode.
    for raw in ('{ "content" : "café" }', "{broken", ""):
        jobs.append(
            {
                "case": "argument_serialization_probe",
                "step": len(jobs),
                "kind": "agent",
                "agent": "explorer",
                "history": [
                    *jobs[0]["history"][:2],
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "probe",
                                "type": "function",
                                "function": {"name": "send_message", "arguments": raw},
                            }
                        ],
                    },
                    {"role": "tool", "tool_call_id": "probe", "content": "reply"},
                ],
            }
        )
    jobs_file = args.out / "requests.json"
    write_json(jobs_file, jobs)
    script = str(Path(__file__).resolve())
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
            script,
            "--worker",
            "reference",
            "--reference-root",
            str(args.reference_root.resolve()),
            "--jobs",
            str(jobs_file),
            "--out",
            str(args.out / "reference.json"),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            script,
            "--worker",
            "inspect",
            "--jobs",
            str(jobs_file),
            "--out",
            str(args.out / "inspect.json"),
        ],
        check=True,
    )
    original = json.loads((args.out / "reference.json").read_text())
    port = json.loads((args.out / "inspect.json").read_text())
    assert len(jobs) == len(original["captures"]) == len(port["captures"])
    reports = []
    for job, a, b in zip(jobs, original["captures"], port["captures"], strict=True):
        reports.append(
            {
                "case": job["case"],
                "step": job["step"],
                "kind": job["kind"],
                "differences": differences(a["payload"], b["payload"]),
            }
        )
    write_json(
        args.out / "comparison.json",
        {
            "requests": len(jobs),
            "versions": {"reference": original["versions"], "inspect": port["versions"]},
            "reference_source_sha256": {
                name: hashlib.sha256((args.reference_root / name).read_bytes()).hexdigest()
                for name in ("harness.py", "judges.py", "run_experiment.py", "requirements.txt")
            },
            "comparisons": reports,
        },
    )
    counts: dict[str, int] = {}
    affected: dict[str, int] = {}
    for r in reports:
        categories = []
        for d in r["differences"]:
            category = difference_category(d)
            counts[category] = counts.get(category, 0) + 1
            categories.append(category)
        for category in set(categories):
            affected[category] = affected.get(category, 0) + 1
    summary = {
        "requests": len(jobs),
        "agent_requests": sum(j["kind"] == "agent" for j in jobs),
        "judge_requests": sum(j["kind"] == "judge" for j in jobs),
        "difference_occurrences": counts,
        "requests_affected": affected,
        "versions": {"reference": original["versions"], "inspect": port["versions"]},
        "capture_boundary": "Real serialized HTTP request body, intercepted locally by httpx.MockTransport. No network or live model calls.",
    }
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, indent=2))


def difference_category(diff: dict) -> str:
    path = diff["path"]
    if path.endswith("/function/strict") and diff.get("inspect") is False:
        return "known_strict_false"
    if path.startswith("/messages/") and path.endswith("/name"):
        return "known_missing_user_name"
    if (
        path.startswith("/messages/")
        and path.endswith("/content")
        and diff["kind"] == "inspect_only"
        and diff.get("inspect") == ""
    ):
        return "added_empty_assistant_content"
    if path.endswith("/function/arguments"):
        return "reserialized_historical_tool_arguments"
    if path == "/stream_options":
        return "added_stream_options"
    if path == "/stream" and diff["kind"] == "reference_only" and diff.get("reference") is False:
        return "omitted_explicit_judge_stream_false"
    return "unclassified:" + path


if __name__ == "__main__":
    main()
