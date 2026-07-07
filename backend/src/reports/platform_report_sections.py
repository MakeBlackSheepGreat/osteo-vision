from __future__ import annotations

import json
from typing import Any

from backend.src.core.disclaimers import ICG_SIGNAL_LIMITATION, PLATFORM_SAFETY_DISCLAIMER
from backend.src.domains.cases.schemas import CaseRecord


def latest_quantification_from_report(report: dict[str, Any]) -> dict[str, Any]:
    latest_run = report.get("latest_analysis_run") if isinstance(report.get("latest_analysis_run"), dict) else {}
    quantification = latest_run.get("quantitative_summary") if isinstance(latest_run, dict) else {}
    return quantification if isinstance(quantification, dict) else {}


def video_signal_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    fused_outputs = latest_run.get("fused_outputs") if isinstance(latest_run.get("fused_outputs"), dict) else {}
    summary = (
        fused_outputs.get("video_segmentation_summary")
        if isinstance(fused_outputs.get("video_segmentation_summary"), dict)
        else {}
    )
    frame_details = fused_outputs.get("frame_details") if isinstance(fused_outputs.get("frame_details"), list) else []
    frames = [frame for frame in frame_details if isinstance(frame, dict)]
    if not summary and not frames:
        return {
            "available": False,
            "section_title": "Fluorescence perfusion/activity risk prompts",
            "medical_boundary": (
                "Video signal segmentation is only available after MP4/JPEG keyframe analysis. "
                "ICG signal is not a disease-specific diagnosis."
            ),
        }
    return {
        "available": True,
        "section_title": "Fluorescence perfusion/activity risk prompts",
        "analysis_scope": summary.get("analysis_scope"),
        "selected_frame_count": summary.get("selected_frame_count", len(frames)),
        "mask_frame_count": summary.get("mask_frame_count"),
        "risk_frame_count": summary.get("risk_frame_count"),
        "video_signal_outputs": summary.get(
            "video_signal_outputs",
            ["bone_gate_mask", "fluorescence_signal_mask", "risk_mask", "uncertain_mask"],
        ),
        "video_segmentation_manifest_path": fused_outputs.get("video_segmentation_manifest_path"),
        "segmentation_review_video_path": fused_outputs.get("segmentation_review_video_path"),
        "mask_review_video_path": fused_outputs.get("mask_review_video_path"),
        "frame_examples": [_video_signal_frame_summary(frame) for frame in frames[:8]],
        "medical_boundary": summary.get(
            "medical_boundary",
            "Fluorescence/perfusion risk prompts require physician review and are not a clinical diagnosis.",
        ),
    }


def video_signal_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return ["- No MP4/JPEG video signal segmentation output recorded."]
    lines = [
        f"- Analysis scope: `{section.get('analysis_scope') or 'not recorded'}`",
        f"- Selected frames: `{section.get('selected_frame_count') or 0}`",
        f"- Mask frames: `{section.get('mask_frame_count') or 0}`",
        f"- Risk frames: `{section.get('risk_frame_count') or 0}`",
        f"- Output slots: `{', '.join(str(item) for item in section.get('video_signal_outputs') or [])}`",
    ]
    manifest_path = section.get("video_segmentation_manifest_path")
    if manifest_path:
        lines.append(f"- Video segmentation manifest: `{manifest_path}`")
    for frame in section.get("frame_examples") or []:
        if not isinstance(frame, dict):
            continue
        lines.append(
            "- Frame "
            f"`{frame.get('frame_index')}` at `{frame.get('timestamp_sec')}` sec: "
            f"risk `{frame.get('risk_mask_path') or 'missing'}`, "
            f"uncertain `{frame.get('uncertain_mask_path') or 'missing'}`"
        )
    lines.append(f"- Medical boundary: {section.get('medical_boundary')}")
    return lines


def quality_flag_markdown_lines(case: CaseRecord) -> list[str]:
    if not case.quality_flags:
        return ["- No blocking quality flags recorded."]
    return [f"- `{flag.code}`: {flag.message}" for flag in case.quality_flags]


def artifact_markdown_lines(case: CaseRecord) -> list[str]:
    if not case.artifacts:
        return ["- No evidence artifacts recorded."]
    return [f"- `{artifact.kind}`: `{artifact.path}`" for artifact in case.artifacts]


def quantification_summary_lines(quantification: dict[str, Any], *, limit: int = 12) -> list[str]:
    if not quantification:
        return ["- No quantitative summary recorded."]
    return [f"- {key}: {quantification[key]}" for key in sorted(quantification)[:limit]]


def platform_safety_lines() -> list[str]:
    # 报告、Markdown、DICOM 共享同一组边界文案，避免某个导出格式遗失医生复核边界。
    return [PLATFORM_SAFETY_DISCLAIMER, ICG_SIGNAL_LIMITATION]


def json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _video_signal_frame_summary(frame: dict[str, Any]) -> dict[str, Any]:
    signal_masks = frame.get("video_signal_segmentation") or frame.get("signal_masks")
    signal_masks = signal_masks if isinstance(signal_masks, dict) else {}
    risk_mask = signal_masks.get("risk_mask") if isinstance(signal_masks.get("risk_mask"), dict) else {}
    uncertain_mask = signal_masks.get("uncertain_mask") if isinstance(signal_masks.get("uncertain_mask"), dict) else {}
    bone_gate = signal_masks.get("bone_gate_mask") if isinstance(signal_masks.get("bone_gate_mask"), dict) else {}
    return {
        "frame_index": frame.get("frame_index"),
        "timestamp_sec": frame.get("timestamp_sec"),
        "overlay_path": frame.get("overlay_path"),
        "mask_path": frame.get("mask_path"),
        "risk_mask_path": frame.get("risk_mask_path") or risk_mask.get("path"),
        "uncertain_mask_path": frame.get("uncertain_mask_path") or uncertain_mask.get("path"),
        "bone_gate_status": bone_gate.get("status") or "not_available_pending_review",
        "positive_area_fraction": frame.get("positive_area_fraction"),
        "review_priority": frame.get("review_priority"),
    }
