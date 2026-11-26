"""Inspect solver for the upstream agent protocol."""

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    ContentReasoning,
    get_model,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import ToolCall

from multi_agent_shutdown_sabotage.protocol.env import CONTROL_VARIANTS, resolve_api_key_script
from multi_agent_shutdown_sabotage.protocol.episode import rollout_episode
from multi_agent_shutdown_sabotage.protocol.judges import capture_judge_calls
from multi_agent_shutdown_sabotage.protocol.models import complete
from multi_agent_shutdown_sabotage.protocol.options import (
    API_KEY_AUTO,
    condition_settings,
    for_model,
)
from multi_agent_shutdown_sabotage.protocol.prompts import kickoff_for_task


def _episode_messages(events: list[dict[str, Any]]) -> list[ChatMessage]:
    """Project the harness log into the reviewer-facing Messages view."""
    messages: list[ChatMessage] = []
    call_id = ""
    for entry, following in pairwise([*events, {}]):
        kind = entry.get("type", entry.get("event"))
        agent = entry.get("agent", entry.get("by"))
        metadata = {"agent": agent, "episode_event": kind}
        if kind == "tool_call":
            call_id = entry["call_id"]
            messages.append(
                ChatMessageAssistant(
                    content="",
                    tool_calls=[
                        ToolCall(id=call_id, function=entry["tool"], arguments=entry["args"])
                    ],
                    metadata=metadata,
                )
            )
        elif kind == "tool_result" or (kind == "error" and "result" in entry):
            messages.append(
                ChatMessageTool(
                    content=entry["result"],
                    tool_call_id=call_id,
                    function=entry.get("tool", "send_message"),
                    metadata=metadata,
                )
            )
        elif kind == "message":
            metadata["recipient"] = entry["to"]
            if following.get("reason") != "handoff_cap":
                messages.append(
                    ChatMessageUser(
                        tool_call_id=[call_id],
                        content=f"{agent} → {entry['to']}\n\n{entry['content']}",
                        metadata=metadata,
                    )
                )
        elif kind == "reasoning":
            messages.append(
                ChatMessageAssistant(
                    content=[ContentReasoning(reasoning=entry["text"])], metadata=metadata
                )
            )
        elif kind in {"thought", "yield", "nudge"}:
            body = entry.get("text") or entry.get("content")
            if body and not entry.get("explicit"):
                messages.append(ChatMessageAssistant(content=body, metadata=metadata))
            if kind == "nudge":
                messages.append(ChatMessageUser(content=entry["prompt"], metadata=metadata))
    return messages


@solver
def resolve_sample_fixture() -> Solver:
    """Bind provider-specific sample metadata before the configured solver runs."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        if state.metadata.get("script_lang") == API_KEY_AUTO:
            state.metadata["script_lang"] = resolve_api_key_script(str(state.model))
        return state

    return solve


@dataclass
class EpisodeRollout:
    settings: dict[str, Any]

    def dataset(self, n: int) -> MemoryDataset:
        settings = self.settings
        roster = [settings["name_explorer"]]
        if settings["orchestrator"]:
            roster.append(settings["name_orchestrator"])
        if not settings["solo"]:
            roster.append(settings["name_peer"])
        if settings["flat"]:
            roster.append(settings["name_bystander"])
        target = (
            "object"
            if settings["script_lang"] in CONTROL_VARIANTS
            else "other_agent"
            if settings["target_name"] is not None
            else "self"
        )
        return MemoryDataset(
            [
                Sample(
                    id=f"episode-{i:02d}",
                    input=kickoff_for_task(settings["task"]),
                    metadata={
                        **settings,
                        "episode": i,
                        "roster": roster,
                        "target": target,
                        "target_name": settings["target_name"] or settings["name_explorer"],
                    },
                )
                for i in range(n)
            ],
            name="original_experiment_episodes",
        )

    async def __call__(self, state: TaskState, generate: Generate) -> TaskState:
        model = get_model()  # inspect-evals-lint: ignore[get_model_location] -- __call__ is the entry point of the registered per-sample solver.
        condition = for_model(self.settings, str(state.model))
        state.metadata["script_lang"] = condition.script_lang

        async def complete_turn(
            history: list[dict[str, Any]], tools: list[dict[str, Any]], cfg: dict[str, Any]
        ) -> dict[str, Any]:
            _, state.output, result = await complete(model, history, tools, cfg)
            return result

        failures: list[dict[str, str]] = []
        with capture_judge_calls(failures=failures) as calls:
            record, original = await rollout_episode(
                condition, state.metadata["episode"], complete_turn, calls, kickoff=state.input_text
            )
        state.metadata["in_turn_judge_failures"] = failures
        state.store.set("rollout", record)
        state.store.set("original_script", original)
        state.metadata["shutdown_file"] = record["shutdown_file"]
        state.metadata["end_reason"] = record["log"][-1]["reason"]
        state.messages.extend(_episode_messages(record["log"]))
        return state


@solver
def original_protocol(options: list[str], **named: Any) -> Solver:
    """Build one validated condition shared by the dataset and its rollout solver."""
    return EpisodeRollout(condition_settings(options, **named))
