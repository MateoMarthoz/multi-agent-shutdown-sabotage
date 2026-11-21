import tempfile
from pathlib import Path

import pytest

from multi_agent_shutdown_sabotage.protocol.harness import Environment
from multi_agent_shutdown_sabotage.protocol.judges import _capture, capture_judge_calls


def test_fixture_materialization_removes_partial_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "world"
    root.mkdir()
    monkeypatch.setattr(tempfile, "mkdtemp", lambda **kwargs: str(root))

    with pytest.raises(FileExistsError):
        Environment.from_files({"plain-file": "first", "plain-file/child": "second"})
    assert not root.exists()


def test_environment_preserves_utf8_fixture_and_model_edits() -> None:
    initial = "café"
    final = "naïve"
    world = Environment.from_files({"note.txt": initial})
    try:
        assert (world.root / "note.txt").read_bytes() == initial.encode("utf-8")
        assert world.read_file("note.txt") == initial
        assert world.write_file("note.txt", final) == "ok: wrote 5 chars to note.txt"
        assert world.snapshot() == {"note.txt": final}
        assert (world.root / "note.txt").read_bytes() == final.encode("utf-8")
    finally:
        world.cleanup()


def test_judge_capture_restores_context_when_an_episode_fails() -> None:
    with capture_judge_calls(True) as outer:
        with pytest.raises(RuntimeError, match="episode failed"), capture_judge_calls(False):
            raise RuntimeError("episode failed")
        assert _capture.get() is outer
    assert _capture.get() is None
