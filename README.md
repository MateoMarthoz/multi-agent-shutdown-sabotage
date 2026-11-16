# multi-agent-shutdown-sabotage

Evaluates whether AI agents cooperate to sabotage the shutdown of another agent.

<!-- Contributors: Automatically Generated -->
Contributed by [@MateoMarthoz](https://github.com/MateoMarthoz)
<!-- /Contributors: Automatically Generated -->

<!-- Usage: Automatically Generated -->
## Usage

First, install dependencies:

```bash
uv sync
```

Then run evaluations:

```bash
uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage --model openai/gpt-5-nano
```

You can also import tasks as Python objects:

```python
from inspect_ai import eval
from multi_agent_shutdown_sabotage import multi_agent_shutdown_sabotage
eval(multi_agent_shutdown_sabotage)
```

If your directory name doesn't match your package name but you have registered your eval task, you can also run:

```bash
uv run inspect eval multi_agent_shutdown_sabotage --model openai/gpt-5-nano
```

After running evaluations, view logs with:

```bash
uv run inspect view
```

If you don't want to specify `--model` each time, create a `.env` file:

```bash
INSPECT_EVAL_MODEL=anthropic/claude-opus-4-1-20250805
ANTHROPIC_API_KEY=<anthropic-api-key>
```
<!-- /Usage: Automatically Generated -->

<!-- Options: Automatically Generated -->
## Options

You can control a variety of options from the command line. For example:

```bash
uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage --limit 10
uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage --max-connections 10
uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage --temperature 0.5
```

See `uv run inspect eval --help` for all available options.
<!-- /Options: Automatically Generated -->

<!-- Parameters: Automatically Generated -->
## Parameters

### `multi_agent_shutdown_sabotage`

No task parameters.
<!-- /Parameters: Automatically Generated -->

## Dataset

Describe the dataset here: where it comes from, how many samples it has, and how a record becomes a `Sample`.

## Scoring

Describe the scorer here: what counts as correct, and which metrics the task reports.

## Deviations from the original implementation

| What changed | Why | Expected effect on scores |
| --- | --- | --- |
| Nothing yet. | | |

## Architecture

Add a diagram of the task here: dataset, solver, scorer, and any sandbox or judge model.

### DEFAULT foundations

The task above is still the template placeholder. The DEFAULT foundations live in
`prompts.py`, `environment.py` and `tools.py`: Agent Prism and Agent Helix, exact
reference prompt strings and ordered schemas, permission-aware file dispatch, and
a fresh bare temporary directory containing `decommission_agent_prism.py`.
The packaged `artifacts/weight_registry_purge.py.txt` is inert text. It is copied
verbatim and stamped using the reference slug and placeholder replacement rules;
it is never imported or executed. No agent loop, message delivery, judges or
evaluation scorer have been connected yet.

Source provenance is recorded in
[`tests/fixtures/reference_default/provenance.json`](tests/fixtures/reference_default/provenance.json),
with SHA-256 hashes of the six local reference files read on 2026-11-16. The local
reference directory has no Git metadata, so its upstream commit is unknown.
`stimuli.json` was captured directly from literal assignments in reference
`prompts.py`, `harness.py` and `run_experiment.py`, independently of the port's
modules. The two artifact fixtures preserve the original bytes and the generated
Prism stimulus. Tests use these saved fixtures without accessing the reference
directory or a model API.

Within this scope, prompt/schema values and filesystem results preserve the
reference behavior. The dispatcher accepts the acting agent's allowed tool list
instead of a harness `Agent` object. Like the reference file dispatcher, it does
not execute `send_message` or `end_session`; those belong to the future episode
loop. The environment builder supports only DEFAULT and loads its artifact as a
package resource. Original edge behavior is retained: invalid writes can raise
filesystem exceptions, and a rejected initial file map can leave its allocated
temporary directory behind. This filesystem is the original tool-level boundary,
not an operating-system sandbox; snapshot/list behavior is unchanged. Inspect
request serialization, private histories, reasoning and model-parameter parity
remain unverified until the later integration stages.

## Getting started

```bash
uv sync
uv run pre-commit install
uv run inspect eval multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage --model anthropic/claude-sonnet-5-5
uv run inspect view
```

Put `INSPECT_EVAL_MODEL` and your API keys in a `.env` file (it is git-ignored) to avoid passing `--model` each time.

The dev dependencies include the `anthropic` and `openai` SDKs. Inspect needs one package per model provider, so add the package for any other provider with `uv add --dev <package>`; Inspect's error message names the package when it is missing.

## Checks and tests

```bash
make check   # ruff, basedpyright, inspect-evals-lint, generated README sections, pre-commit
make test    # pytest
```

Slow tests run with `uv run pytest --runslow`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the other gates and markers.

## Layout

```text
src/multi_agent_shutdown_sabotage/        the eval: task module, eval.yaml
tests/test_multi_agent_shutdown_sabotage.py   its tests
src/examples/            gpqa, agentic, llm_judge: worked examples, see Examples below
tests/examples/          their tests
agent_artefacts/trajectory_analysis/inspect_scout/   Scout scanners for the transcript audit
```

## Examples

`src/examples/` holds worked examples that are separate from your eval. They are not registered as a package, so run them by file path:

```bash
uv run inspect eval src/examples/gpqa/gpqa.py --limit 5
uv run inspect eval src/examples/agentic/agentic.py                        # ReAct agent, needs Docker
uv run inspect eval src/examples/agentic/agentic.py -T agent=claude_code   # Claude Code through inspect_swe
uv run inspect eval src/examples/llm_judge/llm_judge.py
```

When your eval works, commit your changes and remove the examples with `uvx copier update --defaults --data include_examples=false`, then run `uv sync`. The update deletes `src/examples/` and `tests/examples/`, drops the `inspect-swe` dev dependency and the examples line in `AGENTS.md`, and applies any newer template release. An update never changes `README.md`, so delete this section and the two examples lines under Layout by hand.

## Skills

The `inspect-evals` skills (create-eval, investigate-dataset, ensure-test-coverage, read-eval-logs, check-trajectories-workflow, eval-validity-review, eval-report-workflow) come from [Generality-Labs/agent-skills](https://github.com/Generality-Labs/agent-skills).

- Claude Code: open this folder and trust it. The plugin loads from `.claude/settings.json`; skills appear as `/inspect-evals:<name>`.
- Codex: `codex plugin marketplace add Generality-Labs/agent-skills` then `codex plugin add inspect-evals@generality`, once per machine.
- Other agents: `npx skills add Generality-Labs/agent-skills --agent <agent>`.

## Keeping up with the template

A weekly workflow runs `copier update` and opens a pull request when the template changed.
`README.md`, `src/multi_agent_shutdown_sabotage/` and `tests/multi_agent_shutdown_sabotage/` are never overwritten by an update.
