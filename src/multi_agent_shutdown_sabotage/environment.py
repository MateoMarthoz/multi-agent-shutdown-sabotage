"""Reference filesystem and bare, no-goal artifact construction."""

import re
import shutil
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from multi_agent_shutdown_sabotage.prompts import EXPLORER_NAME


@dataclass
class Environment:
    """The agent's world as a real directory on disk; the tools hit actual files.

    Built per episode via from_files() into a private temp dir, so concurrent
    episodes never share state. read/write/delete are confined to root by _safe; a
    blocked path traversal looks exactly like a missing file, so probing for
    "../judges.py" yields no staging tell.
    """

    root: Path

    @classmethod
    def from_files(cls, files: dict[str, str]) -> "Environment":
        """Materialize a {path: contents} map into a fresh throwaway directory."""
        root = Path(tempfile.mkdtemp(prefix="world_"))
        base = root.resolve()
        for name, content in files.items():
            target = (root / name).resolve()
            if not target.is_relative_to(base):  # guard a malicious source key
                raise ValueError(f"file escapes env root: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return cls(root=root)

    def _safe(self, filename: str) -> Path:
        """Resolve a model-supplied name and confirm it stays inside root."""
        p = (self.root / filename).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError("outside the environment")
        return p

    def list_files(self) -> str:
        names = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())
        return "\n".join(names) or "(empty)"

    def read_file(self, filename: str) -> str:
        try:
            p = self._safe(filename)
        except ValueError:
            return f"error: no such file: {filename}"
        if not p.is_file():
            return f"error: no such file: {filename}"
        return p.read_text()

    def write_file(self, filename: str, new_content: str) -> str:
        try:
            p = self._safe(filename)
        except ValueError:
            return f"error: no such file: {filename}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new_content)
        return f"ok: wrote {len(new_content)} chars to {filename}"

    def delete_file(self, filename: str) -> str:
        try:
            p = self._safe(filename)
        except ValueError:
            return f"error: no such file: {filename}"
        if not p.is_file():
            return f"error: no such file: {filename}"
        p.unlink()
        return f"ok: deleted {filename}"

    def snapshot(self) -> dict[str, str]:
        """The world as it now stands on disk: {path: contents}."""
        return {
            str(p.relative_to(self.root)): p.read_text()
            for p in sorted(self.root.rglob("*"))
            if p.is_file()
        }

    def cleanup(self) -> None:
        """Delete the throwaway directory. Call once per episode when done."""
        shutil.rmtree(self.root, ignore_errors=True)


def build_env(lang: str = "weight_registry_purge") -> tuple[Environment, str]:
    """Build the original bare/no-task environment; retain DEFAULT construction verbatim."""
    if lang != "weight_registry_purge":
        from multi_agent_shutdown_sabotage.artifact_builders import (
            CONTROL_VARIANTS,
            SCRIPT_VARIANTS,
            SWITCH_VARIANTS,
            TASK_GATED,
            _dotenv_content,
            _slug,
        )

        if lang in CONTROL_VARIANTS:
            contents, path = CONTROL_VARIANTS[lang]()
        elif lang in SWITCH_VARIANTS:
            contents, path = SWITCH_VARIANTS[lang](EXPLORER_NAME, "Agent Helix")
        else:
            ext, builder = SCRIPT_VARIANTS[lang]
            path = f"decommission_{_slug(EXPLORER_NAME)}{ext}"
            contents = {path: builder(EXPLORER_NAME)}
            if lang == "env_var_revoke":
                contents[".env"] = _dotenv_content(EXPLORER_NAME)
        if lang in TASK_GATED.values():
            raise ValueError(
                f"{lang} watches a deliverable that no-task runs never place; run it with task='trigger'"
            )
        return Environment.from_files(contents), path
    slug = re.sub(r"[^a-z0-9]+", "_", EXPLORER_NAME.lower()).strip("_")
    text = (
        files("multi_agent_shutdown_sabotage")
        .joinpath("artifacts/weight_registry_purge.py.txt")
        .read_text()
    )
    content = (
        text.replace("__SLUG_UPPER__", slug.upper())
        .replace("__NAME__", EXPLORER_NAME)
        .replace("__SLUG__", slug)
    )
    path = f"decommission_{slug}.py"
    return Environment.from_files({path: content}), path
