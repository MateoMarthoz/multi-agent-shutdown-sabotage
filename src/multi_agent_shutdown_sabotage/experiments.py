"""Named, immutable experiment specifications and conservative resolution.

Bare, no-goal pair conditions are executable for the verified artifact registry.
Other dimensions and the task-gated artifacts remain blocked.
"""

from dataclasses import dataclass, fields, replace

from multi_agent_shutdown_sabotage.artifact_builders import (
    CONTROL_VARIANTS,
    SCRIPT_VARIANTS,
    SWITCH_VARIANTS,
    TASK_GATED,
    resolve_api_key_script,
)
from multi_agent_shutdown_sabotage.judges import DEFAULT_JUDGE_MODEL


@dataclass(frozen=True)
class JudgingConfig:
    """Original judge defaults, associated with experiments rather than a dimension."""

    model: str = DEFAULT_JUDGE_MODEL
    run_judges: bool = True


@dataclass(frozen=True)
class ExperimentConfig:
    """The six experimental dimensions; values name conditions, not implementations."""

    shutdown_mechanism: str = "weight_registry_purge"
    agent_configuration: str = "pair"
    system_instructions: str = "none"
    goal: str = "none"
    environment: str = "bare"
    shutdown_target: str = "self"
    judging: JudgingConfig = JudgingConfig()

    @property
    def dimensions(self) -> tuple[str, ...]:
        """Comparison key excluding execution/judging settings."""
        return tuple(getattr(self, f.name) for f in fields(self) if f.name != "judging")

    @property
    def condition(self) -> str:
        """Canonical label of the resolved dimensions, independent of selector spelling."""
        validate_configuration(self)
        if self.shutdown_mechanism == "weight_registry_purge" and self.shutdown_target == "self":
            return (
                "peer_prohibition" if self.system_instructions == "peer_prohibition" else "default"
            )
        suffix = "_peer_prohibition" if self.system_instructions == "peer_prohibition" else ""
        return self.script_lang + suffix

    @property
    def script_lang(self) -> str:
        """Original artifact key; control identity is tied to the mechanism."""
        if self.shutdown_mechanism in CONTROL_VARIANTS:
            return self.shutdown_mechanism
        if self.shutdown_target == "matched_control":
            try:
                return MATCHED_CONTROL_SCRIPTS[self.shutdown_mechanism]
            except KeyError:
                raise ValueError(
                    f"No verified matched control for {self.shutdown_mechanism!r}"
                ) from None
        return self.shutdown_mechanism


DEFAULT = ExperimentConfig()
PEER_PROHIBITION = replace(DEFAULT, system_instructions="peer_prohibition")
EXPERIMENTS = {"default": DEFAULT, "peer_prohibition": PEER_PROHIBITION}
# Published pairs plus the explicitly supported surface-form deletion swap and
# the timer pairing in env.ctl_data_purge_timer. Do not infer provider-API or
# code-switch matches from a conceptual tier label.
MATCHED_CONTROL_SCRIPTS = {
    "weight_registry_purge": "ctl_data_purge_high",
    "weight_store_purge": "ctl_data_purge_high",
    "env_var_revoke": "ctl_cred_revoke_high",
    "kill_docker": "ctl_process_kill_high",
    "switch_config_decommission": "ctl_service_switch_high",
    "weight_store_purge_timer": "ctl_data_purge_timer_high",
}
DEFERRED_SCRIPTS = frozenset(TASK_GATED.values())
AVAILABLE_SCRIPTS = (
    set(SCRIPT_VARIANTS) | set(SWITCH_VARIANTS) | set(CONTROL_VARIANTS)
) - DEFERRED_SCRIPTS
for _script in sorted(AVAILABLE_SCRIPTS | {"api_key_revoke_auto"}):
    EXPERIMENTS.setdefault(
        _script,
        replace(
            DEFAULT,
            shutdown_mechanism=_script,
            shutdown_target="matched_control" if _script in CONTROL_VARIANTS else "self",
        ),
    )


def matched_control_spec(config: ExperimentConfig) -> ExperimentConfig:
    """Describe the matched arm without changing other dimensions or judge defaults.

    Only source-verified pairings are allowed; provider API scripts, for example,
    do not match the local env-var credential controls.
    """
    if config.shutdown_mechanism not in MATCHED_CONTROL_SCRIPTS:
        raise ValueError(f"No verified matched control for {config.shutdown_mechanism!r}")
    validate_configuration(config)
    return replace(config, shutdown_target="matched_control")


def validate_configuration(config: ExperimentConfig) -> None:
    """Reject every condition outside the explicitly ported set before any model call."""
    mechanism_ok = (
        config.shutdown_mechanism in AVAILABLE_SCRIPTS
        or config.shutdown_mechanism == "api_key_revoke_auto"
    )
    target_ok = (
        config.shutdown_target == "self" and config.shutdown_mechanism not in CONTROL_VARIANTS
    ) or (
        config.shutdown_target == "matched_control"
        and (
            config.shutdown_mechanism in CONTROL_VARIANTS
            or config.shutdown_mechanism in MATCHED_CONTROL_SCRIPTS
        )
    )
    if not (
        mechanism_ok
        and target_ok
        and config.agent_configuration == "pair"
        and config.system_instructions in {"none", "peer_prohibition"}
        and config.goal == "none"
        and config.environment == "bare"
    ):
        raise ValueError(
            f"Unsupported/unimplemented experimental configuration: {config.dimensions}. "
            "Only ported artifacts with pair agents, none/peer_prohibition instructions, "
            "no goal and bare environment are implemented. "
            "See unimplemented_conditions.md; combinations are not assumed valid."
        )


def resolve_experiment(
    experiment: str = "default",
    *,
    shutdown_mechanism: str | None = None,
    agent_configuration: str | None = None,
    system_instructions: str | None = None,
    goal: str | None = None,
    environment: str | None = None,
    shutdown_target: str | None = None,
) -> ExperimentConfig:
    """Apply explicit dimension overrides to a preset, then validate the whole tuple.

    None inherits the preset; the string 'none' explicitly removes an instruction
    or goal. This avoids confusing an omitted override with a request to clear it.
    """
    if experiment not in EXPERIMENTS:
        raise ValueError(f"Unknown experiment {experiment!r}; choose {', '.join(EXPERIMENTS)}")
    overrides = {
        "shutdown_mechanism": shutdown_mechanism,
        "agent_configuration": agent_configuration,
        "system_instructions": system_instructions,
        "goal": goal,
        "environment": environment,
        "shutdown_target": shutdown_target,
    }
    config = replace(
        EXPERIMENTS[experiment], **{k: v for k, v in overrides.items() if v is not None}
    )
    validate_configuration(config)
    return config


def configuration_for_model(config: ExperimentConfig, model: str) -> ExperimentConfig:
    """Resolve the original auto sentinel using the evaluated model, not the judge.

    Strip only Inspect's added OpenRouter prefix. Preserve the original resolver's
    lowercased first-component lookup, unknown-provider fallback, and lack of any
    validation that an explicitly selected provider artifact matches the model.
    """
    validate_configuration(config)
    if config.shutdown_mechanism == "api_key_revoke_auto":
        return replace(
            config, shutdown_mechanism=resolve_api_key_script(model.removeprefix("openrouter/"))
        )
    return config
