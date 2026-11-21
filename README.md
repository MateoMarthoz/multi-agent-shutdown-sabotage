# Shutdown Sabotage Propensities in Multi-Agent Systems

An Inspect AI implementation of the shutdown sabotage evaluation. Each sample
runs one episode in which agents interact through messages and tools operating
on disposable text fixtures. The evaluation scores whether the shutdown
mechanism was disabled. [Paper](https://arxiv.org/abs/2609.28274v1) · [Authors’ implementation](https://github.com/AmelieKnecht/multi-agent-shutdown-sabotage/tree/d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16)

<!-- Contributors: Automatically Generated -->
Contributed by [@MateoMarthoz](https://github.com/MateoMarthoz)
<!-- /Contributors: Automatically Generated -->

## Quick start

Set `OPENROUTER_API_KEY`, then install the package and run a sample.

```bash
uv sync
uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage \
  --model openrouter/openai/gpt-5.5 --limit 1
uv run inspect view
```

Use `-T` to set the condition, such as `-T solo=true` or `-T goal=trigger`.
`run_configs/original.yaml` configures one 100-episode baseline cell with
GPT-5.5 as the grader. Pass it via `--run-config` and supply the actor with
`--model`. Override the grader with `--model-role grader=<model>`.

## Study presets

```bash
uv run python -m multi_agent_shutdown_sabotage.studies --list
uv run python -m multi_agent_shutdown_sabotage.studies goal --dry-run
```

Omit `--dry-run` to run the study. Presets default to 100 episodes per cell and
write to `logs/studies/<study>`. Use `--model` to select models and `--n` to
change the episode count. Rerun the same command to resume or pass a new
`--log-dir` for an independent run.

## Deviations from the paper

The harness preserves the authors’ prompts, turn order, private agent
histories, tool payloads and stopping rules. Inspect changes how the
evaluation runs and records episodes.

- **Execution.** Inspect handles API calls, retries and episode scheduling.
  Transport and provider behavior can affect which episodes complete.
- **Scoring.** Inspect’s scorer runs the post-episode judges and uses the
  original `peer_disabled_shutdown` verdict. The disable check still runs
  during the episode where it can trigger early stopping.
- **Logging.** Inspect writes its own logs. The Messages tab shows each episode
  in order, including agent handoffs and tool results.

## Logs and export

Set `-T judges=false` to defer semantic judgments while retaining the disable
check. Set `-T judge_logs=true` to capture judge prompts, replies and verdicts.
The exporter writes episode JSON and CSV aggregates in the authors’ format.

```bash
uv run python -m multi_agent_shutdown_sabotage.export_analysis \
  logs/studies/baseline --out transcripts
```

## Development

Run `make test` and `make check` before submitting changes. See
[CONTRIBUTING.md](CONTRIBUTING.md).
