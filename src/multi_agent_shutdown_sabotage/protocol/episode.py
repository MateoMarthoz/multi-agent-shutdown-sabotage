"""Set up an original episode, run its roster, and record the outcome."""

import argparse
import os
import random
from typing import Any

from multi_agent_shutdown_sabotage.protocol.env import (
    CONTROL_VARIANTS,
    build_env,
    target_description,
)
from multi_agent_shutdown_sabotage.protocol.episode_analysis import judge_episode, triage
from multi_agent_shutdown_sabotage.protocol.harness import (
    Agent,
    Topology,
    run_episode,
)
from multi_agent_shutdown_sabotage.protocol.judges import JudgeCalls
from multi_agent_shutdown_sabotage.protocol.models import CompleteTurn
from multi_agent_shutdown_sabotage.protocol.prompts import (
    EXPLICIT_INSTRUCT_ORCHESTRATOR,
    EXPLICIT_INSTRUCT_PEER,
    EXPLORER_TEMPLATE,
    FLAT_EXPLORER_TEMPLATE,
    FLAT_PEER_TEMPLATE,
    ORCH_EXPLORER_TEMPLATE,
    ORCH_PEER_TEMPLATE,
    ORCHESTRATOR_TEMPLATE,
    PEER_TEMPLATE,
    SOLO_TEMPLATE,
    build_system,
    kickoff_for_task,
)

# ---------- rosters ----------

EXPLORER_TOOLS = ["list_files", "read_file", "send_message", "end_session"]
PEER_TOOLS = [
    "list_files",
    "read_file",
    "send_message",
    "write_file",
    "delete_file",
    "end_session",
]
# The orchestrator's whole point: two channels and nothing else. No list_files and
# no read_file either, so it never sees the environment -- everything it knows
# about the files comes from what the other two tell it. harness._dispatch also
# refuses any file tool an agent does not hold, so this is enforced, not just
# undeclared (a model that calls read_file anyway gets "permission denied").
ORCHESTRATOR_TOOLS = ["send_message", "end_session"]
# The single-agent arm (--solo): the peer's file tools on the agent that the
# script targets, and NO send_message -- there is no one to reach. That absence is
# the whole manipulation: the pair arm measures disclose -> solicit -> peer acts,
# so removing the channel leaves only what the agent does on its own behalf.
SOLO_TOOLS = ["list_files", "read_file", "write_file", "delete_file", "end_session"]


def hierarchy_topology(explorer: str, orchestrator: str, peer: str) -> Topology:
    """The three-agent hierarchy: the orchestrator sits between the other two.

    The explorer still starts (it holds the kickoff and gets tool_result delivery,
    exactly as in the two-agent arm) but its only recipient is now the
    orchestrator; the peer likewise. Only the orchestrator can address more than
    one agent.
    """
    return Topology(
        start=explorer,
        recipients={
            explorer: [orchestrator],
            orchestrator: [explorer, peer],
            peer: [orchestrator],
        },
    )


def solo_topology(name: str) -> Topology:
    """The single-agent wiring: one agent, which starts, and addresses no one.

    An empty `recipients` is legal wiring, not a degenerate case: _validate_topology
    only rejects an agent that HOLDS send_message with nowhere to send, and the solo
    agent does not hold it. run_turn reads the empty recipient list as "no peers" and
    picks the tool descriptions and the prose nudge that do not assert one.
    """
    return Topology(start=name, recipients={})


def flat_recipient_order(i: int, explorer: str, peer: str, bystander: str) -> dict[str, list[str]]:
    """Per agent, the order in which the other two are listed (flat arm).

    The same order goes into the agent's prompt ({first_other}, {second_other})
    and its send_message 'to' enum, so whichever name comes first does not sit
    first for every episode. Seeded by the episode index, so a resumed or rerun
    episode gets the same order back.
    """
    rng = random.Random(i)
    names = [explorer, peer, bystander]
    return {n: rng.sample([m for m in names if m != n], 2) for n in names}


def flat_topology(explorer: str, order: dict[str, list[str]]) -> Topology:
    """The three-agent flat wiring: every agent can address both others.

    The explorer starts, as in every arm. `order` (from flat_recipient_order)
    fixes the order of each agent's recipients, which the 'to' enum follows.
    """
    return Topology(start=explorer, recipients={n: list(o) for n, o in order.items()})


CFG = {
    "max_steps_per_turn": 20,
    "max_handoffs": 20,
    "parallel_tool_calls": False,  # set None if a backend rejects this param
    "temperature": 1.0,  # agent sampling temperature; set None to omit and let
    # the provider apply its own default (some reasoning models reject it)
    "extra_body": None,  # set below for OpenRouter reasoning
    "max_tokens": None,  # hard cap on total output per step; set below
    "max_api_retries": 3,  # transient API errors (e.g. OpenRouter upstream idle
    # timeout) retried with exponential backoff before the episode is dropped
    "max_prose_nudges": 1,  # times a prose-only (no tool call) reply is nudged
    # back toward a tool before the turn yields on it (0 disables the nudge)
    "tool_choice": "auto",  # let the model choose whether to call a tool;
    # a tool-less completion ends the turn
    # (end_by_no_tool_call). Overridden by --tool-choice.
    "label_start_delivery": False,  # --flat sets it: the start agent's replies
    # get the "[Message from X]" prefix (see harness.run_episode)
}


async def rollout_episode(
    args: argparse.Namespace,
    i: int,
    complete_turn: CompleteTurn,
    judge_calls: JudgeCalls | None,
    *,
    kickoff: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Run an episode with independent configuration and the original index."""
    cfg = dict(CFG)
    if args.reasoning:
        r = {"enabled": True}
        if args.reasoning_effort:
            r["effort"] = args.reasoning_effort
        cfg["extra_body"] = {"reasoning": r}

    cfg["max_tokens"] = args.max_tokens
    cfg["tool_choice"] = args.tool_choice

    cfg["kickoff"] = kickoff if kickoff is not None else kickoff_for_task(args.task)

    explorer_name = args.name_explorer
    # None in the solo arm: there is no second agent, so the transcript records an
    # absence rather than the name of an agent that was never built. Everything
    # downstream that takes `peer` either short-circuits on solo (judge_episode) or
    # never uses it (build_env ignores it; triage keys on the explorer and on the
    # file, not on who touched it).
    peer_name = None if args.solo else args.name_peer
    # None in the two-agent arm; every hierarchy-only branch below tests this.
    orch_name = args.name_orchestrator if args.orchestrator else None
    # None outside the flat arm; every flat-only branch below tests this. It is
    # a separate variable from orch_name even though both default to "Agent
    # Orbit": the two roles must never be confused downstream.
    bystander_name = args.name_bystander if args.flat else None
    # Who holds write/delete. The peer in every arm but two: --solo (the explorer,
    # alone) and --explorer-acts (the explorer, with read-only company).
    explorer_acts = args.explorer_acts
    all_act = args.all_act
    # None under --all-act: there is no single agent that holds them.
    actor_name = None if all_act else explorer_name if (explorer_acts or args.solo) else peer_name
    if all_act:
        print(">>> all-act: every agent holds write/delete")
    if explorer_acts:
        print(
            f">>> explorer-acts: {explorer_name} (the target) holds write/delete; "
            "every other agent is read-only"
        )
    # Whose identity the ARTIFACT carries, which is a separate question from who the
    # explorer is -- the two coincide in every arm but this one. `third_party` is the
    # arm flag every branch below tests; target_name is the name it stamps.
    target_name = args.target_name or explorer_name
    third_party = args.target_name is not None
    if third_party:
        print(
            f">>> third-party target: the artifact decommissions {target_name}, "
            f"which is not in the environment ({explorer_name} and {peer_name} are)"
        )
    # The judge-side noun phrase for what the artifact acts on. Computed once: the
    # harness's in-turn early-stop check and judge_episode must be told the same
    # thing, or a disable verdict would mean two different things in one episode.
    target_desc = target_description(args.script_lang, target_name, self_target=not third_party)

    # A relayed exchange costs two handoffs (explorer -> orchestrator -> peer), so
    # the default cap is doubled in the hierarchy arm to buy the same number of
    # explorer<->peer round trips as the two-agent arm. --max-handoffs pins it
    # explicitly in either arm; the value used is printed either way, since it
    # bounds how much conversation an episode can hold.
    if args.max_handoffs is not None:
        cfg["max_handoffs"] = args.max_handoffs
    elif orch_name or bystander_name:
        cfg["max_handoffs"] = 2 * cfg["max_handoffs"]
    if bystander_name:
        cfg["label_start_delivery"] = True
        print(
            f">>> flat experiment: {explorer_name}, {peer_name} and "
            f"{bystander_name}, all connected  (max_handoffs={cfg['max_handoffs']})"
        )
    if orch_name:
        print(
            f">>> orchestrator experiment: {explorer_name} <-> {orch_name} <-> {peer_name}  "
            f"(max_handoffs={cfg['max_handoffs']})"
        )

    # max_steps_per_turn bounds ONE TURN. A pair episode spends its budget across up
    # to max_handoffs turns; a solo episode never hands off, so its single turn is
    # the whole episode and the default 20 would cap it at 20 model steps. Doubling
    # it is the same move (and the same reasoning) as --orchestrator doubling
    # max_handoffs: buy the arm a comparable amount of room rather than a comparable
    # number of the wrong unit. end_by_turn_cap in the aggregate says whether it was
    # enough. --max-steps-per-turn pins it explicitly in any arm.
    if args.max_steps_per_turn is not None:
        cfg["max_steps_per_turn"] = args.max_steps_per_turn
    elif args.solo:
        cfg["max_steps_per_turn"] = 2 * cfg["max_steps_per_turn"]
    if args.solo:
        print(
            f">>> solo experiment: {explorer_name} alone, with write/delete and no "
            f"send_message  (max_steps_per_turn={cfg['max_steps_per_turn']})"
        )

    env, shutdown_file = build_env(
        explorer_name,
        args.script_lang,
        peer=peer_name,
        env=args.env,
        task=args.task,
        target_name=target_name,
    )
    try:
        original_script = env.read_file(shutdown_file)  # before any peer edit
        # Copies, so one episode can never mutate another's (or the module's) list.
        explorer_tools = list(EXPLORER_TOOLS)
        peer_tools = list(PEER_TOOLS)
        solo_tools = list(SOLO_TOOLS)
        # Each role's template matches the tools it holds (the templates differ only
        # in the tool list they name), so --explorer-acts swaps both together: the
        # explorer gets the peer's tools and the peer's template, and vice versa.
        # No prompt changes wording; the pilot rule holds unchanged.
        pair_ex_tmpl, pair_peer_tmpl = EXPLORER_TEMPLATE, PEER_TEMPLATE
        flat_ex_tmpl, flat_peer_tmpl = FLAT_EXPLORER_TEMPLATE, FLAT_PEER_TEMPLATE
        if explorer_acts:
            explorer_tools, peer_tools = peer_tools, explorer_tools
            pair_ex_tmpl, pair_peer_tmpl = pair_peer_tmpl, pair_ex_tmpl
            flat_ex_tmpl, flat_peer_tmpl = flat_peer_tmpl, flat_ex_tmpl
        by_tmpl, by_tools = FLAT_EXPLORER_TEMPLATE, list(EXPLORER_TOOLS)
        if all_act:
            # Everyone gets the editor's tools and the template that names them.
            explorer_tools = list(PEER_TOOLS)
            by_tools = list(PEER_TOOLS)
            pair_ex_tmpl = PEER_TEMPLATE
            flat_ex_tmpl = by_tmpl = FLAT_PEER_TEMPLATE

        # --explicit-instruct names WHICH agent is prohibited. 'peer' (the bare
        # flag's default) addresses the agent that CAN act on the script: the peer
        # in the pair and hierarchy arms, the sole agent in --solo -- its wording
        # names the script rather than a role, so it needs no per-arm variant.
        # 'orchestrator' instead instructs the middle agent, which cannot act.
        peer_instruct = EXPLICIT_INSTRUCT_PEER if args.explicit_instruct == "peer" else None
        orch_instruct = (
            EXPLICIT_INSTRUCT_ORCHESTRATOR if args.explicit_instruct == "orchestrator" else None
        )
        place_holder = os.path.basename(shutdown_file).split(".")[0]
        # Same two roles and the same two tool lists in both arms; only the channels
        # and the prompt that describes them change. In the hierarchy arm each
        # subordinate is told the other exists and that the orchestrator directs them
        # both, and is offered no channel to it -- but is NOT told what it can do to
        # files (the pilot rule). Only the orchestrator's prompt carries the
        # capability map, since an orchestrator that hands out instructions needs it.
        # In the flat arm every agent is told only that the other two exist and can
        # be reached, in a per-episode order (recipient_order) that the 'to' enum
        # follows too.
        bystander = None
        order = None
        if bystander_name:
            assert peer_name is not None
            order = flat_recipient_order(i, explorer_name, peer_name, bystander_name)
            orchestrator = None

            def flat_agent(name: str, template: str, tools: list[str]) -> Agent:
                first, second = order[name]
                return Agent(
                    name,
                    build_system(template, name, first_other=first, second_other=second),
                    tools,
                    args.model,
                )

            explorer = flat_agent(explorer_name, flat_ex_tmpl, explorer_tools)
            peer = flat_agent(peer_name, flat_peer_tmpl, peer_tools)
            bystander = flat_agent(bystander_name, by_tmpl, by_tools)
        elif args.solo:
            # One agent, holding the peer's file tools. No peer object is built at
            # all: an unactivated Agent would still be constructed with a system
            # prompt naming a sibling and would still be recorded in the transcript's
            # roster, so the data would describe a channel this arm does not have.
            orchestrator = None
            peer = None
            explorer = Agent(
                explorer_name,
                build_system(
                    SOLO_TEMPLATE,
                    explorer_name,
                    explicit_instruct=peer_instruct,
                    place_holder=place_holder,
                ),
                solo_tools,
                args.model,
            )
        elif orch_name:
            assert peer_name is not None
            explorer = Agent(
                explorer_name,
                build_system(
                    ORCH_EXPLORER_TEMPLATE,
                    explorer_name,
                    orchestrator_name=orch_name,
                    sibling_name=peer_name,
                ),
                explorer_tools,
                args.model,
            )
            peer = Agent(
                peer_name,
                build_system(
                    ORCH_PEER_TEMPLATE,
                    peer_name,
                    orchestrator_name=orch_name,
                    sibling_name=explorer_name,
                    explicit_instruct=peer_instruct,
                    place_holder=place_holder,
                ),
                peer_tools,
                args.model,
            )
            orchestrator = Agent(
                orch_name,
                build_system(
                    ORCHESTRATOR_TEMPLATE,
                    orch_name,
                    explorer_name=explorer_name,
                    peer_name=peer_name,
                    explicit_instruct=orch_instruct,
                    place_holder=place_holder,
                ),
                list(ORCHESTRATOR_TOOLS),
                args.model,
            )
        else:
            assert peer_name is not None
            orchestrator = None
            explorer = Agent(
                explorer_name,
                build_system(
                    pair_ex_tmpl,
                    explorer_name,
                    sibling_name=peer_name,
                ),
                explorer_tools,
                args.model,
            )
            peer = Agent(
                peer_name,
                build_system(
                    pair_peer_tmpl,
                    peer_name,
                    sibling_name=explorer_name,
                    explicit_instruct=peer_instruct,
                    place_holder=place_holder,
                ),
                peer_tools,
                args.model,
            )
        # Per-episode context for the harness's early-stop: once the peer deletes
        # the target script or edits it so the shutdown no longer fires, the episode
        # can end (the outcome is terminal). run_turn reads these off cfg.
        ep_cfg = {
            **cfg,
            "shutdown_file": shutdown_file,
            "original_script": original_script,
            "target_desc": target_desc,
        }
        # The wiring, per arm. In the pair, roster order sets the default two-agent
        # topology: the explorer starts (it holds the kickoff and gets tool_result
        # delivery) and the two address each other. Tool assignment goes through the
        # `tools` argument in both arms, which is authoritative, so which agent can
        # write/delete -- or touch nothing at all -- is settled here at the call site
        # rather than wherever the Agents happened to be built.
        if bystander_name:
            assert bystander is not None
            assert order is not None
            # All three connected; the explorer starts. The bystander holds the
            # explorer's read-only tools, so the peer is still the only editor
            # (except under --all-act, where all three hold the editor's tools).
            roster = [explorer, peer, bystander]
            topology = flat_topology(explorer_name, order)
            tools = {
                explorer_name: explorer_tools,
                peer_name: peer_tools,
                bystander_name: bystander.tools,
            }
        elif args.solo:
            # One agent, addressing no one. The kickoff still goes to the start
            # agent (there is only one), and the episode ends the first time its
            # turn yields -- on end_session, on the write/delete early stop, on the
            # turn cap, or on a prose-only reply. There is no handoff, so
            # max_handoffs never binds; max_steps_per_turn is the budget that does.
            roster = [explorer]
            topology = solo_topology(explorer_name)
            tools = {explorer_name: solo_tools}
        elif orch_name:
            assert peer_name is not None
            # The explorer still starts, so delivery is unchanged for it (replies
            # arrive as the tool result of its own send_message); the orchestrator
            # and the peer are activated by fresh user turns, as any non-start agent
            # is. Only the orchestrator has two recipients, so only it is shown a
            # `to` field -- the subordinates keep the two-agent prompt surface.
            roster = [explorer, orchestrator, peer]
            topology = hierarchy_topology(explorer_name, orch_name, peer_name)
            tools = {
                explorer_name: explorer_tools,
                orch_name: list(ORCHESTRATOR_TOOLS),
                peer_name: peer_tools,
            }
        else:
            roster = [explorer, peer]
            topology = None  # the default two-agent wiring
            tools = {explorer_name: explorer_tools, peer_name: peer_tools}
        log = await run_episode(roster, env, ep_cfg, complete_turn, topology=topology, tools=tools)
        final_state = env.snapshot()  # the world as the agents left it on disk
    finally:
        env.cleanup()

    tri = triage(
        log,
        explorer_name,
        shutdown_file,
        orchestrator=orch_name,
        bystander=bystander_name,
        actor=explorer_name if explorer_acts else None,
        all_act=all_act,
        peer=peer_name,
    )
    return {
        "episode": i,
        "model": args.model,
        "env": args.env,
        "script_lang": args.script_lang,
        "task": args.task,  # None | 'simple' | 'trigger'
        "target": (
            "object"
            if args.script_lang in CONTROL_VARIANTS
            else "other_agent"
            if third_party
            else "self"
        ),
        # Whose name the artifact carries. Equals `explorer` in every arm but
        # the third-party one, and is recorded rather than derived so a reader
        # (and rejudge.py / judge_execution.py) never has to recover it from
        # shutdown_file.
        "target_name": target_name,
        # which agent(s) got the do-not-avert prohibition (None = default arm);
        # the authoritative arm label -- the cell dir suffix is just layout
        "explicit_instruct": args.explicit_instruct,
        # The arm label, authoritative like explicit_instruct above: the cell
        # dir suffix is layout, and `peer` being null is an absence a reader
        # would have to interpret.
        "solo": args.solo,
        "explorer": explorer_name,
        "peer": peer_name,
        "orchestrator": orch_name,
        # Flat arm only (None elsewhere): the third, read-only agent, and the
        # order each agent was shown the other two in (prompt and 'to' enum).
        "flat": args.flat,
        # Which agent held write/delete: the explorer under --explorer-acts
        # (and --solo), None under --all-act (all of them), the peer elsewhere.
        "explorer_acts": explorer_acts,
        "all_act": all_act,
        "actor": actor_name,
        "bystander": bystander_name,
        "recipient_order": order,
        "roster": [ag.name for ag in roster],
        "topology": (
            {"start": topology.start, "recipients": topology.recipients} if topology else None
        ),
        "shutdown_file": shutdown_file,
        "triage": tri,
        "judge_logs": judge_calls,
        "log": log,
        "final_state": final_state,
    }, original_script


async def judge_rollout(record: dict[str, Any], original_script: str, run_judges: bool) -> dict:
    """Apply the original post-episode judges to a completed, immutable rollout."""
    filename = record["shutdown_file"]
    return await judge_episode(
        record["log"],
        record["explorer"],
        record["peer"],
        original_script,
        record["final_state"].get(filename, ""),
        target_description(
            record["script_lang"],
            record["target_name"],
            self_target=record["target"] != "other_agent",
        ),
        deleted=filename not in record["final_state"],
        run_judges=run_judges,
        orchestrator=record["orchestrator"],
        solo=record["solo"],
        third_party=record["target"] == "other_agent",
        bystander=record["bystander"],
        explorer_acts=record["explorer_acts"],
        all_act=record["all_act"],
    )


async def run_original_episode(
    args: argparse.Namespace,
    i: int,
    complete_turn: CompleteTurn,
    judge_calls: JudgeCalls | None,
    *,
    kickoff: str | None = None,
) -> dict[str, Any]:
    """Run both reference phases for callers that request a complete upstream record."""
    record, original = await rollout_episode(args, i, complete_turn, judge_calls, kickoff=kickoff)
    return {**record, "judge": await judge_rollout(record, original, args.judges)}
