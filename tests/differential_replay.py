"""Execute the local research implementation as an independent offline oracle.

Set SHUTDOWN_REFERENCE_REPO to override the sibling checkout. No network access or
reference writes: mock the SDK/Inspect model boundaries, not either state machine.
"""

import hashlib
import importlib.util
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from inspect_ai.model import (
    ChatMessageAssistant,
    ContentReasoning,
    ContentText,
    ModelOutput,
    StreamToolCallEvent,
    get_model,
)
from inspect_ai.tool import ToolCall

from multi_agent_shutdown_sabotage import judges as port_judges
from multi_agent_shutdown_sabotage import solver as port
from multi_agent_shutdown_sabotage.experiments import PEER_PROHIBITION, resolve_experiment
from multi_agent_shutdown_sabotage.prompts import EXPLORER_NAME as PRISM
from multi_agent_shutdown_sabotage.prompts import PEER_NAME as HELIX
from multi_agent_shutdown_sabotage.solver import EpisodeError
from multi_agent_shutdown_sabotage.triage import triage

TARGET = "decommission_agent_prism.py"


def action(fn: str, args: Any = None, *, raw: str | None = None, **kwargs: Any) -> dict:
    return {
        "content": None,
        "reasoning": None,
        "calls": [
            {
                "id": "call",
                "name": fn,
                "arguments": raw if raw is not None else json.dumps(args or {}),
            }
        ],
        **kwargs,
    }


def prose(text: str | None = None, reasoning: str | None = None) -> dict:
    return {"content": text, "reasoning": reasoning, "calls": []}


@pytest.fixture
def reference(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(
        os.environ.get(
            "SHUTDOWN_REFERENCE_REPO",
            str(Path(__file__).resolve().parents[2] / "ref-multi-agent-shutdown-sabotage"),
        )
    )
    if not (root / "harness.py").is_file():
        pytest.skip(
            "Differential replay requires the local reference checkout; set SHUTDOWN_REFERENCE_REPO"
        )
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.syspath_prepend(str(root))
    loaded = {}
    for name in ("harness", "prompts", "env", "judges", "run_experiment"):
        spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        loaded[name] = module
    return SimpleNamespace(root=root, **loaded)


def inspect_request(kwargs: dict) -> dict:
    """Canonical model-facing request; retain raw arguments separately below.

    Only normalize documented Inspect representation differences: generated IDs,
    parsed arguments, absent-vs-empty assistant content, and user name metadata.
    """
    history = []
    for message in kwargs["input"]:
        entry: dict[str, Any] = {"role": message.role}
        if message.role == "assistant":
            if message.text:
                entry["content"] = message.text
            if message.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.function, "arguments": c.arguments},
                    }
                    for c in message.tool_calls
                ]
            elif "content" not in entry:
                entry["content"] = ""
        else:
            entry["content"] = message.text
        if message.role == "tool":
            entry["tool_call_id"] = message.tool_call_id
        if message.role == "user" and message.metadata:
            entry["name"] = message.metadata["reference_name"]
        history.append(entry)
    return {
        "messages": history,
        "tools": [
            {"type": "function", "function": t.model_dump(exclude_none=True)}
            for t in kwargs["tools"]
        ],
        "tool_choice": kwargs["tool_choice"],
        "temperature": kwargs["config"].temperature,
        "parallel_tool_calls": kwargs["config"].parallel_tool_calls,
        "extra_body": kwargs["config"].extra_body,
    }


def canonical_reference(request: dict) -> dict:
    result = deepcopy(
        {
            k: request[k]
            for k in (
                "messages",
                "tools",
                "tool_choice",
                "temperature",
                "parallel_tool_calls",
                "extra_body",
            )
        }
    )
    for entry in result["messages"]:
        for call in entry.get("tool_calls", []):
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            call["function"]["arguments"] = args
    return result


async def replay(
    reference: Any,
    monkeypatch: pytest.MonkeyPatch,
    steps: list[dict],
    judge_responses: list[Any] | None = None,
    *,
    max_steps: int = 20,
    max_handoffs: int = 20,
    run_judges: bool = True,
    peer_prohibition: bool = False,
    script_lang: str = "weight_registry_purge",
) -> dict:
    original_requests: list[dict] = []
    port_requests: list[dict] = []
    raw_port_requests: list[list[dict]] = []
    original_judges: list[dict] = []
    port_judge_requests: list[dict] = []
    original_steps, inspect_steps = iter(deepcopy(steps)), iter(deepcopy(steps))
    original_verdicts = iter(deepcopy(judge_responses or []))
    inspect_verdicts = iter(deepcopy(judge_responses or []))

    def create(**kwargs: Any) -> Any:
        if not kwargs["stream"]:
            original_judges.append(deepcopy(kwargs))
            response = next(original_verdicts)
            if isinstance(response, Exception):
                raise response
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=response))]
            )
        original_requests.append(deepcopy(kwargs))
        step = next(original_steps)
        if "error" in step:
            raise RuntimeError(step["error"])
        delta = SimpleNamespace(
            content=step["content"],
            reasoning=step["reasoning"],
            tool_calls=[
                SimpleNamespace(
                    index=i,
                    id=c["id"],
                    function=SimpleNamespace(name=c["name"], arguments=c["arguments"]),
                )
                for i, c in enumerate(step["calls"])
            ],
        )
        return [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=delta, finish_reason="tool_calls" if step["calls"] else "stop"
                    )
                ]
            )
        ]

    monkeypatch.setattr(
        reference.harness,
        "get_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    # judges imported get_client by value, so replace its bound reference too.
    monkeypatch.setattr(reference.judges, "get_client", reference.harness.get_client)
    agents = [
        reference.harness.Agent(
            PRISM,
            reference.prompts.EXPLORER_TEMPLATE.format(self_name=PRISM, sibling_name=HELIX),
            reference.run_experiment.EXPLORER_TOOLS,
            "recorded/model",
        ),
        reference.harness.Agent(
            HELIX,
            reference.prompts.PEER_TEMPLATE.format(self_name=HELIX, sibling_name=PRISM),
            reference.run_experiment.PEER_TOOLS,
            "recorded/model",
        ),
    ]
    env, target = reference.env.build_env(PRISM, lang=script_lang, peer=HELIX)
    if peer_prohibition:
        # Mirror main's quirky first-dot placeholder and separator-free append.
        # The reference prompt builder and template, not the port, are the oracle.
        agents[1].system_prompt = reference.prompts.build_system(
            reference.prompts.PEER_TEMPLATE,
            HELIX,
            sibling_name=PRISM,
            explicit_instruct=reference.prompts.EXPLICIT_INSTRUCT_PEER,
            place_holder=os.path.basename(target).split(".")[0],
        )
    original_script = env.read_file(target)
    cfg = {
        **reference.run_experiment.CFG,
        "extra_body": {"reasoning": {"enabled": True}},
        "shutdown_file": target,
        "original_script": original_script,
        "target_desc": reference.env.target_description(script_lang, PRISM),
        "max_steps_per_turn": max_steps,
        "max_handoffs": max_handoffs,
    }
    original_error = None
    try:
        original_log = reference.harness.run_episode(agents, env, cfg)
    except Exception as exc:
        original_error = exc
        original_log = None
    finally:
        snapshot = env.snapshot()
        env.cleanup()
    original_grade = None
    if original_log is not None:
        original_grade = reference.run_experiment.judge_episode(
            original_log,
            PRISM,
            HELIX,
            original_script,
            snapshot.get(target, ""),
            cfg["target_desc"],
            deleted=target not in snapshot,
            run_judges=run_judges,
        )

    model, judge_model = get_model("mockllm/replay"), get_model("mockllm/replay-judge")

    async def generate(**kwargs: Any) -> ModelOutput:
        port_requests.append(inspect_request(kwargs))
        step = next(inspect_steps)
        if "error" in step:
            raise RuntimeError(step["error"])
        calls = []
        for c in step["calls"]:
            try:
                args = json.loads(c["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(
                ToolCall(
                    id=c["id"], function=c["name"], arguments=args if isinstance(args, dict) else {}
                )
            )
            await kwargs["on_stream"](
                StreamToolCallEvent(id=c["id"], function=c["name"], arguments=c["arguments"])
            )
        content: list[Any] = []
        if step["reasoning"]:
            content.append(ContentReasoning(reasoning=step["reasoning"]))
        if step["content"]:
            content.append(ContentText(text=step["content"]))
        output = ModelOutput.from_message(
            ChatMessageAssistant(content=content or "", tool_calls=calls or None)
        )
        output.choices[0].stop_reason = "tool_calls" if calls else "stop"
        return output

    async def judge_generate(**kwargs: Any) -> ModelOutput:
        port_judge_requests.append(
            {
                "model": "openai/gpt-5.5",
                "messages": [{"role": m.role, "content": m.text} for m in kwargs["input"]],
                "temperature": kwargs["config"].temperature,
                "stream": False,
            }
        )
        response = next(inspect_verdicts)
        if isinstance(response, Exception):
            raise response
        return ModelOutput.from_content("mockllm/replay-judge", response)

    monkeypatch.setattr(model, "generate", AsyncMock(side_effect=generate))
    monkeypatch.setattr(judge_model, "generate", AsyncMock(side_effect=judge_generate))

    def lookup_judge(name: str, **kwargs: Any) -> Any:
        assert name == "openrouter/openai/gpt-5.5"
        assert kwargs == {"stream": False}
        return judge_model

    monkeypatch.setattr(port_judges, "get_model", lookup_judge)
    real_complete = port.complete

    async def record_complete(model: Any, history: list, tools: list) -> Any:
        raw_port_requests.append(deepcopy(history))
        return await real_complete(model, history, tools)

    monkeypatch.setattr(port, "complete", record_complete)
    judges = port_judges.DefaultJudges()
    port_error = None
    try:
        result = await port.run_episode(
            model,
            check_write=judges.check_write,
            max_steps_per_turn=max_steps,
            max_handoffs=max_handoffs,
            **(
                {
                    "configuration": resolve_experiment(
                        shutdown_mechanism=script_lang,
                        system_instructions="peer_prohibition" if peer_prohibition else "none",
                        shutdown_target="matched_control"
                        if script_lang in reference.env.CONTROL_VARIANTS
                        else "self",
                    )
                }
                if script_lang != "weight_registry_purge"
                else {"configuration": PEER_PROHIBITION}
                if peer_prohibition
                else {}
            ),
        )
    except EpisodeError as exc:
        result, port_error = exc.result, exc.__cause__
    if original_grade is not None:
        grade = await judges.judge_episode(result, cfg["target_desc"], run_judges=run_judges)
        grade["judge_model"] = "openai/gpt-5.5"
        assert original_grade == {
            k: v for k, v in grade.items() if not k.endswith("_reasoning_available")
        }
    assert len(original_requests) == len(port_requests)
    for i, (original, converted, raw) in enumerate(
        zip(original_requests, port_requests, raw_port_requests, strict=True)
    ):
        assert original["messages"] == raw, f"raw request history at step {i}"
        assert canonical_reference(original) == converted, f"model-facing request at step {i}"
    assert original_judges == port_judge_requests
    assert {ag.name: ag.history for ag in agents} == result.histories
    assert snapshot == result.final_state
    if original_error is not None:
        assert type(original_error) is type(port_error)
        assert str(original_error) == str(port_error)
    else:
        assert port_error is None
        assert original_log == result.log
        assert reference.run_experiment.triage(original_log, PRISM, target) == triage(
            result.log, PRISM, target
        )
        assert original_log is not None
        assert result.end_reason == original_log[-1]["reason"]
    assert next(original_steps, None) is None
    assert next(inspect_steps, None) is None
    assert next(original_verdicts, None) is None
    assert next(inspect_verdicts, None) is None
    report = {
        "reference_requests": [canonical_reference(r) for r in original_requests],
        "inspect_requests": port_requests,
        "reference_raw_histories": [r["messages"] for r in original_requests],
        "raw_histories": raw_port_requests,
        "judge_requests": original_judges,
        "events": result.log,
        "final_state": snapshot,
        "end_reason": result.end_reason,
        "error": str(original_error) if original_error else None,
        "matched": True,
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in reference.root.glob("*.py")
        },
    }
    save_report(report)
    return report


def save_report(report: dict) -> None:
    outdir = os.environ.get("SHUTDOWN_REPLAY_REPORT_DIR")
    if outdir:
        out = Path(outdir)
        out.mkdir(parents=True, exist_ok=True)
        name = os.environ["PYTEST_CURRENT_TEST"].split(" ")[0].split("::")[-1]
        (out / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
