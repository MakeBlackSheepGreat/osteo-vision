from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path


CORE_IMPORTS = ["yaml", "numpy"]
OPTIONAL_IMPORTS = ["gradio", "PIL", "sklearn"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    warnings: list[str] = []
    for name in CORE_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            failures.append(f"{name}: {exc}")
    for name in OPTIONAL_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            (failures if args.strict else warnings).append(f"{name}: {exc}")
    for path in ["configs/inference/osteo_vision.yml", "artifacts/reports", "artifacts/visual_evidence"]:
        if not Path(path).exists():
            failures.append(f"missing {path}")
    try:
        Path("AGENTS.md").read_text(encoding="utf-8")
    except Exception as exc:
        failures.append(f"utf8 read failed: {exc}")
    report = {"python": sys.version.split()[0], "failures": failures, "warnings": warnings}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

