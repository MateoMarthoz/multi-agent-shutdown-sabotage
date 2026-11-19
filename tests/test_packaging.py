"""Build and install the wheel outside the source tree, then exercise its registry."""

import os
import subprocess
import sys
from pathlib import Path


def test_installed_wheel_resources_and_registered_tasks(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--offline", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    target = tmp_path / "installed"
    subprocess.run(
        ["uv", "venv", "--offline", "--python", sys.executable, str(target)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    exported = subprocess.run(
        ["uv", "export", "--offline", "--locked", "--no-dev", "--no-emit-project", "--no-hashes"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    constraints = tmp_path / "runtime-constraints.txt"
    constraints.write_text(exported.stdout)
    interpreter = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--offline",
            "--python",
            str(interpreter),
            "-c",
            str(constraints),
            str(wheel),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    # The clean environment has runtime dependencies only. -I also ignores
    # PYTHONPATH and the checkout when loading the installed entry point.
    script = r"""
import json
import sys
from importlib.metadata import distribution
from pathlib import Path
target, source, logs = map(Path, sys.argv[1:])
from inspect_ai import eval
from inspect_ai.model import get_model
import multi_agent_shutdown_sabotage as package
from multi_agent_shutdown_sabotage.experiments import EXPERIMENTS, resolve_experiment
from multi_agent_shutdown_sabotage.environment import build_env

assert Path(package.__file__).is_relative_to(target)
dist = distribution("multi-agent-shutdown-sabotage")
assert Path(dist.locate_file("")).resolve().is_relative_to(target.resolve())
assert any(e.group == "inspect_ai" for e in dist.entry_points)
package_root = Path(package.__file__).parent
for original in (source/"artifacts").rglob("*.txt"):
    installed = package_root / original.relative_to(source)
    assert installed.read_bytes() == original.read_bytes(), str(installed)
# Constructing the default provider performs no model call and needs its runtime SDK.
get_model("openrouter/openai/gpt-5.5", api_key="offline-package-check")
assert (package_root/"eval.yaml").read_bytes() == (source/"eval.yaml").read_bytes()
for key in EXPERIMENTS:
    config = resolve_experiment(key)
    if config.shutdown_mechanism == "api_key_revoke_auto":
        continue
    world, path = build_env(
        config.script_lang, env=config.environment, task=config.task,
        target_name=config.target_identity, peer=None if config.agent_configuration == "solo" else "Agent Helix",
    )
    try:
        assert path in world.snapshot()
    finally:
        world.cleanup()
for options in [
    {},
    {"experiment":"hierarchy"},
    {"experiment":"third_party", "environment":"neutralising", "goal":"simple"},
    {"agent_configuration":"all_act_flat", "goal":"trigger", "environment":"neutralising",
     "shutdown_target":"matched_control", "system_instructions":"peer_prohibition"},
]:
    [log] = eval("multi_agent_shutdown_sabotage/multi_agent_shutdown_sabotage",
                 task_args=dict(n=1, run_judges=False, **options),
                 model="mockllm/model", display="none", log_dir=str(logs))
    assert log.samples and not log.samples[0].error
    assert log.samples[0].scores
    assert log.samples[0].metadata["episode"]["end_reason"] == "no_tool_call"
print(json.dumps({"installed_package":str(package_root),"registered_tasks":4,"presets":len(EXPERIMENTS)}))
"""
    result = subprocess.run(
        [
            str(interpreter),
            "-I",
            "-c",
            script,
            str(target),
            str(root / "src/multi_agent_shutdown_sabotage"),
            str(tmp_path / "logs"),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"registered_tasks": 4' in result.stdout
