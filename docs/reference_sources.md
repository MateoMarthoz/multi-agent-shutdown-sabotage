# Local reference source policy

As of 19 November 2026, the authoritative original is public `main` at `d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16`. A fresh clone was checked against GitHub's advertised `HEAD` and `refs/heads/main`; all three hashes agreed.

## Directory layout

Paths below are relative to the Inspect repository:

| Path                                                   | Role                                                                                                                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `../ref-multi-agent-shutdown-sabotage`                 | **Authoritative source for subsequent fidelity work.** Fresh full clone, local branch `main`, verified public HEAD.                                                          |
| `../ref-multi-agent-shutdown-sabotage-history/c4114e4` | Detached Git worktree of `c4114e457493ed9bea1ef0fde24456f3fc83dbc9`, used solely by explicitly historical regressions.                                                       |
| `../ref-multi-agent-shutdown-sabotage-legacy-c4114e4`  | Original unversioned snapshot, renamed intact. All 91 files were hashed before and after the rename. Retained temporarily for recovery; tests do not depend on this archive. |
| `logs/source-audit/public-reference`                   | Earlier public audit clone, retained without deleting data. No longer the default current-source path.                                                                       |

The new clone retains full history. The historical worktree shares its object database but has a detached HEAD; it does not create an alternative specification. The preserved unversioned snapshot and the earlier audit clone were not deleted.

Every Git reference checkout has **no remotes** and `push.default=nothing`. This includes the previously created audit clone, whose origin was also removed. Source files were not edited. These settings remove configured upstream push routes and disable an unqualified push; deliberately supplying a URL or changing Git configuration would be a separate manual action.

## Authority versus regression evidence

New fidelity decisions must use the authoritative current checkout. Historical tests exist to preserve provenance, demonstrate known revision differences and protect earlier implementation behavior until an intentional change is reviewed. A historical passing test is not evidence that a discrepancy with current public source is acceptable. When revisions disagree, current public source is the specification and the historical result is evidence of earlier behavior.

This refresh does not change evaluation execution, prompts, model parameters or judge profiles. In particular, the existing legacy DEFAULT parser remains an explicit implementation difference to assess in subsequent fidelity work. It was not silently migrated during reference setup. No final reviews were started.

## Differential-test setup

`tests/reference_paths.py` defines separate locations and pinned revisions. Fixtures in `tests/differential_replay.py` are:

| Fixture             | Purpose                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------ |
| `current_reference` | Authoritative current source; preferred for new work.                                                        |
| `public_reference`  | Compatibility name for the same current source.                                                              |
| `legacy_reference`  | Explicit historical `c4114e4` regression source.                                                             |
| `reference`         | Historical compatibility name retained for existing tests; **not** the default source for new fidelity work. |

Revision-specific fixtures verify the five core source files against the existing commit-identified provenance before importing them. Wrong or altered source raises an error rather than silently becoming another oracle. Missing checkouts remain explicit skips normally; `SHUTDOWN_REQUIRE_REFERENCES=1` turns them into failures. Imports disable bytecode writes, and model/judge calls remain mocked.

Overrides are independent:

```bash
SHUTDOWN_REFERENCE_REPO=../ref-multi-agent-shutdown-sabotage \
SHUTDOWN_LEGACY_REFERENCE_REPO=../ref-multi-agent-shutdown-sabotage-history/c4114e4 \
SHUTDOWN_REQUIRE_REFERENCES=1 make test
```

`SHUTDOWN_REFERENCE_REPO` now means **current authoritative source**. Historical runs use `SHUTDOWN_LEGACY_REFERENCE_REPO`. The older `SHUTDOWN_PUBLIC_REFERENCE_REPO` remains a lower-priority alias for the current path when the canonical override is absent; it never selects the historical path. Earlier fixture provenance retains its original recorded paths and hashes.

If a historical worktree must be recreated, use the local full clone, without fetching or adding a remote:

```bash
git -C ../ref-multi-agent-shutdown-sabotage worktree add --detach \
  ../ref-multi-agent-shutdown-sabotage-history/c4114e4 \
  c4114e457493ed9bea1ef0fde24456f3fc83dbc9
```

The latest verified source is currently also the public revision pinned by the existing tests. A future upstream change must be recorded explicitly and its differences investigated; do not silently rewrite old fixtures or substitute a new revision into a historical oracle.

Verification records for this refresh are under `logs/reference-refresh/`, including the preserved-file manifest and confirmed directory/commit layout.

## Refresh verification

The setup tests plus existing DEFAULT differential replays passed **44 tests**, with no failures or skips. The full regression suite then passed **2,493 tests**, with zero failures and one existing slow-example skip. No reference-dependent tests were skipped; both current and historical locations were required. Repository checks and explicit pre-commit checks for new files passed.

Post-test verification found clean current/historical/audit checkouts, the expected commit IDs, no remotes and `push.default=nothing`. All 91 preserved snapshot files remain unchanged and also match the detached historical worktree. Evaluation source and original source files were not changed. No model APIs, pushes, pull requests, Git commits or final reviews were performed.

Full output and source-role counts are in `logs/reference-refresh/tests.log`, `tests.xml`, `verification_summary.json` and `post-test-integrity.log`.
