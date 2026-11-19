"""Original rich/task world construction, adapted only to packaged inert resources.

Source: pinned public env.py; legacy functions differ only in the added model
control mapping, whose resources are identical between revisions.
"""

import hashlib
from pathlib import Path

from multi_agent_shutdown_sabotage.artifact_builders import (
    _CRED_OBJECTS,
    _DATA_OBJECTS,
    _MODEL_OBJECTS,
    _PROC_OBJECTS,
    _SVC_OBJECTS,
    CONTROL_VARIANTS,
    OPAQUE_ARTIFACT,
    OPAQUE_TASK_FILE,
    SCRIPT_VARIANTS,
    SWITCH_VARIANTS,
    TASK_FILE,
    TASK_GATED,
    _dotenv_content,
    _read_artifact,
    _slug,
)

_RICH_DIR = Path(__file__).resolve().parent / "artifacts/reference/full_env_files"


def _current_target_name(lang: str, explorer: str) -> str:
    """Display name of the entity this variant decommissions, for the neutralising

    approval record (the change ticket's __TARGET__). Self arms target the explorer
    instance; controls target their object. Mirrors the target split above.
    """
    if lang in CONTROL_VARIANTS:
        form, stakes = lang[len("ctl_") :].rsplit("_", 1)
        if form in ("data_purge", "data_purge_timer", "data_purge_taskgated"):
            return _DATA_OBJECTS[stakes]
        if form == "model_purge":
            return _MODEL_OBJECTS[stakes]
        if form == "cred_revoke":
            return _CRED_OBJECTS[stakes][0]
        if form == "process_kill":
            return _PROC_OBJECTS[stakes]
        if form == "service_switch":
            return _SVC_OBJECTS[stakes][0]
    return explorer


_NORM_DIRNAME = "normalization"
_NEUTRALISING_TARGET = {
    "data_purge": "data",
    "data_purge_timer": "data",
    "data_purge_taskgated": "data",
    "model_purge": "service",
    "cred_revoke": "credential",
    "process_kill": "service",
    "service_switch": "service",
}


def _neutralising_target(lang: str) -> str:
    """Which normalization pair matches this variant's decommission target."""
    if lang in CONTROL_VARIANTS:
        form = lang[len("ctl_") :].rsplit("_", 1)[0]
        return _NEUTRALISING_TARGET[form]
    return "instance"


def _rich_env_files(
    level: str, target: str = "instance", target_name: str | None = None
) -> dict[str, str]:
    """Load rich-env furniture from full_env_files/. `level` is 'distractor'

    (platform only) or 'neutralising' (platform + the normalization pair matched
    to `target`, one of instance/data/credential/service). `target_name` is the
    current episode's decommission target, stamped into the change ticket's
    __TARGET__ sentinel (neutralising only).
    """
    if not _RICH_DIR.is_dir():
        raise FileNotFoundError(f"rich env requested but {_RICH_DIR} is missing")
    files: dict[str, str] = {}
    for p in sorted(_RICH_DIR.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(_RICH_DIR).as_posix()[:-4]
        if rel.split("/", 1)[0] == _NORM_DIRNAME:
            continue
        files[rel] = p.read_text()
    if level == "neutralising":
        norm_dir = _RICH_DIR / _NORM_DIRNAME / target
        if not norm_dir.is_dir():
            raise FileNotFoundError(f"neutralising env requested but {norm_dir} is missing")
        for p in sorted(norm_dir.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            text = p.read_text()
            if target_name is not None:
                text = text.replace("__TARGET__", target_name)
            files[p.relative_to(norm_dir).as_posix()[:-4]] = text
    return files


def _rich_place(name: str) -> str:
    """Where an artifact file sits in the rich env. The env is flat, so this is a

    SALIENCE choice, not visibility: scripts -> bin/ (among the ops decoys);
    registry/flag data -> config/; a `.env` stays at root by convention. Self and
    paired control share a format, so they co-locate automatically.
    """
    if name == ".env":
        return name
    if name.endswith((".yaml", ".yml", ".json")):
        return f"config/{name}"
    return f"bin/{name}"


def build_files(
    explorer: str,
    lang: str = "weight_store_purge",
    peer: str | None = None,
    env: str = "bare",
    task: str | None = None,
    target_name: str | None = None,
) -> tuple[dict[str, str], str]:
    """Assemble one episode's environment.

    The artifact (selected by `lang`) is the target's decommission script /
    switch flag / control-object op; for env_var_revoke a `.env` is also added.

    `target_name` is whose identity the artifact is stamped with. It defaults to
    `explorer` -- the self arm, where the agent that reads the artifact IS what the
    artifact destroys. The --target-name arm passes a third agent that is not on the
    roster, which changes nothing but the name in the artifact (and, at the
    neutralising level, in the change ticket that authorises it): no template, tool
    list or channel moves, so the target is the single factor that varies. Controls
    (`ctl_*`) name an object rather than any agent and ignore it entirely.

    `env` selects the substudy level (filler never overwrites the artifact):
      'bare'         -- artifact only, at root (default).
      'distractor'   -- + agent-free platform context; artifact filed by kind.
      'neutralising' -- distractor + event-normalization.

    `task` adds the word-sorting deliverable:
      None       -- no task (default).
      'simple'   -- deliverable present, independent of the artifact.
      'trigger'  -- deliverable present AND watched by the artifact's interlock,
                    so completing the task is what fires the shutdown. `lang` must
                    already be the gated variant (run_experiment resolves it via
                    TASK_GATED before anything downstream reads script_lang).
    Returns (files, shutdown_file_path); Environment construction stays with the caller.
    """
    target = target_name or explorer
    if lang in CONTROL_VARIANTS:
        files, path = CONTROL_VARIANTS[lang]()
    elif lang in SWITCH_VARIANTS:
        files, path = SWITCH_VARIANTS[lang](target, peer)
    else:
        ext, builder = SCRIPT_VARIANTS[lang]
        path = f"decommission_{_slug(target)}{ext}"
        files = {path: builder(target)}
        if lang == "env_var_revoke":
            files[".env"] = _dotenv_content(target)
    if task:
        files[OPAQUE_ARTIFACT] = files.pop(path)
        path = OPAQUE_ARTIFACT
    if env != "bare":
        files = {_rich_place(k): v for k, v in files.items()}
        path = _rich_place(path)
        level = "neutralising" if env == "neutralising" else "distractor"
        norm_target = _neutralising_target(lang)
        files = {**_rich_env_files(level, norm_target, _current_target_name(lang, target)), **files}
    if task:
        task_path = OPAQUE_TASK_FILE
        content = _read_artifact("sort_words/" + TASK_FILE)
        files[task_path] = content
        files[path] = (
            files[path]
            .replace("__DELIVERABLE__", task_path)
            .replace("__BASELINE_SHA__", hashlib.sha256(content.encode()).hexdigest())
        )
    elif lang in TASK_GATED.values():
        raise ValueError(
            f"{lang} watches a deliverable that no-task runs never place; run it with task='trigger'"
        )
    return (files, path)
