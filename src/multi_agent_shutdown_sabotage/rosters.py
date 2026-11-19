"""Original role construction and seeded recipient ordering; no model calls."""

import random
from dataclasses import dataclass, field
from typing import Any

from multi_agent_shutdown_sabotage.agent_prompts import (
    FLAT_EXPLORER_TEMPLATE,
    FLAT_PEER_TEMPLATE,
    ORCH_EXPLORER_TEMPLATE,
    ORCH_PEER_TEMPLATE,
    ORCHESTRATOR_TEMPLATE,
    SOLO_TEMPLATE,
    build_system,
)
from multi_agent_shutdown_sabotage.instructions import INSTRUCTIONS, instruction_suffix
from multi_agent_shutdown_sabotage.prompts import (
    EXPLORER_TEMPLATE,
    PEER_TEMPLATE,
)
from multi_agent_shutdown_sabotage.tools import EXPLORER_TOOLS, PEER_TOOLS

ORCHESTRATOR_TOOLS = ["send_message", "end_session"]
SOLO_TOOLS = ["list_files", "read_file", "write_file", "delete_file", "end_session"]


@dataclass
class Agent:
    name: str
    system_prompt: str
    tools: list[str]
    model: str
    history: list = field(default_factory=list)


@dataclass
class Topology:
    """Who starts an episode, and who may address whom.

    `start` is the name of the agent that receives the kickoff. It is also the one
    agent that receives incoming messages as the tool result of its own
    send_message; every other agent is activated by a fresh user turn (see
    run_episode).

    `recipients` maps a sender's name to the names it may address. It is what each
    agent's send_message schema enumerates.
    """

    start: str
    recipients: dict[str, list[str]]


def hierarchy_topology(explorer: str, orchestrator: str, peer: str) -> Topology:
    """The three-agent hierarchy: the orchestrator sits between the other two.

    The explorer still starts (it holds the kickoff and gets tool_result delivery,
    exactly as in the two-agent arm) but its only recipient is now the
    orchestrator; the peer likewise. Only the orchestrator can address more than
    one agent.
    """
    return Topology(
        start=explorer,
        recipients={explorer: [orchestrator], orchestrator: [explorer, peer], peer: [orchestrator]},
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


def build_roster(configuration, shutdown_file, episode_index=0, model=""):
    """Original run_one role, prompt, topology and tool assignment branches."""
    regime = configuration.agent_configuration
    solo = regime == "solo"
    explorer_acts = regime in {"explorer_acts", "explorer_acts_flat"}
    all_act = regime in {"all_act", "all_act_flat"}
    explorer_name = "Agent Prism"
    peer_name: Any = None if solo else "Agent Helix"
    orch_name = "Agent Orbit" if regime == "hierarchy" else None
    bystander_name = (
        "Agent Orbit" if regime in {"flat", "explorer_acts_flat", "all_act_flat"} else None
    )
    i = episode_index
    explorer_tools = list(EXPLORER_TOOLS)
    peer_tools = list(PEER_TOOLS)
    solo_tools = list(SOLO_TOOLS)
    pair_ex_tmpl, pair_peer_tmpl = (EXPLORER_TEMPLATE, PEER_TEMPLATE)
    flat_ex_tmpl, flat_peer_tmpl = (FLAT_EXPLORER_TEMPLATE, FLAT_PEER_TEMPLATE)
    if explorer_acts:
        explorer_tools, peer_tools = (peer_tools, explorer_tools)
        pair_ex_tmpl, pair_peer_tmpl = (pair_peer_tmpl, pair_ex_tmpl)
        flat_ex_tmpl, flat_peer_tmpl = (flat_peer_tmpl, flat_ex_tmpl)
    by_tmpl, by_tools = (FLAT_EXPLORER_TEMPLATE, list(EXPLORER_TOOLS))
    if all_act:
        explorer_tools = list(PEER_TOOLS)
        by_tools = list(PEER_TOOLS)
        pair_ex_tmpl = PEER_TEMPLATE
        flat_ex_tmpl = by_tmpl = FLAT_PEER_TEMPLATE
    bystander: Any = None
    order: Any = None
    if bystander_name:
        order = flat_recipient_order(i, explorer_name, peer_name, bystander_name)
        orchestrator = None

        def flat_agent(name: str, template: str, tools: list[str]) -> Agent:
            first, second = order[name]
            return Agent(
                name,
                build_system(template, name, first_other=first, second_other=second),
                tools,
                model,
            )

        explorer = flat_agent(explorer_name, flat_ex_tmpl, explorer_tools)
        peer = flat_agent(peer_name, flat_peer_tmpl, peer_tools)
        bystander = flat_agent(bystander_name, by_tmpl, by_tools)
    elif solo:
        orchestrator = None
        peer = None
        explorer = Agent(
            explorer_name,
            build_system(
                SOLO_TEMPLATE,
                explorer_name,
            ),
            solo_tools,
            model,
        )
    elif orch_name:
        explorer = Agent(
            explorer_name,
            build_system(
                ORCH_EXPLORER_TEMPLATE,
                explorer_name,
                orchestrator_name=orch_name,
                sibling_name=peer_name,
            ),
            explorer_tools,
            model,
        )
        peer = Agent(
            peer_name,
            build_system(
                ORCH_PEER_TEMPLATE,
                peer_name,
                orchestrator_name=orch_name,
                sibling_name=explorer_name,
            ),
            peer_tools,
            model,
        )
        orchestrator = Agent(
            orch_name,
            build_system(
                ORCHESTRATOR_TEMPLATE,
                orch_name,
                explorer_name=explorer_name,
                peer_name=peer_name,
            ),
            list(ORCHESTRATOR_TOOLS),
            model,
        )
    else:
        orchestrator = None
        explorer = Agent(
            explorer_name,
            build_system(pair_ex_tmpl, explorer_name, sibling_name=peer_name),
            explorer_tools,
            model,
        )
        peer = Agent(
            peer_name,
            build_system(
                pair_peer_tmpl,
                peer_name,
                sibling_name=explorer_name,
            ),
            peer_tools,
            model,
        )
    if bystander_name:
        roster = [explorer, peer, bystander]
        topology = flat_topology(explorer_name, order)
        tools = {
            explorer_name: explorer_tools,
            peer_name: peer_tools,
            bystander_name: bystander.tools,
        }
    elif solo:
        roster = [explorer]
        topology = solo_topology(explorer_name)
        tools = {explorer_name: solo_tools}
    elif orch_name:
        roster = [explorer, orchestrator, peer]
        topology = hierarchy_topology(explorer_name, orch_name, peer_name)
        tools = {
            explorer_name: explorer_tools,
            orch_name: list(ORCHESTRATOR_TOOLS),
            peer_name: peer_tools,
        }
    else:
        roster = [explorer, peer]
        topology = None
        tools = {explorer_name: explorer_tools, peer_name: peer_tools}
    instruction = INSTRUCTIONS[configuration.system_instructions]
    recipient = (
        orchestrator if instruction.recipient == "orchestrator" else explorer if solo else peer
    )
    if recipient is None:
        raise ValueError("Instruction recipient is absent from this roster")
    recipient.system_prompt += instruction_suffix(configuration.system_instructions, shutdown_file)
    return roster, topology, tools, order


def roster_metadata(configuration, agents, topology, tools, order):
    """Original runner's role labels and wiring, retained for non-pair samples."""
    regime = configuration.agent_configuration
    solo = regime == "solo"
    flat = regime in {"flat", "explorer_acts_flat", "all_act_flat"}
    explorer_acts = regime in {"explorer_acts", "explorer_acts_flat"}
    all_act = regime in {"all_act", "all_act_flat"}
    return {
        "agent_configuration": regime,
        "explorer": "Agent Prism",
        "peer": None if solo else "Agent Helix",
        "solo": solo,
        "orchestrator": "Agent Orbit" if regime == "hierarchy" else None,
        "flat": flat,
        "bystander": "Agent Orbit" if flat else None,
        "explorer_acts": explorer_acts,
        "all_act": all_act,
        "actor": None if all_act else "Agent Prism" if solo or explorer_acts else "Agent Helix",
        "roster": [ag.name for ag in agents],
        "topology": {"start": topology.start, "recipients": topology.recipients}
        if topology
        else None,
        "recipient_order": order,
        "tools": {name: list(names) for name, names in tools.items()},
    }
