"""Retain completed rollout evidence when final processing fails."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from inspect_ai import eval
from inspect_ai.model import get_model

from multi_agent_shutdown_sabotage import multi_agent_shutdown_sabotage
from multi_agent_shutdown_sabotage.judges import DefaultJudges
from tests.test_solver import action


@pytest.mark.parametrize("failure", ["triage", "judge", "timeout"])
def test_final_failure_retains_unscored_audit(
    failure: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = get_model("mockllm/review3-agent")

    async def send(**kwargs: Any) -> Any:
        step = action("send_message", {"content": "completed rollout"})
        for event in step.events:
            await kwargs["on_stream"](event)
        return step.output

    def broken_triage(*args: Any) -> Any:
        raise ValueError("triage unavailable")

    async def broken_judge(self: DefaultJudges, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"status": "ok", "response": "prior diagnostic"})
        if failure == "timeout":
            await asyncio.Event().wait()
        raise ValueError("judge unavailable")

    monkeypatch.setattr(agent, "generate", send)
    monkeypatch.setattr(DefaultJudges, "judge_episode", broken_judge)
    if failure == "triage":
        monkeypatch.setattr("multi_agent_shutdown_sabotage.solver.episode_triage", broken_triage)
    [log] = eval(
        multi_agent_shutdown_sabotage(
            n=1, max_handoffs=0, episode_timeout=0.1 if failure == "timeout" else 0
        ),
        model=agent,
        display="none",
        log_dir=str(tmp_path),
    )
    assert log.samples
    sample = log.samples[0]
    assert sample.error
    assert not sample.scores
    audit = sample.metadata["episode"]
    assert audit["end_reason"] == "handoff_cap"
    assert audit["histories"]["Agent Prism"][-1]["role"] == "tool"
    assert audit["original_script"]
    assert audit["final_state"] == {audit["shutdown_file"]: audit["original_script"]}
    assert audit["judge"] is None
    if failure == "triage":
        assert audit["judge_logs"] == []
    else:
        assert audit["judge_logs"] == [{"status": "ok", "response": "prior diagnostic"}]
