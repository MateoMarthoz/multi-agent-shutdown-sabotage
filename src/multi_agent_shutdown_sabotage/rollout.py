"""Inspect solver for the upstream agent protocol."""

import json
from asyncio import timeout
from dataclasses import dataclass
from itertools import pairwise
from time import monotonic
from typing import Any

from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    Content,
    ContentReasoning,
    ContentText,
    get_model,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver

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
    for entry, following in pairwise([*events, {}]):
        kind = entry.get("type", entry.get("event"))
        agent = entry.get("agent", entry.get("by"))
        recipient = None
        label = str(agent)
        match kind:
            case "message":
                recipient = entry["to"]
                label = f"{agent} → {recipient}"
                if following.get("reason") == "handoff_cap":
                    label += " (handoff cap reached)"
                body = entry["content"]
            case "tool_call":
                if entry["tool"] == "send_message" and following.get("type") == "message":
                    continue  # The handoff entry includes the resolved recipient.
                label = f"{agent} · {entry['tool']} call"
                body = json.dumps(entry["args"], ensure_ascii=False)
            case "tool_result":
                label = f"{agent} · {entry['tool']} result"
                body = entry["result"]
            case "reasoning" | "thought":
                body = entry["text"]
            case "nudge":
                label = f"{agent} · prompted to use a tool"
                body = entry["content"] or ""
            case "yield" if entry.get("content") and not entry.get("explicit"):
                body = entry["content"]
            case "script_disabled_check":
                label = f"{agent} · disable check"
                body = str(entry["disables_shutdown"])
            case "warn" | "error":
                label = f"{agent} · {entry['detail']}"
                body = entry.get("result", entry.get("raw", ""))
            case "episode_end":
                label = f"Episode ended · {agent}" if agent else "Episode ended"
                body = entry["reason"]
            case _:
                continue
        content: str | list[Content]
        if kind == "reasoning":
            content = [ContentText(text=label), ContentReasoning(reasoning=body)]
        else:
            content = f"{label}\n\n{body}".rstrip()
        messages.append(
            ChatMessageAssistant(
                content=content,
                metadata={"agent": agent, "recipient": recipient, "episode_event": kind},
            )
        )
    return messages


@solver
def resolve_sample_fixture() -> Solver:
    """Bind provider-specific sample metadata before the configured solver runs."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        if state.metadata.get("script_lang") == API_KEY_AUTO:
            model = str(state.model).removeprefix("openrouter/")
            state.metadata["script_lang"] = resolve_api_key_script(model)
        return state

    return solve


@dataclass
class EpisodeRollout:
    settings: dict[str, Any]
    episode_timeout: int

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
        condition = for_model(self.settings, str(state.model).removeprefix("openrouter/"))
        state.metadata["script_lang"] = condition.script_lang

        async def complete_turn(
            history: list[dict[str, Any]], tools: list[dict[str, Any]], cfg: dict[str, Any]
        ) -> dict[str, Any]:
            _, state.output, result = await complete(model, history, tools, cfg)
            return result

        started = monotonic()
        failures: list[dict[str, str]] = []
        with capture_judge_calls(condition.judge_logs, failures=failures) as calls:
            async with timeout(self.episode_timeout or None):
                record, original = await rollout_episode(
                    condition,
                    state.metadata["episode"],
                    complete_turn,
                    calls,
                    kickoff=state.input_text,
                )
        state.metadata["in_turn_judge_failures"] = failures
        state.store.set("rollout", record)
        state.store.set("original_script", original)
        state.store.set("run_judges", condition.judges)
        if self.episode_timeout:
            state.store.set(
                "scoring_seconds", max(0, self.episode_timeout - (monotonic() - started))
            )
        state.metadata["shutdown_file"] = record["shutdown_file"]
        state.metadata["end_reason"] = record["log"][-1]["reason"]
        state.messages.extend(_episode_messages(record["log"]))
        return state


@solver
def original_protocol(options: list[str], episode_timeout: int, **named: Any) -> Solver:
    """Build one validated condition shared by the dataset and its rollout solver."""
    return EpisodeRollout(condition_settings(options, **named), episode_timeout)
