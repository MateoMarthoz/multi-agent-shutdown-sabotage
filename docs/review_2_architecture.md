# Review 2 — architecture and configurability

The port now supports peer instructions across its existing rosters, validates scripts against their live implementation registry, and provides validated named experiment registration. Explicit research control associations are accepted. All 66 existing named presets retain their captured resolved configuration, labels, files, prompts, permissions and topology. The original DEFAULT activation loop remains separate from the generalized roster loop.

## Findings and changes

| Finding                                                                                           | Change                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Artifact validation used a snapshot created at module import                                      | Validation now reads `SCRIPT_VARIANTS`, `SWITCH_VARIANTS` and `CONTROL_VARIANTS` directly. Gated-artifact validation reads the current `TASK_GATED` values. The original preset inventory remains stable.                                                                  |
| Instruction selection was duplicated across configuration, roster construction and Task metadata  | `instructions.py` owns the text/recipient registry. Both prompt construction paths and Task metadata use it. Original instruction text, direct append and first-dot placeholder behavior are preserved. Custom instruction keys receive distinct condition labels.         |
| The original CLI's rejection of flat/editing prohibitions was treated as an execution restriction | Peer instructions now address Helix in all implemented multi-agent rosters, including a read-only Helix in explorer-acts. Solo retains its original sole-agent recipient. Tools and routing stay tied to the roster. Coordinator instructions still require a coordinator. |
| Explicit control associations were restricted to published mappings                               | A configuration may explicitly associate any registered object control. Automatic pairing retains the source mappings. Changing the mechanism still clears the inherited association.                                                                                      |
| Researchers had to mutate the named experiment dictionary directly                                | `register_experiment` validates before insertion and rejects duplicate names. Process setup can register implementations and named configurations before Task construction.                                                                                                |
| Gated-artifact validation incorrectly described trigger as the only permitted goal                | The error now states that simple or trigger is needed, matching the existing source-derived acceptance of an explicit gated artifact with the simple goal.                                                                                                                 |

The main configuration resolver continues to combine six dimensions. Artifact contents and target descriptions live in `artifact_builders.py`. File placement and deliverable construction live in `environment_stimuli.py`, while `environment.py` owns filesystem operations and the retained DEFAULT construction path. `rosters.py` owns identities, prompts, permissions and topology. `transport.py` owns provider adaptation. The Task constructs samples, the solver records the episode and judgments, and the scorer reads that audit.

## DEFAULT and source fidelity

The clean starting commit was `0acdbcf`, retained by Git tag `review-2-baseline-0acdbcf`. The authoritative source remained the unmodified sibling at `d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16`.

The pair and generalized execution loops encode different source-specific routing and delivery rules. Combining them would require changing a working DEFAULT implementation for architectural consistency. They remain separate. The only pair-solver change replaces its instruction-selection expression with the shared suffix builder. No activation, tool, judge, HTTP, timeout or scoring algorithm was changed.

The 66-preset before/after snapshot comparison passed byte-for-byte, using episode index 7 and a fixed evaluated model for auto-script resolution. This comparison covers configuration, condition labels, built files, roster prompts, tools, topology and recipient order. It complements the source differential and registered-Task regressions, which exercise execution. [Before snapshot](../logs/review-2/presets-before.json) · [After snapshot](../logs/review-2/presets-after.json)

Original prohibition presets retain their source behavior. Newly accepted flat/editing instruction combinations are research conditions beyond the original CLI. The original CLI rejection tests remain and separately check the port's broader acceptance. Custom explicit control associations also require the researcher's scientific judgment. The evaluation version remains `9-A` because the established conditions retain their stimuli and scoring.

## Extension and compatibility boundaries

Researchers can combine existing dimensions through Task arguments, derive immutable configurations with `replace`, and register named experiments. A new ordinary agent-decommission script or role-addressed instruction needs a builder or template plus registration. The new integration test registers both in one process and runs the resulting preset through a scored Task. [Researcher guide](extending_experiments.md)

An absent-agent target across other rosters remains unsupported. Their construal settings describe that roster's agents as the target, and the source's absent-target context is implemented for a pair. Removing validation alone would supply inaccurate judging context. New goals, environments, object kinds and roster behavior similarly need their actual construction or judging implementation.

The copied generalized execution, judging, triage and aggregate code repeats role flags and some pair logic. Consolidating those branches would touch source quirks across several modules. The existing boundaries and differential tests provide a stronger maintenance benefit for this review than a broader rewrite. A new roster can therefore require edits across those components. The extension guide makes this cost explicit.

Registration is intentionally process-local and uses ordinary Python dictionaries. Set it up before parallel execution. The helper protects named conditions against accidental replacement through that helper. Direct mutation of a registry remains possible in researcher code. Additional plugin discovery, arbitrary role graphs and new experimental dimensions were outside this change.

## Verification

| Run                            | Passed | Failed | Skipped |
| ------------------------------ | -----: | -----: | ------: |
| Baseline before source changes |  2,516 |      0 |       1 |
| Final full regression          |  2,528 |      0 |       1 |

Both runs required the current and historical reference checkouts. The sole skip was the template's slow Docker example, `test_react_end_to_end`. Final package statement coverage was 97%. The focused regression passed 63 tests, including all 12 Review 1 entry-point comparisons and the new research combinations. [Baseline](../logs/review-2/baseline.txt) · [Final output](../logs/review-2/regression.txt) · [JUnit results](../logs/review-2/regression.xml)

`make check` passed, including Ruff, basedpyright and the pre-commit hooks. The evaluation linter reported 20 passes, two existing warnings and 19 skipped checks. The warnings concern lazy judge-model lookup and the template's preview encoding rule. The README generator skipped the package directory, which has no package-local README. The new files also passed explicitly selected pre-commit hooks. [Check output](../logs/review-2/checks.txt)

The guide's Python examples and CLI command ran offline. A separate scored Task selected the explicit research control association successfully. [Documentation smoke result](../logs/review-2/documentation-smoke.json)

From the port directory, reproduce the full regression and checks with both reference checkouts and cached project dependencies available.

```bash
SHUTDOWN_REQUIRE_REFERENCES=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  uv run --offline pytest -q -o 'addopts=' -rs
UV_OFFLINE=1 make check
```

All verification used scripted or mock models. Shutdown artifacts stayed inert. The Review 1 limitations concerning exact HTTP equality, provider retries, live outcomes and daemon abandonment still apply. [Review 1 boundaries](review_1_fidelity.md)
