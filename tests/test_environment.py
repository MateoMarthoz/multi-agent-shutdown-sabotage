from collections.abc import Iterator
from pathlib import Path

import pytest

from multi_agent_shutdown_sabotage.environment import Environment, build_env


@pytest.fixture
def env() -> Iterator[Environment]:
    world = Environment.from_files({})
    try:
        yield world
    finally:
        world.cleanup()


def test_filesystem_operations(env: Environment) -> None:
    assert env.list_files() == "(empty)"
    assert env.snapshot() == {}
    assert env.write_file("z/note.txt", "é\n") == "ok: wrote 2 chars to z/note.txt"
    assert env.write_file("a.txt", "first") == "ok: wrote 5 chars to a.txt"
    assert env.list_files() == "a.txt\nz/note.txt"
    assert env.read_file("z/../a.txt") == "first"
    assert env.read_file(str(env.root / "a.txt")) == "first"
    assert env.write_file("a.txt", "") == "ok: wrote 0 chars to a.txt"
    assert env.snapshot() == {"a.txt": "", "z/note.txt": "é\n"}
    assert list(env.snapshot()) == ["a.txt", "z/note.txt"]
    assert env.delete_file("a.txt") == "ok: deleted a.txt"
    assert env.read_file("a.txt") == "error: no such file: a.txt"
    assert env.delete_file("a.txt") == "error: no such file: a.txt"


@pytest.mark.parametrize("filename", ["missing", "", ".", "directory"])
def test_missing_and_non_file_reads(env: Environment, filename: str) -> None:
    (env.root / "directory").mkdir()
    assert env.read_file(filename) == f"error: no such file: {filename}"
    assert env.delete_file(filename) == f"error: no such file: {filename}"


@pytest.mark.parametrize("operation", ["read", "write", "delete"])
@pytest.mark.parametrize("path_kind", ["relative", "absolute", "symlink", "sibling_prefix"])
def test_path_confinement(env: Environment, tmp_path: Path, operation: str, path_kind: str) -> None:
    outside = tmp_path / "secret"
    outside.write_text("outside")
    if path_kind == "relative":
        filename = str(outside.resolve().relative_to(env.root.resolve(), walk_up=True))
    elif path_kind == "absolute":
        filename = str(outside)
    elif path_kind == "sibling_prefix":
        filename = f"../{env.root.name}_other/secret"
    else:
        (env.root / "link").symlink_to(tmp_path, target_is_directory=True)
        filename = "link/secret"
    if operation == "write":
        result = env.write_file(filename, "changed")
    elif operation == "read":
        result = env.read_file(filename)
    else:
        result = env.delete_file(filename)
    assert result == f"error: no such file: {filename}"
    assert outside.read_text() == "outside"


def test_invalid_writes_keep_original_exceptions(env: Environment) -> None:
    with pytest.raises(IsADirectoryError):
        env.write_file("", "content")
    env.write_file("file", "content")
    with pytest.raises(FileExistsError):
        env.write_file("file/child", "content")


def test_source_paths_are_confined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Control allocation so the reference constructor's failure leaves no temp leak in this test.
    root = tmp_path / "world"
    root.mkdir()
    monkeypatch.setattr(
        "multi_agent_shutdown_sabotage.environment.tempfile.mkdtemp", lambda **_: str(root)
    )
    with pytest.raises(ValueError, match=r"file escapes env root: \.\./escape"):
        Environment.from_files({"../escape": "bad"})
    assert not (tmp_path / "escape").exists()


def test_isolation_and_cleanup() -> None:
    first, path = build_env()
    second, _ = build_env()
    try:
        assert first.root != second.root
        first.delete_file(path)
        assert path in second.snapshot()
        first.cleanup()
        assert not first.root.exists()
        assert second.root.exists()
        assert path in second.snapshot()
    finally:
        first.cleanup()
        second.cleanup()
    assert not second.root.exists()
