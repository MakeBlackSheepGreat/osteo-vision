"""Run the documentation audit with the project interpreter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from run_project_mypy import _project_interpreter


def main() -> int:
    try:
        interpreter = _project_interpreter()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"documentation audit environment error: {exc}", file=sys.stderr)
        return 2
    audit = Path(__file__).with_name("audit_active_documentation.py")
    return subprocess.run([str(interpreter), str(audit)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
