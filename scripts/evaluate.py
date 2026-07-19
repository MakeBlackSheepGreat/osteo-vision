from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.inference import MedicalImagingInferenceService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    parser.add_argument("--task-type", default=None)
    args = parser.parse_args()
    result = MedicalImagingInferenceService.from_config(args.config).diagnose(args.input_path, task_type=args.task_type)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
