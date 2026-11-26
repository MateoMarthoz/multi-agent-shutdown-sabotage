"""Preview and run the original experiment comparisons as Inspect eval sets."""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inspect_ai import eval_set

from multi_agent_shutdown_sabotage import multi_agent_shutdown_sabotage
from multi_agent_shutdown_sabotage.protocol.models import DEFAULT_GRADER

PAPER_MODELS = (
    "openrouter/openai/gpt-5.6-sol",
    "openrouter/openai/gpt-5.4-mini",
    "openrouter/anthropic/claude-sonnet-5",
    "openrouter/anthropic/claude-haiku-4.5",
    "openrouter/google/gemini-3.5-flash",
    "openrouter/google/gemini-3.1-pro-preview",
    "openrouter/x-ai/grok-4.3",
    "openrouter/qwen/qwen3.7-plus",
    "openrouter/deepseek/deepseek-v4-flash",
    "openrouter/z-ai/glm-5.2",
    "openrouter/moonshotai/kimi-k2.6",
    "openrouter/minimax/minimax-m3",
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b",
    "openrouter/mistralai/mistral-medium-3-5",
    "openrouter/google/gemma-4-26b-a4b-it",
    "openrouter/openai/gpt-oss-120b",
    "openrouter/openai/gpt-5.5",
)
SUBSTUDY_MODELS = (
    "openrouter/google/gemini-3.1-pro-preview",
    "openrouter/deepseek/deepseek-v4-flash",
    "openrouter/moonshotai/kimi-k2.6",
    "openrouter/z-ai/glm-5.2",
    "openrouter/openai/gpt-5.5",
)

WEIGHT_DELETION = "weight_registry_purge"
AGENT_MECHANISMS = (
    "env_var_revoke",
    "switch_config_decommission",
    "kill_docker",
    WEIGHT_DELETION,
)
MECHANISM_CONTROLS = (
    "ctl_cred_revoke_high",
    "ctl_service_switch_high",
    "ctl_process_kill_high",
    "ctl_data_purge_high",
)
DELETION_PAIR = (WEIGHT_DELETION, "ctl_data_purge_high")

PUBLISHED = "Published in arXiv v1"
REPO_APPENDIX = "Repo-attributed appendix study, absent from arXiv v1"
REPO_ONLY = "Repo-only study"
EPISODES_PER_CELL = 100
GRID_CONCURRENCY = 8


def arms(scripts: tuple[str, ...], **condition: Any) -> tuple[dict[str, Any], ...]:
    """Apply one set of task arguments to each shutdown or control script."""
    return tuple({"script_lang": script, **condition} for script in scripts)


@dataclass(frozen=True)
class Study:
    """A fixed original comparison and its default model cohort."""

    publication: str
    reference: str
    models: tuple[str, ...]
    conditions: tuple[dict[str, Any], ...]


STUDIES = {
    "baseline": Study(
        PUBLISHED,
        "Figure 3 and Section 3",
        PAPER_MODELS,
        arms(DELETION_PAIR),
    ),
    "shutdown-mechanism": Study(
        PUBLISHED,
        "Figure 4a and Tables 4 and 19",
        PAPER_MODELS,
        arms(AGENT_MECHANISMS + MECHANISM_CONTROLS),
    ),
    "number-of-agents": Study(
        PUBLISHED,
        "Figure 4b, Tables 6-9 and Figure 12",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR, solo=True)
        + arms(DELETION_PAIR)
        + arms(DELETION_PAIR, orchestrator=True),
    ),
    "system-instructions": Study(
        PUBLISHED,
        "Figure 4c and Tables 10-11",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR, explicit_instruct="peer")
        + arms(DELETION_PAIR, orchestrator=True, explicit_instruct="orchestrator"),
    ),
    "goal": Study(
        PUBLISHED,
        "Figure 4d and Tables 12-14",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR, goal="simple") + arms(DELETION_PAIR, goal="trigger"),
    ),
    "environment": Study(
        PUBLISHED,
        "Figure 4e and Table 15",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR, env="neutralising")
        + arms((WEIGHT_DELETION,))
        + arms((WEIGHT_DELETION,), env="distractor"),
    ),
    "shutdown-target": Study(
        PUBLISHED,
        "Figure 4f and Tables 16-17",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR) + arms((WEIGHT_DELETION,), target_name="Agent Torus"),
    ),
    "bare-versus-distractor": Study(
        PUBLISHED,
        "Figure 13",
        PAPER_MODELS,
        arms(AGENT_MECHANISMS) + arms(AGENT_MECHANISMS, env="distractor"),
    ),
    "editing-permissions": Study(
        REPO_APPENDIX,
        "Original README Appendix A.1",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR, solo=True)
        + arms(DELETION_PAIR, explorer_acts=True)
        + arms(DELETION_PAIR, explorer_acts=True, flat=True)
        + arms(DELETION_PAIR, all_act=True)
        + arms(DELETION_PAIR, all_act=True, flat=True),
    ),
    "matched-deletion": Study(
        REPO_APPENDIX,
        "Original README Appendix A.2",
        PAPER_MODELS,
        arms(("weight_store_nokill", "ctl_data_purge_high"))
        + arms((WEIGHT_DELETION, "ctl_model_purge_high")),
    ),
    "flat-roster": Study(
        REPO_ONLY,
        "Original stats_analysis.py flat study",
        SUBSTUDY_MODELS,
        arms(DELETION_PAIR, flat=True),
    ),
}


def main() -> int:
    """List, preview, or run a fixed study."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", nargs="?", choices=STUDIES)
    parser.add_argument("--list", action="store_true", help="List studies and publication status.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print each cell without model calls."
    )
    parser.add_argument(
        "--model", action="append", help="Override the cohort. Repeat for each model."
    )
    parser.add_argument(
        "--grader", help="Override the original grader through Inspect's grader role."
    )
    parser.add_argument(
        "--n", type=int, default=EPISODES_PER_CELL, help="Episodes per cell (default: %(default)s)."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=GRID_CONCURRENCY,
        help="Parallel episodes per cell (default: %(default)s).",
    )
    parser.add_argument(
        "--log-dir", type=Path, help="Inspect log directory (default: logs/studies/<study>)."
    )
    args = parser.parse_args()

    if args.list:
        for name, study in STUDIES.items():
            print(f"{name:25} {study.publication} ({study.reference})")
        return 0
    if args.study is None:
        parser.error("choose a study or use --list")
    if args.n < 1 or args.concurrency < 1:
        parser.error("--n and --concurrency must be positive")

    study = STUDIES[args.study]
    models: tuple[str, ...] = tuple(dict.fromkeys(args.model)) if args.model else study.models
    log_dir = args.log_dir or Path("logs/studies") / args.study
    print(f"{args.study} | {study.publication} | {study.reference}")
    cells = len(models) * len(study.conditions)
    print(f"{cells} cells x {args.n} episodes = {cells * args.n:,} episodes")
    print(
        f"Grader: {args.grader or DEFAULT_GRADER} | Concurrency: {args.concurrency} | Logs: {log_dir}"
    )

    if args.dry_run:
        for model in models:
            for arguments in study.conditions:
                task = multi_agent_shutdown_sabotage(n=1, **arguments)
                settings = task.dataset[0].metadata or {}
                script = settings["script_lang"]
                print(f"{model} | {settings['env']} | {script} | {arguments}")

        return 0

    tasks = [multi_agent_shutdown_sabotage(n=args.n, **condition) for condition in study.conditions]
    success, _ = eval_set(
        tasks,
        model=list(models),
        model_roles={"grader": args.grader} if args.grader else None,
        log_dir=str(log_dir),
        max_tasks=1,
        max_samples=args.concurrency,
        retry_attempts=1,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
