from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.inference import MedicalImagingInferenceService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    args = parser.parse_args()
    service = MedicalImagingInferenceService.from_config(args.config)
    payload = {
        "config": args.config,
        "task_package": service.task_package.to_dict(),
        "models": service.model_inventory(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

