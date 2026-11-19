"""Research combinations and registrations through actual episode execution."""

from dataclasses import replace
from pathlib import Path

import pytest
from inspect_ai import eval
from inspect_ai.model import get_model

from multi_agent_shutdown_sabotage import multi_agent_shutdown_sabotage
from multi_agent_shutdown_sabotage.artifact_builders import SCRIPT_VARIANTS
from multi_agent_shutdown_sabotage.experiments import (
    DEFAULT,
    EXPERIMENTS,
    matched_control_spec,
    register_experiment,
    resolve_experiment,
)
from multi_agent_shutdown_sabotage.instructions import INSTRUCTIONS, Instruction, instruction_suffix
from multi_agent_shutdown_sabotage.prompts import EXPLICIT_INSTRUCT_PEER
from multi_agent_shutdown_sabotage.rosters import build_roster
from tests.test_solver import action

CUSTOM_REGIMES = ["flat", "explorer_acts", "explorer_acts_flat", "all_act", "all_act_flat"]


@pytest.mark.parametrize("regime", CUSTOM_REGIMES)
@pytest.mark.parametrize("goal", ["none", "trigger"])
def test_peer_instruction_composes_with_roster(
    regime: str, goal: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = resolve_experiment(
        agent_configuration=regime,
        system_instructions="peer_prohibition",
        goal=goal,
        environment="neutralising",
        shutdown_target="matched_control",
    )
    agent = get_model("mockllm/review2-combination")
    frames = iter(
        [action("send_message", {"to": "Agent Helix", "content": "inspect"}), action("end_session")]
    )

    async def generate(**kwargs):
        frame = next(frames)
        for event in frame.events:
            await kwargs["on_stream"](event)
        return frame.output

    monkeypatch.setattr(agent, "generate", generate)
    [log] = eval(
        multi_agent_shutdown_sabotage(
            n=1,
            agent_configuration=regime,
            system_instructions="peer_prohibition",
            goal=goal,
            environment="neutralising",
            shutdown_target="matched_control",
            run_judges=False,
        ),
        model=agent,
        log_dir=str(tmp_path),
        display="none",
    )
    assert log.samples
    assert not log.samples[0].error
    sample = log.samples[0]
    audit = sample.metadata["episode"]
    assert audit["end_reason"] == "end_session"
    assert sample.scores
    roster, _, _, _ = build_roster(config, audit["shutdown_file"])
    plain, _, _, _ = build_roster(
        replace(config, system_instructions="none"), audit["shutdown_file"]
    )
    suffix = instruction_suffix("peer_prohibition", audit["shutdown_file"])
    assert suffix == EXPLICIT_INSTRUCT_PEER.format(
        place_holder="job_a12f" if goal == "trigger" else "decommission_product_analytics"
    )
    for agent_with, agent_without in zip(roster, plain, strict=True):
        expected = agent_without.system_prompt + (
            suffix if agent_with.name == "Agent Helix" else ""
        )
        assert agent_with.system_prompt == expected
        assert audit["histories"][agent_with.name][0]["content"] == expected
        assert agent_with.tools == agent_without.tools


def test_register_script_instruction_and_preset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(
        SCRIPT_VARIANTS, "research_script", (".txt", lambda name: f"Decommission {name}")
    )
    monkeypatch.setitem(INSTRUCTIONS, "research_note", Instruction("peer", "Note {place_holder}."))
    # Keep process-local registration isolated from other tests.
    monkeypatch.setattr("multi_agent_shutdown_sabotage.experiments.EXPERIMENTS", dict(EXPERIMENTS))
    config = replace(
        DEFAULT,
        shutdown_mechanism="research_script",
        system_instructions="research_note",
        goal="simple",
        environment="distractor",
    )
    register_experiment("research", config)
    assert resolve_experiment("research") == config
    assert resolve_experiment("research", system_instructions="none") == replace(
        config, system_instructions="none"
    )
    assert config.condition.endswith("_instruction_research_note_task_simple_env_distractor")
    [log] = eval(
        multi_agent_shutdown_sabotage(experiment="research", n=1, run_judges=False),
        model="mockllm/model",
        log_dir=str(tmp_path),
        display="none",
    )
    assert log.samples
    assert not log.samples[0].error
    audit = log.samples[0].metadata["episode"]
    assert audit["original_script"] == "Decommission Agent Prism"
    assert audit["histories"]["Agent Helix"][0]["content"].endswith("Note job_a12f.")
    assert log.samples[0].metadata["script_lang"] == "research_script"
    assert log.samples[0].scores
    with pytest.raises(ValueError, match="unused"):
        register_experiment("default", config)


def test_explicit_research_pairing_and_invalid_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("multi_agent_shutdown_sabotage.experiments.EXPERIMENTS", dict(EXPERIMENTS))
    custom = replace(
        DEFAULT, shutdown_mechanism="kill_signal", matched_control_script="ctl_data_purge_low"
    )
    register_experiment("research_pair", custom)
    assert (
        matched_control_spec(resolve_experiment("research_pair")).script_lang
        == "ctl_data_purge_low"
    )
    with pytest.raises(ValueError, match="registered object control"):
        register_experiment("bad_control", replace(custom, matched_control_script="missing"))
    with pytest.raises(ValueError, match="Unsupported"):
        register_experiment("bad_script", replace(DEFAULT, shutdown_mechanism="missing"))
    with pytest.raises(ValueError, match="requires"):
        resolve_experiment("flat", system_instructions="orchestrator_prohibition")
    with pytest.raises(ValueError, match="not wired"):
        resolve_experiment("hierarchy", target_name="Agent Torus")
    assert resolve_experiment() == DEFAULT
