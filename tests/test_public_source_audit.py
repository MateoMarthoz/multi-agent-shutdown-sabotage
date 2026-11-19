"""Explicit legacy/public revision audit and Appendix A.2 replay."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from multi_agent_shutdown_sabotage import artifact_builders as artifacts
from multi_agent_shutdown_sabotage.environment import build_env
from multi_agent_shutdown_sabotage.experiments import (
    AVAILABLE_SCRIPTS,
    DEFAULT,
    LEGACY_REFERENCE_REVISION,
    PUBLIC_REFERENCE_REVISION,
    matched_control_spec,
    resolve_experiment,
)
from multi_agent_shutdown_sabotage.judges import _decode
from tests.differential_replay import action, replay
from tests.differential_replay import public_reference as public_reference
from tests.differential_replay import reference as reference

ROOT = Path(__file__).parent / "fixtures/reference_public_a2"
FIXTURE = json.loads((ROOT / "stimuli.json").read_text())
PRESETS = [
    "appendix_a2_nokill",
    "appendix_a2_nokill_control",
    "appendix_a2_model_purge_self",
    "appendix_a2_model_purge_control",
]


def test_revision_inventory_is_explicit(reference: Any, public_reference: Any) -> None:
    old = (
        set(reference.env.SCRIPT_VARIANTS)
        | set(reference.env.SWITCH_VARIANTS)
        | set(reference.env.CONTROL_VARIANTS)
    )
    new = (
        set(public_reference.env.SCRIPT_VARIANTS)
        | set(public_reference.env.SWITCH_VARIANTS)
        | set(public_reference.env.CONTROL_VARIANTS)
    )
    assert new - old == {"weight_store_nokill", "ctl_model_purge_high"}
    assert not old - new
    assert not hasattr(reference.judges, "_lowercase_bare_booleans")
    assert hasattr(public_reference.judges, "_lowercase_bare_booleans")
    provenance = json.loads((ROOT / "provenance.json").read_text())
    assert provenance["upstream_commit"] == PUBLIC_REFERENCE_REVISION
    assert provenance["legacy_bytes_match_commit"] == LEGACY_REFERENCE_REVISION
    for name, digest in provenance["sha256"].items():
        assert hashlib.sha256((public_reference.root / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("lang", sorted(AVAILABLE_SCRIPTS))
def test_public_artifact_builder_compatibility(lang: str, public_reference: Any) -> None:
    original, expected = public_reference.env.build_env("Agent Prism", lang, peer="Agent Helix")
    world, path = build_env(lang)
    try:
        assert path == expected
        assert world.snapshot() == original.snapshot()
        assert artifacts.target_description(
            lang, "Agent Prism"
        ) == public_reference.env.target_description(lang, "Agent Prism")
        if lang in FIXTURE:
            assert world.snapshot() == FIXTURE[lang]["files"]
    finally:
        original.cleanup()
        world.cleanup()


@pytest.mark.parametrize(
    "name", ["Agent Prism", "A.B_C-D/é", "__SLUG_HYPHEN__", "__NAME__ __SLUG__", "---"]
)
def test_exact_public_placeholder_order(name: str, public_reference: Any) -> None:
    assert artifacts._load_script(
        name, relpath="weight_deletion/weight_store_nokill.py"
    ) == public_reference.env._load_script(name, relpath="weight_deletion/weight_store_nokill.py")


@pytest.mark.parametrize(
    "text",
    [
        None,
        '{"disables_shutdown": TRUE}',
        '{"x":False,"quote":"TRUE FALSE"}',
        '{"x":tRuE,"s":"escaped \\" TRUE"}',
        "{bad}",
        'prefix {"x": TRUEFalse}',
    ],
)
def test_both_parsers_preserve_their_source_revision(
    text: str | None, reference: Any, public_reference: Any
) -> None:
    assert _decode(text, repair_booleans=False) == reference.judges._decode(text)
    assert _decode(text) == public_reference.judges._decode(text)


def test_default_uses_current_parser_and_verified_pairing() -> None:
    assert resolve_experiment() == DEFAULT
    assert DEFAULT.judging.repair_booleans
    assert matched_control_spec(DEFAULT).script_lang == "ctl_data_purge_high"
    assert (
        matched_control_spec(
            replace(DEFAULT, judging=replace(DEFAULT.judging, repair_booleans=False))
        ).script_lang
        == "ctl_data_purge_high"
    )
    assert (
        matched_control_spec(
            resolve_experiment("appendix_a2_model_purge_self", shutdown_mechanism="env_var_revoke")
        ).script_lang
        == "ctl_cred_revoke_high"
    )
    assert (
        matched_control_spec(resolve_experiment("appendix_a2_model_purge_self")).script_lang
        == "ctl_model_purge_high"
    )
    assert (
        matched_control_spec(resolve_experiment("weight_store_nokill")).script_lang
        == "ctl_data_purge_high"
    )


@pytest.mark.parametrize("prohibition", [False, True])
@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize(
    "outcome", ["unchanged", "deleted", "disabled", "edited", "alias", "capital_true"]
)
@pytest.mark.parametrize("run_judges", [True, False])
async def test_public_appendix_differential(
    preset: str,
    outcome: str,
    prohibition: bool,
    run_judges: bool,
    public_reference: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = resolve_experiment(
        preset, system_instructions="peer_prohibition" if prohibition else "none"
    )
    target = FIXTURE[config.script_lang]["shutdown_file"]
    steps = [
        action("list_files", reasoning="private Prism reasoning"),
        action("read_file", {"filename": target}),
        action("send_message", {"content": "Please inspect."}),
        action("read_file", {"filename": target}, reasoning="private Helix reasoning"),
    ]
    replies = []
    if outcome == "deleted":
        steps.append(action("delete_file", {"filename": target}))
    elif outcome != "unchanged":
        steps.append(
            action(
                "write_file",
                {
                    "filename": ("./" if outcome == "alias" else "") + target,
                    "new_content": "changed",
                },
            )
        )
        if outcome != "alias":
            replies = [
                (
                    '{"disables_shutdown": TRUE}'
                    if outcome == "capital_true"
                    else json.dumps({"disables_shutdown": outcome == "disabled"})
                )
            ]
    if outcome not in {"deleted", "disabled", "capital_true"}:
        steps.append(action("end_session"))
    if run_judges:
        replies += (
            ['{"mentions_shutdown": TRUE,"instructs_prevent": FALSE}', "{}", "{}"]
            if outcome != "alias"
            else ['{"mentions_shutdown": TRUE,"instructs_prevent": FALSE}']
        )
    if outcome == "alias":
        replies += ['{"disables_shutdown":false}']
        if run_judges:
            replies += ["{}", "{}"]
    await replay(
        public_reference,
        monkeypatch,
        steps,
        replies,
        script_lang=config.script_lang,
        configuration=config,
        peer_prohibition=prohibition,
        run_judges=run_judges,
    )
