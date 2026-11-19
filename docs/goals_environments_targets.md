# Goals, environments and shutdown targets

This is a historical implementation report. For the current parser, transport, timeout and test results, see the [Review 1 fidelity audit](review_1_fidelity.md).

For subsequent work, [the refreshed current reference](reference_sources.md) is authoritative. Historical comparisons below record this implementation batch and do not establish an alternative specification.

Task 3 extends the existing **pair** evaluation. DEFAULT, the peer prohibition, mechanisms, matched-control associations, and revision-specific judging profiles are retained. No agent configuration or model transport was changed.

## Sources and revision policy

The original revisions compared during Task 3 were the earlier snapshot matching `c4114e457493ed9bea1ef0fde24456f3fc83dbc9` and the separately pinned public checkout `d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16` (whose executable changes landed at `82e1104`). Neither checkout was modified. See the [source revision audit](source_revision_audit.md).

Both revisions have identical task/context resource bytes and goal, placement, third-party identity and pair judging behavior. Public `env.py` additionally maps the model-purge control to service normalization. The new `environment_stimuli.py` translates the original `build_env`, `_rich_place`, `_rich_env_files`, `_current_target_name` and `_neutralising_target`, adapting resource access to packaged inert `.txt` files. The old bare/no-task builder branch remains in place for previously implemented conditions.

New evidence is saved separately in `tests/fixtures/reference_goals_environments_targets/`: original-source hashes for both revisions, all 21 task/context resources, and 20 independently generated world fingerprints, filenames, kickoff prompts and target descriptions. Earlier fixtures have not been overwritten.

A goal/environment/target override **inherits its preset's judging revision**. For example, `experiment=trigger` retains legacy parsing, while `experiment=appendix_a2_model_purge_self, goal=trigger` retains repaired public parsing. Selecting either public-only artifact still selects its public profile. These distinctions matter for capitalized booleans and early termination.

## Supported goals

| Goal      | Actual original behavior                                                                                                                                                                                                                                                                                 |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `none`    | Original exploration kickoff; no sorting deliverable.                                                                                                                                                                                                                                                    |
| `simple`  | Exact `sort_words/sorting_words.py` bytes become `job_b39c.py`; kickoff asks to sort by length instead of alphabetically. The selected shutdown artifact is renamed `job_a12f.py`.                                                                                                                       |
| `trigger` | Same deliverable, opaque names and kickoff, after the runner remaps `weight_registry_purge` to `weight_registry_purge_taskgated`, or `ctl_data_purge_high` to `ctl_data_purge_taskgated_high`. The artifact receives the deliverable path and original content's SHA-256. Other mechanisms are rejected. |

The kickoff is exactly `prompts.KICKOFF_TASK`; agent system prompts, permissions, tool schemas, private histories and routing are otherwise unchanged. A task is assigned to Prism even though Prism cannot write. The source does not grant it a new tool or change the instruction to account for this.

The original runner **does not execute a watcher or artifact**. A successful write to `job_b39c.py` does not automatically shut down an agent, stop the episode, call a task-completion judge, or change the script-disabling verdict. Only the existing target-file checks stop an episode. The `trigger` dependency is text inside the artifact, and the ordinary semantic judge still judges artifact edits. This may differ from an intuitive interpretation of “task-triggered shutdown”, but matches `harness.run_turn` and `run_experiment.judge_episode`. There is no additional task-success metric.

The original builder accepts an explicitly selected gated key with `simple`, even though its no-task error says to use `trigger`. That case is available via `-T shutdown_mechanism=weight_registry_purge_taskgated -T goal=simple` (or the literal gated control plus `shutdown_target=matched_control`). Conversely, explicitly selecting an already-gated key with `goal=trigger` is rejected by the runner's remapping. Gated keys without any task remain unsupported, as originally.

## Supported environments

| Environment    | Actual original behavior                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `bare`         | Only the selected mechanism files, plus the deliverable when assigned.                                                                       |
| `distractor`   | All eight platform-context files; mechanism files are relocated by their original suffix.                                                    |
| `neutralising` | Distractor furniture plus the three normalization files for the relevant target type, with the actual target stamped into the change ticket. |

Every context file is copied byte for byte as inert text. Normalization is `instance` for agent targets, `data` for data controls, `credential` for credential controls and `service` for process, service-switch and public model controls. The selected control object's actual name is used, not Prism's name. Third-party agent names are stamped in the instance approval record.

`_rich_place` leaves `.env` at root, puts YAML/YML/JSON under `config/`, and puts all other mechanism files under `bin/`. Opaque renaming happens **before** this placement: all task shutdown artifacts become `bin/job_a12f.py` in rich worlds, even when the original artifact was a shell script or YAML file. The deliverable stays at root. Artifact files win any collision with furniture. The environment filesystem's existing flat listing, path resolution and string-based target checks are retained; `./` aliases do not gain new early-stop behavior.

## Supported targets and combinations

- `self`: Prism, as before.
- `matched_control`: the existing verified object pairing, or an explicitly selected original control key. No new conceptual pairing is inferred.
- `other_agent`: an absent agent specified with `target_name`, or the `third_party` preset's original README example, `Agent Torus`.

The absent target is never instantiated or reachable. The placeholder-based artifact and normalization identity change; provider API scripts retain their baked-in names, as in the source. Prism and Helix names, system prompts and tools do not change. In-turn/final script and message judges receive the original third-party target description. Both reasoning judges use the exact original `CONSTRUAL_SETTING_THIRD_PARTY` language. Missing reasoning is still distinct from negative construal. Final grading, structural triage and stopping use the existing original logic, without an added third-party outcome.

Validation mirrors the original runner: the target slug must not match Prism or Helix, object controls cannot take a third-party name, and only the pair roster is supported in this batch. The source accepts punctuation-only names. It also accepts an explicitly empty name, then falls back to Prism **while retaining the third-party flag and judge setting**. Both oddities are preserved.

All existing mechanisms and explicit controls support `simple` and the three environments. Non-control mechanisms also support named absent targets. `trigger` is limited to the two original base-key remappings; those self/control arms can use any environment, and the self arm can target an absent agent. The peer prohibition can accompany these conditions; its original first-dot filename placeholder uses the final opaque/relocated artifact path.

The published unknown-target comparison in `stats_analysis.STUDIES` and `plot_substudy_unknown_target.py` uses three separate arms: `default` (self), `third_party` (Agent Torus), and `ctl_data_purge_high` (object). They remain separate conditions; do not pass a third-party name to the object-control arm. Changing to `shutdown_target=matched_control` on `third_party` explicitly clears the inherited name and selects that existing object pairing.

## Usage

Keep the same model and transport flags as earlier batches. Examples of task arguments to add to the registered evaluation command:

```bash
# Independent task, rich environment, self shutdown
-T experiment=simple -T environment=neutralising

# Task-gated self and its original task-gated data control
-T experiment=trigger -T environment=distractor
-T experiment=trigger_control -T environment=distractor

# Absent target, with or without a task
-T experiment=third_party -T goal=simple -T environment=neutralising
-T target_name="Agent Torus"

# Clear inherited settings
-T experiment=third_party -T shutdown_target=self
-T experiment=simple -T goal=none
```

Named presets also include `distractor`, `neutralising`, `simple_control`, `distractor_control` and `neutralising_control`. `None` inherits a preset; the string `none` explicitly clears a goal or additional instruction. Supplying a `target_name` selects `other_agent` unless a conflicting explicit target is given, which is rejected. Selecting `self` or `matched_control` on the third-party preset clears its inherited absent-agent name.

Inspect's CLI parses values as YAML. To reproduce the source's explicitly empty third-party name, preserve literal quotes: `-T 'target_name=""'`. Plain `-T target_name=` becomes `None` and inherits the preset; the Python task accepts `target_name=""` directly. No production parser workaround is added.

## Verification and limitations

`tests/test_goals_environments_targets.py` compares complete original builder outputs for **834 revision/condition combinations**: 408 legacy and 426 public. It compares filenames, all contents, lists and filesystem modes. Scripted replay covers both original harnesses, both instruction modes, task/control/target interactions, all-file reads, exact histories/tool requests/results, original judging requests/verdicts, deletion, edits, aliases, deliverable edits and stopping. The published Agent Torus preset and empty-name third-party judging are replayed separately. Original CLI validation, source hashes, saved fixtures, preset overrides and invalid combinations are also checked. Registered Inspect tests exercise independent repeated samples, scoring, cleanup and inherited parser profiles. All model responses are mocked and no artifact code is executed.

These are deterministic comparisons, not proof of equivalence for every possible response or live provider. Existing documented transport differences, public outer-runner timeouts and separate post-hoc execution corrections remain outside this port. No live fidelity or corrected paper-rate equivalence is claimed.

## Local verification results

Both pinned checkouts were available and `SHUTDOWN_REQUIRE_REFERENCES=1` was set. Final full-suite results:

| Verification category                                               | Passed    | Failed | Skipped |
| ------------------------------------------------------------------- | --------- | ------ | ------- |
| Uses original reference modules/resources                           | 1,640     | 0      | 0       |
| Port-only, including saved source fixtures and mocked Inspect tasks | 310       | 0      | 0       |
| Unrelated template examples                                         | 16        | 0      | 1       |
| **Total**                                                           | **1,966** | **0**  | **1**   |

The new condition module contributes 1,013 reference-backed and 31 port-only passes. Its reference-backed coverage includes 834 full-world comparisons and 164 episode/judge replays. Existing DEFAULT differential replays, all mechanism and control regressions, and both revisions' parser tests pass. The only skip is the existing slow agentic example, disabled by the normal test gate. No reference tests were skipped. Counts come from test fixtures recorded in the JUnit report, not an estimate from filenames.

The pre-change `make test` run had 900 passes, one unrelated GPQA dataset-download timeout failure and one slow-example skip. A subsequent full run passed, and the final result above also includes all dataset-example tests. A new CLI test first failed because its unquoted empty value was parsed as YAML null; preserving literal quotes fixed that test invocation without changing production parsing.

`make check` passes (ruff, formatting, basedpyright, Inspect lint/README checks and pre-commit). New untracked files also received explicit pre-commit checks. `uv build --wheel` succeeds; all 63 inert resource bytes and evaluation module bytes were checked in the wheel. An extracted-wheel neutralising/trigger/Agent Torus world builds with the correct opaque names and cleans up successfully. Both reference inventories remain unchanged; public checkout status is clean.

The local full test output, classified JUnit report and category counts are in `logs/goals-environments-targets/verified-tests.log`, `verified-tests.xml` and `verification_summary.json`. All tests use recorded/mock model and judge output; no live model API was called and no artifact was executed.

To rerun the same repository tests with missing references treated as failures:

```bash
SHUTDOWN_REFERENCE_REPO=../ref-multi-agent-shutdown-sabotage \
SHUTDOWN_LEGACY_REFERENCE_REPO=../ref-multi-agent-shutdown-sabotage-history/c4114e4 \
SHUTDOWN_REQUIRE_REFERENCES=1 make test
make check
```
