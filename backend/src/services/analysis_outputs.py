from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import checksum_for_file
from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.enums import ArtifactKind, ReviewState
from backend.src.domains.cases.schemas import CandidateRegion, CaseInputAsset, CaseRecord, EvidenceArtifact
from backend.src.services.video_hotspot_outputs import (
    hotspot_artifacts,
    video_manifest_artifacts,
    video_segmentation_artifacts,
)


def video_fused_outputs(
    *,
    source_path: str,
    video: CaseInputAsset | None,
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    segmentation_model_id: str,
    frame_details: list[dict[str, Any]],
    keyframe_report: dict[str, Any],
    timeline_summary: dict[str, Any],
    temporal_summary: dict[str, Any],
    frame_details_manifest_path: str | None,
    video_segmentation_outputs: dict[str, Any],
    roi_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    # MP4 分析结果字段较多，集中装配可以让 AnalysisService 只保留流程编排。
    return {
        "mode": "video_file_keyframes",
        "source_path": source_path,
        "video_metadata": video.metadata if video else {},
        "keyframes": keyframes,
        "hotspot_outputs": hotspot_outputs,
        "keyframe_segmentation_outputs": hotspot_outputs,
        "keyframe_segmentation_model_id": segmentation_model_id,
        "frame_details": frame_details,
        "quality_summary": keyframe_report.get("quality_summary", {}),
        "keyframe_report_source": keyframe_report.get("report_source", "new_analysis_extract"),
        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "timeline_summary": timeline_summary,
        "temporal_stability_summary": temporal_summary,
        "frame_details_manifest_path": frame_details_manifest_path,
        "video_segmentation_manifest_path": video_segmentation_outputs.get("video_segmentation_manifest_path"),
        "segmentation_review_video_path": video_segmentation_outputs.get("segmentation_review_video_path"),
        "mask_review_video_path": video_segmentation_outputs.get("mask_review_video_path"),
        "video_segmentation_summary": video_segmentation_outputs.get("summary", {}),
        "roi_hints": roi_hints,
        "disclaimer_context": disclaimer_context(),
    }


def video_quantitative_summary(
    *,
    keyframe_report: dict[str, Any],
    keyframes: list[dict[str, Any]],
    roi_hints: list[dict[str, Any]],
    video_segmentation_outputs: dict[str, Any],
    temporal_summary: dict[str, Any],
    hotspot_summary: dict[str, Any],
) -> dict[str, Any]:
    segmentation_summary = video_segmentation_outputs.get("summary", {})
    segmentation_summary = segmentation_summary if isinstance(segmentation_summary, dict) else {}
    return {
        "frame_count": keyframe_report.get("frame_count"),
        "duration_sec": keyframe_report.get("duration_sec"),
        "keyframes_extracted": len(keyframes),
        "keyframe_source": keyframe_report.get("report_source", "new_analysis_extract"),
        "roi_hint_count": len(roi_hints),
        "roi_filter_applied": bool(roi_hints),
        "segmentation_frame_count": segmentation_summary.get("selected_frame_count", 0),
        "segmentation_overlay_video_available": bool(video_segmentation_outputs.get("segmentation_review_video_path")),
        "hotspot_temporal_instability_frame_count": temporal_summary.get("instability_frame_count", 0),
        **hotspot_summary,
    }


def video_artifacts(
    case_id: str,
    run_id: str,
    *,
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    keyframe_report: dict[str, Any],
    frame_details_manifest_path: str | None,
    video_segmentation_outputs: dict[str, Any],
) -> list[EvidenceArtifact]:
    return [
        *_keyframe_artifacts(case_id, run_id, keyframes),
        *hotspot_artifacts(case_id, run_id, hotspot_outputs),
        *video_manifest_artifacts(
            case_id,
            run_id,
            [
                keyframe_report.get("frame_index_manifest_path"),
                keyframe_report.get("timeline_manifest_path"),
                frame_details_manifest_path,
                video_segmentation_outputs.get("video_segmentation_manifest_path"),
            ],
        ),
        *video_segmentation_artifacts(case_id, run_id, video_segmentation_outputs),
    ]


def fusion_fused_outputs(
    fusion_report: dict[str, Any],
    *,
    outputs: dict[str, Any],
    roi_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    # 双通道融合报告来自底层处理函数，这里只补平台层需要追踪的 ROI 和安全边界上下文。
    return {
        **fusion_report,
        "outputs": outputs,
        "roi_hints": roi_hints,
        "disclaimer_context": disclaimer_context(),
    }


def fusion_quantitative_summary(
    fusion_report: dict[str, Any],
    *,
    roi_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    quantification = fusion_report.get("quantification", {})
    quantification = quantification if isinstance(quantification, dict) else {}
    return {**quantification, "roi_hint_count": len(roi_hints)}


def fusion_candidate_regions(
    run_id: str,
    fusion_report: dict[str, Any],
    *,
    roi_hints: list[dict[str, Any]],
) -> list[CandidateRegion]:
    quantification = fusion_report.get("quantification", {})
    quantification = quantification if isinstance(quantification, dict) else {}
    return [
        CandidateRegion(
            candidate_id=f"cand_{uuid4().hex[:10]}",
            run_id=run_id,
            score=float(quantification.get("roi_mean_intensity", quantification.get("mean_intensity", 0.0))),
            risk_type="fluorescence_hotspot",
            confidence=float(quantification.get("roi_p95_intensity", quantification.get("p95_intensity", 0.0))),
            status=ReviewState.REVIEW_REQUIRED,
            explanation=(
                "Derived from ROI-constrained fluorescence quantification heuristics."
                if roi_hints
                else "Derived from fluorescence quantification heuristics."
            ),
        )
    ]


def missing_dual_channel_warning() -> dict[str, Any]:
    return {
        "code": "missing_dual_channel_pair",
        "message": "Dual-channel white-light and fluorescence inputs are required for fusion.",
        "blocking": True,
    }


def fusion_artifacts(case_id: str, run_id: str, outputs: dict[str, Any]) -> list[EvidenceArtifact]:
    mapping = {
        "overlay_path": ArtifactKind.OVERLAY,
        "heatmap_path": ArtifactKind.HEATMAP,
        "normalized_fluorescence_path": ArtifactKind.NORMALIZED_FLUORESCENCE,
        "colorbar_path": ArtifactKind.COLORBAR,
        "report_path": ArtifactKind.REPORT_JSON,
        "markdown_report_path": ArtifactKind.REPORT_MD,
    }
    artifacts: list[EvidenceArtifact] = []
    for output_key, kind in mapping.items():
        path = outputs.get(output_key)
        if not path:
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=kind,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts


def merge_roi_hints(case: CaseRecord, request_hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in request_hints:
        roi_id = str(hint.get("roi_id") or f"request_roi_{len(merged) + 1}")
        merged.append({**hint, "roi_id": roi_id, "source": hint.get("source", "request")})
        seen.add(roi_id)
    for roi in case.rois:
        if roi.roi_id in seen:
            continue
        merged.append(
            {
                "roi_id": roi.roi_id,
                "source": roi.source.value,
                "geometry": roi.geometry,
                "label": roi.label,
                "review_state": roi.review_state.value,
                "candidate_id": roi.candidate_id,
            }
        )
        seen.add(roi.roi_id)
    return merged


def _keyframe_artifacts(case_id: str, run_id: str, keyframes: list[dict[str, Any]]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    for frame in keyframes:
        path = frame.get("evidence_path") or frame.get("path")
        if not path:
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.KEYFRAME,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts
