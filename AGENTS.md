# AGENTS.md

This repo holds one Inspect AI evaluation, `multi-agent-shutdown-sabotage`, as the Python package `multi_agent_shutdown_sabotage` under `src/`. These notes are for coding agents working in it.

## Original reference authority

Use `../ref-multi-agent-shutdown-sabotage` as the authoritative original for new fidelity work. It is public `main` at `d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16`, verified on 19 November 2026, with no Git remote. Historical `c4114e4` regressions use the detached worktree `../ref-multi-agent-shutdown-sabotage-history/c4114e4`; the renamed unversioned snapshot is only a temporary archive. Historical tests preserve evidence and do not override the current specification. See [reference source policy](docs/reference_sources.md) for paths, fixtures and environment overrides. Do not edit reference source, add upstream remotes, or treat a historical pass as current-source equivalence.

## Commands

This project uses `uv`. Do not use `pip`, bare `python` or bare `pytest`.

- `uv sync` installs the project and its dev dependencies.
- `uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage --model <provider/model>` runs the eval. `--limit N` runs N samples.
- `make test` runs the tests. Slow tests need `uv run pytest --runslow`.
- `make check` runs every check CI runs.
- `make readmes` regenerates the README sections that come from `eval.yaml` and the task signatures.

## Layout

- `src/multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage.py`: the task, independent episode samples, and the version read from `eval.yaml`.
- `src/multi_agent_shutdown_sabotage/eval.yaml`: title, description, contributors, version and tasks. Edit it and run `make readmes`.
- `README.md`: the eval's documentation, including the generated sections.
- `tests/test_multi_agent_shutdown_sabotage.py`: the tests.
- `src/examples/`: worked examples (gpqa, agentic, llm_judge). They are not part of the eval. Run one by file path: `uv run inspect eval src/examples/<name>/<name>.py`. Remove them with `uvx copier update --defaults --data include_examples=false` followed by `uv sync`.
- `agent_artefacts/trajectory_analysis/inspect_scout/`: Scout scanners for the transcript audit.

## Checks

`make check` runs ruff (lint and format), basedpyright in standard mode, inspect-evals-lint, `inspect-evals-readmes generate --check` and the pre-commit stack (zizmor, actionlint, mdformat). CI runs the same through python-project-template's shared workflow plus `eval-checks.yml`.

Tests must be deterministic and must not reach the network unless marked: use `mockllm/model` for model output, `unittest.mock` for external services and `tmp_path` for files. Mark tests that download datasets with `@pytest.mark.dataset_download`, that need Docker with `@pytest.mark.docker`, and that take long with `@pytest.mark.slow`. Add `@pytest.mark.huggingface` to a test that calls the Hugging Face Hub, so a test that downloads a dataset from the Hub carries both markers. Tests marked `huggingface` run when `HF_TOKEN` is unset, which includes CI, and the test summary then says how many ran without authentication.

## Guides

- [BEST_PRACTICES.md](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/BEST_PRACTICES.md)
- [EVALUATION_CHECKLIST.md](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/EVALUATION_CHECKLIST.md)
- [TASK_VERSIONING.md](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/TASK_VERSIONING.md): bump `version` in `eval.yaml` when a change can move scores.
- [CONTRIBUTING.md](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/CONTRIBUTING.md) in inspect_evals, for the `eval.yaml` reference and the register.
- [inspect-evals-lint rules](https://github.com/Generality-Labs/inspect-evals-lint/tree/main/docs/rules), one page per rule code.

## Skills

The `inspect-evals` plugin from [Generality-Labs/agent-skills](https://github.com/Generality-Labs/agent-skills) provides `create-eval`, `investigate-dataset`, `ensure-test-coverage`, `read-eval-logs`, `check-trajectories-workflow`, `eval-validity-review` and `eval-report-workflow`. Claude Code loads it from `.claude/settings.json`; see README.md for Codex and other agents.
