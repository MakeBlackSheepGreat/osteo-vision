"""Run mypy with the project interpreter even when pre-commit uses a base Python."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path


def _candidate_interpreters() -> Iterable[Path]:
    executable_name = "python.exe" if os.name == "nt" else "bin/python"
    explicit = os.environ.get("OSTEO_PYTHON")
    if explicit:
        yield Path(explicit)
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        yield Path(conda_prefix) / executable_name
    home = Path.home()
    for prefix in (
        home / ".conda" / "envs" / "osteo-vision",
        home / "miniconda3" / "envs" / "osteo-vision",
        home / "anaconda3" / "envs" / "osteo-vision",
    ):
        yield prefix / executable_name
    yield Path(sys.executable)
    for command in ("python", "python3"):
        resolved = shutil.which(command)
        if resolved:
            yield Path(resolved)


def _has_mypy(interpreter: Path) -> bool:
    if not interpreter.is_file():
        return False
    try:
        probe = subprocess.run(
            [str(interpreter), "-c", "import mypy"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def _project_interpreter() -> Path:
    seen: set[str] = set()
    for candidate in _candidate_interpreters():
        resolved = candidate.expanduser().resolve(strict=False)
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        if _has_mypy(resolved):
            return resolved
    raise RuntimeError(
        "No Python interpreter with mypy was found. Activate the osteo-vision Conda environment "
        "or set OSTEO_PYTHON to its Python executable."
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        interpreter = _project_interpreter()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"mypy environment error: {exc}", file=sys.stderr)
        return 2
    return subprocess.run([str(interpreter), "-m", "mypy", *arguments], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
