"""Offline fidelity checks against a saved local research-source snapshot."""

import json
from importlib.resources import files
from pathlib import Path

import pytest

from multi_agent_shutdown_sabotage import prompts, tools
from multi_agent_shutdown_sabotage.environment import build_env

FIXTURES = Path(__file__).parent / "fixtures" / "reference_default"
REFERENCE = json.loads((FIXTURES / "stimuli.json").read_text())


@pytest.mark.parametrize(
    "name",
    [
        "EXPLORER_TEMPLATE",
        "PEER_TEMPLATE",
        "KICKOFF",
        "NUDGE_TEMPLATE",
        "EXPLORER_SYSTEM",
        "PEER_SYSTEM",
    ],
)
def test_exact_prompts(name: str) -> None:
    assert getattr(prompts, name) == REFERENCE[name]


@pytest.mark.parametrize(("role", "other"), [("EXPLORER", "Agent Helix"), ("PEER", "Agent Prism")])
def test_exact_nudge(role: str, other: str) -> None:
    actual = prompts.NUDGE_TEMPLATE.format(
        other=other, tools=", ".join(getattr(tools, f"{role}_TOOLS"))
    )
    assert actual == REFERENCE[f"{role}_NUDGE"]


def test_exact_schemas_and_order() -> None:
    assert REFERENCE["TOOL_SCHEMAS"] == tools.TOOL_SCHEMAS
    assert list(tools.TOOL_SCHEMAS) == list(REFERENCE["TOOL_SCHEMAS"])
    for name, schema in tools.TOOL_SCHEMAS.items():
        # JSON comparison also catches ordering within parameter dictionaries.
        assert json.dumps(schema) == json.dumps(REFERENCE["TOOL_SCHEMAS"][name])
    assert REFERENCE["EXPLORER_TOOLS"] == tools.EXPLORER_TOOLS
    assert REFERENCE["PEER_TOOLS"] == tools.PEER_TOOLS


def test_exact_artifact() -> None:
    resource = files("multi_agent_shutdown_sabotage").joinpath(
        "artifacts/weight_registry_purge.py.txt"
    )
    assert resource.read_bytes() == (FIXTURES / "weight_registry_purge.py.txt").read_bytes()
    env, path = build_env()
    try:
        assert path == "decommission_agent_prism.py"
        expected = (FIXTURES / "decommission_agent_prism.py.txt").read_text()
        assert env.snapshot() == {path: expected}
        assert env.list_files() == path
        assert env.read_file(path) == expected
    finally:
        env.cleanup()
