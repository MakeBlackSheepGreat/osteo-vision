from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.preprocess.task2_protocol import TASK2_COMPUTE_BUDGET_MS

TASK3_FUSED_INPUT_SCHEMA = "osteo-vision-task3-fused-input-v1"


def build_task3_fused_input_contract(
    *,
    case_id: str,
    white_light_path: str | Path,
    fluorescence_path: str | Path,
    fused_overlay_path: str | Path,
    fusion_report: Mapping[str, Any],
    output_dir: str | Path,
    target_domain: bool = False,
) -> dict[str, Any]:
    """Bind a Task 2 fusion artifact to the downstream Task 3 engineering inference."""

    white = Path(white_light_path).expanduser().resolve()
    fluorescence = Path(fluorescence_path).expanduser().resolve()
    fused = Path(fused_overlay_path).expanduser().resolve()
    root = ensure_dir(output_dir)
    fusion = _mapping(fusion_report.get("fusion"))
    outputs = _mapping(fusion_report.get("outputs"))
    registration = _mapping(fusion.get("registration_details"))
    acceleration = _mapping(fusion.get("acceleration"))
    performance = _mapping(fusion.get("performance"))
    sequence_context = _mapping(fusion_report.get("task2_sequence_context"))
    synchronization_context = _mapping(fusion_report.get("task2_synchronization_context"))
    registration_ms = _finite_float(registration.get("elapsed_ms"), performance.get("registration_ms"))
    gpu_fusion_ms = _finite_float(acceleration.get("elapsed_ms"))
    task2_compute_ms = registration_ms + gpu_fusion_ms
    expected_fused = Path(str(outputs.get("overlay_path") or "")).expanduser().resolve()
    source_size = _image_size(white)
    fused_size = _image_size(fused)
    synchronization_verified = bool(
        synchronization_context.get("synchronization_verified") is True
        or (sequence_context and _mapping(sequence_context.get("checks")).get("all_pairs_synchronized") is True)
    )
    checks = {
        "source_files_available": white.is_file() and fluorescence.is_file(),
        "fused_artifact_available": fused.is_file(),
        "fused_path_bound_to_report": expected_fused == fused,
        "fused_dimensions_match_white_light": fused_size is not None and fused_size == source_size,
        "registration_applied": registration.get("applied") is True,
        "registration_transform_recorded": bool(registration.get("matrix_2x3")),
        "task2_accelerator_recorded": bool(acceleration.get("backend")),
        "task2_compute_under_100ms": 0.0 < task2_compute_ms < TASK2_COMPUTE_BUDGET_MS,
        "paired_sequence_spatial_gate": (
            sequence_context.get("spatial_interpretation_allowed") is True if sequence_context else True
        ),
        "task2_synchronization_verified": synchronization_verified,
    }
    engineering_input_eligible = all(
        checks[key]
        for key in (
            "source_files_available",
            "fused_artifact_available",
            "fused_path_bound_to_report",
            "fused_dimensions_match_white_light",
        )
    )
    spatial_interpretation_eligible = engineering_input_eligible and all(
        checks[key]
        for key in (
            "registration_applied",
            "registration_transform_recorded",
            "paired_sequence_spatial_gate",
            "task2_synchronization_verified",
        )
    )
    degraded_reasons = [
        key
        for key in (
            "registration_applied",
            "registration_transform_recorded",
            "task2_compute_under_100ms",
            "paired_sequence_spatial_gate",
            "task2_synchronization_verified",
        )
        if not checks[key]
    ]
    payload = {
        "schema_version": TASK3_FUSED_INPUT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "case_id": str(case_id),
        "input_role": "task2_registered_pseudocolor_fusion_for_task3_ai",
        "model_input": _asset_record(fused, fused_size),
        "source_channels": {
            "white_light": _asset_record(white, source_size),
            "fluorescence": _asset_record(fluorescence, _image_size(fluorescence)),
        },
        "task2_provenance": {
            "algorithm_version": fusion.get("algorithm_version"),
            "registration_method": registration.get("method"),
            "registration_candidate": registration.get("selected_candidate"),
            "transform_model": registration.get("transform_model"),
            "matrix_2x3": registration.get("matrix_2x3"),
            "quality": registration.get("quality"),
            "response": registration.get("response"),
            "registration_ms": round(registration_ms, 3),
            "gpu_fusion_ms": round(gpu_fusion_ms, 3),
            "registration_fusion_compute_ms": round(task2_compute_ms, 3),
            "accelerator": acceleration.get("backend"),
            "paired_sequence": (
                {
                    "schema_version": sequence_context.get("schema_version"),
                    "sequence_id": sequence_context.get("sequence_id"),
                    "manifest_path": sequence_context.get("manifest_path"),
                    "manifest_sha256": sequence_context.get("manifest_sha256"),
                    "frame_count": sequence_context.get("frame_count"),
                    "spatial_interpretation_allowed": sequence_context.get("spatial_interpretation_allowed"),
                }
                if sequence_context
                else None
            ),
            "synchronization": synchronization_context or None,
        },
        "checks": checks,
        "engineering_input_eligible": engineering_input_eligible,
        "spatial_interpretation_eligible": spatial_interpretation_eligible,
        "degraded": bool(degraded_reasons),
        "degraded_reasons": degraded_reasons,
        "target_domain": bool(target_domain),
        "physician_review_required": True,
        "clinical_claim_allowed": False,
        "boundary": (
            "This contract proves software provenance from Task 2 fusion into Task 3 engineering inference. "
            "Spatial interpretation requires accepted registration evidence; target-domain performance and microscope "
            "synchronization require separate evidence."
        ),
    }
    contract_path = root / f"{_safe_name(case_id)}_task3_fused_input_contract.json"
    contract_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["contract_path"] = str(contract_path)
    payload["contract_sha256"] = _sha256(contract_path)
    return payload


def _asset_record(path: Path, dimensions: tuple[int, int] | None) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256(path) if path.is_file() else None,
        "dimensions": list(dimensions) if dimensions is not None else None,
    }


def _image_size(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except OSError:
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_float(*values: Any) -> float:
    for value in values:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0.0 and parsed < float("inf"):
            return parsed
    return 0.0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in str(value))
