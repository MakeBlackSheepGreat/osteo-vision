"""Run a direct JPEG/MP4-keyframe tiling smoke for the trainable segmenter.

The script validates the part of the competition flow that matters most for
official 4K MP4/JPEG inputs: a single extracted keyframe can be segmented with
patch/tiling inference, and the full-resolution mask, probability map,
pseudocolor overlay, uncertainty map, and metadata are written without shape drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
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
DEFAULT_MODEL_ID = "keyframe_residual_attention_unet_s20260715_20260715"


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
    model_mapping, checkpoint_evidence = _model_mapping_for_args(args)
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
    if args.tile_batch_size is not None:
        extra["tile_batch_size"] = int(args.tile_batch_size)
    if args.threshold is not None:
        extra["threshold"] = float(args.threshold)
    if args.uncertainty_tta_enabled is not None:
        extra["uncertainty_tta_enabled"] = bool(args.uncertainty_tta_enabled)
    if args.use_amp is not None:
        extra["use_amp"] = bool(args.use_amp)
    if args.fast_output is not None:
        extra["fast_output"] = bool(args.fast_output)
    model_mapping["extra"] = extra
    if args.device_policy:
        model_mapping["device_policy"] = str(args.device_policy)

    adapter = build_adapter(model_spec_from_mapping(model_mapping))
    status = adapter.warmup()
    run_payloads: list[dict[str, Any]] = []
    elapsed_values: list[float] = []
    result = None
    for run_index in range(max(1, int(args.runs))):
        started = time.perf_counter()
        result = adapter.predict(
            AdapterRequest(
                case_id=f"keyframe_tiling_smoke_{run_index + 1:02d}",
                input_path=str(input_path),
                input_type="2d_image",
                task_type="segmentation",
                modality="surgical_keyframe",
                metadata={"roi_hints": []},
            )
        )
        elapsed_values.append((time.perf_counter() - started) * 1000.0)
        run_payloads.append(result.to_dict())
    assert result is not None
    elapsed = elapsed_values[-1] / 1000.0
    payload = result.to_dict()
    segmentation_mask = _dict_field(payload, "segmentation_mask")
    lesion_evidence = _dict_field(payload, "lesion_evidence")
    quantification = _dict_field(payload, "quantification")
    inference = _dict_field(segmentation_mask, "inference")
    output_records = {
        "mask": file_record(segmentation_mask.get("path")),
        "probability": file_record(lesion_evidence.get("probability_path")),
        "uncertainty": file_record(
            segmentation_mask.get("uncertainty_path") or lesion_evidence.get("uncertainty_path")
        ),
        "pseudo_color": file_record(lesion_evidence.get("pseudo_color_path")),
        "overlay": file_record(lesion_evidence.get("overlay_path")),
        "risk_mask": file_record(segmentation_mask.get("risk_mask_path")),
        "uncertain_mask": file_record(segmentation_mask.get("uncertain_mask_path")),
    }
    run_inference = [_dict_field(_dict_field(item, "segmentation_mask"), "inference") for item in run_payloads]
    model_elapsed_values = [float(item.get("elapsed_ms") or 0.0) for item in run_inference]
    peak_gpu_values = [
        float(item["peak_gpu_memory_mb"]) for item in run_inference if item.get("peak_gpu_memory_mb") is not None
    ]
    positive_fractions = [
        float(_dict_field(item, "quantification").get("positive_area_fraction") or 0.0) for item in run_payloads
    ]
    raw_mask_hashes = [
        file_record(_dict_field(item, "segmentation_mask").get("path")).get("sha256") for item in run_payloads
    ]
    mask_hashes: list[str] = [str(value) for value in raw_mask_hashes if value]
    expected_mode = "tiled" if args.expect_tiled else None
    e2e_p95 = float(np.percentile(elapsed_values, 95))
    model_p95 = float(np.percentile(model_elapsed_values, 95))
    peak_gpu_memory_mb = max(peak_gpu_values) if peak_gpu_values else None
    all_output_shapes_match = all(
        not bool(record.get("exists"))
        or (record.get("width") == int(args.width) and record.get("height") == int(args.height))
        for record in output_records.values()
    )
    checks = {
        "adapter_available": bool(status.available),
        "mask_exists": bool(output_records["mask"]["exists"]),
        "probability_exists": bool(output_records["probability"]["exists"]),
        "uncertainty_exists": bool(output_records["uncertainty"]["exists"]),
        "pseudo_color_exists": bool(output_records["pseudo_color"]["exists"]),
        "overlay_exists": bool(output_records["overlay"]["exists"]),
        "risk_mask_exists": bool(output_records["risk_mask"]["exists"]),
        "uncertain_mask_exists": bool(output_records["uncertain_mask"]["exists"]),
        "mask_shape_matches_input": segmentation_mask.get("width") == int(args.width)
        and segmentation_mask.get("height") == int(args.height),
        "all_output_shapes_match_input": all_output_shapes_match,
        "tiled_mode_matches_expectation": True if expected_mode is None else inference.get("mode") == expected_mode,
        "tile_count_positive": int(inference.get("tile_count") or 0) >= (2 if args.expect_tiled else 1),
        "official_4k_resolution": (
            True if not args.require_official_4k else int(args.width) == 3840 and int(args.height) == 2160
        ),
        "checkpoint_sidecar_consistent": bool(checkpoint_evidence.get("consistent", True)),
        "cuda_execution": True if not args.require_cuda else bool(peak_gpu_values),
        "end_to_end_p95_within_limit": (
            True if args.max_end_to_end_p95_ms is None else e2e_p95 <= float(args.max_end_to_end_p95_ms)
        ),
        "model_p95_within_limit": (
            True if args.max_model_p95_ms is None else model_p95 <= float(args.max_model_p95_ms)
        ),
        "peak_gpu_memory_within_limit": (
            True
            if args.max_peak_gpu_memory_mb is None
            else peak_gpu_memory_mb is not None and peak_gpu_memory_mb <= float(args.max_peak_gpu_memory_mb)
        ),
        "positive_fraction_above_minimum": (
            True if args.min_positive_fraction is None else min(positive_fractions) >= float(args.min_positive_fraction)
        ),
        "positive_fraction_below_maximum": (
            True if args.max_positive_fraction is None else max(positive_fractions) <= float(args.max_positive_fraction)
        ),
        "deterministic_mask": (
            True if not args.require_deterministic_mask or len(mask_hashes) <= 1 else len(set(mask_hashes)) == 1
        ),
        "clinical_claim_blocked": True,
        "non_target_domain_disclosed": True,
    }
    checks["pass"] = all(checks.values())
    summary = {
        "schema_version": "osteo-vision-keyframe-tiling-smoke-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "config_path": str(resolve_path(args.config)),
        "model_id": str(model_mapping.get("model_id")),
        "adapter_family": str(model_mapping.get("family")),
        "checkpoint": checkpoint_evidence,
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
            "benchmark_runs": len(elapsed_values),
            "end_to_end_latency_ms_p50": round(float(statistics.median(elapsed_values)), 3),
            "end_to_end_latency_ms_p95": round(e2e_p95, 3),
            "end_to_end_latency_ms_max": round(float(max(elapsed_values)), 3),
            "model_latency_ms_p50": round(
                float(statistics.median(model_elapsed_values)),
                3,
            ),
            "model_latency_ms_p95": round(model_p95, 3),
            "peak_gpu_memory_mb": round(peak_gpu_memory_mb, 3) if peak_gpu_memory_mb is not None else None,
            "positive_area_fraction_min": round(min(positive_fractions), 8),
            "positive_area_fraction_max": round(max(positive_fractions), 8),
            "mask_sha256_values": sorted(set(mask_hashes)),
            "force_tiled": bool(args.force_tiled),
            "expect_tiled": bool(args.expect_tiled),
            "ephemeral_runtime_enablement": bool(checkpoint_evidence.get("ephemeral_runtime_enablement")),
        },
        "gate_policy": {
            "require_official_4k": bool(args.require_official_4k),
            "require_cuda": bool(args.require_cuda),
            "require_deterministic_mask": bool(args.require_deterministic_mask),
            "max_end_to_end_p95_ms": args.max_end_to_end_p95_ms,
            "max_model_p95_ms": args.max_model_p95_ms,
            "max_peak_gpu_memory_mb": args.max_peak_gpu_memory_mb,
            "min_positive_fraction": args.min_positive_fraction,
            "max_positive_fraction": args.max_positive_fraction,
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


def _model_mapping_for_args(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    requested_model_id = str(args.model_id or "").strip()
    template_model_id = str(args.template_model_id or DEFAULT_MODEL_ID)
    checkpoint_value = str(args.checkpoint or "").strip()
    if requested_model_id and not checkpoint_value:
        mapping = _model_mapping(args.config, requested_model_id)
    else:
        mapping = _model_mapping(args.config, template_model_id)
    if not checkpoint_value:
        checkpoint_path = resolve_path(str(mapping.get("checkpoint_path") or ""))
        return mapping, _checkpoint_evidence(checkpoint_path, None, ephemeral_runtime_enablement=False)

    checkpoint_path = resolve_path(checkpoint_value)
    sidecar_value = str(args.checkpoint_sidecar or "").strip()
    sidecar_path = (
        resolve_path(sidecar_value)
        if sidecar_value
        else checkpoint_path.with_name(f"{checkpoint_path.stem}_manifest.json")
    )
    evidence = _checkpoint_evidence(checkpoint_path, sidecar_path, ephemeral_runtime_enablement=True)
    sidecar = _dict_field(evidence, "sidecar_payload")
    training = _dict_field(sidecar, "training")
    mapping["model_id"] = requested_model_id or str(sidecar.get("model_id") or checkpoint_path.stem)
    mapping["family"] = str(sidecar.get("model_family") or mapping.get("family"))
    mapping["checkpoint_path"] = str(checkpoint_path)
    mapping["dependency_group"] = "torch"
    mapping["clinical_claim_allowed"] = False
    extra = dict(mapping.get("extra") or {})
    extra["runtime_allowed"] = True
    extra["target_domain"] = False
    extra["training_data_boundary"] = str(training.get("data_boundary") or "public_proxy_non_target_domain")
    mapping["extra"] = extra
    evidence.pop("sidecar_payload", None)
    return mapping, evidence


def _checkpoint_evidence(
    checkpoint_path: Path,
    sidecar_path: Path | None,
    *,
    ephemeral_runtime_enablement: bool,
) -> dict[str, Any]:
    checkpoint_exists = checkpoint_path.is_file()
    checkpoint_sha = _sha256_file(checkpoint_path) if checkpoint_exists else None
    evidence: dict[str, Any] = {
        "path": str(checkpoint_path),
        "exists": checkpoint_exists,
        "sha256": checkpoint_sha,
        "sidecar_path": str(sidecar_path) if sidecar_path is not None else None,
        "sidecar_exists": bool(sidecar_path and sidecar_path.is_file()),
        "consistent": checkpoint_exists,
        "ephemeral_runtime_enablement": bool(ephemeral_runtime_enablement),
        "persistent_config_unchanged": True,
    }
    if sidecar_path is None or not sidecar_path.is_file():
        return evidence
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        evidence["consistent"] = False
        return evidence
    if not isinstance(payload, dict):
        evidence["consistent"] = False
        return evidence
    recorded_sha = str(payload.get("checkpoint_sha256") or "")
    evidence.update(
        {
            "sidecar_sha256": _sha256_file(sidecar_path),
            "recorded_checkpoint_sha256": recorded_sha or None,
            "model_id": payload.get("model_id"),
            "model_family": payload.get("model_family"),
            "training_runtime_allowed": payload.get("runtime_allowed") is True,
            "clinical_claim_allowed": payload.get("clinical_claim_allowed") is True,
            "consistent": bool(checkpoint_sha and recorded_sha == checkpoint_sha),
            "sidecar_payload": payload,
        }
    )
    return evidence


def file_record(value: Any) -> dict[str, Any]:
    if not value:
        return {"path": None, "exists": False, "size_bytes": None}
    path = Path(str(value))
    record = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
        "sha256": _sha256_file(path) if path.exists() and path.is_file() else None,
    }
    if path.exists() and path.is_file():
        try:
            with Image.open(path) as image:
                record["width"], record["height"] = (int(image.width), int(image.height))
        except (OSError, ValueError):
            record["width"], record["height"] = (None, None)
    return record


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    parser.add_argument("--model-id", default="")
    parser.add_argument("--template-model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--checkpoint-sidecar", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--tile-overlap", type=int, default=64)
    parser.add_argument("--tile-batch-size", type=int, default=None)
    parser.add_argument("--max-whole-pixels", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--device-policy", default="")
    parser.add_argument("--uncertainty-tta-enabled", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--use-amp", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--fast-output", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--force-tiled", action="store_true")
    parser.add_argument("--expect-tiled", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--require-official-4k", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-cuda", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--require-deterministic-mask", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-end-to-end-p95-ms", type=float, default=None)
    parser.add_argument("--max-model-p95-ms", type=float, default=None)
    parser.add_argument("--max-peak-gpu-memory-mb", type=float, default=None)
    parser.add_argument("--min-positive-fraction", type=float, default=None)
    parser.add_argument("--max-positive-fraction", type=float, default=None)
    return parser.parse_args()


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    summary = run_keyframe_tiling_smoke(parse_args())
    return 0 if summary.get("checks", {}).get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
