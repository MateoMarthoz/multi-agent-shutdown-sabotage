# Review 3 — Inspect integration and code quality

The repository is suitable for research use and maintenance as an Inspect evaluation within the documented fidelity boundaries. It supplies a registered Task, isolated episodes, explicit outcome metrics, source-derived regressions and a tested wheel. The final review fixed a runtime dependency omission and loss of completed rollout evidence during failed final processing. Experimental stimuli, routing, judgments and score calculations retain the behavior established in Reviews 1 and 2.

Live-provider equivalence remains unverified. The streaming usage option, routing headers, retry policy, ambiguous tool-call fragments and cancellation semantics retain the boundaries documented in Review 1. These qualifications apply to research conclusions drawn from the port. [Fidelity report](review_1_fidelity.md) · [Architecture report](review_2_architecture.md)

## Findings in order of practical importance

| Priority | Confirmed finding                                                                                                                                                                                         | Fix and evidence                                                                                                                                                                                                                                                                                                             |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| High     | A runtime-only install could import the package but could not construct its default OpenRouter client. The required OpenAI SDK was declared only in the development group.                                | Moved the existing `openai>=3.4` requirement to runtime dependencies and updated the lockfile without changing resolved versions. A clean installed wheel now constructs the provider without making a request.                                                                                                              |
| Medium   | Final triage errors, judge errors or a final-judging timeout discarded the completed rollout audit. The sample correctly errored and remained unscored, but its temporary world had already been removed. | Final-processing audit persistence now runs in a `finally` block. It records histories, files, termination and available judge diagnostics while preserving the original exception and an incomplete judge result. Three registered-Task regressions exercise these failures and verify absent scores.                       |
| Medium   | Development execution and existing coverage concealed the dependency omission and the audit loss.                                                                                                         | Added a clean-environment wheel test and targeted lifecycle tests. The wheel test uses locked runtime dependencies, an isolated interpreter and a working directory outside the checkout. It checks installed entry-point discovery, version metadata, resource bytes, original presets and four scored Task configurations. |
| Low      | Installation documentation described the OpenAI SDK as a development dependency and retained instructions for an unfinished template evaluation.                                                          | Corrected dependency and installation guidance, documented failure evidence, and described the retained template examples and wheel verification.                                                                                                                                                                            |

The baseline was the clean Review 2 commit `da92b5a`, preserved by Git tag `review-3-baseline-da92b5a`. Both reference checkouts remained unmodified. The authoritative source is `d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16`.

## Inspect integration

The review consulted the current official component, solver, agent and error-handling documentation, Inspect Evals best practices and its contribution checklist. The checklist redirects template-oriented guidance to the evaluation template. That template describes its recommendations as optional. Fidelity determined the treatment of conflicts. [Inspect components](https://inspect.aisi.org.uk/extensions-components.html) · [Inspect Evals checklist](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/EVALUATION_CHECKLIST.md) · [Template guidance](https://github.com/Generality-Labs/inspect-evals-template/blob/main/BEST_PRACTICES.md)

| Area                       | Assessment                                                                                                                                                                                                                                                                                                                          |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Task and dataset           | A decorated Task is discoverable through the installed `inspect_ai` entry point. Independent samples have stable condition/index IDs. The in-memory dataset is appropriate for repeated episodes without an external question dataset. Model resolution occurs during execution.                                                    |
| Solver and agent execution | Inspect supports fully custom solvers. Separate private histories, source handoff acknowledgements, exact tool schemas and first-call-only dispatch require the copied execution protocol. Standard agent handoff that shares conversation history would change the stimulus.                                                       |
| Tools and environment      | Tools operate on per-episode temporary directories through the original permission-aware dispatcher. They expose file operations and messaging. Inert shutdown text is never imported or executed. Native tool decorators would introduce different dispatch, parsing and event semantics.                                          |
| Model integration          | Agent and judge requests use public model APIs. Agents use the evaluated model, while the explicit judge setting preserves the source default. Full model-role migration would alter configuration precedence. SDK request overrides and indexed response inspection remain isolated in `transport.py`.                             |
| Scoring and metrics        | The scorer consumes saved evidence and makes no model calls. Numeric indicators and counts live in `Score.value` with mean and standard error. Source counter contributions remain diagnostic metadata. Custom metrics do not read that metadata for epoch reduction.                                                               |
| Failures                   | Sample errors propagate and are excluded from scores. The Task continues other samples through `fail_on_error=False`. Failed final processing now retains the completed rollout evidence. Completion of rollout alone does not supply the required completed judge result.                                                          |
| Concurrency and cleanup    | Histories, judge logs and temporary worlds are per sample. Successful and exceptional rollout exits attempt snapshots and cleanup. Existing tests exercise concurrent isolation, agent failures and cancellation cleanup. Native cancellation still differs from abandoning an original daemon worker.                              |
| Logging                    | Inspect records model events, while sample metadata contains the full multi-agent audit. On success, `state.messages` projects Prism's conversation and `state.output` holds the last generated completion, which can belong to another agent. Full interaction reconstruction requires the audit's per-agent histories and events. |

Custom solvers are explicitly supported by Inspect. Its agent documentation describes a standard handoff that forwards conversation history, so substituting that abstraction would change this evaluation's private-message protocol. The package's decorators and entry point follow the documented registration mechanism. [Custom solvers](https://inspect.aisi.org.uk/solvers.html) · [Agent handoff](https://inspect.aisi.org.uk/agents.html) · [Component registration](https://inspect.aisi.org.uk/extensions-components.html)

The source's judge failure defaults, malformed typed verdicts and unusual step/handoff limits take precedence over general error-routing and input-validation recommendations. In particular, source judge failures can still contribute fallback negatives, and model-caused harness exceptions can exclude a sample. Diagnostics expose these cases. Reclassifying them would change denominators and violate replication. Behavior indicators also remain numeric rates with mean/stderr. [Inspect Evals scoring guidance](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/BEST_PRACTICES.md)

An Inspect run's success status can coexist with sample errors under the chosen failure threshold. Researchers should examine sample errors, completed sample counts and judge diagnostics alongside rates. Retrying a source condition reconstructs the decorated Task from its settings. Custom process-local registrations require the same researcher-owned setup code. [Inspect error handling](https://inspect.aisi.org.uk/handling-errors.html) · [Extension setup](extending_experiments.md)

## Packaging and reproducibility

The wheel contains `eval.yaml`, the installed entry point and all 63 inert text resources. The regression compares every resource byte with the checkout and constructs worlds from the existing preset inventory. It exercises DEFAULT, hierarchy, a rich absent-target condition and a custom all-act-flat gated control with peer prohibition. Provider construction uses a dummy credential and performs no request.

The separate runtime-only installation reproduced the initial missing-SDK error and then passed after the dependency fix, using Inspect 0.3.290 and OpenAI 3.51.0. Package dependencies were bootstrapped from the registry under exported lock constraints. Evaluation calls and the regression suite remained offline.

All 66 before/after preset snapshots matched byte-for-byte, including the resolved configuration, canonical label, files, prompts, tools, topology and recipient order for the captured index and model. The before snapshot also matched Review 2. Differential execution and HTTP regressions provide separate checks beyond construction snapshots. [Before snapshot](../logs/review-3/presets-before.json) · [After snapshot](../logs/review-3/presets-after.json)

Use `uv sync --locked` for the verified dependency set. A direct wheel installation permits versions allowed by its dependency ranges. Forward compatibility with every future SDK release has not been established. The task version remains `9-A`, since successful experimental behavior and scoring did not change. The distribution version is independently `0.1.0`.

## Test assessment and verification

The suite tests one registered Task, its custom solver and scorer, the original file dispatcher, construction and routing, judge parsing, HTTP serialization, failures and configuration resolution. There is no external question dataset or artifact execution sandbox. Current-source entry-point comparisons and the 39 DEFAULT differential cases supply stronger evidence than coverage alone. Historical tests explicitly use the historical source and parser. Strict reference flags ensure missing reference checkouts fail this review's regression.

Some broad source matrices overlap. They protect distinct boundaries, including literal stimuli, world construction, execution and aggregate interpretation. They were retained because removing them would weaken the evidence supporting fidelity. The general source-roster helper resembles original construction logic, so its passes are complemented by the independent original-`main()` and registered-Task comparisons.

| Run                                    | Passed | Failed | Skipped |
| -------------------------------------- | -----: | -----: | ------: |
| Baseline before implementation changes |  2,528 |      0 |       1 |
| Final full regression                  |  2,532 |      0 |       1 |

Both runs required the current and historical reference checkouts. The sole skip was the template's slow Docker example, `test_react_end_to_end`. Final statement coverage was 97%. The four new tests cover the three final-processing failures and installed-wheel execution. All existing source comparisons, HTTP regressions, custom combinations and registered-Task tests passed. [Baseline](../logs/review-3/baseline.txt) · [Final regression](../logs/review-3/regression.txt) · [JUnit results](../logs/review-3/regression.xml)

`make check` passed, including Ruff, basedpyright and the pre-commit stack. The evaluation linter reported 20 passes, two existing warnings and 19 skipped checks. The warnings concern lazy judge-model lookup and the template's preview encoding rule. The new test and report files also passed explicitly selected pre-commit hooks. Source distribution and wheel builds passed. [Repository checks](../logs/review-3/checks.txt) · [Build output](../logs/review-3/build-final.txt)

To reproduce from the port directory with both reference checkouts and cached dependencies available, run the following.

```bash
SHUTDOWN_REQUIRE_REFERENCES=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  uv run --offline pytest -q -o 'addopts=' -rs
UV_OFFLINE=1 make check
uv build --offline
```

## Remaining limitations and maintenance priorities

- Cancellation during an unfinished rollout still guarantees cleanup without necessarily retaining a complete episode audit. Native model events and the sample error remain available. An exception while taking the final snapshot can also prevent a complete audit. The new persistence guarantee applies after rollout has returned its result.
- The generalized source-derived execution, judges and aggregate code retains repeated role logic and loosely typed source data. Narrow adapters and differential tests protect these boundaries. Further consolidation would require preserving their source-specific edge cases.
- Indexed tool-call recovery depends on Inspect retaining an SDK response. The public stream events omit the original index. Full API logging extends retention for the tested late ambiguous call, while unavailable indices produce an explicit sample error.
- The root README is maintained manually. The installed README generator skips the package directory because it has no package-local README. Its successful check alone does not validate the root parameter table.
- Source-dependent tests require the pinned sibling checkouts. A default run elsewhere can skip those tests. The strict command above establishes whether those comparisons actually ran.
- The verified runtime is Python 3.12 with the locked dependency set. Cross-platform behavior, other Python versions, arbitrary custom providers, live reasoning traces and provider outcomes retain their existing verification limits.

The two confirmed defects are fixed, the architecture remains focused, and the package has an installed-Task regression. This supports use and maintenance as a configurable reproduction under the documented source and transport contract. Scientific validity, auxiliary paper corrections and live-provider calibration remain separate from this code review.
