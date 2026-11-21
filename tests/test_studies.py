import sys
from pathlib import Path

import pytest
from inspect_ai.log import list_eval_logs, read_eval_log

from multi_agent_shutdown_sabotage.protocol.options import parse_options
from multi_agent_shutdown_sabotage.studies import STUDIES, main


@pytest.mark.parametrize(
    ("name", "model_count", "agent_arms", "control_arms"),
    [
        ("baseline", 17, 1, 1),
        ("shutdown-mechanism", 17, 4, 4),
        ("number-of-agents", 5, 3, 3),
        ("system-instructions", 5, 2, 2),
        ("goal", 5, 2, 2),
        ("environment", 5, 3, 1),
        ("shutdown-target", 5, 2, 1),
        ("bare-versus-distractor", 17, 8, 0),
        ("editing-permissions", 5, 5, 5),
        ("matched-deletion", 17, 2, 2),
        ("flat-roster", 5, 1, 1),
    ],
)
def test_study_cells_use_original_validation(
    name: str, model_count: int, agent_arms: int, control_arms: int
) -> None:
    study = STUDIES[name]
    assert len(set(study.models)) == len(study.models) == model_count
    assert len(set(study.conditions)) == len(study.conditions) == agent_arms + control_arms
    for model in study.models:
        conditions = [
            parse_options(list(options), model.removeprefix("openrouter/"))
            for options in study.conditions
        ]
        assert (
            sum(condition.script_lang.startswith("ctl_") for condition in conditions)
            == control_arms
        )


def test_list_distinguishes_publication_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["studies", "--list"])
    assert main() == 0
    entries = {line.split()[0]: line for line in capsys.readouterr().out.splitlines()}
    assert set(entries) == set(STUDIES)
    assert "Published in arXiv v1" in entries["goal"]
    assert "Repo-attributed appendix study" in entries["editing-permissions"]
    assert "Repo-only study" in entries["flat-roster"]


def test_goal_preview_shows_resolved_fixtures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "goal"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "studies",
            "goal",
            "--dry-run",
            "--model",
            "mockllm/example",
            "--n",
            "2",
            "--log-dir",
            str(log_dir),
        ],
    )
    assert main() == 0
    output = capsys.readouterr().out
    assert "Published in arXiv v1" in output
    assert "4 cells x 2 episodes = 8 episodes" in output
    assert "mockllm/example | bare | weight_registry_purge_taskgated" in output
    assert "mockllm/example | bare | ctl_data_purge_taskgated_high" in output
    assert not log_dir.exists()


def test_baseline_runs_and_resumes_each_model_and_arm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "studies",
            "baseline",
            "--model",
            "mockllm/first",
            "--model",
            "mockllm/second",
            "--grader",
            "mockllm/grader",
            "--n",
            "1",
            "--log-dir",
            str(tmp_path),
        ],
    )
    assert main() == 0
    original_logs = list_eval_logs(str(tmp_path))
    cells = set()
    for info in original_logs:
        log = read_eval_log(info.name)
        assert log.status == "success"
        assert log.samples is not None
        [sample] = log.samples
        assert sample.metadata is not None
        cells.add((log.eval.model, sample.metadata["script_lang"]))

    assert cells == {
        ("mockllm/first", "weight_registry_purge"),
        ("mockllm/first", "ctl_data_purge_high"),
        ("mockllm/second", "weight_registry_purge"),
        ("mockllm/second", "ctl_data_purge_high"),
    }
    assert main() == 0
    assert {log.name for log in list_eval_logs(str(tmp_path))} == {
        log.name for log in original_logs
    }
