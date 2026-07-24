from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osteo_vision_core.engine.benchmark import evaluate_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/runs")
    args = parser.parse_args()
    report = evaluate_manifest(args.config, args.manifest, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
