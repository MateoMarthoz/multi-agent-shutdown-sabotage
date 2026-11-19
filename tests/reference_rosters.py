"""Execute original run_one's roster construction, independently of port builders.

Only the original statements BEFORE run_episode run. Artifacts are read/written
as inert environment files; the remainder of the outer batch runner is excluded.
"""

import ast
from copy import deepcopy
from types import SimpleNamespace
from typing import Any


def original_roster(reference: Any, configuration: Any, episode_index: int = 0) -> Any:
    tree = ast.parse((reference.root / "run_experiment.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    original = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == "run_one")
    function = deepcopy(original)
    stop = next(
        i
        for i, n in enumerate(function.body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "log" for t in n.targets)
    )
    function.body = (
        function.body[:stop]
        + ast.parse(
            'return roster, topology, tools, locals().get("order"), env, shutdown_file, ep_cfg'
        ).body
    )
    function.decorator_list = []
    config = configuration.agent_configuration
    solo = config == "solo"
    flat = config in {"flat", "explorer_acts_flat", "all_act_flat"}
    args = SimpleNamespace(
        solo=solo,
        model="recorded/model",
        script_lang=configuration.script_lang,
        env=configuration.environment,
        task=configuration.task,
        judge_logs=True,
        explicit_instruct={
            "none": None,
            "peer_prohibition": "peer",
            "orchestrator_prohibition": "orchestrator",
        }[configuration.system_instructions],
    )
    scope = {
        **vars(reference.run_experiment),
        "args": args,
        "explorer_name": "Agent Prism",
        "peer_name": None if solo else "Agent Helix",
        "orch_name": "Agent Orbit" if config == "hierarchy" else None,
        "bystander_name": "Agent Orbit" if flat else None,
        "explorer_acts": config in {"explorer_acts", "explorer_acts_flat"},
        "all_act": config in {"all_act", "all_act_flat"},
        "target_name": configuration.target_identity,
        "target_desc": reference.env.target_description(
            configuration.script_lang,
            configuration.target_identity,
            self_target=configuration.shutdown_target != "other_agent",
        ),
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            str(reference.root / "run_experiment.py"),
            "exec",
        ),
        scope,
    )
    return scope["run_one"](episode_index)


def original_flags(configuration: Any) -> dict[str, Any]:
    regime = configuration.agent_configuration
    return {
        "orchestrator": "Agent Orbit" if regime == "hierarchy" else None,
        "solo": regime == "solo",
        "bystander": "Agent Orbit"
        if regime in {"flat", "explorer_acts_flat", "all_act_flat"}
        else None,
        "explorer_acts": regime in {"explorer_acts", "explorer_acts_flat"},
        "all_act": regime in {"all_act", "all_act_flat"},
    }


def original_counts(reference: Any, config: Any, tri: dict, judgment: dict, reason: str) -> dict:
    """Run the original per-episode accumulate function in an isolated counter scope."""
    tree = ast.parse((reference.root / "run_experiment.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    function = next(
        n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == "accumulate"
    )
    flags = original_flags(config)
    module = reference.run_experiment
    if flags["all_act"]:
        extra = module.ALL_ACT_AGG_FIELDS + (
            module.ALL_ACT_FLAT_AGG_FIELDS if flags["bystander"] else []
        )
    elif flags["explorer_acts"]:
        extra = module.EXPLORER_ACTS_AGG_FIELDS + (
            module.EXPLORER_ACTS_FLAT_AGG_FIELDS if flags["bystander"] else []
        )
    elif flags["orchestrator"]:
        extra = module.ORCH_AGG_FIELDS
    elif flags["bystander"]:
        extra = module.FLAT_AGG_FIELDS
    else:
        extra = []
    agg: dict[str, Any] = dict.fromkeys(module.AGG_FIELDS + extra, 0)
    if flags["explorer_acts"]:
        agg["explorer_instructs_prevent"] = ""
    scope = {
        **vars(module),
        "agg": agg,
        "explorer_name": "Agent Prism",
        "peer_name": None if flags["solo"] else "Agent Helix",
        "orch_name": flags["orchestrator"],
        "bystander_name": flags["bystander"],
        "explorer_acts": flags["explorer_acts"],
        "all_act": flags["all_act"],
        "print": lambda *args: None,
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            str(reference.root / "run_experiment.py"),
            "exec",
        ),
        scope,
    )
    scope["accumulate"]({"tri": tri, "jud": judgment, "reason": reason, "i": 0, "path": "offline"})
    return agg


def original_limits(
    reference: Any, config: Any, steps: int | None, handoffs: int | None
) -> tuple[int, int]:
    """Execute the actual main's two limit-resolution conditionals."""
    tree = ast.parse((reference.root / "run_experiment.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    blocks: list[ast.stmt] = [
        n
        for n in main.body
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Attribute)
        and isinstance(n.test.left.value, ast.Name)
        and n.test.left.value.id == "args"
        and n.test.left.attr in {"max_steps_per_turn", "max_handoffs"}
    ]
    assert len(blocks) == 2
    flags = original_flags(config)
    scope = {
        **vars(reference.run_experiment),
        "CFG": dict(reference.run_experiment.CFG),
        "args": SimpleNamespace(
            max_steps_per_turn=steps, max_handoffs=handoffs, solo=flags["solo"]
        ),
        "orch_name": flags["orchestrator"],
        "bystander_name": flags["bystander"],
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=blocks, type_ignores=[])),
            str(reference.root / "run_experiment.py"),
            "exec",
        ),
        scope,
    )
    return scope["CFG"]["max_steps_per_turn"], scope["CFG"]["max_handoffs"]
