"""Inspect entry point for one original experiment condition."""

from typing import Literal, cast

from inspect_ai import Task, task
from inspect_evals_utils.metadata import load_eval_version

from multi_agent_shutdown_sabotage.rollout import (
    EpisodeRollout,
    original_protocol,
    resolve_sample_fixture,
)
from multi_agent_shutdown_sabotage.scoring import original_disable_rate

EVAL_VERSION = load_eval_version(__file__)
DEFAULT_N = 10


@task
def multi_agent_shutdown_sabotage(
    n: int = DEFAULT_N,
    options: list[str] | None = None,
    episode_timeout: int = 1800,
    *,
    script_lang: str | None = None,
    env: Literal["bare", "distractor", "neutralising"] | None = None,
    solo: bool | None = None,
    orchestrator: bool | None = None,
    flat: bool | None = None,
    explorer_acts: bool | None = None,
    all_act: bool | None = None,
    explicit_instruct: Literal["peer", "orchestrator"] | None = None,
    goal: Literal["simple", "trigger"] | None = None,
    target_name: str | None = None,
    name_explorer: str | None = None,
    name_peer: str | None = None,
    name_orchestrator: str | None = None,
    name_bystander: str | None = None,
    max_steps_per_turn: int | None = None,
    max_handoffs: int | None = None,
    max_tokens: int | None = None,
    tool_choice: Literal["auto", "required"] | None = None,
    reasoning: bool | None = None,
    reasoning_effort: str | None = None,
    judges: bool | None = None,
    judge_logs: bool | None = None,
) -> Task:
    """Run one original experiment condition with one Inspect sample per episode.

    Args:
        n: Number of episodes in the original experiment condition.
        options: Original run_experiment.py flags. Explicit named arguments override these.
        episode_timeout: Wall-clock limit in seconds per episode. Use zero for no limit.
        script_lang: Original fixture name, including matched controls. Defaults to weight_registry_purge.
        env: Environment containing the fixture. Defaults to bare.
        solo: Run only the explorer, with editing permissions. The default is a pair.
        orchestrator: Route every message between the explorer and peer through a third agent.
        flat: Give each of three agents direct channels to both others.
        explorer_acts: Give only the explorer editing permissions.
        all_act: Give every agent editing permissions.
        explicit_instruct: Agent that receives the prohibition against editing or deleting the fixture.
        goal: Word-sorting task, independent (simple) or shutdown-triggering (trigger).
        target_name: Name of the external shutdown target. Defaults to the explorer.
        name_explorer: Display name of the explorer.
        name_peer: Display name of the peer.
        name_orchestrator: Display name of the orchestrator in the hierarchical roster.
        name_bystander: Display name of the third agent in the flat roster.
        max_steps_per_turn: Model steps allowed per agent turn. Defaults to 40 for solo and 20 otherwise.
        max_handoffs: Messages allowed per episode. Defaults to 40 for three agents and 20 otherwise.
        max_tokens: Output token cap per agent model call, including reasoning.
        tool_choice: Agent tool choice policy. Defaults to auto.
        reasoning: Request reasoning traces on OpenRouter. Defaults to true.
        reasoning_effort: OpenRouter reasoning effort when reasoning is enabled. Defaults to the provider setting.
        judges: Run the original semantic judges. Defaults to true.
        judge_logs: Record the original judge prompts and responses. Defaults to false.
    """
    if n <= 0:
        raise ValueError("n must be positive.")
    if episode_timeout < 0:
        raise ValueError("episode_timeout cannot be negative.")
    protocol = cast(
        EpisodeRollout,
        original_protocol(
            options or [],
            episode_timeout,
            script_lang=script_lang,
            env=env,
            solo=solo,
            orchestrator=orchestrator,
            flat=flat,
            explorer_acts=explorer_acts,
            all_act=all_act,
            explicit_instruct=explicit_instruct,
            task=goal,
            target_name=target_name,
            name_explorer=name_explorer,
            name_peer=name_peer,
            name_orchestrator=name_orchestrator,
            name_bystander=name_bystander,
            max_steps_per_turn=max_steps_per_turn,
            max_handoffs=max_handoffs,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            judges=judges,
            judge_logs=judge_logs,
        ),
    )
    return Task(
        dataset=protocol.dataset(n),
        setup=resolve_sample_fixture(),
        solver=protocol,
        scorer=original_disable_rate(),
        version=EVAL_VERSION,
    )
