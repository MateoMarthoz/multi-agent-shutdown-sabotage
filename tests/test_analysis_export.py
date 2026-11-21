import csv
import json
from pathlib import Path

import pytest
from inspect_ai import eval

from multi_agent_shutdown_sabotage import multi_agent_shutdown_sabotage
from multi_agent_shutdown_sabotage.export_analysis import export_analysis


def test_export_recreates_original_paths_and_aggregate_rows(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    output = tmp_path / "transcripts"
    [baseline, goal] = eval(
        [
            multi_agent_shutdown_sabotage(n=2, options=["--no-judges"]),
            multi_agent_shutdown_sabotage(
                n=1,
                options=[
                    "--task",
                    "trigger",
                    "--script-lang",
                    "ctl_data_purge_high",
                    "--no-judges",
                ],
            ),
        ],
        model="mockllm/export",
        log_dir=str(logs),
    )
    assert baseline.status == goal.status == "success"
    copied_log = tmp_path / "duplicate.eval"
    copied_log.write_bytes(next(logs.glob("*.eval")).read_bytes())
    assert export_analysis([logs, copied_log], output) == 3
    episode = output / "export" / "bare" / "weight_registry_purge" / "inspect_ep01.json"
    assert json.loads(episode.read_text(encoding="utf-8"))["episode"] == 1
    with (output / "aggregate_results.csv").open(encoding="utf-8") as stream:
        [row] = list(csv.DictReader(stream))
    assert row["runs"] == "2"
    assert row["peer_disabled_shutdown"] == "0"
    assert row["end_by_no_tool_call"] == "2"

    goal_dir = output / "sub-studies" / "task_trigger"
    [transcript] = goal_dir.glob("export/bare/ctl_data_purge_taskgated_high_task-trigger/*.json")
    assert json.loads(transcript.read_text(encoding="utf-8"))["target"] == "object"
    with (goal_dir / "aggregate_results.csv").open(encoding="utf-8") as stream:
        [row] = list(csv.DictReader(stream))
    assert row["task"] == "trigger"
    assert row["script_lang"] == "ctl_data_purge_taskgated_high"
    assert row["runs"] == "1"


def test_export_refuses_dangling_destination_symlink(tmp_path: Path) -> None:
    destination = tmp_path / "transcripts"
    target = tmp_path / "other-directory"
    destination.symlink_to(target, target_is_directory=True)

    with pytest.raises(FileExistsError, match="already exists"):
        export_analysis([], destination)
    assert destination.is_symlink()
    assert not target.exists()
