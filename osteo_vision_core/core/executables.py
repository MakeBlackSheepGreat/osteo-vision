from __future__ import annotations

import shutil
import sys
from pathlib import Path


def find_runtime_executable(name: str) -> str | None:
    executable = shutil.which(name)
    if executable:
        return executable
    environment_root = Path(sys.executable).resolve().parent
    suffixes = (".exe", "") if sys.platform == "win32" else ("",)
    search_roots = (environment_root, environment_root / "Scripts", environment_root / "Library" / "bin")
    for root in search_roots:
        for suffix in suffixes:
            candidate = root / f"{name}{suffix}"
            if candidate.is_file():
                return str(candidate)
    return None
