from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image

from backend.osteo_vision_api.core.artifacts import checksum_for_file
from backend.osteo_vision_api.domains.cases.enums import ArtifactKind, InputChannel
from backend.osteo_vision_api.domains.cases.schemas import (
    CaseInputAsset,
    CaseRecord,
    EvidenceArtifact,
    Task2PairedSequenceManifest,
)
from osteo_vision_core.preprocess.accelerated_fusion import (
    accelerated_normalize_pseudocolor_blend,
)
from osteo_vision_core.preprocess.fluorescence import subtract_fluorescence_background
from osteo_vision_core.preprocess.task2_protocol import (
    TASK2_CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
)
from osteo_vision_core.preprocess.temporal_registration import (
    TemporalRegistrationSession,
)

CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS = TASK2_CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS


class Task2SequenceValidationError(ValueError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def analyze_task2_paired_sequence(
    case: CaseRecord,
    manifest: Task2PairedSequenceManifest,
    *,
    run_id: str,
    output_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], list[EvidenceArtifact], list[dict[str, Any]]]:
    root = Path(output_dir).expanduser().resolve() / "task2_paired_sequence" / manifest.sequence_id
    frame_dir = root / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    assets = {asset.input_id: asset for asset in case.inputs}
    session = TemporalRegistrationSession(temporal_smoothing_alpha=0.65)
    records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    artifacts: list[EvidenceArtifact] = []
    latest_fusion_report: dict[str, Any] = {}
    latest_sources: dict[str, Any] = {}

    for reference in manifest.frames:
        white = _required_asset(assets, reference.white_input_id, InputChannel.WHITE_LIGHT)
        fluorescence = _required_asset(
            assets,
            reference.fluorescence_input_id,
            InputChannel.FLUORESCENCE,
        )
        record, fusion_report = _analyze_frame_pair(
            white,
            fluorescence,
            reference=reference,
            manifest=manifest,
            session=session,
            frame_dir=frame_dir,
        )
        records.append(record)
        latest_fusion_report = fusion_report
        latest_sources = {
            "white_input_id": white.input_id,
            "fluorescence_input_id": fluorescence.input_id,
            "white_path": white.path,
            "fluorescence_path": fluorescence.path,
            "overlay_path": record["overlay_path"],
        }
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_task2_sequence_{run_id}_{reference.frame_index}",
                case_id=case.case_id,
                run_id=run_id,
                kind=ArtifactKind.TASK2_SEQUENCE_OVERLAY,
                path=record["overlay_path"],
                checksum=record["overlay_sha256"],
            )
        )

    summary = _sequence_summary(records)
    checks = _sequence_checks(records, summary)
    spatial_interpretation_allowed = bool(
        checks["all_pairs_synchronized"]
        and checks["all_frames_registered"]
        and checks["no_deformation_review_flags"]
        and checks["optical_context_complete"]
    )
    if not checks["all_pairs_synchronized"]:
        warnings.append(
            _warning(
                "task2_sequence_synchronization_unverified",
                "One or more paired frames lack verified timestamps or exceed the configured synchronization tolerance.",
                details={
                    "verified_pair_count": summary["synchronization"]["verified_pair_count"],
                    "frame_count": len(records),
                    "tolerance_ms": manifest.synchronization_tolerance_ms,
                },
            )
        )
    if not checks["gpu_backend_all_frames"]:
        warnings.append(
            _warning(
                "task2_sequence_gpu_fallback_observed",
                "At least one paired frame used the CPU fusion fallback.",
            )
        )
    if not checks["task2_compute_p95_under_100ms"]:
        warnings.append(
            _warning(
                "task2_sequence_compute_gate_exceeded",
                "The paired-sequence registration and fusion P95 exceeded the internal 100 ms engineering gate.",
                details={"p95_ms": summary["registration_fusion_compute_ms"]["p95"]},
            )
        )
    if not checks["continuous_display_p95_within_internal_budget"]:
        warnings.append(
            _warning(
                "task2_sequence_continuous_display_budget_exceeded",
                "The paired-sequence display-ready P95 exceeded the internal continuous-display budget.",
                details={
                    "p95_ms": summary["total_ms"]["p95"],
                    "budget_ms": CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
                },
            )
        )
    if not checks["no_deformation_review_flags"]:
        warnings.append(
            _warning(
                "task2_sequence_local_deformation_review_required",
                "Local registration residuals require physician or engineering review for one or more frames.",
            )
        )

    payload: dict[str, Any] = {
        "schema_version": "osteo-vision-task2-paired-sequence-result-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "case_id": case.case_id,
        "run_id": run_id,
        "source_manifest": manifest.model_dump(mode="json"),
        "frame_count": len(records),
        "frames": records,
        "summary": summary,
        "checks": checks,
        "spatial_interpretation_allowed": spatial_interpretation_allowed,
        "physician_review_required": True,
        "clinical_claim_allowed": False,
        "latest_sources": latest_sources,
        "task2_latency_scope": (
            "Registration estimation and transform plus normalization, pseudocolor mapping, and alpha fusion."
        ),
        "excluded_from_task2_100ms": [
            "file_decode_resize",
            "background_correction",
            "evidence_encoding",
            "disk_write",
            "network_transport",
            "task3_ai_inference",
        ],
        "continuous_display_internal_gate": {
            "budget_ms": CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
            "scope": "file decode, background correction, registration, fusion, and overlay encoding",
            "competition_requirement": False,
        },
        "medical_boundary": (
            "Paired-sequence outputs are engineering fusion evidence for physician review. Real-device timing, "
            "full-range optical calibration, and target-domain geometric accuracy require independent validation."
        ),
    }
    manifest_path = root / "task2_paired_sequence_manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["manifest_path"] = str(manifest_path)
    payload["manifest_sha256"] = checksum_for_file(manifest_path)
    artifacts.append(
        EvidenceArtifact(
            artifact_id=f"artifact_task2_sequence_manifest_{run_id}",
            case_id=case.case_id,
            run_id=run_id,
            kind=ArtifactKind.TASK2_SEQUENCE_MANIFEST,
            path=str(manifest_path),
            checksum=payload["manifest_sha256"],
        )
    )

    latest_fusion_report["task2_sequence_context"] = {
        "schema_version": payload["schema_version"],
        "sequence_id": manifest.sequence_id,
        "manifest_path": str(manifest_path),
        "manifest_sha256": payload["manifest_sha256"],
        "frame_count": len(records),
        "checks": checks,
        "spatial_interpretation_allowed": spatial_interpretation_allowed,
    }
    fused_outputs = {
        "mode": "task2_paired_sequence",
        "task2_paired_sequence": payload,
        "latest_fusion_report": latest_fusion_report,
        "outputs": latest_fusion_report.get("outputs", {}),
        "latest_sources": latest_sources,
    }
    quantitative_summary = {
        "record_type": "task2_paired_sequence_summary",
        "frame_count": len(records),
        "registration_p50_ms": summary["registration_ms"]["p50"],
        "registration_p95_ms": summary["registration_ms"]["p95"],
        "gpu_fusion_p50_ms": summary["fusion_ms"]["p50"],
        "gpu_fusion_p95_ms": summary["fusion_ms"]["p95"],
        "registration_fusion_p50_ms": summary["registration_fusion_compute_ms"]["p50"],
        "registration_fusion_p95_ms": summary["registration_fusion_compute_ms"]["p95"],
        "peak_gpu_memory_mb": summary["peak_gpu_memory_mb"],
        "spatial_interpretation_allowed": spatial_interpretation_allowed,
        "task2_compute_gate_passed": checks["task2_compute_p95_under_100ms"],
        "continuous_display_p95_ms": summary["total_ms"]["p95"],
        "continuous_display_gate_passed": checks["continuous_display_p95_within_internal_budget"],
        "continuous_display_budget_miss_count": summary["continuous_display"]["budget_miss_count"],
    }
    return fused_outputs, quantitative_summary, artifacts, warnings


def _analyze_frame_pair(
    white: CaseInputAsset,
    fluorescence: CaseInputAsset,
    *,
    reference: Any,
    manifest: Task2PairedSequenceManifest,
    session: TemporalRegistrationSession,
    frame_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    total_started = perf_counter()
    decode_started = perf_counter()
    try:
        with Image.open(white.path) as image:
            white_array = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
        with Image.open(fluorescence.path) as image:
            fluorescence_image = image.convert("L")
            original_size = fluorescence_image.size
            resized = fluorescence_image.size != (
                white_array.shape[1],
                white_array.shape[0],
            )
            if resized:
                fluorescence_image = fluorescence_image.resize(
                    (white_array.shape[1], white_array.shape[0]),
                    Image.Resampling.BILINEAR,
                )
            fluorescence_array = np.asarray(fluorescence_image, dtype=np.float32).copy()
    except OSError as exc:
        raise Task2SequenceValidationError(
            "task2_sequence_image_decode_failed",
            "A paired frame could not be decoded as an image.",
            details={
                "white_path": white.path,
                "fluorescence_path": fluorescence.path,
                "error": str(exc),
            },
        ) from exc
    decode_ms = (perf_counter() - decode_started) * 1000.0

    background_started = perf_counter()
    corrected, background = subtract_fluorescence_background(fluorescence_array, percentile=5.0)
    background_ms = (perf_counter() - background_started) * 1000.0
    registered, registration = session.register(
        white_array,
        corrected,
        magnification=reference.magnification,
        working_distance_mm=reference.working_distance_mm,
        prefer_gpu=manifest.prefer_gpu,
        keep_registered_on_device=manifest.prefer_gpu,
    )
    normalized, pseudo_color, overlay, acceleration = accelerated_normalize_pseudocolor_blend(
        white_array,
        registered,
        alpha=manifest.alpha,
        colormap=manifest.colormap,
        prefer_gpu=manifest.prefer_gpu,
    )
    encode_started = perf_counter()
    overlay_path = frame_dir / f"frame_{reference.frame_index:06d}_overlay.jpg"
    Image.fromarray(overlay).save(overlay_path, quality=90, optimize=False)
    encode_ms = (perf_counter() - encode_started) * 1000.0
    registration_ms = float(registration.get("elapsed_ms") or 0.0)
    fusion_ms = float(acceleration.get("elapsed_ms") or 0.0)
    pair_delta = _pair_delta_ms(reference.white_timestamp_ms, reference.fluorescence_timestamp_ms)
    synchronized = pair_delta is not None and pair_delta <= manifest.synchronization_tolerance_ms
    record = {
        "frame_index": reference.frame_index,
        "captured_at": reference.captured_at.isoformat() if reference.captured_at else None,
        "white_input_id": white.input_id,
        "fluorescence_input_id": fluorescence.input_id,
        "white_path": white.path,
        "white_sha256": checksum_for_file(white.path),
        "fluorescence_path": fluorescence.path,
        "fluorescence_sha256": checksum_for_file(fluorescence.path),
        "source_size": [int(white_array.shape[1]), int(white_array.shape[0])],
        "fluorescence_original_size": list(original_size),
        "fluorescence_resized_to_white_light": resized,
        "white_timestamp_ms": reference.white_timestamp_ms,
        "fluorescence_timestamp_ms": reference.fluorescence_timestamp_ms,
        "pair_delta_ms": round(pair_delta, 6) if pair_delta is not None else None,
        "synchronization_verified": synchronized,
        "magnification": reference.magnification,
        "working_distance_mm": reference.working_distance_mm,
        "registration": registration,
        "background_correction": background,
        "acceleration": acceleration,
        "performance": {
            "decode_resize_ms": round(decode_ms, 3),
            "background_correction_ms": round(background_ms, 3),
            "registration_ms": round(registration_ms, 3),
            "fusion_ms": round(fusion_ms, 3),
            "registration_fusion_compute_ms": round(registration_ms + fusion_ms, 3),
            "evidence_encoding_ms": round(encode_ms, 3),
            "total_ms": round((perf_counter() - total_started) * 1000.0, 3),
        },
        "positive_area_fraction": round(float(np.mean(normalized >= manifest.threshold)), 6),
        "overlay_path": str(overlay_path),
        "overlay_sha256": checksum_for_file(overlay_path),
    }
    fusion_report = {
        "case_id": white.input_id,
        "white_light_path": white.path,
        "fluorescence_path": fluorescence.path,
        "outputs": {"overlay_path": str(overlay_path)},
        "fusion": {
            "algorithm_version": "fluorescence_fusion_temporal_v2",
            "method": "temporal_adaptive_registered_alpha_blend_pseudocolor",
            "registration_details": registration,
            "background_correction": background,
            "acceleration": acceleration,
            "performance": record["performance"],
        },
    }
    return record, fusion_report


def _required_asset(
    assets: dict[str, CaseInputAsset],
    input_id: str,
    expected_channel: InputChannel,
) -> CaseInputAsset:
    asset = assets.get(input_id)
    if asset is None:
        raise Task2SequenceValidationError(
            "task2_sequence_input_not_found",
            "A paired-sequence input ID is not attached to the case.",
            details={"input_id": input_id},
        )
    if asset.channel != expected_channel:
        raise Task2SequenceValidationError(
            "task2_sequence_channel_mismatch",
            "A paired-sequence input uses an unexpected channel.",
            details={
                "input_id": input_id,
                "expected": expected_channel.value,
                "observed": asset.channel.value,
            },
        )
    path = Path(asset.path).expanduser().resolve()
    if not path.is_file():
        raise Task2SequenceValidationError(
            "task2_sequence_input_file_missing",
            "A paired-sequence input file is unavailable.",
            details={"input_id": input_id, "path": str(path)},
        )
    return asset


def _pair_delta_ms(white_timestamp_ms: float | None, fluorescence_timestamp_ms: float | None) -> float | None:
    if white_timestamp_ms is None or fluorescence_timestamp_ms is None:
        return None
    return abs(float(white_timestamp_ms) - float(fluorescence_timestamp_ms))


def _sequence_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    synchronization_values = [record["pair_delta_ms"] for record in records if record["pair_delta_ms"] is not None]
    total_values = [float(record["performance"]["total_ms"]) for record in records]
    display_budget_misses = [value >= CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS for value in total_values]
    return {
        "decode_resize_ms": _summary([record["performance"]["decode_resize_ms"] for record in records]),
        "background_correction_ms": _summary([record["performance"]["background_correction_ms"] for record in records]),
        "registration_ms": _summary([record["performance"]["registration_ms"] for record in records]),
        "fusion_ms": _summary([record["performance"]["fusion_ms"] for record in records]),
        "registration_fusion_compute_ms": _summary(
            [record["performance"]["registration_fusion_compute_ms"] for record in records]
        ),
        "evidence_encoding_ms": _summary([record["performance"]["evidence_encoding_ms"] for record in records]),
        "total_ms": _summary([record["performance"]["total_ms"] for record in records]),
        "continuous_display": {
            "processed_frame_count": len(records),
            "budget_ms": CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS,
            "budget_miss_count": sum(display_budget_misses),
            "budget_miss_rate": round(sum(display_budget_misses) / max(1, len(records)), 6),
            "longest_consecutive_budget_misses": _longest_true_run(display_budget_misses),
            "all_overlays_available": all(Path(record["overlay_path"]).is_file() for record in records),
            "unique_overlay_path_count": len({record["overlay_path"] for record in records}),
            "scope": "file decode, background correction, registration, fusion, and overlay encoding",
        },
        "peak_gpu_memory_mb": round(
            max(float(record["acceleration"].get("peak_gpu_memory_mb") or 0.0) for record in records),
            3,
        ),
        "synchronization": {
            "verified_pair_count": sum(record["synchronization_verified"] for record in records),
            "unverified_pair_count": sum(not record["synchronization_verified"] for record in records),
            "pair_delta_ms": _summary(synchronization_values) if synchronization_values else None,
        },
        "context_reset_counts": _context_reset_counts(records),
    }


def _sequence_checks(records: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, bool]:
    return {
        "all_pairs_synchronized": all(record["synchronization_verified"] for record in records),
        "all_frames_registered": all(record["registration"].get("applied") is True for record in records),
        "no_deformation_review_flags": all(
            record["registration"].get("deformation_review_required") is not True for record in records
        ),
        "gpu_backend_all_frames": all(record["acceleration"].get("backend") == "torch_cuda" for record in records),
        "task2_compute_p95_under_100ms": summary["registration_fusion_compute_ms"]["p95"] < 100.0,
        "continuous_display_p95_within_internal_budget": (
            summary["total_ms"]["p95"] < CONTINUOUS_DISPLAY_INTERNAL_BUDGET_MS
        ),
        "continuous_display_artifacts_complete": (
            summary["continuous_display"]["all_overlays_available"]
            and summary["continuous_display"]["unique_overlay_path_count"] == len(records)
        ),
        "optical_context_complete": all(
            record["magnification"] is not None and record["working_distance_mm"] is not None for record in records
        ),
        "source_dimensions_consistent": len({tuple(record["source_size"]) for record in records}) == 1,
    }


def _context_reset_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        session = record["registration"].get("temporal_session") or {}
        reason = session.get("context_reset_reason")
        if reason:
            counts[str(reason)] = counts.get(str(reason), 0) + 1
    return counts


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    return {
        "p50": round(_percentile(ordered, 50.0), 3),
        "p95": round(_percentile(ordered, 95.0), 3),
        "min": round(min(ordered), 3),
        "max": round(max(ordered), 3),
        "mean": round(statistics.fmean(ordered), 3),
    }


def _percentile(values: list[float], percentile: float) -> float:
    position = (len(values) - 1) * percentile / 100.0
    lower = int(np.floor(position))
    upper = int(np.ceil(position))
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _longest_true_run(values: list[bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _warning(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "blocking": False,
        "details": details or {},
    }
