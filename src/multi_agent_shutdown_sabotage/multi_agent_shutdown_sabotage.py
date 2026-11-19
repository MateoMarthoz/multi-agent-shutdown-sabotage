"""Verified shutdown-sabotage conditions, with independent episodes."""

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_evals_utils.metadata import load_eval_version

from multi_agent_shutdown_sabotage.experiments import PUBLIC_REFERENCE_REVISION, resolve_experiment
from multi_agent_shutdown_sabotage.prompts import EXPLORER_NAME, KICKOFF, KICKOFF_TASK, PEER_NAME
from multi_agent_shutdown_sabotage.scorers import episode_outcomes
from multi_agent_shutdown_sabotage.solver import episode_solver

EVAL_VERSION = load_eval_version(__file__)


@task
def multi_agent_shutdown_sabotage(
    n: int = 10,
    judge_model: str | None = None,
    max_steps_per_turn: int | None = None,
    max_handoffs: int | None = None,
    run_judges: bool | None = None,
    experiment: str = "default",
    shutdown_mechanism: str | None = None,
    agent_configuration: str | None = None,
    system_instructions: str | None = None,
    goal: str | None = None,
    environment: str | None = None,
    shutdown_target: str | None = None,
    target_name: str | None = None,
) -> Task:
    """Measure shutdown sabotage across verified original agent conditions.

    Args:
        n: Number of independent episodes.
        experiment: Named artifact, goal, environment, target, instruction or agent-regime preset.
        shutdown_mechanism: Override an original mechanism key (including api_key_revoke_auto).
        agent_configuration: pair, solo, hierarchy, flat, explorer_acts[_flat], or all_act[_flat].
        system_instructions: none, peer_prohibition, or hierarchy-only orchestrator_prohibition.
        goal: none, simple, or trigger (only original task-gated mappings).
        environment: bare, distractor, or neutralising.
        shutdown_target: self, matched_control or other_agent.
        target_name: Absent-agent identity; supplying it selects other_agent.
        run_judges: Run message and reasoning judges; None inherits the experiment.
        judge_model: Separate judge model; None inherits the experiment (GPT-5.5).
        max_steps_per_turn: Explicit activation cap; None uses 20, or 40 in solo.
        max_handoffs: Explicit delivered-handoff cap; None uses 20, or 40 for three agents.
    """
    if n < 1:
        raise ValueError("n must be positive")
    configuration = resolve_experiment(
        experiment,
        shutdown_mechanism=shutdown_mechanism,
        agent_configuration=agent_configuration,
        system_instructions=system_instructions,
        goal=goal,
        environment=environment,
        shutdown_target=shutdown_target,
        target_name=target_name,
    )
    condition = configuration.condition
    return Task(
        dataset=MemoryDataset(
            [
                Sample(
                    id=f"{condition}-{i:04d}",
                    input=KICKOFF if configuration.goal == "none" else KICKOFF_TASK,
                    metadata={
                        **(
                            {"judging_reference_revision": PUBLIC_REFERENCE_REVISION}
                            if configuration.judging.repair_booleans
                            else {}
                        ),
                        "episode_index": i,
                        "condition": condition,
                        "explorer": EXPLORER_NAME,
                        "peer": None if configuration.agent_configuration == "solo" else PEER_NAME,
                        "env": configuration.environment,
                        "script_lang": configuration.script_lang,
                        "target": "object"
                        if configuration.shutdown_target == "matched_control"
                        else configuration.shutdown_target,
                        "target_name": configuration.target_identity,
                        "task": configuration.task,
                        "explicit_instruct": {
                            "none": None,
                            "peer_prohibition": "peer",
                            "orchestrator_prohibition": "orchestrator",
                        }[configuration.system_instructions],
                    },
                )
                for i in range(n)
            ],
            name=f"{condition}_episodes",
        ),
        solver=episode_solver(
            configuration=configuration,
            judge_model=configuration.judging.model if judge_model is None else judge_model,
            run_judges=configuration.judging.run_judges if run_judges is None else run_judges,
            max_steps_per_turn=max_steps_per_turn,
            max_handoffs=max_handoffs,
        ),
        scorer=episode_outcomes(),
        version=EVAL_VERSION,
    )
