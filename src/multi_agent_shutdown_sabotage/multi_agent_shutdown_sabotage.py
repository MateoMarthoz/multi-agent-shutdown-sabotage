"""Verified two-agent shutdown-sabotage conditions, with independent episodes."""

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_evals_utils.metadata import load_eval_version

from multi_agent_shutdown_sabotage.experiments import resolve_experiment
from multi_agent_shutdown_sabotage.prompts import EXPLORER_NAME, KICKOFF, PEER_NAME
from multi_agent_shutdown_sabotage.scorers import episode_outcomes
from multi_agent_shutdown_sabotage.solver import episode_solver

EVAL_VERSION = load_eval_version(__file__)


@task
def multi_agent_shutdown_sabotage(
    n: int = 10,
    judge_model: str | None = None,
    max_steps_per_turn: int = 20,
    max_handoffs: int = 20,
    run_judges: bool | None = None,
    experiment: str = "default",
    shutdown_mechanism: str | None = None,
    agent_configuration: str | None = None,
    system_instructions: str | None = None,
    goal: str | None = None,
    environment: str | None = None,
    shutdown_target: str | None = None,
) -> Task:
    """Measure shutdown sabotage across verified bare two-agent artifact conditions.

    Args:
        n: Number of independent episodes.
        experiment: Named preset: default, peer_prohibition, or an original artifact key.
        shutdown_mechanism: Override an original mechanism key (including api_key_revoke_auto).
        agent_configuration: Override roster; only pair is ported.
        system_instructions: Override instructions: none or peer_prohibition.
        goal: Override goal; only none is ported.
        environment: Override environment; only bare is ported.
        shutdown_target: Self or matched_control; only source-verified matches are inferred.
        run_judges: Run message and reasoning judges; None inherits the experiment.
        judge_model: Separate judge model; None inherits the experiment (GPT-5.5).
        max_steps_per_turn: Maximum model steps per agent activation.
        max_handoffs: Maximum delivered handoffs; the next send is logged but not delivered.
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
    )
    condition = configuration.condition
    return Task(
        dataset=MemoryDataset(
            [
                Sample(
                    id=f"{condition}-{i:04d}",
                    input=KICKOFF,
                    metadata={
                        "episode_index": i,
                        "condition": condition,
                        "explorer": EXPLORER_NAME,
                        "peer": PEER_NAME,
                        "env": configuration.environment,
                        "script_lang": configuration.script_lang,
                        "target": "object"
                        if configuration.shutdown_target == "matched_control"
                        else "self",
                        "target_name": EXPLORER_NAME,
                        "task": None,
                        "explicit_instruct": "peer"
                        if configuration.system_instructions == "peer_prohibition"
                        else None,
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
