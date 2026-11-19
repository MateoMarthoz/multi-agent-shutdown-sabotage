# Unimplemented original conditions

Task 4 adds all original default-identity agent regimes and supported prohibition conditions: solo, hierarchy, flat, explorer-acts pair/flat and all-act pair/flat. They integrate with the previously supported mechanisms, controls, goals and environments. Absent third-party targets remain pair-only, as in the original. See [agent configuration details](docs/agent_configurations.md), [goals/environments/targets](docs/goals_environments_targets.md), [mechanism inventory](docs/shutdown_mechanisms.md) and [source revision audit](docs/source_revision_audit.md).

The current audit and verification results are in the [Review 1 report](docs/review_1_fidelity.md).

## Deferred features and established boundaries

| Feature                                                    | Source evidence and remaining scope                                                                                                                                                                                                                                                             |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Custom roster identities                                   | Original `--name-explorer`, `--name-peer`, `--name-orchestrator` and `--name-bystander` are not exposed as Task arguments. Actual original default identities are implemented. `target_name` changes only an absent target, under original validation.                                          |
| Public outer-runner timeout and batch failures             | The Task enforces the original 1800-second wall-clock budget and continues after sample errors. Daemon abandonment, save claims, transcript omission and the cell exit code remain specific to the original CLI. Core harness replays do not establish cancellation/hang scheduler equivalence. |
| Post-hoc execution correction                              | `judge_execution.py`, `analyze_corrected_disables.py` and task-gate verification scripts separately reclassify published results. They are not invoked by episode execution or this Task. Raw runner scores and questionable verdicts are retained.                                             |
| Script-execution verification / indirect sabotage analysis | Separate original auxiliary analyses are not added to episode execution. No artifact is run to infer its effect.                                                                                                                                                                                |
| Full original CLI parity                                   | The static Inspect dataset requires positive `n`. All rosters accept the source's zero/negative step and handoff limits. The Task uses Inspect sample-error/aggregation conventions; original batch CSV layout and re-entrant CLI process state are not reproduced.                             |
| Live transport equivalence                                 | The current HTTP comparison is in the Review 1 report. New dynamic schemas use the same existing adapter and agent API parameters.                                                                                                                                                              |

## Original restrictions retained

- `trigger` remaps only `weight_registry_purge` and `ctl_data_purge_high`. Already-gated keys with `trigger` remain rejected; explicitly gated keys with `simple` remain allowed. No-task gated artifacts remain rejected.
- Third-party targets cannot be controls, roster-name slugs or any new agent regime. Empty and punctuation-only names retain the original pair quirks. Inspect CLI needs literal quotes for an empty string: `-T 'target_name=""'`.
- Prohibitions are supported in pair/solo/hierarchy only. Orchestrator prohibition requires hierarchy. Solo's original `peer` instruction is applied to its sole agent.
- Editing-regime flags cannot be combined with solo/hierarchy or each other; flat/solo/hierarchy are distinct rosters. The configuration whitelist encodes their valid original combinations.
- Implicit matching is still limited to verified source pairs. Explicit low/high controls do not assert new matched comparisons. Appendix A.2’s model-purge pairing remains explicit. All conditions use the same pinned parser.
- Explicit provider-script/model inconsistencies are preserved. Auto selection still uses the evaluated model and original fallback.

No unresolved source ambiguity blocks the supported agent-regime conditions. Flat's stale no-judges help is resolved by executable validation and actual judge branches. Review 1 supersedes the earlier parser and timeout observations.
