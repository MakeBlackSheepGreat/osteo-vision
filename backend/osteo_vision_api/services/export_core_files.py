from __future__ import annotations

import json
from typing import Any

from backend.osteo_vision_api.core.disclaimers import disclaimer_context
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord, ExportRequest
from backend.osteo_vision_api.reports.dicom_secondary_capture import write_secondary_capture_dicom
from backend.osteo_vision_api.reports.platform_markdown import build_platform_markdown
from backend.osteo_vision_api.reports.platform_report import build_platform_report
from backend.osteo_vision_api.reports.platform_report_sections import (
    clinical_feature_vector_from_payload,
    three_d_navigation_evidence_summary,
)
from backend.osteo_vision_api.reports.quantification_csv import write_quantification_csv
from backend.osteo_vision_api.services.export_bundle import ExportPaths
from backend.osteo_vision_api.services.review_manifest import REVIEW_MANIFEST_FIELDS, build_review_manifest
from osteo_vision_core.reports.writers import write_csv, write_json


def write_core_export_files(
    case: CaseRecord,
    request: ExportRequest,
    paths: ExportPaths,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    # 核心报告、复核清单和定量 CSV 先落盘，再统一进入 ZIP 与 manifest。
    report = build_platform_report(
        case,
        export_meta={
            "export_format": request.export_format,
            "selected_artifacts": request.selected_artifacts,
            **disclaimer_context(),
        },
    )
    write_json(paths.report_json, report)
    paths.report_md.write_text(build_platform_markdown(case, report), encoding="utf-8")
    write_secondary_capture_dicom(paths.dicom, case, report)
    review_manifest, review_rows = build_review_manifest(case)
    write_json(paths.review_manifest_json, review_manifest)
    write_csv(paths.review_manifest_csv, review_rows, REVIEW_MANIFEST_FIELDS)
    write_json(paths.three_d_scene_manifest, _three_d_scene_manifest_payload(case))
    quant_rows = _quantification_rows(case)
    write_quantification_csv(paths.quantification_csv, quant_rows)
    return report, quant_rows, review_rows


def _three_d_scene_manifest_payload(case: CaseRecord) -> dict[str, Any]:
    latest_run = case.analysis_runs[-1] if case.analysis_runs else None
    fused_outputs = latest_run.fused_outputs if latest_run is not None else {}
    evidence_value = fused_outputs.get("three_d_evidence")
    evidence = dict(evidence_value) if isinstance(evidence_value, dict) else {}
    case_evidence = case.three_d_evidence
    if isinstance(case_evidence, dict) and case_evidence:
        evidence = {**evidence, **case_evidence}
    scene_manifest_value = evidence.get("scene_manifest_v2")
    scene_manifest_v2 = dict(scene_manifest_value) if isinstance(scene_manifest_value, dict) else {}
    navigation_evidence = three_d_navigation_evidence_summary(evidence)
    if scene_manifest_v2 or navigation_evidence.get("available"):
        return {
            "schema_version": "osteo-vision-exported-three-d-evidence-manifest-v2",
            "case_id": case.case_id,
            "run_id": evidence.get("run_id"),
            "modeling_job_id": case.three_d_modeling.get("job_id"),
            "available": True,
            "scene_available": bool(scene_manifest_v2),
            "navigation_evidence_available": bool(navigation_evidence.get("available")),
            "scene_manifest_v2": scene_manifest_v2 or None,
            "navigation_evidence": navigation_evidence,
            "three_d_evidence_boundary": evidence.get("boundary_note") or evidence.get("data_boundary"),
        }
    return {
        "schema_version": "osteo-vision-exported-three-d-evidence-manifest-v2",
        "case_id": case.case_id,
        "run_id": latest_run.run_id if latest_run is not None else None,
        "available": False,
        "scene_available": False,
        "navigation_evidence_available": False,
        "scene_manifest_v2": None,
        "navigation_evidence": navigation_evidence,
        "three_d_evidence_boundary": (
            "No Slicer-like CBCT/STL scene graph is attached. The exported 3D layer remains unavailable for "
            "navigation and can only be reconstructed after CBCT/STL import and modeling."
        ),
    }


def _quantification_rows(case: CaseRecord) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in case.analysis_runs:
        quant = run.quantitative_summary or {}
        parameters = run.parameters if isinstance(run.parameters, dict) else {}
        clinical_quality = parameters.get("clinical_context_quality")
        clinical_quality = clinical_quality if isinstance(clinical_quality, dict) else {}
        calibration = parameters.get("calibration_evidence")
        calibration = calibration if isinstance(calibration, dict) else {}
        clinical_fields = {
            "clinical_context_revision": parameters.get("clinical_context_revision"),
            "clinical_context_checksum": parameters.get("clinical_context_checksum"),
            "clinical_context_quality_status": clinical_quality.get("status"),
            "clinical_calibration_applied": calibration.get("applied", False),
            "clinical_calibration_status": calibration.get("status"),
            "clinical_spatial_effect_applied": parameters.get("spatial_effect_applied", False),
        }
        rows.append(
            {
                "case_id": case.case_id,
                "run_id": run.run_id,
                "roi_id": "",
                **quant,
                "review_state": case.status,
                "record_type": "analysis_summary",
                **clinical_fields,
            }
        )
        patient_conditioning = _patient_conditioning_evidence(run.fused_outputs)
        if patient_conditioning:
            patient_quantification = patient_conditioning.get("quantification")
            patient_quantification = patient_quantification if isinstance(patient_quantification, dict) else {}
            reviewed_gate = patient_conditioning.get("reviewed_bone_gate")
            reviewed_gate = reviewed_gate if isinstance(reviewed_gate, dict) else {}
            clinical_feature_vector = clinical_feature_vector_from_payload(patient_conditioning)
            rows.append(
                {
                    "case_id": case.case_id,
                    "run_id": run.run_id,
                    "roi_id": "",
                    "threshold": patient_conditioning.get("threshold"),
                    "positive_area_px": patient_quantification.get("positive_area_px"),
                    "positive_area_fraction": patient_quantification.get("positive_area_fraction"),
                    "review_state": case.status,
                    "record_type": "patient_conditioning_summary",
                    "spatial_effect_applied": patient_conditioning.get("spatial_effect_applied", False),
                    "medical_boundary": patient_conditioning.get("medical_boundary"),
                    "patient_conditioned_model_id": patient_conditioning.get("model_id"),
                    "patient_conditioning_available": patient_conditioning.get("available", False),
                    "patient_conditioning_proxy_checkpoint": patient_conditioning.get("proxy_checkpoint", False),
                    "patient_conditioning_safe_fallback": patient_conditioning.get("safe_fallback_applied", True),
                    "patient_conditioning_target_domain_promotion_ready": patient_conditioning.get(
                        "target_domain_promotion_ready", False
                    ),
                    "patient_conditioning_runtime_replacement_allowed": patient_conditioning.get(
                        "runtime_replacement_allowed", False
                    ),
                    "patient_conditioning_feature_present_fraction": patient_conditioning.get(
                        "clinical_present_fraction"
                    ),
                    "patient_conditioning_difference_area_px": patient_quantification.get("difference_area_px"),
                    "patient_conditioning_spatial_effect_area_px": patient_quantification.get("spatial_effect_area_px"),
                    "patient_conditioning_delta_abs_mean": patient_quantification.get("delta_abs_mean"),
                    "patient_conditioning_uncertainty_mean": patient_quantification.get("uncertainty_mean"),
                    "patient_conditioning_failure_reasons": "|".join(
                        str(item) for item in patient_conditioning.get("failure_reasons") or []
                    ),
                    "patient_conditioning_reviewed_bone_gate_sha256": reviewed_gate.get("sha256"),
                    "patient_conditioning_evidence_manifest_path": patient_conditioning.get("evidence_manifest_path"),
                    "clinical_feature_vector_schema_version": clinical_feature_vector.get("schema_version"),
                    "clinical_feature_vector_feature_version": clinical_feature_vector.get("feature_version"),
                    "clinical_feature_vector_feature_names": _json_csv_value(
                        clinical_feature_vector.get("feature_names")
                    ),
                    "clinical_feature_vector_present_mask": _json_csv_value(
                        clinical_feature_vector.get("present_mask")
                    ),
                    "clinical_feature_vector_missing_mask": _json_csv_value(
                        clinical_feature_vector.get("missing_mask")
                    ),
                    "clinical_feature_vector_ood_mask": _json_csv_value(clinical_feature_vector.get("ood_mask")),
                    "clinical_feature_vector_checkpoint_consumed_mask": _json_csv_value(
                        clinical_feature_vector.get("checkpoint_consumed_mask")
                    ),
                    "clinical_feature_vector_spatial_effect_applied_mask": _json_csv_value(
                        clinical_feature_vector.get("spatial_effect_applied_mask")
                    ),
                    "clinical_feature_vector_recorded_input_summary": _json_csv_value(
                        clinical_feature_vector.get("recorded_input_summary")
                    ),
                    "clinical_feature_vector_checkpoint_consumed_feature_names": _json_csv_value(
                        clinical_feature_vector.get("checkpoint_consumed_feature_names")
                    ),
                    "clinical_feature_vector_spatially_applied_feature_names": _json_csv_value(
                        clinical_feature_vector.get("spatially_applied_feature_names")
                    ),
                    "clinical_feature_vector_missing_feature_names": _json_csv_value(
                        clinical_feature_vector.get("missing_feature_names")
                    ),
                    "clinical_feature_vector_ood_feature_names": _json_csv_value(
                        clinical_feature_vector.get("ood_feature_names")
                    ),
                    "clinical_feature_vector_unconsumed_recorded_inputs": _json_csv_value(
                        clinical_feature_vector.get("unconsumed_recorded_inputs")
                    ),
                    "clinical_feature_vector_vector_checksum": clinical_feature_vector.get("vector_checksum"),
                    "clinical_feature_vector_runtime_vector_checksum": clinical_feature_vector.get(
                        "runtime_vector_checksum"
                    ),
                    **clinical_fields,
                }
            )
        bone_activity = _bone_activity_checkpoint_evidence(run.fused_outputs)
        if bone_activity:
            raw_value = bone_activity.get("raw_engineering_outputs")
            raw = dict(raw_value) if isinstance(raw_value, dict) else {}
            registration_value = bone_activity.get("registration_evidence")
            registration = dict(registration_value) if isinstance(registration_value, dict) else {}
            selection_value = bone_activity.get("reviewed_bone_gate_selection")
            selection = dict(selection_value) if isinstance(selection_value, dict) else {}
            target_gate_value = bone_activity.get("target_domain_input_gate")
            target_gate = dict(target_gate_value) if isinstance(target_gate_value, dict) else {}
            rows.append(
                {
                    "case_id": case.case_id,
                    "run_id": run.run_id,
                    "roi_id": "",
                    "review_state": case.status,
                    "record_type": "bone_activity_checkpoint_engineering_evidence",
                    "spatial_effect_applied": bone_activity.get("spatial_effect_applied", False),
                    "medical_boundary": bone_activity.get("medical_boundary"),
                    "bone_activity_evidence_type": "checkpoint_engineering_evidence",
                    "bone_activity_model_id": bone_activity.get("model_id"),
                    "bone_activity_model_family": bone_activity.get("model_family"),
                    "bone_activity_input_domain": bone_activity.get("input_domain"),
                    "bone_activity_execution_state": bone_activity.get("execution_state"),
                    "bone_activity_engineering_inference_executed": bone_activity.get(
                        "engineering_inference_executed", False
                    ),
                    "bone_activity_proxy_checkpoint": bone_activity.get("proxy_checkpoint", False),
                    "bone_activity_engineering_ready": bone_activity.get("engineering_ready", False),
                    "bone_activity_engineering_utility_ready": bone_activity.get("engineering_utility_ready", False),
                    "bone_activity_spatial_candidates_available": bone_activity.get(
                        "spatial_candidates_available", False
                    ),
                    "bone_activity_spatial_effect_applied": bone_activity.get("spatial_effect_applied", False),
                    "bone_activity_safe_fallback_applied": bone_activity.get("safe_fallback_applied", True),
                    "bone_activity_target_domain_promotion_ready": bone_activity.get(
                        "target_domain_promotion_ready", False
                    ),
                    "bone_activity_runtime_replacement_allowed": bone_activity.get(
                        "runtime_replacement_allowed", False
                    ),
                    "bone_activity_checkpoint_sha256": bone_activity.get("checkpoint_sha256"),
                    "bone_activity_manifest_sha256": bone_activity.get("manifest_sha256"),
                    "bone_activity_raw_engineering_outputs_path": raw.get("path"),
                    "bone_activity_raw_engineering_outputs_sha256": raw.get("sha256"),
                    "bone_activity_raw_spatial_use_allowed": raw.get("spatial_use_allowed", False),
                    "bone_activity_evidence_manifest_path": bone_activity.get("evidence_manifest_path"),
                    "bone_activity_evidence_manifest_sha256": bone_activity.get("evidence_manifest_sha256"),
                    "bone_activity_registration_verified": registration.get("applied", False),
                    "bone_activity_reviewed_bone_gate_status": selection.get("status"),
                    "bone_activity_target_domain_input_verified": target_gate.get("verified", False),
                    "bone_activity_failure_reasons": "|".join(
                        str(item) for item in bone_activity.get("failure_reasons") or []
                    ),
                    **clinical_fields,
                }
            )
        frame_details = run.fused_outputs.get("frame_details") if isinstance(run.fused_outputs, dict) else []
        for frame in frame_details if isinstance(frame_details, list) else []:
            if not isinstance(frame, dict):
                continue
            signal = frame.get("video_signal_segmentation") or frame.get("signal_masks")
            spectrum = signal.get("bone_activity_spectrum") if isinstance(signal, dict) else None
            if not isinstance(spectrum, dict):
                continue
            for activity_class in (
                "low_activity_candidate",
                "transition_candidate",
                "high_activity_candidate",
                "ignore_region",
            ):
                candidate = spectrum.get(activity_class)
                candidate = candidate if isinstance(candidate, dict) else {}
                rows.append(
                    {
                        "case_id": case.case_id,
                        "run_id": run.run_id,
                        "roi_id": "",
                        "positive_area_px": candidate.get("positive_area_px"),
                        "review_state": case.status,
                        "record_type": "bone_activity_candidate",
                        "frame_index": frame.get("frame_index"),
                        "timestamp_sec": frame.get("timestamp_sec"),
                        "activity_class": activity_class,
                        "activity_label": candidate.get("label"),
                        "bone_gate_fraction": candidate.get("bone_gate_fraction"),
                        "activity_mask_sha256": candidate.get("sha256"),
                        "activity_sources": "|".join(_activity_source_names(candidate.get("sources"))),
                        "activity_status": spectrum.get("status"),
                        "calibration_status": spectrum.get("calibration_status"),
                        "spatial_effect_applied": spectrum.get("spatial_effect_applied"),
                        "review_required": spectrum.get("review_required"),
                        "confidence_boundary": spectrum.get("confidence_statement"),
                        "medical_boundary": spectrum.get("medical_boundary"),
                        **clinical_fields,
                    }
                )
    return rows


def _patient_conditioning_evidence(fused_outputs: Any) -> dict[str, Any]:
    fused = fused_outputs if isinstance(fused_outputs, dict) else {}
    evidence = fused.get("patient_conditioning_evidence")
    if not isinstance(evidence, dict):
        return {}
    prediction_value = evidence.get("prediction")
    prediction = dict(prediction_value) if isinstance(prediction_value, dict) else {}
    return {**prediction, **evidence}


def _bone_activity_checkpoint_evidence(fused_outputs: Any) -> dict[str, Any]:
    fused = fused_outputs if isinstance(fused_outputs, dict) else {}
    evidence = fused.get("bone_activity_checkpoint_evidence")
    return dict(evidence) if isinstance(evidence, dict) else {}


def _activity_source_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            names.append(item)
        elif isinstance(item, dict) and item.get("source_type"):
            names.append(str(item["source_type"]))
    return names


def _json_csv_value(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
