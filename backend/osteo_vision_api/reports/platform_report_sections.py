from __future__ import annotations

import json
from typing import Any

from backend.osteo_vision_api.core.disclaimers import ICG_SIGNAL_LIMITATION, PLATFORM_SAFETY_DISCLAIMER
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord

NAVIGATION_FAILURE_REASON_LABELS = {
    "calibration_selection_ambiguous": "标定选择存在歧义",
    "calibration_selection_oscillation": "出现 A/B/A 内参振荡",
    "calibration_switch_rate_exceeded": "内参切换率超限",
    "magnification_rate_exceeded": "倍率变化率超限",
    "working_distance_rate_exceeded": "工作距离变化率超限",
    "video_variable_frame_rate_unsupported": "视频帧间隔不满足已验证恒定帧率门",
    "video_pts_unverified": "视频逐帧 PTS 未通过核验",
    "tracking_lost": "位姿跟踪丢失",
    "pose_time_offset_exceeded": "影像与位姿时间偏移超限",
    "drift_threshold_exceeded": "跟踪漂移超限",
    "tre_proxy_threshold_exceeded": "TRE 代理超限",
    "dynamic_target_error_threshold_exceeded": "独立动态目标误差超限",
    "projection_visible_points_insufficient": "画幅内可见投影点不足",
    "l2_threshold_exceeds_platform_safety_ceiling": "L2 安全参数超出平台允许边界",
    "l2_threshold_policy_not_approved": "L2 安全参数策略未获批准",
    "doctor_review_not_accepted": "可信医生复核未通过",
}

CLINICAL_FEATURE_VECTOR_FIELDS = (
    "schema_version",
    "feature_version",
    "feature_names",
    "present_mask",
    "missing_mask",
    "ood_mask",
    "checkpoint_consumed_mask",
    "spatial_effect_applied_mask",
    "recorded_input_summary",
    "checkpoint_consumed_feature_names",
    "spatially_applied_feature_names",
    "missing_feature_names",
    "ood_feature_names",
    "unconsumed_recorded_inputs",
    "vector_checksum",
    "runtime_vector_checksum",
)


def _dict_payload(value: Any) -> dict[str, Any]:
    # Report sections only read these JSON-compatible payloads.  Reusing the
    # original container avoids copying large per-frame evidence dictionaries.
    return value if isinstance(value, dict) else {}


def _list_payload(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clinical_feature_vector_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    vector = _dict_payload(source.get("clinical_feature_vector"))
    if not vector:
        return {}
    return {field: vector.get(field) for field in CLINICAL_FEATURE_VECTOR_FIELDS}


def clinical_context_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    parameters_value = latest_run.get("parameters")
    parameters = dict(parameters_value) if isinstance(parameters_value, dict) else {}
    assessment_value = parameters.get("clinical_context_assessment")
    assessment = dict(assessment_value) if isinstance(assessment_value, dict) else {}
    if not assessment:
        return {
            "available": False,
            "section_title": "Clinical context safety assessment",
            "medical_boundary": "No versioned clinical context assessment was recorded for this analysis run.",
        }
    return {
        "available": True,
        "section_title": "Clinical context safety assessment",
        "schema_version": assessment.get("schema_version"),
        "assessed_at": assessment.get("assessed_at"),
        "clinical_context_revision": assessment.get("clinical_context_revision"),
        "clinical_context_checksum": assessment.get("clinical_context_checksum"),
        "clinical_context_quality": assessment.get("clinical_context_quality") or {},
        "normalized_labs": assessment.get("normalized_labs") or [],
        "rule_based_risk_summary": assessment.get("rule_based_risk_summary") or {},
        "calibration_evidence": assessment.get("calibration_evidence") or {},
        "spatial_effect_applied": False,
        "medical_boundary": (
            "Clinical variables provide rule-based review prompts only. No validated clinical risk probability, "
            "diagnosis, or pixel-level boundary modification is produced."
        ),
    }


def clinical_context_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return [f"- {section.get('medical_boundary')}"]
    quality = section.get("clinical_context_quality") or {}
    summary = section.get("rule_based_risk_summary") or {}
    calibration = section.get("calibration_evidence") or {}
    lines = [
        f"- Context revision: `{section.get('clinical_context_revision')}`",
        f"- Context checksum: `{section.get('clinical_context_checksum') or 'not recorded'}`",
        f"- Quality status: `{quality.get('status') or 'not recorded'}`",
        f"- Physician verification status: `{quality.get('review_status') or 'not recorded'}`",
        f"- Usable labs: `{quality.get('usable_lab_count') or 0} / {quality.get('recorded_lab_count') or 0}`",
        f"- Missing critical fields: `{', '.join(quality.get('missing_critical_fields') or []) or 'none'}`",
        f"- Quality issues: `{', '.join(quality.get('issues') or []) or 'none'}`",
        f"- Rule-based factor count: `{summary.get('factor_count') or 0}`",
        f"- Clinical probability produced: `{summary.get('probability') is not None}`",
        f"- Calibration applied: `{bool(calibration.get('applied'))}`",
        f"- Calibration status: `{calibration.get('status') or 'not recorded'}`",
        f"- Spatial effect applied: `{bool(section.get('spatial_effect_applied'))}`",
        f"- Boundary: {section.get('medical_boundary')}",
    ]
    return lines


def task3_fused_image_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    fused_outputs = _dict_payload(latest_run.get("fused_outputs"))
    evidence = _dict_payload(fused_outputs.get("fused_image_ai"))
    if not evidence:
        return {
            "available": False,
            "section_title": "Task 3 fused-image AI review evidence",
            "medical_boundary": "No Task 3 fused-image AI evidence was recorded for this analysis run.",
        }
    input_contract = _dict_payload(evidence.get("input_contract"))
    boundary = _dict_payload(evidence.get("boundary_assessment"))
    lesion = _dict_payload(evidence.get("lesion_evidence"))
    return {
        "available": evidence.get("available") is True,
        "section_title": "Task 3 fused-image AI review evidence",
        "execution_state": evidence.get("execution_state"),
        "model_id": evidence.get("model_id"),
        "model_family": evidence.get("model_family"),
        "task_role": evidence.get("task_role"),
        "input_contract_schema": input_contract.get("schema_version"),
        "input_contract_path": input_contract.get("contract_path"),
        "input_contract_sha256": input_contract.get("contract_sha256"),
        "engineering_input_eligible": input_contract.get("engineering_input_eligible") is True,
        "task2_provenance": input_contract.get("task2_provenance") or {},
        "boundary_assessment_schema": boundary.get("schema_version"),
        "boundary_assessment_path": boundary.get("summary_path"),
        "candidate_count": boundary.get("candidate_count", 0),
        "evaluated_candidate_count": boundary.get("evaluated_candidate_count", boundary.get("candidate_count", 0)),
        "suppressed_candidate_count": boundary.get("suppressed_candidate_count", 0),
        "boundary_type_counts": boundary.get("boundary_type_counts") or {},
        "evaluated_boundary_type_counts": boundary.get("evaluated_boundary_type_counts") or {},
        "activity_class_counts": boundary.get("activity_class_counts") or {},
        "evaluated_activity_class_counts": boundary.get("evaluated_activity_class_counts") or {},
        "activity_evidence": boundary.get("activity_evidence") or {},
        "candidate_retention": boundary.get("candidate_retention") or {},
        "review_priority": boundary.get("review_priority"),
        "spatial_interpretation_allowed": evidence.get("spatial_interpretation_allowed") is True,
        "clinical_claim_allowed": evidence.get("clinical_claim_allowed") is True,
        "mask_path": lesion.get("mask_path"),
        "probability_path": lesion.get("probability_path"),
        "risk_mask_path": lesion.get("risk_mask_path"),
        "uncertain_mask_path": lesion.get("uncertain_mask_path"),
        "overlay_path": lesion.get("overlay_path"),
        "physician_review_required": boundary.get("physician_review_required", True),
        "medical_boundary": boundary.get("medical_boundary")
        or (
            "Boundary classes describe engineering signal, risk, and uncertainty layers. Pathological necrosis, "
            "active bone status, and surgical margins require physician review and target-domain evidence."
        ),
    }


def task3_fused_image_section_from_runs(runs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Select the newest run that actually contains fused-image AI evidence.

    A case can have a JPEG fusion run followed by an MP4 video run.  Using only
    the final run hides the JPEG Task 3 result from the exported report.  Keep
    the latest-run field untouched while selecting this section by evidence
    availability and retaining the source run id for auditability.
    """

    candidates = [run for run in (runs or []) if isinstance(run, dict)]
    for run in reversed(candidates):
        fused_outputs = _dict_payload(run.get("fused_outputs"))
        evidence = _dict_payload(fused_outputs.get("fused_image_ai"))
        if not evidence:
            continue
        section = task3_fused_image_section_from_run(run)
        section["source_run_id"] = run.get("run_id")
        section["source_run_selection"] = "latest_run_with_task3_fused_image_ai"
        return section
    section = task3_fused_image_section_from_run(candidates[-1] if candidates else None)
    section["source_run_id"] = None
    section["source_run_selection"] = "no_task3_fused_image_ai_run"
    return section


def task3_fused_image_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return [f"- {section.get('medical_boundary')}"]
    provenance = _dict_payload(section.get("task2_provenance"))
    boundary_counts = _dict_payload(section.get("boundary_type_counts"))
    activity_counts = _dict_payload(section.get("activity_class_counts"))
    activity_evidence = _dict_payload(section.get("activity_evidence"))
    return [
        f"- Execution state: `{section.get('execution_state') or 'not recorded'}`",
        f"- Model: `{section.get('model_id') or 'not recorded'}`",
        f"- Input contract: `{section.get('input_contract_schema') or 'not recorded'}`",
        f"- Input contract SHA256: `{section.get('input_contract_sha256') or 'not recorded'}`",
        f"- Engineering input eligible: `{bool(section.get('engineering_input_eligible'))}`",
        f"- Task 2 registration and fusion compute: `{provenance.get('registration_fusion_compute_ms')}` ms",
        f"- Task 2 accelerator: `{provenance.get('accelerator') or 'not recorded'}`",
        f"- Boundary candidate count: `{section.get('candidate_count') or 0}`",
        f"- Evaluated boundary candidates: `{section.get('evaluated_candidate_count') or 0}`",
        f"- Suppressed low-priority boundary candidates: `{section.get('suppressed_candidate_count') or 0}`",
        f"- Signal candidate boundaries: `{boundary_counts.get('signal_candidate_boundary') or 0}`",
        f"- High-risk transition boundaries: `{boundary_counts.get('high_risk_transition_boundary') or 0}`",
        f"- Uncertain boundaries: `{boundary_counts.get('uncertain_boundary') or 0}`",
        f"- Bone-activity evidence available: `{bool(activity_evidence.get('available'))}`",
        f"- Low-activity review candidates: `{activity_counts.get('low_activity_candidate') or 0}`",
        f"- Transition review candidates: `{activity_counts.get('transition_candidate') or 0}`",
        f"- High-activity references: `{activity_counts.get('high_activity_candidate') or 0}`",
        f"- Activity-unavailable candidates: `{activity_counts.get('unavailable_pending_reviewed_bone_gate') or 0}`",
        f"- Spatial interpretation allowed: `{bool(section.get('spatial_interpretation_allowed'))}`",
        f"- Physician review required: `{bool(section.get('physician_review_required'))}`",
        f"- Clinical claim allowed: `{bool(section.get('clinical_claim_allowed'))}`",
        f"- Boundary: {section.get('medical_boundary')}",
    ]


def patient_conditioning_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    fused_outputs = _dict_payload(latest_run.get("fused_outputs"))
    evidence = _dict_payload(fused_outputs.get("patient_conditioning_evidence"))
    if not evidence:
        return {
            "available": False,
            "section_title": "Patient-conditioned segmentation comparison",
            "medical_boundary": "No patient-conditioned segmentation evidence was recorded for this analysis run.",
        }
    prediction = _dict_payload(evidence.get("prediction"))
    payload = {**prediction, **evidence}
    quantification = _dict_payload(payload.get("quantification"))
    reviewed_gate = _dict_payload(payload.get("reviewed_bone_gate"))
    clinical_feature_vector = clinical_feature_vector_from_payload(payload)
    return {
        "available": True,
        "inference_available": bool(payload.get("available")),
        "section_title": "Patient-conditioned segmentation comparison",
        "schema_version": payload.get("schema_version"),
        "model_id": payload.get("model_id"),
        "model_family": payload.get("model_family"),
        "proxy_checkpoint": bool(payload.get("proxy_checkpoint")),
        "spatial_effect_applied": bool(payload.get("spatial_effect_applied")),
        "safe_fallback_applied": bool(payload.get("safe_fallback_applied", True)),
        "failure_reasons": list(payload.get("failure_reasons") or []),
        "target_domain_promotion_ready": bool(payload.get("target_domain_promotion_ready")),
        "runtime_replacement_allowed": bool(payload.get("runtime_replacement_allowed")),
        "clinical_context_checksum": payload.get("clinical_context_checksum"),
        "clinical_present_fraction": payload.get("clinical_present_fraction"),
        "clinical_feature_vector": clinical_feature_vector,
        "reviewed_bone_gate": reviewed_gate,
        "image_only_probability_path": payload.get("image_only_probability_path"),
        "conditioned_probability_path": payload.get("conditioned_probability_path"),
        "delta_map_path": payload.get("delta_map_path"),
        "difference_mask_path": payload.get("difference_mask_path"),
        "spatial_effect_mask_path": payload.get("spatial_effect_mask_path"),
        "uncertainty_path": payload.get("uncertainty_path"),
        "evidence_manifest_path": payload.get("evidence_manifest_path"),
        "quantification": quantification,
        "medical_boundary": payload.get(
            "medical_boundary",
            "Patient-conditioned output is research-validation evidence and requires physician review.",
        ),
    }


def patient_conditioning_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return [f"- {section.get('medical_boundary')}"]
    quantification = _dict_payload(section.get("quantification"))
    failure_reasons = [str(item) for item in section.get("failure_reasons") or [] if str(item).strip()]
    vector = clinical_feature_vector_from_payload(section)
    vector_lines = _clinical_feature_vector_markdown_lines(vector)
    return [
        f"- Model: `{section.get('model_id') or 'not recorded'}`",
        f"- Inference evidence available: `{bool(section.get('inference_available'))}`",
        f"- Proxy checkpoint: `{bool(section.get('proxy_checkpoint'))}`",
        f"- Spatial effect applied: `{bool(section.get('spatial_effect_applied'))}`",
        f"- Safe image-only fallback: `{bool(section.get('safe_fallback_applied'))}`",
        f"- Target-domain promotion ready: `{bool(section.get('target_domain_promotion_ready'))}`",
        f"- Runtime replacement allowed: `{bool(section.get('runtime_replacement_allowed'))}`",
        f"- Clinical context checksum: `{section.get('clinical_context_checksum') or 'not recorded'}`",
        f"- Clinical feature present fraction: `{section.get('clinical_present_fraction')}`",
        f"- Difference area: `{quantification.get('difference_area_px', 0)} px`",
        f"- Spatial-effect area: `{quantification.get('spatial_effect_area_px', 0)} px`",
        f"- Failure reasons: `{', '.join(failure_reasons) or 'none'}`",
        f"- Evidence manifest: `{section.get('evidence_manifest_path') or 'not recorded'}`",
        *vector_lines,
        f"- Boundary: {section.get('medical_boundary')}",
    ]


def bone_activity_checkpoint_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    fused_outputs = _dict_payload(latest_run.get("fused_outputs"))
    payload = _dict_payload(fused_outputs.get("bone_activity_checkpoint_evidence"))
    if not payload:
        return {
            "available": False,
            "section_title": "Bone-activity checkpoint engineering evidence",
            "evidence_type": "checkpoint_engineering_evidence",
            "medical_boundary": "No bone-activity checkpoint execution evidence was recorded for this run.",
        }
    raw = _dict_payload(payload.get("raw_engineering_outputs"))
    selection = _dict_payload(payload.get("reviewed_bone_gate_selection"))
    target_gate = _dict_payload(payload.get("target_domain_input_gate"))
    registration = _dict_payload(payload.get("registration_evidence"))
    return {
        "available": True,
        "section_title": "Bone-activity checkpoint engineering evidence",
        "evidence_type": "checkpoint_engineering_evidence",
        "rule_derived_spectrum_location": "video_signal_segmentation",
        "schema_version": payload.get("schema_version"),
        "model_id": payload.get("model_id"),
        "model_family": payload.get("model_family"),
        "input_domain": payload.get("input_domain"),
        "training_domain": _dict_payload(payload.get("training_domain")),
        "execution_state": payload.get("execution_state"),
        "engineering_inference_executed": bool(payload.get("engineering_inference_executed")),
        "proxy_checkpoint": bool(payload.get("proxy_checkpoint")),
        "spatial_candidates_available": bool(payload.get("spatial_candidates_available")),
        "spatial_effect_applied": bool(payload.get("spatial_effect_applied")),
        "safe_fallback_applied": bool(payload.get("safe_fallback_applied", True)),
        "checkpoint_sha256": payload.get("checkpoint_sha256"),
        "manifest_sha256": payload.get("manifest_sha256"),
        "raw_engineering_outputs": {
            "available": bool(raw.get("available")),
            "spatial_use_allowed": bool(raw.get("spatial_use_allowed")),
            "path": raw.get("path"),
            "sha256": raw.get("sha256"),
            "summary": _dict_payload(raw.get("summary")),
        },
        "evidence_manifest_path": payload.get("evidence_manifest_path"),
        "evidence_manifest_sha256": payload.get("evidence_manifest_sha256"),
        "failure_reasons": [str(item) for item in _list_payload(payload.get("failure_reasons"))],
        "reviewed_bone_gate_selection": selection,
        "target_domain_input_gate": target_gate,
        "registration_evidence": registration,
        "medical_boundary": payload.get("medical_boundary")
        or "Bone-activity checkpoint evidence requires physician review and validated promotion gates.",
    }


def bone_activity_checkpoint_section_from_runs(runs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Select the newest run containing bone-activity checkpoint evidence."""

    candidates = [run for run in (runs or []) if isinstance(run, dict)]
    for run in reversed(candidates):
        fused_outputs = _dict_payload(run.get("fused_outputs"))
        evidence = _dict_payload(fused_outputs.get("bone_activity_checkpoint_evidence"))
        if not evidence:
            continue
        section = bone_activity_checkpoint_section_from_run(run)
        section["source_run_id"] = run.get("run_id")
        section["source_run_selection"] = "latest_run_with_bone_activity_checkpoint_evidence"
        return section
    section = bone_activity_checkpoint_section_from_run(candidates[-1] if candidates else None)
    section["source_run_id"] = None
    section["source_run_selection"] = "no_bone_activity_checkpoint_run"
    return section


def bone_activity_checkpoint_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return [f"- {section.get('medical_boundary')}"]
    raw = _dict_payload(section.get("raw_engineering_outputs"))
    selection = _dict_payload(section.get("reviewed_bone_gate_selection"))
    target_gate = _dict_payload(section.get("target_domain_input_gate"))
    registration = _dict_payload(section.get("registration_evidence"))
    failure_reasons = [str(item) for item in section.get("failure_reasons") or [] if str(item).strip()]
    return [
        f"- Evidence type: `{section.get('evidence_type')}`",
        f"- Rule-derived spectrum location: `{section.get('rule_derived_spectrum_location')}`",
        f"- Model: `{section.get('model_id') or 'not recorded'}`",
        f"- Model family: `{section.get('model_family') or 'not recorded'}`",
        f"- Input/training domain: `{section.get('input_domain') or 'not recorded'}`",
        f"- Engineering inference executed: `{bool(section.get('engineering_inference_executed'))}`",
        f"- Proxy checkpoint: `{bool(section.get('proxy_checkpoint'))}`",
        f"- Spatial candidates available: `{bool(section.get('spatial_candidates_available'))}`",
        f"- Spatial effect applied: `{bool(section.get('spatial_effect_applied'))}`",
        f"- Safe fallback applied: `{bool(section.get('safe_fallback_applied'))}`",
        f"- Registration applied: `{bool(registration.get('applied'))}`",
        f"- Reviewed bone-gate selection: `{selection.get('status') or 'not recorded'}`",
        f"- Target-domain input verified: `{bool(target_gate.get('verified'))}`",
        f"- Checkpoint SHA256: `{section.get('checkpoint_sha256') or 'not recorded'}`",
        f"- Manifest SHA256: `{section.get('manifest_sha256') or 'not recorded'}`",
        f"- Raw engineering NPZ: `{raw.get('path') or 'not recorded'}`",
        f"- Raw engineering NPZ SHA256: `{raw.get('sha256') or 'not recorded'}`",
        f"- Raw engineering spatial use allowed: `{bool(raw.get('spatial_use_allowed'))}`",
        f"- Evidence JSON: `{section.get('evidence_manifest_path') or 'not recorded'}`",
        f"- Evidence JSON SHA256: `{section.get('evidence_manifest_sha256') or 'not recorded'}`",
        f"- Failure reasons: `{', '.join(failure_reasons) or 'none'}`",
        f"- Boundary: {section.get('medical_boundary')}",
    ]


def _clinical_feature_vector_markdown_lines(vector: dict[str, Any]) -> list[str]:
    if not vector:
        return ["- Clinical feature vector: `not recorded`"]
    feature_names = _string_list(vector.get("feature_names"))
    present_mask = _binary_mask(vector.get("present_mask"))
    consumed_names = _string_list(vector.get("checkpoint_consumed_feature_names"))
    spatial_names = _string_list(vector.get("spatially_applied_feature_names"))
    missing_names = _string_list(vector.get("missing_feature_names"))
    ood_names = _string_list(vector.get("ood_feature_names"))
    recorded_count = sum(present_mask) if present_mask else 0
    return [
        f"- Clinical feature vector schema: `{vector.get('schema_version') or 'not recorded'}`",
        f"- Clinical feature version: `{vector.get('feature_version') or 'not recorded'}`",
        f"- Recorded feature count: `{recorded_count} / {len(feature_names)}`",
        f"- Checkpoint-consumed features ({len(consumed_names)}): `{', '.join(consumed_names) or 'none'}`",
        f"- Final spatially applied feature count: `{len(spatial_names)}`",
        f"- Final spatially applied features: `{', '.join(spatial_names) or 'none'}`",
        f"- Missing features: `{', '.join(missing_names) or 'none'}`",
        f"- OOD features: `{', '.join(ood_names) or 'none'}`",
        "- Unconsumed recorded inputs and reasons: "
        f"`{_json_inline(vector.get('unconsumed_recorded_inputs') or [])}`",
        f"- Recorded input summary: `{_json_inline(vector.get('recorded_input_summary') or {})}`",
        f"- Vector checksum: `{vector.get('vector_checksum') or 'not recorded'}`",
        f"- Runtime vector checksum: `{vector.get('runtime_vector_checksum') or 'not recorded'}`",
        f"- Present mask: `{_json_inline(vector.get('present_mask') or [])}`",
        f"- Missing mask: `{_json_inline(vector.get('missing_mask') or [])}`",
        f"- OOD mask: `{_json_inline(vector.get('ood_mask') or [])}`",
        f"- Checkpoint-consumed mask: `{_json_inline(vector.get('checkpoint_consumed_mask') or [])}`",
        f"- Spatial-effect-applied mask: `{_json_inline(vector.get('spatial_effect_applied_mask') or [])}`",
    ]


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _list_payload(value) if str(item).strip()]


def _binary_mask(value: Any) -> list[int]:
    return [1 if item is True or item == 1 else 0 for item in _list_payload(value)]


def _json_inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def latest_quantification_from_report(report: dict[str, Any]) -> dict[str, Any]:
    latest_run = _dict_payload(report.get("latest_analysis_run"))
    return _dict_payload(latest_run.get("quantitative_summary"))


def three_channel_quality_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest = run if isinstance(run, dict) else {}
    fused = _dict_payload(latest.get("fused_outputs"))
    quality = _dict_payload(fused.get("three_channel_quality"))
    if not quality:
        return {"available": False, "section_title": "Three-channel offline quality control"}
    return {"available": True, "section_title": "Three-channel offline quality control", **quality}


def three_channel_quality_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return ["- Three-channel offline QC: unavailable"]
    overall = _dict_payload(section.get("overall"))
    sync = _dict_payload(section.get("synchronization"))
    geometry = _dict_payload(section.get("geometry"))
    comparison = _dict_payload(section.get("overlay_comparison"))
    return [
        f"- Overall status: `{overall.get('status', 'unknown')}`",
        f"- Synchronization status: `{sync.get('status', 'unknown')}`",
        f"- Geometry status: `{geometry.get('status', 'unknown')}`",
        f"- Device/software overlay comparison: `{comparison.get('status', 'unavailable')}`",
        f"- Difference heatmap: `{comparison.get('difference_heatmap_path', '')}`",
        "- Safety boundary: device-overlay differences are engineering display evidence and do not affect model inference.",
    ]


def video_signal_section_from_run(run: dict[str, Any] | None) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    fused_outputs = _dict_payload(latest_run.get("fused_outputs"))
    summary = _dict_payload(fused_outputs.get("video_segmentation_summary"))
    frame_details = _list_payload(fused_outputs.get("frame_details"))
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


def three_d_evidence_section_from_run(
    run: dict[str, Any] | None,
    *,
    fallback_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest_run = run if isinstance(run, dict) else {}
    fused_outputs = _dict_payload(latest_run.get("fused_outputs"))
    evidence = _dict_payload(fused_outputs.get("three_d_evidence"))
    if isinstance(fallback_evidence, dict) and fallback_evidence:
        evidence = {**evidence, **fallback_evidence}
    if not evidence:
        return {
            "available": False,
            "section_title": "CBCT/STL 3D evidence reference",
            "boundary_note": (
                "No CBCT/STL evidence metadata is attached. The 3D workspace must remain an illustrative "
                "reference and cannot be used as navigation."
            ),
        }
    transform_chain = _list_payload(evidence.get("transform_chain"))
    markups = _list_payload(evidence.get("registration_markups"))
    scene_manifest_v2 = _dict_payload(evidence.get("scene_manifest_v2"))
    scene_nodes = _list_payload(scene_manifest_v2.get("nodes"))
    scene_markups = _list_payload(scene_manifest_v2.get("markups"))
    geometry_jobs = _list_payload(scene_manifest_v2.get("geometry_jobs"))
    navigation_evidence = three_d_navigation_evidence_summary(evidence)
    ready_transform_count = sum(
        1 for item in transform_chain if isinstance(item, dict) and item.get("status") == "ready"
    )
    ready_markup_count = sum(
        1
        for item in markups
        if isinstance(item, dict) and str(item.get("status") or "").lower() in {"ready", "accepted", "recorded"}
    )
    return {
        "available": True,
        "section_title": "CBCT/STL 3D evidence reference",
        "model_available": bool(evidence.get("model_path")),
        "model_path": evidence.get("model_path"),
        "model_file_name": evidence.get("model_file_name"),
        "model_source": evidence.get("model_source"),
        "model_format": evidence.get("model_format"),
        "registration_status": evidence.get("registration_status") or "not_recorded",
        "registration_error_mm": evidence.get("registration_error_mm"),
        "coordinate_space": evidence.get("coordinate_space"),
        "navigation_ready": bool(evidence.get("navigation_ready")),
        "doctor_review_status": evidence.get("doctor_review_status") or "not_recorded",
        "transform_ready_count": ready_transform_count,
        "transform_count": len(transform_chain),
        "markup_ready_count": ready_markup_count,
        "markup_count": len(markups),
        "scene_manifest_v2_schema": scene_manifest_v2.get("schema_version"),
        "scene_node_count": len(scene_nodes),
        "scene_markup_count": len(scene_markups),
        "geometry_job_count": len(geometry_jobs),
        "navigation_evidence": navigation_evidence,
        "boundary_note": evidence.get(
            "boundary_note",
            "CBCT/STL evidence is a reference layer only unless registration and physician review are recorded.",
        ),
    }


def three_d_navigation_evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    payload = evidence if isinstance(evidence, dict) else {}
    available = bool(
        payload
        and any(
            field in payload
            for field in (
                "navigation_level",
                "navigation_ready",
                "requested_navigation_level",
                "registration_status",
                "replay_mode",
            )
        )
    )
    if not available:
        return {
            "available": False,
            "medical_boundary": "No versioned L0/L1/L2 navigation evidence is attached.",
        }
    failures = _list_payload(payload.get("failure_reasons"))
    failure_codes = [str(item) for item in failures if str(item).strip()]
    calibration_selection = _dict_payload(payload.get("calibration_selection"))
    transition_value = payload.get("calibration_transition_summary")
    transition_summary = (
        _dict_payload(transition_value) if isinstance(transition_value, dict) else calibration_selection
    )
    return {
        "available": True,
        "schema_version": payload.get("schema_version"),
        "analysis_mode": payload.get("analysis_mode"),
        "replay_mode": payload.get("replay_mode"),
        "requested_navigation_level": payload.get("requested_navigation_level"),
        "navigation_level": payload.get("navigation_level") or "L0",
        "navigation_ready": bool(payload.get("navigation_ready")),
        "degradation_state": payload.get("degradation_state"),
        "fallback_mode": payload.get("fallback_mode"),
        "failure_reasons": failure_codes,
        "failure_reason_labels": [NAVIGATION_FAILURE_REASON_LABELS.get(code, code) for code in failure_codes],
        "video_evidence": _dict_payload(payload.get("video_evidence")),
        "microscope_pose_evidence": _dict_payload(payload.get("microscope_pose_evidence")),
        "calibration_selection": calibration_selection,
        "calibration_transition_summary": transition_summary,
        "l2_threshold_approval": _dict_payload(payload.get("l2_threshold_approval")),
        "l2_threshold_policy_evidence": _dict_payload(payload.get("l2_threshold_policy_evidence")),
        "artifact_lifecycle": _dict_payload(payload.get("artifact_lifecycle")),
        "pose_manifest_path": payload.get("pose_manifest_path"),
        "pose_manifest_sha256": payload.get("pose_manifest_sha256"),
        "pose_replay_manifest_path": payload.get("pose_replay_manifest_path"),
        "pose_replay_manifest_sha256": payload.get("pose_replay_manifest_sha256"),
        "pose_replay_frames_csv_path": payload.get("pose_replay_frames_csv_path"),
        "pose_replay_frames_csv_sha256": payload.get("pose_replay_frames_csv_sha256"),
        "overlay_video_path": payload.get("overlay_video_path"),
        "overlay_video_sha256": payload.get("overlay_video_sha256"),
        "medical_boundary": (
            "L0 is an unregistered 3D reference, L1 is static phantom-registration validation, and L2 is "
            "offline dynamic AR engineering validation. Physician review remains required."
        ),
    }


def three_d_evidence_markdown_lines(section: dict[str, Any]) -> list[str]:
    if not section.get("available"):
        return [f"- {section.get('boundary_note')}"]
    lines = [
        f"- Model file: `{section.get('model_file_name') or 'not recorded'}`",
        f"- Model path: `{section.get('model_path') or 'not recorded'}`",
        f"- Registration status: `{section.get('registration_status') or 'not recorded'}`",
        f"- Registration error: `{section.get('registration_error_mm') or 'not recorded'}`",
        f"- Coordinate space: `{section.get('coordinate_space') or 'not recorded'}`",
        f"- Transform chain: `{section.get('transform_ready_count') or 0} / {section.get('transform_count') or 0}` ready",
        f"- Markups: `{section.get('markup_ready_count') or 0} / {section.get('markup_count') or 0}` ready",
        f"- Slicer-like scene: `{section.get('scene_manifest_v2_schema') or 'not recorded'}`",
        f"- Scene graph: `{section.get('scene_node_count') or 0}` nodes, "
        f"`{section.get('scene_markup_count') or 0}` markups, `{section.get('geometry_job_count') or 0}` geometry jobs",
        f"- Navigation ready: `{bool(section.get('navigation_ready'))}`",
        f"- Doctor review: `{section.get('doctor_review_status') or 'not recorded'}`",
    ]
    navigation = section.get("navigation_evidence")
    if isinstance(navigation, dict) and navigation.get("available"):
        lines.extend(_three_d_navigation_markdown_lines(navigation))
    lines.append(f"- Boundary: {section.get('boundary_note')}")
    return lines


def _three_d_navigation_markdown_lines(navigation: dict[str, Any]) -> list[str]:
    requested = navigation.get("requested_navigation_level") or "not recorded"
    current = navigation.get("navigation_level") or "L0"
    ready = bool(navigation.get("navigation_ready"))
    lines = [
        f"- Navigation gate: requested `{requested}`, current `{current}`, ready `{ready}`",
        f"- Replay mode: `{navigation.get('replay_mode') or 'not recorded'}`",
        f"- Fallback: `{navigation.get('fallback_mode') or 'none'}`",
    ]
    failure_codes = _list_payload(navigation.get("failure_reasons"))
    failure_labels = _list_payload(navigation.get("failure_reason_labels"))
    if failure_codes:
        readable = [
            f"{code} ({failure_labels[index] if index < len(failure_labels) else code})"
            for index, code in enumerate(failure_codes)
        ]
        lines.append(f"- Navigation degradation reasons: `{'; '.join(readable)}`")
    transition = _dict_payload(navigation.get("calibration_transition_summary"))
    if transition:
        thresholds = _dict_payload(transition.get("approved_thresholds"))
        lines.extend(
            [
                "- Calibration continuity: "
                f"`{transition.get('status') or 'not recorded'}`; switches "
                f"`{transition.get('switch_count', 'not recorded')}`; ambiguous frames "
                f"`{transition.get('ambiguous_frame_count', 'not recorded')}`; oscillations "
                f"`{transition.get('oscillation_count', 'not recorded')}`",
                "- Magnification rate: "
                f"`{transition.get('max_magnification_rate_per_s', 'not recorded')}` / approved "
                f"`{thresholds.get('max_magnification_rate_per_s', 'not recorded')}` per second",
                "- Working-distance rate: "
                f"`{transition.get('max_working_distance_rate_mm_per_s', 'not recorded')}` / approved "
                f"`{thresholds.get('max_working_distance_rate_mm_per_s', 'not recorded')}` mm/s",
                "- Intrinsics-switch rate: "
                f"`{transition.get('max_intrinsics_switch_rate_hz_observed', 'not recorded')}` / approved "
                f"`{thresholds.get('max_intrinsics_switch_rate_hz', 'not recorded')}` Hz",
            ]
        )
    policy = _dict_payload(navigation.get("l2_threshold_policy_evidence"))
    if policy:
        lines.append(
            "- L2 safety policy: "
            f"`{policy.get('policy_id') or 'not recorded'}` / `{policy.get('policy_version') or 'not recorded'}`; "
            f"SHA256 `{policy.get('artifact_sha256') or 'not recorded'}`"
        )
    for label, path_field, sha_field in (
        ("Pose replay manifest", "pose_replay_manifest_path", "pose_replay_manifest_sha256"),
        ("Pose replay frame CSV", "pose_replay_frames_csv_path", "pose_replay_frames_csv_sha256"),
        ("AR overlay", "overlay_video_path", "overlay_video_sha256"),
    ):
        path = navigation.get(path_field)
        if path:
            lines.append(f"- {label}: `{path}`; SHA256 `{navigation.get(sha_field) or 'not recorded'}`")
    lines.append(f"- Navigation boundary: {navigation.get('medical_boundary')}")
    return lines


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
        spectrum = _dict_payload(frame.get("bone_activity_spectrum"))
        if spectrum:
            lines.append(
                f"  - Bone activity spectrum: status `{spectrum.get('status') or 'not recorded'}`, "
                f"calibration `{spectrum.get('calibration_status') or 'not recorded'}`, "
                f"spatial candidates applied `{bool(spectrum.get('spatial_effect_applied'))}`"
            )
            candidates = _dict_payload(spectrum.get("candidates"))
            for key in (
                "low_activity_candidate",
                "transition_candidate",
                "high_activity_candidate",
                "ignore_region",
            ):
                candidate = _dict_payload(candidates.get(key))
                source_summary = _activity_source_summary(candidate.get("sources"))
                lines.append(
                    f"  - {candidate.get('label') or key}: area `{candidate.get('positive_area_px') if candidate.get('positive_area_px') is not None else 'not available'}` px, "
                    f"reviewed bone fraction `{candidate.get('bone_gate_fraction') if candidate.get('bone_gate_fraction') is not None else 'not available'}`, "
                    f"mask `{candidate.get('path') or 'not available'}`, "
                    f"SHA256 `{candidate.get('sha256') or 'not available'}`, "
                    f"sources `{source_summary or 'not recorded'}`"
                )
            if spectrum.get("confidence_statement"):
                lines.append(f"  - Confidence boundary: {spectrum.get('confidence_statement')}")
            if spectrum.get("medical_boundary"):
                lines.append(f"  - Activity safety boundary: {spectrum.get('medical_boundary')}")
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
    signal_masks = _dict_payload(signal_masks)
    risk_mask = _dict_payload(signal_masks.get("risk_mask"))
    uncertain_mask = _dict_payload(signal_masks.get("uncertain_mask"))
    bone_gate = _dict_payload(signal_masks.get("bone_gate_mask"))
    spectrum = _dict_payload(signal_masks.get("bone_activity_spectrum"))
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
        "bone_activity_spectrum": _bone_activity_spectrum_summary(spectrum),
    }


def _bone_activity_spectrum_summary(spectrum: dict[str, Any]) -> dict[str, Any]:
    candidates: dict[str, Any] = {}
    for key in (
        "low_activity_candidate",
        "transition_candidate",
        "high_activity_candidate",
        "ignore_region",
    ):
        item = _dict_payload(spectrum.get(key))
        candidates[key] = {
            "available": bool(item.get("available")),
            "label": item.get("label"),
            "positive_area_px": item.get("positive_area_px"),
            "bone_gate_fraction": item.get("bone_gate_fraction"),
            "path": item.get("path"),
            "sha256": item.get("sha256"),
            "sources": _list_payload(item.get("sources")),
        }
    return {
        "available": bool(spectrum.get("available")),
        "status": spectrum.get("status") or "not_recorded",
        "activity_score": _dict_payload(spectrum.get("activity_score")),
        "activity_class_map_path": spectrum.get("activity_class_map_path"),
        "thresholds": _dict_payload(spectrum.get("thresholds")),
        "candidates": candidates,
        "calibration_status": spectrum.get("calibration_status") or "not_recorded",
        "spatial_effect_applied": bool(spectrum.get("spatial_effect_applied")),
        "review_required": spectrum.get("review_required", True),
        "confidence_statement": spectrum.get("confidence_statement"),
        "medical_boundary": spectrum.get("medical_boundary"),
    }


def _activity_source_summary(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    values: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            values.append(item)
        elif isinstance(item, dict) and item.get("source_type"):
            source_type = str(item["source_type"])
            path = str(item.get("path") or "")
            checksum = str(item.get("sha256") or "")
            values.append(":".join(part for part in (source_type, path, checksum) if part))
    return " | ".join(values)
