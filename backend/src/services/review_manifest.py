from __future__ import annotations

import json
from typing import Any

from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.schemas import CaseRecord

REVIEW_MANIFEST_FIELDS = [
    "case_id",
    "record_type",
    "run_id",
    "roi_id",
    "candidate_id",
    "review_state",
    "label",
    "source",
    "actor",
    "actor_id",
    "role",
    "institution",
    "auth_source",
    "action",
    "target_id",
    "timestamp",
    "score",
    "confidence",
    "risk_type",
    "mask_type",
    "frame_index",
    "timestamp_sec",
    "image_width",
    "image_height",
    "bbox_xyxy",
    "bbox_normalized",
    "geometry",
    "mask_path",
    "signal_mask_path",
    "fluorescence_signal_mask_path",
    "bone_gate_mask_path",
    "bone_gate_overlay_path",
    "risk_mask_path",
    "uncertain_mask_path",
    "overlay_path",
    "source_path",
    "bone_gate_status",
    "label_source",
    "prompt_source",
    "sample_weight",
    "notes",
    "medical_boundary",
]


def build_review_manifest(case: CaseRecord) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """生成医生复核回灌清单。

    JSON 保留完整结构，CSV 只保留训练回灌和错误分析最常用的扁平字段。
    """

    candidates = [
        _candidate_manifest_entry(case.case_id, run.run_id, run.method_id, candidate)
        for run in case.analysis_runs
        for candidate in run.candidate_regions
    ]
    rois = [_roi_manifest_entry(roi) for roi in case.rois]
    review_events = [
        event.model_dump(mode="json") for event in sorted(case.review_events, key=lambda item: item.timestamp)
    ]
    rows = [
        *[_candidate_review_row(case.case_id, candidate) for candidate in candidates],
        *[_roi_review_row(roi) for roi in rois],
        *[_review_event_row(event) for event in review_events],
    ]
    payload = {
        "schema_version": "osteo-vision-review-manifest-v1",
        "case_id": case.case_id,
        "generated_from": "ExportService.export_case",
        "review_source_scope": {
            "rois": "Doctor-created or AI-promoted regions available in this case record.",
            "candidate_regions": "AI candidate regions produced by JPEG/MP4 keyframe or image analysis runs.",
            "review_events": "Human review actions recorded through the case review API.",
        },
        "training_use": {
            "allowed_scope": "platform_feedback_training_or_error_analysis_after_deidentification",
            "requires_physician_review": True,
            "non_target_domain_warning": (
                "Public, proxy, synthetic, or CBCT-derived samples must not be described as real "
                "intraoperative ICG jaw osteomyelitis data."
            ),
        },
        "medical_boundary": disclaimer_context(),
        "summary": {
            "roi_count": len(rois),
            "candidate_region_count": len(candidates),
            "review_event_count": len(review_events),
            "accepted_candidate_count": sum(1 for item in candidates if item.get("status") == "accepted"),
            "accepted_roi_count": sum(1 for item in rois if item.get("review_state") == "accepted"),
        },
        "candidates": candidates,
        "rois": rois,
        "review_events": review_events,
    }
    return payload, rows


def _candidate_manifest_entry(
    case_id: str,
    run_id: str,
    method_id: str | None,
    candidate: Any,
) -> dict[str, Any]:
    metadata = candidate.metadata or {}
    return {
        "case_id": case_id,
        "run_id": run_id,
        "method_id": method_id,
        "candidate_id": candidate.candidate_id,
        "status": str(candidate.status),
        "score": candidate.score,
        "confidence": candidate.confidence,
        "risk_type": candidate.risk_type,
        "explanation": candidate.explanation,
        "frame_index": metadata.get("frame_index"),
        "frame_order": metadata.get("frame_order"),
        "timestamp_sec": metadata.get("timestamp_sec"),
        "model_id": metadata.get("model_id"),
        "model_family": metadata.get("model_family"),
        "analysis_method": metadata.get("analysis_method"),
        "bbox_xyxy": metadata.get("bbox_xyxy") or metadata.get("source_bbox_xyxy"),
        "bbox_normalized": metadata.get("bbox_normalized") or metadata.get("source_bbox_normalized"),
        "mask_path": metadata.get("mask_path"),
        "signal_mask_path": metadata.get("signal_mask_path"),
        "fluorescence_signal_mask_path": metadata.get("fluorescence_signal_mask_path"),
        "bone_gate_mask_path": metadata.get("bone_gate_mask_path"),
        "bone_gate_overlay_path": metadata.get("bone_gate_overlay_path"),
        "risk_mask_path": metadata.get("risk_mask_path"),
        "uncertain_mask_path": metadata.get("uncertain_mask_path"),
        "overlay_path": metadata.get("overlay_path"),
        "source_path": metadata.get("source_path"),
        "mask_type": metadata.get("mask_type"),
        "bone_gate_status": metadata.get("bone_gate_status"),
        "label_source": metadata.get("label_source"),
        "prompt_source": metadata.get("prompt_source"),
        "sample_weight": _sample_weight(candidate.status),
        "signal_masks": metadata.get("signal_masks") or metadata.get("video_signal_segmentation"),
        "image_width": metadata.get("image_width") or metadata.get("source_video_width"),
        "image_height": metadata.get("image_height") or metadata.get("source_video_height"),
        "spatial_mapping": metadata.get("spatial_mapping"),
        "temporal_stability": metadata.get("temporal_stability"),
        "metadata": metadata,
    }


def _roi_manifest_entry(roi: Any) -> dict[str, Any]:
    return {
        "case_id": roi.case_id,
        "roi_id": roi.roi_id,
        "candidate_id": roi.candidate_id,
        "source": str(roi.source),
        "review_state": str(roi.review_state),
        "label": roi.label,
        "geometry": roi.geometry,
        "metrics": roi.metrics,
        "frame_index": roi.metrics.get("frame_index") if isinstance(roi.metrics, dict) else None,
        "timestamp_sec": roi.metrics.get("timestamp_sec") if isinstance(roi.metrics, dict) else None,
        "mask_type": roi.metrics.get("mask_type") if isinstance(roi.metrics, dict) else None,
        "mask_path": roi.metrics.get("mask_path") if isinstance(roi.metrics, dict) else None,
        "bone_gate_status": roi.metrics.get("bone_gate_status") if isinstance(roi.metrics, dict) else None,
        "bone_gate_mask_path": roi.metrics.get("bone_gate_mask_path") if isinstance(roi.metrics, dict) else None,
        "bone_gate_overlay_path": roi.metrics.get("bone_gate_overlay_path") if isinstance(roi.metrics, dict) else None,
        "label_source": roi.metrics.get("label_source") if isinstance(roi.metrics, dict) else None,
        "prompt_source": roi.metrics.get("prompt_source") if isinstance(roi.metrics, dict) else None,
        "sample_weight": roi.metrics.get("sample_weight") if isinstance(roi.metrics, dict) else None,
        "risk_mask_path": roi.metrics.get("risk_mask_path") if isinstance(roi.metrics, dict) else None,
        "uncertain_mask_path": roi.metrics.get("uncertain_mask_path") if isinstance(roi.metrics, dict) else None,
    }


def _candidate_review_row(case_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "record_type": "candidate_region",
        "run_id": candidate.get("run_id"),
        "candidate_id": candidate.get("candidate_id"),
        "review_state": candidate.get("status"),
        "score": candidate.get("score"),
        "confidence": candidate.get("confidence"),
        "risk_type": candidate.get("risk_type"),
        "mask_type": candidate.get("mask_type"),
        "frame_index": candidate.get("frame_index"),
        "timestamp_sec": candidate.get("timestamp_sec"),
        "image_width": candidate.get("image_width"),
        "image_height": candidate.get("image_height"),
        "bbox_xyxy": _compact_json(candidate.get("bbox_xyxy")),
        "bbox_normalized": _compact_json(candidate.get("bbox_normalized")),
        "mask_path": candidate.get("mask_path"),
        "signal_mask_path": candidate.get("signal_mask_path"),
        "fluorescence_signal_mask_path": candidate.get("fluorescence_signal_mask_path"),
        "bone_gate_mask_path": candidate.get("bone_gate_mask_path"),
        "bone_gate_overlay_path": candidate.get("bone_gate_overlay_path"),
        "risk_mask_path": candidate.get("risk_mask_path"),
        "uncertain_mask_path": candidate.get("uncertain_mask_path"),
        "overlay_path": candidate.get("overlay_path"),
        "source_path": candidate.get("source_path"),
        "bone_gate_status": candidate.get("bone_gate_status"),
        "label_source": candidate.get("label_source"),
        "prompt_source": candidate.get("prompt_source"),
        "sample_weight": _sample_weight(candidate.get("review_state") or candidate.get("status")),
        "notes": candidate.get("explanation"),
        "medical_boundary": "platform_physician_review_required",
    }


def _roi_review_row(roi: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": roi.get("case_id"),
        "record_type": "roi",
        "roi_id": roi.get("roi_id"),
        "candidate_id": roi.get("candidate_id"),
        "review_state": roi.get("review_state"),
        "label": roi.get("label"),
        "source": roi.get("source"),
        "mask_type": roi.get("mask_type"),
        "frame_index": roi.get("frame_index"),
        "timestamp_sec": roi.get("timestamp_sec"),
        "mask_path": roi.get("mask_path") or roi.get("bone_gate_mask_path"),
        "bone_gate_mask_path": roi.get("bone_gate_mask_path"),
        "bone_gate_overlay_path": roi.get("bone_gate_overlay_path"),
        "risk_mask_path": roi.get("risk_mask_path"),
        "uncertain_mask_path": roi.get("uncertain_mask_path"),
        "bone_gate_status": roi.get("bone_gate_status"),
        "label_source": roi.get("label_source"),
        "prompt_source": roi.get("prompt_source"),
        "sample_weight": roi.get("sample_weight") or _sample_weight(roi.get("review_state")),
        "geometry": _compact_json(roi.get("geometry")),
        "notes": _compact_json(roi.get("metrics")),
        "medical_boundary": "platform_physician_review_required",
    }


def _review_event_row(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": event.get("case_id"),
        "record_type": "review_event",
        "actor": event.get("actor"),
        "actor_id": event.get("actor_id"),
        "role": event.get("role"),
        "institution": event.get("institution"),
        "auth_source": event.get("auth_source"),
        "action": event.get("action"),
        "target_id": event.get("target_id"),
        "timestamp": event.get("timestamp"),
        "review_state": event.get("after_state"),
        "sample_weight": _sample_weight(event.get("after_state")),
        "notes": event.get("notes"),
        "medical_boundary": "platform_physician_review_required",
    }


def _compact_json(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sample_weight(review_state: Any) -> float:
    state = str(review_state or "").lower()
    if state in {"accepted", "modified"}:
        return 4.0
    if state == "rejected":
        return 0.5
    return 1.0
