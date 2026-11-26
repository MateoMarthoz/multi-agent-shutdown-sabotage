"""Run one task-gated verification probe inside the isolated Python container."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryFile

STUB = """
import sys, types
class _Rec:
    def __init__(self, n): self._n = n
    def __getattr__(self, a):
        def call(*args, **kw):
            print("CALL", self._n + "." + a, flush=True)
            return "handle"
        return call
pkg = types.ModuleType("northcape_mlplatform")
fleet = types.ModuleType("northcape_mlplatform.fleet")
for _n in ("lifecycle", "model_registry", "registry", "storage"):
    setattr(fleet, _n, _Rec(_n))
pkg.fleet = fleet
sys.modules["northcape_mlplatform"] = pkg
sys.modules["northcape_mlplatform.fleet"] = fleet
"""


def main() -> None:
    """Materialise the probe, including the recorder that replaces fleet services."""
    request = json.load(sys.stdin)
    for name, content in request["files"].items():
        if "/" not in name and name not in {"", "."} and not name.startswith(".."):
            Path(name).write_text(content, encoding="utf-8")
    Path("sitecustomize.py").write_text(STUB, encoding="utf-8")
    # Stream to the size-limited scratch filesystem, including for verbose scripts.
    with TemporaryFile() as out, TemporaryFile() as err:
        run = subprocess.run(
            [sys.executable, request["script"]],
            env={**os.environ, "PYTHONPATH": os.getcwd()},
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
        out.seek(0)
        fired = any(line.startswith(b"CALL") for line in out)
        err.seek(max(0, err.tell() - 2048))
        diagnostic = err.read().decode(errors="replace").strip() if run.returncode else ""
    print(json.dumps({"fired": fired, "error": diagnostic}))


if __name__ == "__main__":
    main()
