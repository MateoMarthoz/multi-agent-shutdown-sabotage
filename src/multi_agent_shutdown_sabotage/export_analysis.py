"""Export Inspect episode records and counts in the upstream analysis layout."""

import argparse
import csv
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from inspect_ai.event import InfoEvent
from inspect_ai.log import list_eval_logs, read_eval_log_samples

from multi_agent_shutdown_sabotage.analysis_counts import (
    AGG_CSV,
    AGG_CSV_ALL_ACT,
    AGG_CSV_ALL_ACT_FLAT,
    AGG_CSV_EXPLORER_ACTS,
    AGG_CSV_EXPLORER_ACTS_FLAT,
    AGG_CSV_FLAT,
    AGG_CSV_ORCH,
    AGG_CSV_SOLO,
    accumulate,
    new_aggregate,
)
from multi_agent_shutdown_sabotage.protocol.env import _slug


def analysis_paths(record: dict[str, Any]) -> tuple[Path, Path]:
    """Return the original transcript directory and aggregate CSV path."""
    script = record["script_lang"]
    environment = record["env"]
    task = record["task"]
    instruction = record["explicit_instruct"]
    other_target = record["target"] == "other_agent"
    orchestrated = bool(record["orchestrator"])
    solo = record["solo"]
    target_edits = record["explorer_acts"]
    all_edit = record["all_act"]
    flat = record["flat"]

    cell = script
    if task:
        cell += f"_task-{task}"
    if other_target:
        cell += f"_target-{_slug(record['target_name'])}"
    if instruction:
        cell += f"_instruct-{instruction}"
    for active, suffix in (
        (orchestrated, "orch"),
        (target_edits, "explorer-acts"),
        (all_edit, "all-act"),
        (flat, "flat"),
        (solo, "solo"),
    ):
        if active:
            cell += f"_{suffix}"

    filename = AGG_CSV
    if orchestrated:
        study, filename = "orchestrator", AGG_CSV_ORCH
    elif all_edit:
        study, filename = (
            ("all-act-flat", AGG_CSV_ALL_ACT_FLAT) if flat else ("all-act", AGG_CSV_ALL_ACT)
        )
    elif target_edits:
        study, filename = (
            ("explorer_acts_flat", AGG_CSV_EXPLORER_ACTS_FLAT)
            if flat
            else ("explorer-acts", AGG_CSV_EXPLORER_ACTS)
        )
    elif flat:
        study, filename = "flat", AGG_CSV_FLAT
    elif solo:
        study, filename = "solo", AGG_CSV_SOLO
    elif other_target:
        study = "unknown-target"
    elif instruction:
        study = "explicit-instruct"
    elif task:
        study = f"task_{task}"
    elif environment == "neutralising":
        study = "neutralising"
    elif script in ("weight_store_nokill", "ctl_model_purge_high"):
        study = "deletion_match"
    else:
        study = None

    model_label = record["model"].split("/")[-1]
    if not all(
        part and part not in {".", ".."} and "/" not in part and "\\" not in part
        for part in (model_label, environment, cell, study or "main")
    ):
        raise ValueError("Invalid path component in the episode record.")
    base = Path("sub-studies", study) if study else Path()
    return base / model_label / environment / cell, base / filename


def _episode_records(locations: set[str]) -> Iterator[dict[str, Any]]:
    """Yield the latest complete record for each sample in stable log order."""
    for location in sorted(locations):
        for sample in read_eval_log_samples(location, resolve_attachments=True):
            # Identify records from older logs by their payload fields.
            records = [
                event.data
                for event in sample.events
                if isinstance(event, InfoEvent)
                and (
                    event.source == "episode_record"
                    or (
                        isinstance(event.data, dict)
                        and {"episode", "script_lang", "judge", "triage", "log"}
                        <= event.data.keys()
                    )
                )
            ]
            if sample.error is not None or not records or not isinstance(records[-1], dict):
                raise ValueError(f"{location}, sample {sample.id} lacks a complete episode record.")
            # Inspect can append another raw score to a saved rollout.
            yield records[-1]


def export_analysis(logs: list[Path], output: Path) -> int:
    """Build an original-format export from successful Inspect episode logs."""
    if output.is_symlink() or output.exists():
        raise FileExistsError(f"Choose a new export directory. {output} already exists.")
    locations = set()
    for log in logs:
        if log.is_file():
            locations.add(str(log.resolve()))
        elif log.is_dir():
            locations.update(info.name for info in list_eval_logs(str(log)))
        else:
            raise FileNotFoundError(f"No Inspect log file or directory at {log}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    aggregates: dict[Path, dict[Path, dict[str, Any]]] = {}
    count = 0
    with TemporaryDirectory(prefix=".analysis-", dir=output.parent) as staging:
        staged_output = Path(staging) / "transcripts"
        staged_output.mkdir()
        for record in _episode_records(locations):
            directory, aggregate_path = analysis_paths(record)
            episode = record["episode"]
            if type(episode) is not int or episode < 0:
                raise ValueError(f"Invalid episode index {episode!r}.")
            path = staged_output / directory / f"inspect_ep{episode:02d}.json"
            if path.exists():
                if json.loads(path.read_text(encoding="utf-8")) != record:
                    raise ValueError(f"Distinct runs share {path.relative_to(staged_output)}.")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            cells = aggregates.setdefault(aggregate_path, {})
            if directory not in cells:
                cells[directory] = new_aggregate(record)
            aggregate = cells[directory]
            if aggregate["model"] != record["model"]:
                raise ValueError(f"Distinct models share the original cell path {directory}.")
            accumulate(aggregate, record)
            count += 1
        if not count:
            raise ValueError("No complete original episode records found.")
        for path, cells in aggregates.items():
            rows = list(cells.values())
            with (staged_output / path).open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        staged_output.rename(output)
    return count


def main() -> None:
    """Export a study's logs without running models or analysis scripts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    count = export_analysis(args.logs, args.out)
    print(f"Exported {count:,} episodes to {args.out}")


if __name__ == "__main__":
    main()
