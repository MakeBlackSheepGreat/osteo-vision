"""Active-review queue construction for video keyframe evidence.

The service consumes existing frame-details or video-segmentation manifests,
ranks frames that offer high review value, and exports a review-state-preserving
training patch after human decisions are supplied.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

REVIEW_STATES = {"accepted", "modified", "rejected", "review_required"}
STATE_WEIGHTS = {
    "accepted": 4.0,
    "modified": 4.0,
    "rejected": 0.5,
    "review_required": 1.0,
}

REVIEW_QUEUE_FIELDS = [
    "queue_rank",
    "review_id",
    "case_id",
    "run_id",
    "source_video_path",
    "source_manifest_path",
    "source_record_id",
    "source_group_id",
    "source_url",
    "license",
    "usage_policy",
    "sampling_weight",
    "source_training_eligible",
    "image_checksum",
    "frame_key",
    "frame_order",
    "frame_index",
    "timestamp_sec",
    "image_path",
    "overlay_path",
    "mask_path",
    "probability_path",
    "uncertainty_path",
    "risk_mask_path",
    "uncertain_mask_path",
    "bone_gate_mask_path",
    "input_domain",
    "target_domain_flag",
    "positive_area_fraction",
    "uncertainty_score",
    "temporal_instability_score",
    "area_anomaly_score",
    "domain_gap_score",
    "failure_score",
    "review_value_score",
    "review_reasons",
    "failure_reason",
    "review_priority",
    "review_state",
    "sample_weight",
    "modified_mask_path",
    "review_notes",
    "medical_boundary",
]

TRAINING_PATCH_FIELDS = [
    "review_id",
    "case_id",
    "source_video_path",
    "source_record_id",
    "source_group_id",
    "source_url",
    "image_path",
    "mask_path",
    "license",
    "usage_policy",
    "sampling_weight",
    "image_checksum",
    "label_checksum",
    "frame_index",
    "timestamp_sec",
    "input_domain",
    "review_state",
    "sample_weight",
    "label_source",
    "training_action",
    "eligible_for_weighted_training",
    "training_eligible",
    "source_review_queue_path",
    "review_notes",
    "medical_boundary",
]

MEDICAL_BOUNDARY = (
    "Active-review ranking supports physician annotation and engineering validation. "
    "Proxy and non-target-domain rows retain their source boundary."
)


@dataclass(frozen=True)
class ActiveReviewConfig:
    max_frames: int = 40
    max_frames_per_source: int = 12
    min_interval_sec: float = 2.0
    uncertainty_weight: float = 0.35
    temporal_weight: float = 0.25
    area_weight: float = 0.20
    domain_weight: float = 0.10
    failure_weight: float = 0.10


def build_active_review_queue(
    manifest_paths: Iterable[str | Path],
    *,
    config: ActiveReviewConfig | None = None,
    review_updates: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Load, score, deduplicate, and select keyframes for focused review."""

    settings = config or ActiveReviewConfig()
    candidates: list[dict[str, Any]] = []
    input_paths: list[str] = []
    load_failures: list[dict[str, str]] = []
    for raw_path in manifest_paths:
        path = Path(raw_path).expanduser().resolve()
        input_paths.append(str(path))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            candidates.extend(_manifest_candidates(payload, manifest_path=path, config=settings))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            load_failures.append({"manifest_path": str(path), "reason": str(exc)})

    deduplicated = _deduplicate_candidates(candidates)
    selected, interval_rejected = _select_with_spacing(deduplicated, config=settings)
    updates = _review_update_map(review_updates or [])
    selected = [_apply_review_update(row, updates.get(str(row["review_id"]))) for row in selected]
    for rank, row in enumerate(selected, start=1):
        row["queue_rank"] = rank

    return {
        "schema_version": "osteo-vision-video-active-review-queue-v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_manifest_paths": input_paths,
        "selection_config": {
            "max_frames": settings.max_frames,
            "max_frames_per_source": settings.max_frames_per_source,
            "min_interval_sec": settings.min_interval_sec,
            "score_weights": {
                "uncertainty": settings.uncertainty_weight,
                "temporal_instability": settings.temporal_weight,
                "mask_area_anomaly": settings.area_weight,
                "domain_gap": settings.domain_weight,
                "failure": settings.failure_weight,
            },
        },
        "summary": {
            "input_candidate_count": len(candidates),
            "deduplicated_candidate_count": len(deduplicated),
            "duplicate_count": len(candidates) - len(deduplicated),
            "interval_or_quota_rejected_count": interval_rejected,
            "selected_count": len(selected),
            "source_count": len({str(row.get("source_video_path") or "") for row in selected}),
            "review_state_counts": _value_counts(selected, "review_state"),
            "reason_counts": _reason_counts(selected),
            "load_failure_count": len(load_failures),
        },
        "load_failures": load_failures,
        "review_contract": {
            "allowed_states": sorted(REVIEW_STATES),
            "sample_weights": STATE_WEIGHTS,
            "modified_mask_requirement": "modified rows require modified_mask_path before training promotion",
            "rejected_handling": "negative candidate or error-analysis record",
        },
        "medical_boundary": MEDICAL_BOUNDARY,
        "rows": selected,
    }


def build_training_manifest_patch(
    queue_payload: dict[str, Any],
    *,
    source_review_queue_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create a training-manifest patch from completed review decisions."""

    queue_rows = queue_payload.get("rows")
    rows = queue_rows if isinstance(queue_rows, list) else []
    patch_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        state = _normalize_state(item.get("review_state"))
        if state == "review_required":
            skipped.append({"review_id": item.get("review_id"), "reason": "review_pending"})
            continue
        mask_path = item.get("modified_mask_path") if state == "modified" else item.get("mask_path")
        if state in {"accepted", "modified"} and not mask_path:
            skipped.append({"review_id": item.get("review_id"), "reason": "reviewed_mask_missing"})
            continue
        artifact_evidence: dict[str, Any] = {
            "image_path": str(item.get("image_path") or ""),
            "mask_path": str(mask_path or ""),
            "image_checksum": "",
            "label_checksum": "",
        }
        if state in {"accepted", "modified"}:
            artifact_evidence, reason = _validated_training_artifacts(item, mask_path)
            if reason:
                skipped.append({"review_id": item.get("review_id"), "reason": reason})
                continue
        else:
            image_path = _resolve_artifact_path(item.get("image_path"), item=item)
            if image_path is not None and image_path.is_file():
                artifact_evidence["image_path"] = str(image_path)
                artifact_evidence["image_checksum"] = _sha256_file(image_path)
        source_training_eligible = _explicit_true(item.get("source_training_eligible"))
        training_eligible = state in {"accepted", "modified"} and source_training_eligible
        training_action = "negative_or_error_analysis" if state == "rejected" else "weighted_positive_proxy"
        if state in {"accepted", "modified"} and not training_eligible:
            training_action = "reviewed_not_training_approved"
        patch_rows.append(
            {
                "review_id": item.get("review_id"),
                "case_id": item.get("case_id"),
                "source_video_path": item.get("source_video_path"),
                "source_record_id": item.get("source_record_id") or "",
                "source_group_id": item.get("source_group_id") or "",
                "source_url": item.get("source_url") or "",
                "image_path": artifact_evidence["image_path"],
                "mask_path": artifact_evidence["mask_path"],
                "license": item.get("license") or "",
                "usage_policy": item.get("usage_policy") or "",
                "sampling_weight": _nonnegative_float(item.get("sampling_weight"), default=1.0),
                "image_checksum": artifact_evidence["image_checksum"],
                "label_checksum": artifact_evidence["label_checksum"],
                "frame_index": item.get("frame_index"),
                "timestamp_sec": item.get("timestamp_sec"),
                "input_domain": item.get("input_domain"),
                "review_state": state,
                "sample_weight": STATE_WEIGHTS[state],
                "label_source": f"active_review_{state}_video_signal_mask",
                "training_action": training_action,
                "eligible_for_weighted_training": training_eligible,
                "training_eligible": training_eligible,
                "source_review_queue_path": str(source_review_queue_path or ""),
                "review_notes": item.get("review_notes") or "",
                "medical_boundary": MEDICAL_BOUNDARY,
            }
        )
    return {
        "schema_version": "osteo-vision-video-active-review-training-patch-v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_review_queue_path": str(source_review_queue_path or ""),
        "summary": {
            "patch_row_count": len(patch_rows),
            "skipped_count": len(skipped),
            "review_state_counts": _value_counts(patch_rows, "review_state"),
            "training_action_counts": _value_counts(patch_rows, "training_action"),
            "training_eligible_counts": _value_counts(patch_rows, "training_eligible"),
        },
        "skipped": skipped,
        "medical_boundary": MEDICAL_BOUNDARY,
        "rows": patch_rows,
    }


def load_review_updates(path: str | Path) -> list[dict[str, Any]]:
    update_path = Path(path).expanduser().resolve()
    if update_path.suffix.lower() == ".json":
        payload = json.loads(update_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        rows = payload.get("rows") if isinstance(payload, dict) else None
        return [item for item in (rows or []) if isinstance(item, dict)]
    if update_path.suffix.lower() == ".csv":
        import csv

        with update_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"Unsupported review update extension: {update_path.suffix}")


def _manifest_candidates(
    payload: dict[str, Any],
    *,
    manifest_path: Path,
    config: ActiveReviewConfig,
) -> list[dict[str, Any]]:
    frames = payload.get("frames")
    if not isinstance(frames, list):
        raise ValueError("Manifest does not contain a frames list")
    case_id = str(payload.get("case_id") or _case_id_from_path(manifest_path))
    run_id = str(payload.get("run_id") or _run_id_from_path(manifest_path))
    source_video_path = str(payload.get("source_path") or "")
    source_metadata = {
        "source_record_id": payload.get("source_record_id") or payload.get("record_id") or "",
        "source_group_id": payload.get("source_group_id") or source_video_path or case_id,
        "source_url": payload.get("source_url") or payload.get("source_page_original_link") or "",
        "license": payload.get("license") or "",
        "usage_policy": payload.get("usage_policy") or "",
        "sampling_weight": payload.get("sampling_weight"),
        "source_training_eligible": payload.get("training_eligible"),
        "image_checksum": payload.get("image_checksum") or payload.get("checksum") or "",
    }
    output: list[dict[str, Any]] = []
    for position, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        output.append(
            _score_frame(
                frame,
                case_id=case_id,
                run_id=run_id,
                source_video_path=source_video_path,
                manifest_path=manifest_path,
                source_metadata=source_metadata,
                position=position,
                config=config,
            )
        )
    return output


def _score_frame(
    frame: dict[str, Any],
    *,
    case_id: str,
    run_id: str,
    source_video_path: str,
    manifest_path: Path,
    source_metadata: dict[str, Any],
    position: int,
    config: ActiveReviewConfig,
) -> dict[str, Any]:
    segmentation = _mapping(frame.get("segmentation_result"))
    routing = _mapping(frame.get("review_routing"))
    candidate = _mapping(frame.get("candidate_result"))
    temporal = _mapping(frame.get("temporal_stability"))
    signal_masks = _mapping(frame.get("video_signal_segmentation") or frame.get("signal_masks"))
    risk_summary = _mapping(_mapping(signal_masks.get("risk_mask")).get("summary"))
    bone_gate = _mapping(signal_masks.get("bone_gate_mask"))
    uncertainty = _mapping(segmentation.get("uncertainty"))

    area_fraction = _first_float(
        segmentation.get("positive_area_fraction"),
        frame.get("positive_area_fraction"),
        temporal.get("positive_area_fraction"),
    )
    uncertainty_score = _clamp01(
        max(
            _first_float(uncertainty.get("mean_uncertainty")),
            _first_float(uncertainty.get("high_uncertainty_fraction")),
            _first_float(risk_summary.get("uncertain_area_fraction")),
            _first_float(frame.get("uncertainty_score")),
        )
    )
    temporal_raw = max(
        _first_float(temporal.get("instability_score")),
        _first_float(temporal.get("positive_area_fraction_delta_previous")),
        _first_float(temporal.get("bbox_center_shift_previous_fraction")),
    )
    temporal_score = _clamp01(temporal_raw / 0.10)
    if temporal.get("flicker_warning"):
        temporal_score = max(temporal_score, 0.8)
    area_score = _area_anomaly_score(area_fraction)
    target_domain = bool(routing.get("target_domain_flag", frame.get("target_domain_flag", False)))
    input_domain = str(routing.get("input_domain") or frame.get("input_domain") or "unknown")
    domain_gap = _domain_gap_score(target_domain=target_domain, input_domain=input_domain)
    failure_reason = str(
        routing.get("failure_reason") or segmentation.get("failure_reason") or frame.get("failure_reason") or ""
    )
    failure_score = 1.0 if failure_reason else 0.0
    review_priority = str(
        candidate.get("review_priority") or routing.get("review_priority") or frame.get("review_priority") or "low"
    )
    priority_bonus = {"high": 0.05, "medium": 0.025}.get(review_priority.lower(), 0.0)
    review_score = min(
        1.0,
        uncertainty_score * config.uncertainty_weight
        + temporal_score * config.temporal_weight
        + area_score * config.area_weight
        + domain_gap * config.domain_weight
        + failure_score * config.failure_weight
        + priority_bonus,
    )

    reasons: list[str] = []
    if uncertainty_score >= 0.5:
        reasons.append("high_uncertainty")
    if temporal_score >= 0.5:
        reasons.append("temporal_jump")
    if area_score >= 0.5:
        reasons.append("mask_area_anomaly")
    if domain_gap > 0:
        reasons.append("domain_gap")
    if failure_reason:
        reasons.append("inference_failure_or_fallback")
    bone_gate_status = str(bone_gate.get("status") or "")
    if bone_gate_status in {"not_available_pending_review", "review_required"}:
        reasons.append("bone_gate_review_pending")
    if not reasons:
        reasons.append("diversity_review_sample")

    frame_index = frame.get("frame_index")
    timestamp_sec = _first_float(frame.get("timestamp_sec"))
    frame_key = str(frame.get("frame_key") or f"{frame_index}-{position}")
    review_id = _review_id(case_id, run_id, source_video_path, frame_index, frame_key)
    mask_path = segmentation.get("mask_path") or frame.get("mask_path")
    source_record_id = str(frame.get("source_record_id") or source_metadata.get("source_record_id") or "")
    source_group_id = str(
        frame.get("source_group_id")
        or source_metadata.get("source_group_id")
        or source_record_id
        or source_video_path
        or case_id
    )
    return {
        "review_id": review_id,
        "case_id": case_id,
        "run_id": run_id,
        "source_video_path": source_video_path,
        "source_manifest_path": str(manifest_path),
        "source_record_id": source_record_id,
        "source_group_id": source_group_id,
        "source_url": str(
            frame.get("source_url") or frame.get("source_page_original_link") or source_metadata.get("source_url") or ""
        ),
        "license": str(frame.get("license") or source_metadata.get("license") or ""),
        "usage_policy": str(frame.get("usage_policy") or source_metadata.get("usage_policy") or ""),
        "sampling_weight": _nonnegative_float(
            frame.get("sampling_weight"),
            default=_nonnegative_float(source_metadata.get("sampling_weight"), default=1.0),
        ),
        "source_training_eligible": _explicit_true(
            frame.get("training_eligible")
            if "training_eligible" in frame
            else source_metadata.get("source_training_eligible")
        ),
        "image_checksum": str(
            frame.get("image_checksum") or frame.get("checksum") or source_metadata.get("image_checksum") or ""
        ).lower(),
        "frame_key": frame_key,
        "frame_order": frame.get("frame_order"),
        "frame_index": frame_index,
        "timestamp_sec": timestamp_sec,
        "image_path": frame.get("evidence_path") or frame.get("source_path") or frame.get("preview_path"),
        "overlay_path": _mapping(frame.get("fluorescence_overlay_result")).get("overlay_path")
        or frame.get("overlay_path"),
        "mask_path": mask_path,
        "probability_path": segmentation.get("probability_path") or frame.get("probability_path"),
        "uncertainty_path": segmentation.get("uncertainty_path") or frame.get("uncertainty_path"),
        "risk_mask_path": segmentation.get("risk_mask_path") or frame.get("risk_mask_path"),
        "uncertain_mask_path": segmentation.get("uncertain_mask_path") or frame.get("uncertain_mask_path"),
        "bone_gate_mask_path": bone_gate.get("path"),
        "input_domain": input_domain,
        "target_domain_flag": target_domain,
        "positive_area_fraction": round(area_fraction, 8),
        "uncertainty_score": round(uncertainty_score, 8),
        "temporal_instability_score": round(temporal_score, 8),
        "temporal_instability_raw": round(temporal_raw, 8),
        "area_anomaly_score": round(area_score, 8),
        "domain_gap_score": round(domain_gap, 8),
        "failure_score": failure_score,
        "review_value_score": round(review_score, 8),
        "review_reasons": reasons,
        "failure_reason": failure_reason,
        "review_priority": review_priority,
        "review_state": "review_required",
        "sample_weight": STATE_WEIGHTS["review_required"],
        "modified_mask_path": "",
        "review_notes": "",
        "medical_boundary": MEDICAL_BOUNDARY,
    }


def _deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        source = str(row.get("source_video_path") or row.get("case_id") or "unknown").lower()
        frame_token = str(row.get("frame_index"))
        if frame_token in {"", "None"}:
            frame_token = f"t:{float(row.get('timestamp_sec') or 0.0):.3f}"
        key = (source, frame_token)
        current = by_key.get(key)
        if current is None or float(row.get("review_value_score") or 0.0) > float(
            current.get("review_value_score") or 0.0
        ):
            by_key[key] = row
    return sorted(
        by_key.values(),
        key=lambda item: (
            -float(item.get("review_value_score") or 0.0),
            str(item.get("review_id")),
        ),
    )


def _select_with_spacing(rows: list[dict[str, Any]], *, config: ActiveReviewConfig) -> tuple[list[dict[str, Any]], int]:
    selected: list[dict[str, Any]] = []
    selected_times: dict[str, list[float]] = {}
    source_counts: dict[str, int] = {}
    rejected = 0
    for row in rows:
        if len(selected) >= max(0, config.max_frames):
            rejected += 1
            continue
        source = str(row.get("source_video_path") or row.get("case_id") or "unknown").lower()
        if source_counts.get(source, 0) >= max(1, config.max_frames_per_source):
            rejected += 1
            continue
        timestamp = _first_float(row.get("timestamp_sec"))
        prior_times = selected_times.setdefault(source, [])
        if prior_times and any(abs(timestamp - prior) < max(0.0, config.min_interval_sec) for prior in prior_times):
            rejected += 1
            continue
        selected.append(dict(row))
        prior_times.append(timestamp)
        source_counts[source] = source_counts.get(source, 0) + 1
    return selected, rejected


def _review_update_map(updates: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in updates:
        review_id = str(item.get("review_id") or "").strip()
        if review_id:
            output[review_id] = item
    return output


def _apply_review_update(row: dict[str, Any], update: dict[str, Any] | None) -> dict[str, Any]:
    if not update:
        return row
    state = _normalize_state(update.get("review_state"))
    merged = dict(row)
    merged["review_state"] = state
    merged["sample_weight"] = STATE_WEIGHTS[state]
    merged["modified_mask_path"] = str(update.get("modified_mask_path") or "")
    merged["review_notes"] = str(update.get("review_notes") or update.get("notes") or "")
    return merged


def _normalize_state(value: Any) -> str:
    state = str(value or "review_required").split(".")[-1].strip().lower()
    if state not in REVIEW_STATES:
        raise ValueError(f"Unsupported review state: {state}")
    return state


def _validated_training_artifacts(
    item: dict[str, Any],
    mask_value: Any,
) -> tuple[dict[str, Any], str]:
    image_path = _resolve_artifact_path(item.get("image_path"), item=item)
    if image_path is None or not image_path.is_file():
        return {}, "reviewed_image_missing"
    mask_path = _resolve_artifact_path(mask_value, item=item)
    if mask_path is None or not mask_path.is_file():
        return {}, "reviewed_mask_missing"
    image_size, image_reason = _read_image_size(image_path)
    if image_reason:
        return {}, image_reason
    mask_size, mask_reason = _read_mask_size(mask_path)
    if mask_reason:
        return {}, mask_reason
    if image_size != mask_size:
        return {}, "mask_image_size_mismatch"
    image_checksum = _sha256_file(image_path)
    expected_image_checksum = str(item.get("image_checksum") or "").strip().lower()
    if expected_image_checksum and expected_image_checksum != image_checksum:
        return {}, "image_checksum_mismatch"
    return {
        "image_path": str(image_path),
        "mask_path": str(mask_path),
        "image_checksum": image_checksum,
        "label_checksum": _sha256_file(mask_path),
    }, ""


def _resolve_artifact_path(value: Any, *, item: dict[str, Any]) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return path.resolve()
    manifest_value = str(item.get("source_manifest_path") or "").strip()
    if manifest_value:
        manifest_relative = Path(manifest_value).expanduser().resolve().parent / path
        if manifest_relative.exists():
            return manifest_relative.resolve()
    return path.resolve()


def _read_image_size(path: Path) -> tuple[tuple[int, int], str]:
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
    except (OSError, ValueError, UnidentifiedImageError):
        return (0, 0), "reviewed_image_unreadable"
    if width < 2 or height < 2:
        return (width, height), "reviewed_image_dimensions_invalid"
    return (width, height), ""


def _read_mask_size(path: Path) -> tuple[tuple[int, int], str]:
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            positive_bbox = image.convert("L").getbbox()
    except (OSError, ValueError, UnidentifiedImageError):
        return (0, 0), "reviewed_mask_unreadable"
    if width < 2 or height < 2:
        return (width, height), "reviewed_mask_dimensions_invalid"
    if positive_bbox is None:
        return (width, height), "reviewed_mask_empty"
    return (width, height), ""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _explicit_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _nonnegative_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if isfinite(parsed) and parsed >= 0 else float(default)


def _area_anomaly_score(area_fraction: float) -> float:
    value = _clamp01(area_fraction)
    if value <= 0.0001 or value >= 0.75:
        return 1.0
    if value <= 0.001 or value >= 0.45:
        return 0.8
    if value <= 0.005 or value >= 0.30:
        return 0.5
    return 0.0


def _domain_gap_score(*, target_domain: bool, input_domain: str) -> float:
    if target_domain:
        return 0.0
    normalized = input_domain.lower()
    if any(token in normalized for token in ("non_target", "proxy", "synthetic", "public")):
        return 1.0
    return 0.5


def _review_id(case_id: str, run_id: str, source_path: str, frame_index: Any, frame_key: str) -> str:
    raw = f"{case_id}|{run_id}|{source_path.lower()}|{frame_index}|{frame_key}"
    return f"review_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _case_id_from_path(path: Path) -> str:
    for part in path.parts:
        if part.startswith("case_"):
            return part
    return path.parent.name


def _run_id_from_path(path: Path) -> str:
    for part in path.parts:
        if part.startswith("run_"):
            return part
    return path.parent.name


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_float(*values: Any) -> float:
    for value in values:
        try:
            if value is not None and value != "":
                parsed = float(value)
                if isfinite(parsed):
                    return parsed
        except (TypeError, ValueError):
            continue
    return 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _value_counts(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _reason_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reasons = row.get("review_reasons")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            key = str(reason)
            counts[key] = counts.get(key, 0) + 1
    return counts
