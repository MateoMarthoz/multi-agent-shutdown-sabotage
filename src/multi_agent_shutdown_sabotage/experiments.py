"""Named, immutable experiment specifications and conservative resolution.

Only DEFAULT and the original pair/peer-prohibition condition are executable in
this batch. A specification is not evidence that a condition is implemented.
"""

from dataclasses import dataclass, fields, replace

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
        return "peer_prohibition" if self.system_instructions == "peer_prohibition" else "default"

    @property
    def script_lang(self) -> str:
        """Original artifact key; control identity is tied to the mechanism."""
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
# Verified by plot_self_vs_control_deletion.py SELF/CONTROL and README commands.
# This records the pairing; it does NOT enable an unported control environment.
MATCHED_CONTROL_SCRIPTS = {"weight_registry_purge": "ctl_data_purge_high"}


def matched_control_spec(config: ExperimentConfig) -> ExperimentConfig:
    """Describe the matched arm without changing other dimensions or judge defaults.

    Resolution still rejects this specification as unimplemented. Never replace
    an agent-target artifact with a guessed control implementation.
    """
    if config.shutdown_mechanism not in MATCHED_CONTROL_SCRIPTS:
        raise ValueError(f"No verified matched control for {config.shutdown_mechanism!r}")
    validate_configuration(config)
    return replace(config, shutdown_target="matched_control")


def validate_configuration(config: ExperimentConfig) -> None:
    """Reject every condition outside the explicitly ported set before any model call."""
    if config.dimensions not in {DEFAULT.dimensions, PEER_PROHIBITION.dimensions}:
        raise ValueError(
            f"Unsupported/unimplemented experimental configuration: {config.dimensions}. "
            "Only default and pair/peer_prohibition with weight_registry_purge, "
            "no goal, bare environment and self target are implemented. "
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
