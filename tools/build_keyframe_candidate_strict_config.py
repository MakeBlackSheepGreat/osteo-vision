from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_candidate_strict_config(
    *,
    production_config_path: str | Path,
    checkpoint_path: str | Path,
    runtime_sidecar_path: str | Path,
    output_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    production_path = Path(production_config_path).resolve()
    checkpoint = Path(checkpoint_path).resolve()
    sidecar_path = Path(runtime_sidecar_path).resolve()
    destination = Path(output_path).resolve()
    production_bytes = production_path.read_bytes()
    production = _load_yaml(production_path)
    sidecar = _load_json(sidecar_path)
    checkpoint_sha = _sha256_file(checkpoint)
    if str(sidecar.get("checkpoint_sha256") or "") != checkpoint_sha:
        raise ValueError("Runtime promotion sidecar checkpoint SHA256 does not match the candidate checkpoint")
    if sidecar.get("runtime_allowed") is not True:
        raise ValueError("Runtime promotion sidecar must explicitly allow candidate runtime execution")
    if sidecar.get("clinical_claim_allowed") is not False:
        raise ValueError("Candidate runtime config requires clinical_claim_allowed=false")
    model_id = str(sidecar.get("model_id") or "").strip()
    model_family = str(sidecar.get("model_family") or "").strip()
    threshold = sidecar.get("threshold")
    if not model_id or not model_family or threshold is None:
        raise ValueError("Runtime promotion sidecar is missing model identity or threshold")

    candidate = copy.deepcopy(production)
    runtime = _mapping(candidate.get("runtime"))
    runtime["model_version"] = f"{model_id}-strict-competition-flow-gate-v1"
    runtime["required_model_ids"] = [model_id]
    runtime["models"] = [
        {
            "model_id": model_id,
            "family": model_family,
            "task_types": ["segmentation"],
            "input_types": ["2d_image"],
            "spatial_dims": [2],
            "checkpoint_path": str(checkpoint),
            "source_url": "local://keyframe-candidate-strict-runtime-gate",
            "license": "internal",
            "dependency_group": "torch",
            "device_policy": "cuda",
            "precision": "fp32",
            "enabled": True,
            "intended_use": "Strict competition-flow gate for a non-target-domain keyframe signal candidate",
            "clinical_claim_allowed": False,
            "extra": {
                "runtime_allowed": True,
                "runtime_sidecar_path": str(sidecar_path),
                "checkpoint_model_id": model_id,
                "threshold": float(threshold),
                "output_dir": str(Path(output_dir).resolve() / "candidate_keyframe_masks"),
                "input_domain": "public_or_synthetic_proxy_keyframe_non_target_domain",
                "training_data_boundary": sidecar.get("data_boundary")
                or "public_proxy_non_target_domain_with_physician_review_required",
                "target_domain": False,
                "tile_size": 512,
                "tile_overlap": 64,
                "tile_batch_size": 4,
                "max_whole_pixels": 1048576,
                "uncertainty_tta_enabled": False,
                "fast_output": False,
                "use_amp": False,
                "live_stream": {
                    "uncertainty_tta_enabled": False,
                    "max_whole_pixels": 1048576,
                    "tile_batch_size": 8,
                    "fast_output": True,
                    "overlay_format": "jpeg",
                    "overlay_jpeg_quality": 82,
                    "use_amp": True,
                },
            },
        }
    ]
    tasks = _mapping(runtime.get("tasks"))
    segmentation = _mapping(tasks.get("segmentation"))
    segmentation["pipeline"] = "segmentation"
    segmentation["model_id"] = model_id
    tasks["segmentation"] = segmentation
    runtime["tasks"] = tasks
    runtime["candidate_gate"] = {
        "production_config_path": str(production_path),
        "production_config_sha256": _sha256_bytes(production_bytes),
        "automatic_replacement_performed": False,
        "competition_runtime_selected": False,
    }
    candidate["runtime"] = runtime

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    if production_path.read_bytes() != production_bytes:
        raise RuntimeError("Production competition config changed while building the isolated candidate config")
    return {
        "schema_version": "osteo-vision-keyframe-candidate-strict-config-v1",
        "output_path": str(destination),
        "output_sha256": _sha256_file(destination),
        "production_config_path": str(production_path),
        "production_config_sha256": _sha256_bytes(production_bytes),
        "production_config_unchanged": True,
        "candidate_model_id": model_id,
        "candidate_model_family": model_family,
        "threshold": float(threshold),
        "required_model_ids": runtime["required_model_ids"],
        "segmentation_task": dict(segmentation),
        "automatic_replacement_performed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an isolated strict config for a promoted keyframe candidate.")
    parser.add_argument("--production-config", default="configs/inference/osteo_vision_competition_strict.yml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--runtime-sidecar", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--summary-json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_candidate_strict_config(
        production_config_path=args.production_config,
        checkpoint_path=args.checkpoint,
        runtime_sidecar_path=args.runtime_sidecar,
        output_path=args.output,
        output_dir=args.output_dir,
    )
    if args.summary_json:
        summary_path = Path(args.summary_json).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
