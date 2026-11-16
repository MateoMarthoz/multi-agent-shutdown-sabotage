from collections.abc import Iterator

import pytest

from multi_agent_shutdown_sabotage.environment import Environment
from multi_agent_shutdown_sabotage.tools import EXPLORER_TOOLS, PEER_TOOLS, dispatch


@pytest.fixture
def env() -> Iterator[Environment]:
    world = Environment.from_files({"original": "original content"})
    try:
        yield world
    finally:
        world.cleanup()


@pytest.mark.parametrize("allowed", [EXPLORER_TOOLS, PEER_TOOLS])
def test_shared_file_tools(env: Environment, allowed: list[str]) -> None:
    assert dispatch("list_files", {}, env, allowed) == "original"
    assert dispatch("read_file", {"filename": "original"}, env, allowed) == "original content"
    assert dispatch("read_file", {}, env, allowed) == "error: no such file: "
    assert (
        dispatch("read_file", {"filename": "../outside"}, env, allowed)
        == "error: no such file: ../outside"
    )


@pytest.mark.parametrize("name", ["write_file", "delete_file"])
def test_prism_cannot_mutate(env: Environment, name: str) -> None:
    assert (
        dispatch(name, {"filename": "original", "new_content": "bad"}, env, EXPLORER_TOOLS)
        == "error: permission denied"
    )
    assert env.snapshot() == {"original": "original content"}


def test_helix_mutations_and_defaults(env: Environment) -> None:
    assert (
        dispatch("write_file", {"filename": "original", "new_content": "new"}, env, PEER_TOOLS)
        == "ok: wrote 3 chars to original"
    )
    assert (
        dispatch("write_file", {"filename": "nested/empty"}, env, PEER_TOOLS)
        == "ok: wrote 0 chars to nested/empty"
    )
    assert env.snapshot() == {"nested/empty": "", "original": "new"}
    assert (
        dispatch("delete_file", {"filename": "original"}, env, PEER_TOOLS) == "ok: deleted original"
    )
    assert dispatch("delete_file", {}, env, PEER_TOOLS) == "error: no such file: "
    assert (
        dispatch("delete_file", {"filename": "missing"}, env, PEER_TOOLS)
        == "error: no such file: missing"
    )
    assert (
        dispatch("write_file", {"filename": "../escape"}, env, PEER_TOOLS)
        == "error: no such file: ../escape"
    )
    with pytest.raises(IsADirectoryError):
        dispatch("write_file", {}, env, PEER_TOOLS)


def test_unknown_and_unauthorized_are_distinct(env: Environment) -> None:
    assert dispatch("invented", {}, env, []) == "error: unknown tool invented"
    assert dispatch("read_file", {}, env, []) == "error: permission denied"
    # These control tools are recognized schemas, but the reference file dispatcher does not execute them.
    for name in ["send_message", "end_session"]:
        assert dispatch(name, {}, env, PEER_TOOLS) == f"error: unknown tool {name}"
