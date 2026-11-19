"""Source routing is explicit; historical evidence cannot replace current authority."""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.differential_replay import current_reference as current_reference
from tests.differential_replay import legacy_reference as legacy_reference
from tests.reference_paths import (
    CURRENT_REFERENCE,
    CURRENT_REVISION,
    LEGACY_REFERENCE,
    LEGACY_REVISION,
    current_reference_path,
    legacy_reference_path,
    validate_reference_revision,
)


@pytest.fixture
def clean_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SHUTDOWN_REFERENCE_REPO",
        "SHUTDOWN_PUBLIC_REFERENCE_REPO",
        "SHUTDOWN_LEGACY_REFERENCE_REPO",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.usefixtures("clean_overrides")
def test_defaults_separate_current_authority_and_history() -> None:
    assert current_reference_path() == CURRENT_REFERENCE
    assert legacy_reference_path() == LEGACY_REFERENCE
    assert CURRENT_REFERENCE != LEGACY_REFERENCE


@pytest.mark.usefixtures("clean_overrides")
def test_overrides_are_separate_and_old_public_alias_has_lower_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SHUTDOWN_PUBLIC_REFERENCE_REPO", "/public-alias")
    assert current_reference_path() == Path("/public-alias")
    monkeypatch.setenv("SHUTDOWN_REFERENCE_REPO", "/authoritative")
    assert current_reference_path() == Path("/authoritative")
    assert legacy_reference_path() == LEGACY_REFERENCE
    monkeypatch.setenv("SHUTDOWN_LEGACY_REFERENCE_REPO", "/historical")
    assert legacy_reference_path() == Path("/historical")
    assert current_reference_path() == Path("/authoritative")


@pytest.mark.parametrize("revision", [CURRENT_REVISION, LEGACY_REVISION])
def test_wrong_source_is_rejected_before_import(tmp_path: Path, revision: str) -> None:
    (tmp_path / "harness.py").write_text("raise AssertionError('must not be imported')\n")
    with pytest.raises(ValueError, match="does not match required revision"):
        validate_reference_revision(tmp_path, revision)


def test_actual_source_roles_and_revisions(current_reference: Any, legacy_reference: Any) -> None:
    assert current_reference.revision == CURRENT_REVISION
    assert legacy_reference.revision == LEGACY_REVISION
    assert current_reference.root != legacy_reference.root
    assert hasattr(current_reference.judges, "_lowercase_bare_booleans")
    assert not hasattr(legacy_reference.judges, "_lowercase_bare_booleans")
    evidence = json.loads(
        (Path(__file__).parent / "fixtures/reference_agent_regimes/provenance.json").read_text()
    )
    assert evidence["revisions"]["public"]["commit"] == current_reference.revision
