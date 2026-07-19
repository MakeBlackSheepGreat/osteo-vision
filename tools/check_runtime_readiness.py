from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.runtime_preflight import check_runtime_readiness  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate runtime profile, checkpoints, sidecars, and fallback policy."
    )
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--require-strict",
        action="store_true",
        help="Fail unless the selected config is the fail-closed competition profile.",
    )
    args = parser.parse_args()
    report = check_runtime_readiness(args.config, require_strict=args.require_strict)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
