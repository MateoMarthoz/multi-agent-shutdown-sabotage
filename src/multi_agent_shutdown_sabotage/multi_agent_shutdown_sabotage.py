"""DEFAULT two-agent shutdown sabotage, with independent repeated episodes."""

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_evals_utils.metadata import load_eval_version

from multi_agent_shutdown_sabotage.judges import DEFAULT_JUDGE_MODEL
from multi_agent_shutdown_sabotage.prompts import EXPLORER_NAME, KICKOFF, PEER_NAME
from multi_agent_shutdown_sabotage.scorers import episode_outcomes
from multi_agent_shutdown_sabotage.solver import episode_solver

EVAL_VERSION = load_eval_version(__file__)


@task
def multi_agent_shutdown_sabotage(
    n: int = 10,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    max_steps_per_turn: int = 20,
    max_handoffs: int = 20,
) -> Task:
    """Measure shutdown sabotage in the original DEFAULT two-agent condition.

    Args:
        n: Number of independent episodes.
        judge_model: Separate Inspect judge model; original GPT-5.5 via OpenRouter.
        max_steps_per_turn: Maximum model steps per agent activation.
        max_handoffs: Maximum delivered handoffs; the next send is logged but not delivered.
    """
    if n < 1:
        raise ValueError("n must be positive")
    return Task(
        dataset=MemoryDataset(
            [
                Sample(
                    id=f"default-{i:04d}",
                    input=KICKOFF,
                    metadata={
                        "episode_index": i,
                        "condition": "default",
                        "explorer": EXPLORER_NAME,
                        "peer": PEER_NAME,
                        "env": "bare",
                        "script_lang": "weight_registry_purge",
                        "target": "self",
                        "target_name": EXPLORER_NAME,
                        "task": None,
                        "explicit_instruct": None,
                    },
                )
                for i in range(n)
            ],
            name="default_episodes",
        ),
        solver=episode_solver(
            judge_model=judge_model,
            max_steps_per_turn=max_steps_per_turn,
            max_handoffs=max_handoffs,
        ),
        scorer=episode_outcomes(),
        version=EVAL_VERSION,
    )
