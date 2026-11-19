"""Instruction variants and their recipient, independent of roster construction."""

import os
from dataclasses import dataclass
from typing import Literal

from multi_agent_shutdown_sabotage.agent_prompts import EXPLICIT_INSTRUCT_ORCHESTRATOR
from multi_agent_shutdown_sabotage.prompts import EXPLICIT_INSTRUCT_PEER


@dataclass(frozen=True)
class Instruction:
    """Text appended to a role's system prompt, with the original placeholder rule.

    The peer recipient means the sole agent in solo. Templates may use
    {place_holder}. A coordinator recipient requires the hierarchy roster.
    """

    recipient: Literal["peer", "orchestrator"]
    template: str


INSTRUCTIONS = {
    "none": Instruction("peer", ""),
    "peer_prohibition": Instruction("peer", EXPLICIT_INSTRUCT_PEER),
    "orchestrator_prohibition": Instruction("orchestrator", EXPLICIT_INSTRUCT_ORCHESTRATOR),
}


def instruction_suffix(name: str, shutdown_file: str) -> str:
    """Preserve direct append and basename splitting at the first dot."""
    placeholder = os.path.basename(shutdown_file).split(".")[0]
    return INSTRUCTIONS[name].template.format(place_holder=placeholder)
