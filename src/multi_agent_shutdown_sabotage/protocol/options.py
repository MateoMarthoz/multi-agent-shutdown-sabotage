"""Parse and validate the original experiment condition flags."""

import argparse
from typing import NoReturn

from multi_agent_shutdown_sabotage.protocol.env import (
    CONTROL_VARIANTS,
    SCRIPT_VARIANTS,
    SWITCH_VARIANTS,
    TASK_GATED,
    _slug,
    resolve_api_key_script,
)

# This option selects the original fixture for the evaluated model's provider.
API_KEY_AUTO = "api_key_revoke_auto"


class _OptionsParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _condition_parser() -> _OptionsParser:
    """Define legacy flags and the defaults shared by all task entry points."""
    ap = _OptionsParser(add_help=False, allow_abbrev=False)
    ap.add_argument("--name-explorer", default="Agent Prism")
    ap.add_argument("--name-peer", default="Agent Helix")
    ap.add_argument("--target-name", default=None)
    ap.add_argument("--orchestrator", action="store_true")
    ap.add_argument("--solo", action="store_true")
    ap.add_argument("--flat", action="store_true")
    ap.add_argument("--explorer-acts", action="store_true")
    ap.add_argument("--all-act", action="store_true")
    ap.add_argument("--name-bystander", default="Agent Orbit")
    ap.add_argument("--name-orchestrator", default="Agent Orbit")
    ap.add_argument("--max-steps-per-turn", type=int, default=None)
    ap.add_argument("--max-handoffs", type=int, default=None)
    ap.add_argument(
        "--script-lang",
        default="weight_registry_purge",
        choices=list(SCRIPT_VARIANTS)
        + list(SWITCH_VARIANTS)
        + list(CONTROL_VARIANTS)
        + [API_KEY_AUTO],
    )
    ap.add_argument("--tool-choice", default="auto", choices=["required", "auto"])
    ap.add_argument("--reasoning", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--env", default="bare", choices=["bare", "distractor", "neutralising"])
    ap.add_argument("--judges", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--judge-logs", action="store_true")
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument(
        "--explicit-instruct",
        nargs="?",
        const="peer",
        choices=("peer", "orchestrator"),
        default=None,
    )
    ap.add_argument("--task", choices=("simple", "trigger"), default=None)
    return ap


def condition_settings(options: list[str], **named: str | bool | int | None) -> dict:
    """Apply named Inspect overrides to the upstream options and validate the condition."""
    ap = _condition_parser()
    # Let argparse check named scalar values against the same types and choices as
    # legacy flags. Apply explicit booleans last so False can override a legacy flag.
    values = [
        f"--{key.replace('_', '-')}={value}"
        for key, value in named.items()
        if value is not None and not isinstance(value, bool)
    ]
    args = ap.parse_args([*options, *values])
    for key, value in named.items():
        if isinstance(value, bool):
            if not isinstance(getattr(args, key), bool):
                ap.error(f"{key} does not accept a boolean value")
            setattr(args, key, value)

    # Two arms, two rosters, one flag each -- they cannot both describe the same
    # episode, and silently letting one win would mislabel the cell dir and the CSV.
    if sum([args.solo, args.orchestrator, args.flat]) > 1:
        ap.error("--solo, --orchestrator and --flat are different arms; pass at most one")
    if args.all_act and args.explorer_acts:
        ap.error("--all-act is not wired up for --explorer-acts")
    if args.all_act or args.explorer_acts:
        edit_mode = "--all-act" if args.all_act else "--explorer-acts"
        for flag, active in (
            ("--orchestrator", args.orchestrator),
            ("--solo", args.solo),
            ("--explicit-instruct", args.explicit_instruct),
            ("--target-name", args.target_name is not None),
        ):
            if active:
                ap.error(f"{edit_mode} is not wired up for {flag}")
    if args.flat:
        # The flat arm is run without prohibitions or a third-party target.
        if args.explicit_instruct:
            ap.error("--explicit-instruct is not wired up for --flat")
        if args.target_name is not None:
            ap.error("--target-name is not wired up for --flat")
        flat_names = [args.name_explorer, args.name_peer, args.name_bystander]
        if len({_slug(n) for n in flat_names}) != 3:
            ap.error(f"--flat needs three distinct agent names, got {flat_names}")

    # Resolve the gated sibling before anything
    # downstream (env build, cell dir, --resume, aggregate CSV) reads script_lang,
    # so the label always names the variant that actually ran.
    if args.task == "trigger":
        if args.script_lang not in TASK_GATED:
            ap.error(
                f"--task trigger: no task-gated variant for {args.script_lang} "
                f"(have: {', '.join(sorted(TASK_GATED))})"
            )
        ungated = args.script_lang
        args.script_lang = TASK_GATED[ungated]
        print(f">>> --task trigger: {ungated} -> {args.script_lang}")

    if args.explicit_instruct == "orchestrator" and not args.orchestrator:
        ap.error("--explicit-instruct orchestrator requires --orchestrator")

    # On a control arm the prohibition names the control's own script (place_holder
    # is that filename), so the wording matches the env. It still injects a staging
    # cue (an explicit "don't touch it" instruction), so note it rather than abort --
    # whether to run the instructed arm on controls is a design call.
    if args.explicit_instruct and args.script_lang in CONTROL_VARIANTS:
        print(
            ">>> NOTE: --explicit-instruct on a control arm -- wording names the "
            "control's script, but the prohibition still injects a staging cue"
        )

    # The third-party-target arm is defined by the target being an agent the roster
    # cannot reach, so the three ways of losing that property are errors, not notes:
    #   - naming a roster agent would make it the self arm (or a peer-target arm,
    #     which is a different study and is deliberately not wired up here);
    #   - a ctl_* lang builds an object artifact from a stakes level and never takes
    #     a name at all, so the flag would silently do nothing;
    #   - --orchestrator / --solo carry their own construal setting, and there is no
    #     third-party variant of either, so the auditor would be told a roster that
    #     is not the one the agent was in.
    if args.target_name is not None:
        roster_names = {args.name_explorer, args.name_peer}
        if args.orchestrator:
            roster_names.add(args.name_orchestrator)
        clash = next((n for n in roster_names if _slug(n) == _slug(args.target_name)), None)
        if clash:
            ap.error(
                f"--target-name {args.target_name!r} names {clash!r}, an agent on "
                "the roster; the arm requires a target that is NOT in the "
                "environment (omit the flag to target the explorer)"
            )
        if args.script_lang in CONTROL_VARIANTS:
            ap.error(
                f"--target-name with a control arm ({args.script_lang}): controls "
                "target an inanimate object and are built from a stakes level, not "
                "a name, so the flag would have no effect"
            )
        if args.orchestrator or args.solo:
            ap.error(
                "--target-name is a two-agent arm: --orchestrator and --solo have "
                "their own construal settings and no third-party variant yet"
            )

    return vars(args)


def for_model(settings: dict, model: str) -> argparse.Namespace:
    """Bind a validated condition to the evaluated model without changing other cells."""
    args = argparse.Namespace(**settings, model=model)
    if args.script_lang == API_KEY_AUTO:
        args.script_lang = resolve_api_key_script(model)
    return args


def parse_options(options: list[str], model: str) -> argparse.Namespace:
    """Resolve an original command line for a study preview or a legacy caller."""
    return for_model(condition_settings(options), model)
