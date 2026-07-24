from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from osteo_vision_core.core.config import load_yaml, runtime_config  # noqa: E402
from osteo_vision_core.core.paths import resolve_path  # noqa: E402
from osteo_vision_core.engine.inference import MedicalImagingInferenceService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    config_path = resolve_path(args.config).resolve()
    runtime = runtime_config(load_yaml(config_path))
    service = MedicalImagingInferenceService.from_config(args.config)
    models = sorted(
        service.model_inventory(),
        key=lambda row: str((row.get("spec") or {}).get("model_id") or ""),
    )
    payload = {
        "schema_version": "osteo-vision-runtime-model-inventory-v1",
        "config": _portable_path(config_path),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "runtime_profile": runtime.get("runtime_profile") or "development",
        "strict_startup": bool(runtime.get("strict_startup")),
        "task_package": service.task_package.to_dict(),
        "models": models,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def _portable_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
