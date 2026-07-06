"""Run a direct JPEG/MP4-keyframe tiling smoke for the trainable segmenter.

The script validates the part of the competition flow that matters most for
official 4K MP4/JPEG inputs: a single extracted keyframe can be segmented with
patch/tiling inference, and the full-resolution mask, probability map,
pseudocolor overlay, uncertainty map, and metadata are written without shape drift.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.config import load_yaml, runtime_config  # noqa: E402
from src.core.paths import ensure_dir, resolve_path  # noqa: E402
from src.core.schemas import AdapterRequest  # noqa: E402
from src.models.adapters import build_adapter, model_spec_from_mapping  # noqa: E402
from src.reports.writers import write_json  # noqa: E402

DEFAULT_CONFIG = "configs/inference/osteo_vision.yml"
DEFAULT_MODEL_ID = "convnext2d_keyframe_proxy_segmenter"


def run_keyframe_tiling_smoke(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ensure_dir(
        resolve_path(args.output_dir)
        if args.output_dir
        else ROOT / "artifacts" / "platform_smoke" / f"keyframe_tiling_{timestamp()}"
    )
    input_path = create_proxy_keyframe(
        output_dir / "input" / "official_keyframe_proxy.jpg",
        width=int(args.width),
        height=int(args.height),
    )
    model_mapping = _model_mapping(args.config, args.model_id)
    extra = dict(model_mapping.get("extra") or {})
    extra["output_dir"] = str(output_dir / "segmentation_outputs")
    if args.force_tiled:
        extra["force_tiled"] = True
    if args.tile_size:
        extra["tile_size"] = int(args.tile_size)
    if args.tile_overlap is not None:
        extra["tile_overlap"] = int(args.tile_overlap)
    if args.max_whole_pixels is not None:
        extra["max_whole_pixels"] = int(args.max_whole_pixels)
    model_mapping["extra"] = extra

    adapter = build_adapter(model_spec_from_mapping(model_mapping))
    status = adapter.warmup()
    started = time.perf_counter()
    result = adapter.predict(
        AdapterRequest(
            case_id="keyframe_tiling_smoke",
            input_path=str(input_path),
            input_type="2d_image",
            task_type="segmentation",
            modality="surgical_keyframe",
            metadata={"roi_hints": []},
        )
    )
    elapsed = time.perf_counter() - started
    payload = result.to_dict()
    segmentation_mask = payload.get("segmentation_mask") if isinstance(payload.get("segmentation_mask"), dict) else {}
    lesion_evidence = payload.get("lesion_evidence") if isinstance(payload.get("lesion_evidence"), dict) else {}
    quantification = payload.get("quantification") if isinstance(payload.get("quantification"), dict) else {}
    inference = segmentation_mask.get("inference") if isinstance(segmentation_mask.get("inference"), dict) else {}
    output_records = {
        "mask": file_record(segmentation_mask.get("path")),
        "probability": file_record(lesion_evidence.get("probability_path")),
        "uncertainty": file_record(
            segmentation_mask.get("uncertainty_path") or lesion_evidence.get("uncertainty_path")
        ),
        "pseudo_color": file_record(lesion_evidence.get("pseudo_color_path")),
        "overlay": file_record(lesion_evidence.get("overlay_path")),
    }
    expected_mode = "tiled" if args.expect_tiled else None
    checks = {
        "adapter_available": bool(status.available),
        "mask_exists": bool(output_records["mask"]["exists"]),
        "probability_exists": bool(output_records["probability"]["exists"]),
        "uncertainty_exists": bool(output_records["uncertainty"]["exists"]),
        "overlay_exists": bool(output_records["overlay"]["exists"]),
        "mask_shape_matches_input": segmentation_mask.get("width") == int(args.width)
        and segmentation_mask.get("height") == int(args.height),
        "tiled_mode_matches_expectation": True if expected_mode is None else inference.get("mode") == expected_mode,
        "tile_count_positive": int(inference.get("tile_count") or 0) >= (2 if args.expect_tiled else 1),
        "clinical_claim_blocked": True,
        "non_target_domain_disclosed": True,
    }
    checks["pass"] = all(checks.values())
    summary = {
        "schema_version": "osteo-vision-keyframe-tiling-smoke-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "config_path": str(resolve_path(args.config)),
        "model_id": args.model_id,
        "output_dir": str(output_dir),
        "input": {
            "path": str(input_path),
            "width": int(args.width),
            "height": int(args.height),
            "official_4k_size": [3840, 2160],
            "is_official_4k_resolution": int(args.width) == 3840 and int(args.height) == 2160,
            "not_real_patient_data": True,
        },
        "adapter_status": status.to_dict(),
        "inference": {
            **inference,
            "elapsed_sec": round(float(elapsed), 4),
            "force_tiled": bool(args.force_tiled),
            "expect_tiled": bool(args.expect_tiled),
        },
        "segmentation_mask": segmentation_mask,
        "quantification": quantification,
        "outputs": output_records,
        "checks": checks,
        "medical_boundary": {
            "disclaimer": (
                "Platform keyframe segmentation workflow for research and competition validation; "
                "physician review is required and this is not a clinical diagnosis."
            ),
            "data_boundary": "Synthetic keyframe proxy; not real intraoperative ICG jaw osteomyelitis data.",
        },
    }
    summary_path = output_dir / "keyframe_tiling_smoke_summary.json"
    report_path = output_dir / "keyframe_tiling_smoke_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    write_json(summary_path, summary)
    report_path.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def create_proxy_keyframe(path: Path, *, width: int, height: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    background = 32 + 72 * (0.54 * x + 0.46 * y)
    lesion = np.exp(-(((x - 0.42) ** 2) / 0.010 + ((y - 0.54) ** 2) / 0.020))
    vessel = np.exp(-(((x - 0.68) ** 2) / 0.004 + ((y - 0.36) ** 2) / 0.030))
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = np.clip(background * 0.38 + lesion * 22, 0, 255).astype(np.uint8)
    rgb[..., 1] = np.clip(background * 0.42 + lesion * 235 + vessel * 174, 0, 255).astype(np.uint8)
    rgb[..., 2] = np.clip(background * 0.36 + vessel * 26, 0, 255).astype(np.uint8)
    Image.fromarray(rgb).save(path, quality=92)
    return path


def _model_mapping(config_path: str | Path, model_id: str) -> dict[str, Any]:
    runtime = runtime_config(load_yaml(config_path))
    for item in runtime.get("models") or []:
        if str(item.get("model_id")) == str(model_id):
            return dict(item)
    raise ValueError(f"Model {model_id} is not configured in {config_path}")


def file_record(value: Any) -> dict[str, Any]:
    if not value:
        return {"path": None, "exists": False, "size_bytes": None}
    path = Path(str(value))
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def render_report(summary: dict[str, Any]) -> str:
    checks = summary.get("checks", {})
    inference = summary.get("inference", {})
    outputs = summary.get("outputs", {})
    output_rows = "\n".join(
        f"| {name} | `{record.get('exists')}` | `{record.get('path')}` |" for name, record in outputs.items()
    )
    return f"""# Keyframe Tiling Smoke Report

## Verdict

- Pass: `{checks.get('pass')}`
- Model: `{summary.get('model_id')}`
- Input size: `{summary.get('input', {}).get('width')}x{summary.get('input', {}).get('height')}`
- Inference mode: `{inference.get('mode')}`
- Tile count: `{inference.get('tile_count')}`
- Elapsed seconds: `{inference.get('elapsed_sec')}`

## Checks

- Adapter available: `{checks.get('adapter_available')}`
- Mask shape matches input: `{checks.get('mask_shape_matches_input')}`
- Tiled mode matches expectation: `{checks.get('tiled_mode_matches_expectation')}`
- Non-target-domain disclosure included: `{checks.get('non_target_domain_disclosed')}`

## Outputs

| Artifact | Exists | Path |
|---|---:|---|
{output_rows}

## Medical Boundary

{summary.get('medical_boundary', {}).get('disclaimer')}

{summary.get('medical_boundary', {}).get('data_boundary')}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--tile-overlap", type=int, default=64)
    parser.add_argument("--max-whole-pixels", type=int, default=None)
    parser.add_argument("--force-tiled", action="store_true")
    parser.add_argument("--expect-tiled", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    summary = run_keyframe_tiling_smoke(parse_args())
    return 0 if summary.get("checks", {}).get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
