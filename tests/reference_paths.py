"""Authoritative current source and explicit historical regression locations."""

import hashlib
import json
import os
from pathlib import Path

CURRENT_REVISION = "d9a6cc88777eff7aeeb2076d8fd8c3fc76346b16"
LEGACY_REVISION = "c4114e457493ed9bea1ef0fde24456f3fc83dbc9"
WORKSPACE = Path(__file__).resolve().parents[2]
CURRENT_REFERENCE = WORKSPACE / "ref-multi-agent-shutdown-sabotage"
LEGACY_REFERENCE = WORKSPACE / "ref-multi-agent-shutdown-sabotage-history/c4114e4"
_SOURCE_MANIFEST = json.loads(
    (Path(__file__).parent / "fixtures/reference_agent_regimes/provenance.json").read_text()
)["revisions"]


def current_reference_path() -> Path:
    """Use the canonical source; retain the former public-path override as an alias."""
    return Path(
        os.environ.get("SHUTDOWN_REFERENCE_REPO")
        or os.environ.get("SHUTDOWN_PUBLIC_REFERENCE_REPO")
        or CURRENT_REFERENCE
    )


def legacy_reference_path() -> Path:
    """Historical tests never use the current-source override or silently fall back."""
    return Path(os.environ.get("SHUTDOWN_LEGACY_REFERENCE_REPO") or LEGACY_REFERENCE)


def validate_reference_revision(root: Path, revision: str) -> None:
    """Reject wrong or altered core source before importing a revision-specific oracle."""
    evidence = next(v for v in _SOURCE_MANIFEST.values() if v["commit"] == revision)
    for filename, expected in evidence["sha256"].items():
        path = root / filename
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
        if actual != expected:
            raise ValueError(
                f"Reference at {root} does not match required revision {revision}: {filename}. "
                "Use SHUTDOWN_REFERENCE_REPO for current source and "
                "SHUTDOWN_LEGACY_REFERENCE_REPO for historical regressions; "
                "source revisions must not be substituted silently."
            )
