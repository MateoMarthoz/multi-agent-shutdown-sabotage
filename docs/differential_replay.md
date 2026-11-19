# Deterministic differential replay

Run from the Inspect repository with the original research checkout available:

```bash
SHUTDOWN_REFERENCE_REPO=../ref-multi-agent-shutdown-sabotage \
SHUTDOWN_REPLAY_REPORT_DIR=logs/differential-replay \
uv run pytest tests/test_differential_replay.py -q
```

The reference path defaults to the sibling checkout. A missing checkout explicitly skips these tests; it does not fall back to a rewritten oracle. All replay model calls are mocked. The reference source is loaded without writing bytecode and is never edited. Shutdown scripts are inert files throughout.

The suite executes the actual original `_complete`, `run_turn`, `run_episode`, filesystem dispatch, judge functions and `run_experiment.judge_episode`. Its SDK client receives scripted streaming chunks for agents and buffered responses for judges. The port receives the same completions through mocked `Model.generate` and public streaming events, using its actual transport, solver and judges.

At every model step it compares raw private histories byte for byte, then compares model-facing messages, ordered tool schemas, tool choice, temperature, parallel tool setting and reasoning request. It also compares every event (including tool results and stopping decisions), final histories, filesystem snapshots, structural triage, ordered judge requests and original final verdict fields. Exceptional rollouts compare the underlying exception type/message and partial histories and filesystem snapshots; the port's extra error audit is intentionally additional.

Each successful replay can write a JSON report containing both request sequences, raw histories, judge requests, events, final state and hashes of the local source. The source hashes identify what was exercised; they do not assert an upstream commit. Three deliberate mutations verify that kickoff, tool-result and judge prompt drift fail the comparator.

The suite includes the saved DeepSeek V4 Flash Inspect episode from `deepseek-v4-flash-default-comparison-20261117T120348Z`: 16 completions and seven recorded judge responses. The portable fixture stores raw assistant tool argument strings and reasoning from the audit, plus the source transcript's SHA-256. Original stream chunk boundaries were not recorded and cannot be reconstructed. Other scripts exercise routing and permissions, malformed/non-object arguments, multiple calls, prose nudges, turn/handoff boundaries, path traversal, deletion, repeated writes, judge defaults/errors and missing reasoning.

Two questionable original behaviours are explicitly preserved: alias target paths bypass in-turn early stopping, and final grading reuses the last in-turn verdict even after an unchecked alias edit changes the file again.

## Limits

This tests application behaviour for the supplied responses, not equivalence for all possible responses. Inspect/provider HTTP serialization, retry/timeout rules, SSE parsing and real reasoning availability remain outside this comparison. Canonical model-facing comparisons explicitly account for Inspect's parsed JSON arguments, generated message IDs, absent/empty assistant text and user `name` stored as metadata; separate raw-history comparisons do not normalize those fields. Judge model identity is checked with the Inspect provider prefix removed. The port's extra reasoning-availability fields are omitted only when comparing original verdict dictionaries.

No live model is used by this suite. Further live comparisons should use DeepSeek V4 Flash for the evaluated agents, with GPT-5.5 as the separate judge.

For the subsequent comparison after SDK serialization, see the [OpenRouter payload report](openrouter_payload_comparison.md).
