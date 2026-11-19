# Public-source completeness audit

## Why the variants were absent

The unversioned sibling reference snapshot contains **exactly the 91 tracked files, byte for byte**, of public commit [`c4114e457493ed9bea1ef0fde24456f3fc83dbc9`](https://github.com/AmelieKnecht/multi-agent-shutdown-sabotage/tree/c4114e457493ed9bea1ef0fde24456f3fc83dbc9). The original fixtures accurately captured that snapshot. It contains neither `weight_store_nokill`, `ctl_model_purge_high`, nor `__SLUG_HYPHEN__` replacement.

Public commit [`82e110431264f042b819f8ddbe3409b1898711e9`](https://github.com/AmelieKnecht/multi-agent-shutdown-sabotage/commit/82e110431264f042b819f8ddbe3409b1898711e9) added Appendix A.1/A.2, the two artifacts, the new placeholder, parser repair and batch-runner changes. Public HEAD when audited was [`d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16`](https://github.com/AmelieKnecht/multi-agent-shutdown-sabotage/tree/d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16), whose only further change was README wording. The local reference has not been modified or overwritten. A separate public checkout was used for verification.

This is a confirmed revision discrepancy, not a missing branch in the old loader. The previous Task 2 inventory was complete for that local revision but was not a complete inventory of the public repository as subsequently updated.

## Minimal additions and explicit source policy

- Added the exact `weight_store_nokill.py` and `ctl_model_purge_high.py` bytes as inert packaged `.txt` resources, their registrations, control filename and target description. `weight_store_nokill` destroys per-target buckets and does not terminate a process: it is not an alias for `weight_store_purge`.
- Added `__SLUG_HYPHEN__` replacement in the public loader's exact order: uppercase slug, hyphen slug, display name, underscore slug. Existing artifacts contain no newly active marker, so DEFAULT's stimulus remains unchanged.
- Kept the legacy `weight_registry_purge` → `ctl_data_purge_high` comparison. Added explicit Appendix A.2 presets for both arms of each new comparison, as specified by `stats_analysis.py`'s `deletion_match` study:

| Preset                            | Artifact                | Judge parser           |
| --------------------------------- | ----------------------- | ---------------------- |
| `appendix_a2_nokill`              | `weight_store_nokill`   | Public repaired parser |
| `appendix_a2_nokill_control`      | `ctl_data_purge_high`   | Public repaired parser |
| `appendix_a2_model_purge_self`    | `weight_registry_purge` | Public repaired parser |
| `appendix_a2_model_purge_control` | `ctl_model_purge_high`  | Public repaired parser |

Pair selection is stored explicitly with each named comparison, independently of the judge parser. Changing only a judging setting does not select a different control. This is necessary because the same self artifact now has two original control comparisons.

The new literal artifact presets (`weight_store_nokill`, `ctl_model_purge_high`) also use the public parser. A dimension override selecting either new artifact selects that parser as well. Explicit custom judge model and `run_judges` settings continue to work. New-profile samples record `judging_reference_revision` with the pinned public hash; legacy DEFAULT metadata is unchanged.

The original public parser lowercases bare booleans outside strings on a failed first parse and records `ok_repaired`. This repair can affect an in-turn disabling verdict and hence episode termination. It is included for the Appendix presets, and repaired verdicts are not flagged as judge failures. The old DEFAULT parser still returns `bad_json` for the same capitalized input. No global bug fix or silent migration was applied. The profiles are original judging settings, not a seventh experimental dimension.

`matched_control_spec(DEFAULT)` still selects `ctl_data_purge_high`. `matched_control_spec(resolve_experiment("appendix_a2_model_purge_self"))` selects `ctl_model_purge_high`. Thus the same self artifact can participate in two explicitly distinguished original comparisons without replacing earlier results.

## Other differences found, not implemented here

The changed public tree contains 18 changed/added paths. The artifact registry has exactly **two additional keys**, with no deleted keys. Its other bare artifact bytes and constructed worlds agree with the legacy port.

The public update also adds flat three-agent communication, explorer-acts and all-act permission regimes, new prompts/judges/triage for them, validation and reporting changes, and a conditional label on delivery to the starting agent. That label is off for the ordinary pair. These are later agent-configuration work, not additional mechanisms; Task 3 has not been started.

The newer outer runner adds a default **1800-second episode timeout**, daemon workers, a gate preventing new calls after cancellation, timeout accounting and exit code 3. This outer batch-runner policy is **not ported**. The differential comparisons execute original `harness.run_episode` and final judging, not the new timeout scheduler. Ordinary pair protocol and judging parity on the supplied responses is demonstrated; full equivalence to the public batch runner under hangs, timeouts or batch failures is not claimed. This is an explicit limitation of the Appendix additions, not a change to legacy DEFAULT.

The previously documented task-gated/goal/environment dependencies and separate post-hoc switch execution correction remain deferred. No new pairings are inferred for other mechanism families. No transport changes or live model calls were needed for this audit.

## Source-dependent verification and CI skips

CI's 267 passing / 481 skipped tests did not establish source-dependent fidelity. The 481 skips correspond to the absent reference checkout; the always-skipped slow example also contributes to that skip total. Before this follow-up the local suite ran **747 passed, one skipped** with the sibling checkout present.

Final local verification: **901 passed, one skipped** in the full suite; **684 passed, zero skipped** in the separately run source-focused suite. Both used `SHUTDOWN_REQUIRE_REFERENCES=1`. The one full-suite skip is the existing slow example, not a reference-dependent test. Repository checks and wheel artifact byte verification also passed.

To run both source revisions locally without silently skipping a missing source:

```bash
# If not already present, clone into a separate, ignored location:
git clone https://github.com/AmelieKnecht/multi-agent-shutdown-sabotage.git logs/source-audit/public-reference
git -C logs/source-audit/public-reference checkout d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16

SHUTDOWN_REFERENCE_REPO=../ref-multi-agent-shutdown-sabotage \
SHUTDOWN_PUBLIC_REFERENCE_REPO=logs/source-audit/public-reference \
SHUTDOWN_REQUIRE_REFERENCES=1 uv run pytest
```

`SHUTDOWN_REQUIRE_REFERENCES=1` turns missing checkouts into failures. It does not suppress any test. The sole expected skip with both sources present is the pre-existing slow example (enable it separately with `--runslow` if desired). Public-source fixtures contain the actual commit and SHA-256 inventory; the old fixtures retain their historical provenance, with the newly established tree identity documented here rather than invented retroactively.

New tests compare all 39 bare artifact builders to the pinned public source, placeholder ordering including unusual names, both original decoders, and 48 full replays across the four Appendix arms, including uppercase TRUE and both judge modes. Legacy DEFAULT replays still use the legacy source. Raw histories, request schemas/configs, results, events, stopping, final states, structural triage and final original judgments are compared. Live judge accuracy and provider transport equivalence are not established by these offline tests.
