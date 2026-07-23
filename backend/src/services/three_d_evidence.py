from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.src.domains.cases.schemas import CaseInputAsset

SCHEMA_VERSION = "osteo-vision-three-d-evidence-v2"
D024_RUNTIME_REFERENCE_DIRECTORY = "artifacts/platform/three_d_runtime/references/d024"
D024_RUNTIME_REFERENCE_MODEL_PATH = f"{D024_RUNTIME_REFERENCE_DIRECTORY}/mandible_d024_0001.stl"
D024_RUNTIME_REFERENCE_GEOMETRY_MANIFEST_PATH = (
    f"{D024_RUNTIME_REFERENCE_DIRECTORY}/mandible_d024_0001.brp_geometry_manifest.json"
)


def build_three_d_evidence(
    *,
    parameters: dict[str, Any],
    source_inputs: list[CaseInputAsset],
    analysis_mode: str,
    run_id: str,
) -> dict[str, Any]:
    """Normalize optional CBCT/STL evidence without pretending it is navigation."""
    explicit = _dict_value(parameters.get("three_d_evidence"))
    explicit = _demo_evidence(parameters) | explicit
    model_path = _string(explicit.get("model_path") or parameters.get("three_d_model_path"))
    model_format = _string(explicit.get("model_format") or parameters.get("three_d_model_format")) or _format_from_path(
        model_path
    )
    registration_status = (
        _string(explicit.get("registration_status") or parameters.get("three_d_registration_status")).lower()
        or "unregistered"
    )
    registration_error = explicit.get("registration_error_mm", parameters.get("three_d_registration_error_mm"))
    registration_error_threshold = explicit.get(
        "registration_error_threshold_mm", parameters.get("three_d_registration_error_threshold_mm")
    )
    registration_error_source = _string(
        explicit.get("registration_error_source") or parameters.get("three_d_registration_error_source")
    )
    transform_path = _string(explicit.get("transform_path") or parameters.get("three_d_transform_path"))
    transform_sha256 = _string(explicit.get("transform_sha256") or parameters.get("three_d_transform_sha256")).lower()
    transform_format = _string(explicit.get("transform_format") or parameters.get("three_d_transform_format")).lower()
    microscope_pose_evidence = _microscope_pose_evidence(explicit, parameters=parameters)
    coordinate_space = _string(explicit.get("coordinate_space") or parameters.get("three_d_coordinate_space"))
    model_coordinate_space = _string(
        explicit.get("model_coordinate_space") or parameters.get("three_d_model_coordinate_space")
    ) or coordinate_space
    dicom_series_uid = _string(explicit.get("dicom_series_uid") or parameters.get("three_d_dicom_series_uid"))
    segmentation_source = _string(explicit.get("segmentation_source") or parameters.get("three_d_segmentation_source"))
    segmentation_review_status = _string(
        explicit.get("segmentation_review_status") or parameters.get("three_d_segmentation_review_status")
    )
    markups = _list_of_dicts(explicit.get("registration_markups"))
    transform_chain = _list_of_dicts(explicit.get("transform_chain")) or _default_transform_chain(
        model_path=model_path,
        transform_path=transform_path,
        coordinate_space=coordinate_space,
        registration_status=registration_status,
    )
    transform_validation = _validate_transform_file(
        transform_path=transform_path,
        expected_sha256=transform_sha256,
        declared_format=transform_format,
    )
    coordinate_chain_validation = _validate_transform_chain(transform_chain)
    camera_calibration_evidence = _dict_value(explicit.get("camera_calibration_evidence"))
    threshold_approval = _dict_value(explicit.get("threshold_approval"))
    requested_navigation_level = _requested_navigation_level(explicit, parameters=parameters)
    navigation_safety = _navigation_safety(
        explicit,
        registration_status=registration_status,
        registration_error=registration_error,
        registration_error_threshold=registration_error_threshold,
        registration_error_source=registration_error_source,
        transform_validation=transform_validation,
        coordinate_chain_validation=coordinate_chain_validation,
        microscope=microscope_pose_evidence,
        camera_calibration_evidence=camera_calibration_evidence,
        threshold_approval=threshold_approval,
        requested_navigation_level=requested_navigation_level,
    )
    boundary_note = _string(explicit.get("boundary_note") or parameters.get("three_d_boundary_note")) or (
        "CBCT/STL evidence is optional. Without a real model, recorded coordinate transform, "
        "registration error, and physician review, the 3D panel must remain a reference layer, "
        "not intraoperative navigation or a resection boundary."
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "analysis_mode": analysis_mode,
        "model_path": model_path or None,
        "model_format": model_format or None,
        "model_file_name": _string(explicit.get("model_file_name")) or _file_name(model_path) or None,
        "model_source": _string(explicit.get("model_source"))
        or ("case_evidence_package" if model_path else "not_provided"),
        "exported_from": _string(explicit.get("exported_from")) or None,
        "dicom_series_uid": dicom_series_uid or None,
        "segmentation_source": segmentation_source or None,
        "segmentation_review_status": segmentation_review_status or None,
        "registration_status": registration_status,
        "registration_method": _string(explicit.get("registration_method")) or None,
        "registration_error_mm": _number_or_string(registration_error),
        "registration_error_threshold_mm": _number_or_string(registration_error_threshold),
        "registration_error_source": registration_error_source or None,
        "camera_registration_status": _string(explicit.get("camera_registration_status")) or None,
        "camera_intrinsics_id": _string(explicit.get("camera_intrinsics_id")) or None,
        "reprojection_error_px": _number_or_string(explicit.get("reprojection_error_px")),
        "reprojection_fit_error_px": _number_or_string(explicit.get("reprojection_fit_error_px")),
        "reprojection_error_threshold_px": _number_or_string(explicit.get("reprojection_error_threshold_px")),
        "reprojection_error_source": _string(explicit.get("reprojection_error_source")) or None,
        "camera_calibration_evidence": camera_calibration_evidence or None,
        "threshold_approval": threshold_approval or None,
        "fiducial_count": _positive_int(explicit.get("fiducial_count") or parameters.get("three_d_fiducial_count")),
        "surface_point_count": _positive_int(
            explicit.get("surface_point_count") or parameters.get("three_d_surface_point_count")
        ),
        "coordinate_space": coordinate_space or None,
        "model_coordinate_space": model_coordinate_space or None,
        "transform_path": transform_path or None,
        "transform_sha256": transform_validation.get("sha256"),
        "transform_expected_sha256": transform_sha256 or None,
        "transform_format": transform_validation.get("format"),
        "transform_validation": transform_validation,
        "registration_markups": markups,
        "transform_chain": transform_chain,
        "coordinate_chain_validation": coordinate_chain_validation,
        "doctor_review_status": _string(explicit.get("doctor_review_status")) or "not_reviewed",
        "navigation_ready": navigation_safety["navigation_ready"],
        "navigation_level": navigation_safety["navigation_level"],
        "degradation_state": navigation_safety["degradation_state"],
        "fallback_mode": navigation_safety["fallback_mode"],
        "failure_reasons": navigation_safety["failure_reasons"],
        "requested_navigation_level": requested_navigation_level,
        "navigation_safety_gate_version": "osteo-vision-navigation-safety-v2",
        "microscope_pose_evidence": microscope_pose_evidence,
        "input_domain": "cbct_stl_reference_optional",
        "data_boundary": (
            "Non-target-domain or missing 3D evidence is allowed for platform validation, but it cannot be "
            "claimed as real jaw osteomyelitis intraoperative navigation."
        ),
        "source_inputs": _source_input_summary(source_inputs),
        "scene_manifest": _dict_value(explicit.get("scene_manifest")) or None,
        "scene_manifest_v2": _dict_value(explicit.get("scene_manifest_v2")) or None,
        "geometry_manifest_path": _string(explicit.get("geometry_manifest_path")) or None,
        "boundary_note": boundary_note,
    }
    return payload


def three_d_evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    payload = evidence if isinstance(evidence, dict) else {}
    return {
        "schema_version": "osteo-vision-three-d-evidence-summary-v1",
        "available": bool(payload),
        "model_available": bool(payload.get("model_path")),
        "model_file_name": payload.get("model_file_name"),
        "registration_status": payload.get("registration_status") or "not_recorded",
        "registration_error_mm": payload.get("registration_error_mm"),
        "registration_error_threshold_mm": payload.get("registration_error_threshold_mm"),
        "registration_error_source": payload.get("registration_error_source"),
        "camera_registration_status": payload.get("camera_registration_status"),
        "camera_intrinsics_id": payload.get("camera_intrinsics_id"),
        "reprojection_error_px": payload.get("reprojection_error_px"),
        "reprojection_error_threshold_px": payload.get("reprojection_error_threshold_px"),
        "camera_calibration_evidence": payload.get("camera_calibration_evidence") or {},
        "threshold_approval": payload.get("threshold_approval") or {},
        "coordinate_space": payload.get("coordinate_space"),
        "navigation_ready": bool(payload.get("navigation_ready")) is True,
        "navigation_level": payload.get("navigation_level") or "L0",
        "degradation_state": payload.get("degradation_state") or "reference_only",
        "failure_reasons": payload.get("failure_reasons") or [],
        "transform_validation": payload.get("transform_validation") or {},
        "coordinate_chain_validation": payload.get("coordinate_chain_validation") or {},
        "microscope_pose_evidence": payload.get("microscope_pose_evidence") or {},
        "doctor_review_status": payload.get("doctor_review_status") or "not_recorded",
        "boundary_note": payload.get("boundary_note"),
    }


def _default_transform_chain(
    *,
    model_path: str,
    transform_path: str,
    coordinate_space: str,
    registration_status: str,
) -> list[dict[str, Any]]:
    model_ready = bool(model_path)
    transform_ready = registration_status == "registered" and bool(transform_path)
    return [
        {
            "name": "DICOM voxel to CBCT RAS",
            "from_space": "dicom_voxel",
            "to_space": coordinate_space or "cbct_ras_unrecorded",
            "path": None,
            "status": "missing" if not coordinate_space else "recorded",
        },
        {
            "name": "CBCT segmentation to STL/GLB surface",
            "from_space": coordinate_space or "cbct_ras_unrecorded",
            "to_space": _file_name(model_path) or "surface_model_missing",
            "path": model_path or None,
            "status": "ready" if model_ready else "missing",
        },
        {
            "name": "3D reference to video keyframe evidence",
            "from_space": "surface_model",
            "to_space": "video_keyframe_reference",
            "path": transform_path or None,
            "status": "ready" if transform_ready else "missing",
        },
    ]


def _source_input_summary(inputs: list[CaseInputAsset]) -> list[dict[str, Any]]:
    return [
        {
            "input_id": item.input_id,
            "channel": item.channel.value if hasattr(item.channel, "value") else str(item.channel),
            "path": item.path,
            "mime_type": item.mime_type,
        }
        for item in inputs
    ]


def _microscope_pose_evidence(payload: dict[str, Any], *, parameters: dict[str, Any]) -> dict[str, Any]:
    source = _dict_value(payload.get("microscope_pose_evidence"))
    calibrated_range = _dict_value(source.get("calibrated_range"))
    return {
        "device_source": _string(source.get("device_source") or parameters.get("microscope_device_source")) or None,
        "device_model": _string(source.get("device_model") or parameters.get("microscope_device_model")) or None,
        "firmware": _string(source.get("firmware") or parameters.get("microscope_firmware")) or None,
        "magnification": _number_or_string(source.get("magnification") or parameters.get("microscope_magnification")),
        "calibration_magnification_min": _number_or_string(
            source.get("calibration_magnification_min")
            or calibrated_range.get("magnification_min")
            or parameters.get("microscope_calibration_magnification_min")
        ),
        "calibration_magnification_max": _number_or_string(
            source.get("calibration_magnification_max")
            or calibrated_range.get("magnification_max")
            or parameters.get("microscope_calibration_magnification_max")
        ),
        "working_distance_mm": _number_or_string(
            source.get("working_distance_mm") or parameters.get("microscope_working_distance_mm")
        ),
        "calibration_working_distance_min_mm": _number_or_string(
            source.get("calibration_working_distance_min_mm")
            or calibrated_range.get("working_distance_min_mm")
            or parameters.get("microscope_calibration_working_distance_min_mm")
        ),
        "calibration_working_distance_max_mm": _number_or_string(
            source.get("calibration_working_distance_max_mm")
            or calibrated_range.get("working_distance_max_mm")
            or parameters.get("microscope_calibration_working_distance_max_mm")
        ),
        "intrinsics_id": _string(source.get("intrinsics_id") or parameters.get("microscope_intrinsics_id")) or None,
        "calibration_status": _string(source.get("calibration_status")).lower() or "not_recorded",
        "pose_tracking_status": _string(source.get("pose_tracking_status")).lower() or "not_recorded",
        "tracker_type": _string(source.get("tracker_type")) or None,
        "pose_timestamp": _string(source.get("pose_timestamp")) or None,
        "frame_timestamp": _string(source.get("frame_timestamp")) or None,
        "time_offset_ms": _number_or_string(source.get("time_offset_ms")),
        "depth_source": _string(source.get("depth_source")) or None,
        "depth_status": _string(source.get("depth_status")).lower() or "not_recorded",
        "tre_mm": _number_or_string(source.get("tre_mm")),
        "tre_threshold_mm": _number_or_string(source.get("tre_threshold_mm")),
        "drift_mm": _number_or_string(source.get("drift_mm")),
        "drift_threshold_mm": _number_or_string(source.get("drift_threshold_mm")),
    }


def _navigation_safety(
    payload: dict[str, Any],
    *,
    registration_status: str,
    registration_error: Any,
    registration_error_threshold: Any,
    registration_error_source: str,
    transform_validation: dict[str, Any],
    coordinate_chain_validation: dict[str, Any],
    microscope: dict[str, Any],
    camera_calibration_evidence: dict[str, Any],
    threshold_approval: dict[str, Any],
    requested_navigation_level: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if registration_status != "registered":
        reasons.append("registration_not_verified")
    reasons.extend(str(item) for item in transform_validation.get("failure_reasons", []))
    reasons.extend(str(item) for item in coordinate_chain_validation.get("failure_reasons", []))
    _append_registration_error_failures(
        reasons,
        value=registration_error,
        threshold=registration_error_threshold,
        source=registration_error_source,
    )
    _append_camera_calibration_failures(
        reasons,
        payload=payload,
        microscope=microscope,
        evidence=camera_calibration_evidence,
    )
    _append_threshold_approval_failures(
        reasons,
        approval=threshold_approval,
        payload=payload,
    )
    _append_range_failure(
        reasons,
        microscope,
        value_key="magnification",
        minimum_key="calibration_magnification_min",
        maximum_key="calibration_magnification_max",
        label="magnification",
    )
    _append_range_failure(
        reasons,
        microscope,
        value_key="working_distance_mm",
        minimum_key="calibration_working_distance_min_mm",
        maximum_key="calibration_working_distance_max_mm",
        label="working_distance",
    )
    if _string(payload.get("doctor_review_status")).lower() not in {"accepted", "approved"}:
        reasons.append("doctor_review_not_accepted")
    if microscope["depth_status"] not in {"valid", "verified", "available"}:
        reasons.append("depth_or_scale_source_invalid")
    if requested_navigation_level == "L2":
        if microscope["pose_tracking_status"] not in {"tracking", "valid", "synchronized"}:
            reasons.append("pose_tracking_invalid_or_missing")
        time_offset = _float_or_none(microscope.get("time_offset_ms"))
        if time_offset is None or abs(time_offset) > 50.0:
            reasons.append("frame_pose_time_sync_out_of_bounds")
        _append_threshold_failure(reasons, microscope, "tre_mm", "tre_threshold_mm", "tre")
        _append_threshold_failure(reasons, microscope, "drift_mm", "drift_threshold_mm", "drift")
    reasons = list(dict.fromkeys(reasons))
    ready = len(reasons) == 0
    return {
        "navigation_ready": ready,
        "navigation_level": requested_navigation_level if ready else "L0",
        "degradation_state": (
            "dynamic_ar_validated"
            if ready and requested_navigation_level == "L2"
            else "static_registration_validated" if ready else "safety_gate_degraded"
        ),
        "fallback_mode": None if ready else "unregistered_3d_reference",
        "failure_reasons": reasons,
    }


def _append_camera_calibration_failures(
    reasons: list[str],
    *,
    payload: dict[str, Any],
    microscope: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    validation = _dict_value(evidence.get("artifact_validation"))
    if not evidence:
        reasons.append("camera_calibration_evidence_missing")
    for reason in validation.get("failure_reasons", []):
        reasons.append(str(reason))
    if not bool(validation.get("valid")):
        reasons.append("camera_calibration_artifact_not_verified")

    if microscope["calibration_status"] not in {"verified", "accepted"}:
        reasons.append("camera_calibration_invalid_or_missing")
    if _string(payload.get("camera_registration_status")).lower() not in {
        "estimated",
        "verified",
        "accepted",
    }:
        reasons.append("camera_registration_not_verified")
    if not _string(payload.get("camera_intrinsics_id")):
        reasons.append("camera_intrinsics_id_missing")

    reprojection_error = _float_or_none(payload.get("reprojection_error_px"))
    reprojection_threshold = _float_or_none(payload.get("reprojection_error_threshold_px"))
    if reprojection_error is None or not math.isfinite(reprojection_error) or reprojection_error < 0:
        reasons.append("reprojection_error_invalid_or_missing")
    if reprojection_threshold is None or not math.isfinite(reprojection_threshold) or reprojection_threshold <= 0:
        reasons.append("reprojection_error_threshold_invalid_or_missing")
    if (
        reprojection_error is not None
        and reprojection_threshold is not None
        and math.isfinite(reprojection_error)
        and math.isfinite(reprojection_threshold)
        and reprojection_error > reprojection_threshold
    ):
        reasons.append("reprojection_error_threshold_exceeded")
    if _string(payload.get("reprojection_error_source")) != ("independent_camera_validation_points"):
        reasons.append("independent_reprojection_evidence_missing")


def _append_threshold_approval_failures(
    reasons: list[str],
    *,
    approval: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    if not approval:
        reasons.append("threshold_approval_missing")
        return
    if _string(approval.get("status")).lower() != "approved":
        reasons.append("threshold_policy_not_approved")
    for field, reason in (
        ("protocol_version", "threshold_protocol_version_missing"),
        ("data_version", "threshold_data_version_missing"),
        ("approved_by", "threshold_approver_missing"),
        ("approved_at", "threshold_approval_time_missing"),
    ):
        if not _string(approval.get(field)):
            reasons.append(reason)

    approved_at = _parse_datetime(approval.get("approved_at"))
    if _string(approval.get("approved_at")) and approved_at is None:
        reasons.append("threshold_approval_time_invalid")
    elif approved_at is not None and approved_at > datetime.now(timezone.utc):
        reasons.append("threshold_approval_time_in_future")

    expected = {
        "fre_threshold_mm": payload.get("fre_threshold_mm"),
        "tre_threshold_mm": payload.get("tre_threshold_mm"),
        "reprojection_threshold_px": payload.get("reprojection_error_threshold_px"),
    }
    for field, current_value in expected.items():
        approved_value = _float_or_none(approval.get(field))
        current = _float_or_none(current_value)
        if current is None:
            continue
        if approved_value is None:
            reasons.append(f"approved_{field}_missing")
        elif not math.isclose(approved_value, current, rel_tol=1e-9, abs_tol=1e-9):
            reasons.append(f"approved_{field}_mismatch")


def _parse_datetime(value: Any) -> datetime | None:
    text = _string(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _requested_navigation_level(payload: dict[str, Any], *, parameters: dict[str, Any]) -> str:
    value = _string(
        payload.get("requested_navigation_level")
        or payload.get("navigation_level")
        or parameters.get("three_d_navigation_level")
    ).upper()
    return value if value in {"L1", "L2"} else "L2"


def _append_registration_error_failures(reasons: list[str], *, value: Any, threshold: Any, source: str) -> None:
    parsed_value = _float_or_none(value)
    parsed_threshold = _float_or_none(threshold)
    if parsed_value is None or not math.isfinite(parsed_value) or parsed_value < 0:
        reasons.append("registration_error_invalid_or_missing")
    if parsed_threshold is None or not math.isfinite(parsed_threshold) or parsed_threshold <= 0:
        reasons.append("registration_error_threshold_invalid_or_missing")
    if not source:
        reasons.append("registration_error_source_missing")
    if (
        parsed_value is not None
        and parsed_threshold is not None
        and math.isfinite(parsed_value)
        and math.isfinite(parsed_threshold)
        and parsed_value > parsed_threshold
    ):
        reasons.append("registration_error_threshold_exceeded")


def _append_range_failure(
    reasons: list[str],
    payload: dict[str, Any],
    *,
    value_key: str,
    minimum_key: str,
    maximum_key: str,
    label: str,
) -> None:
    value = _float_or_none(payload.get(value_key))
    minimum = _float_or_none(payload.get(minimum_key))
    maximum = _float_or_none(payload.get(maximum_key))
    if value is None or not math.isfinite(value):
        reasons.append(f"{label}_not_recorded")
        return
    if minimum is None or maximum is None:
        reasons.append(f"{label}_calibration_range_missing")
        return
    if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum > maximum:
        reasons.append(f"{label}_calibration_range_invalid")
        return
    if value < minimum or value > maximum:
        reasons.append(f"{label}_out_of_calibration_range")


def _append_threshold_failure(
    reasons: list[str], payload: dict[str, Any], value_key: str, threshold_key: str, label: str
) -> None:
    value = _float_or_none(payload.get(value_key))
    threshold = _float_or_none(payload.get(threshold_key))
    if value is None or threshold is None:
        reasons.append(f"{label}_not_recorded")
    elif value > threshold:
        reasons.append(f"{label}_threshold_exceeded")


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_transform_file(*, transform_path: str, expected_sha256: str, declared_format: str) -> dict[str, Any]:
    reasons: list[str] = []
    result: dict[str, Any] = {
        "path": transform_path or None,
        "file_exists": False,
        "format": None,
        "supported_format": False,
        "sha256": None,
        "expected_sha256": expected_sha256 or None,
        "sha256_match": False,
        "matrix_shape": None,
        "matrix_finite": False,
        "matrix_invertible": False,
        "matrix_homogeneous": False,
        "valid": False,
        "failure_reasons": reasons,
    }
    if not transform_path:
        reasons.append("transform_missing")
        return result

    path = Path(transform_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    result["resolved_path"] = str(path)
    if not path.is_file():
        reasons.append("transform_file_not_found")
        return result
    result["file_exists"] = True

    actual_format = _normalize_transform_format(path.suffix.lstrip("."))
    requested_format = _normalize_transform_format(declared_format)
    transform_format = requested_format or actual_format
    result["format"] = transform_format or None
    if requested_format and actual_format and requested_format != actual_format:
        reasons.append("transform_format_mismatch")
    if transform_format not in {"json", "txt", "csv", "tfm", "npy"}:
        reasons.append("transform_format_unsupported")
        return result
    result["supported_format"] = True

    actual_sha256 = _sha256(path)
    result["sha256"] = actual_sha256
    if not expected_sha256:
        reasons.append("transform_sha256_missing")
    elif not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        reasons.append("transform_sha256_invalid")
    elif actual_sha256 != expected_sha256:
        reasons.append("transform_sha256_mismatch")
    else:
        result["sha256_match"] = True

    try:
        matrix = _load_transform_matrix(path, transform_format)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        reasons.append("transform_matrix_unreadable")
        return result

    shape = [len(matrix), len(matrix[0]) if matrix and isinstance(matrix[0], list) else 0]
    result["matrix_shape"] = shape
    if shape != [4, 4] or any(not isinstance(row, list) or len(row) != 4 for row in matrix):
        reasons.append("transform_matrix_shape_invalid")
        return result
    finite = all(math.isfinite(value) for row in matrix for value in row)
    result["matrix_finite"] = finite
    if not finite:
        reasons.append("transform_matrix_non_finite")
        return result
    homogeneous = all(abs(matrix[3][index] - expected) <= 1e-9 for index, expected in enumerate([0, 0, 0, 1]))
    result["matrix_homogeneous"] = homogeneous
    if not homogeneous:
        reasons.append("transform_matrix_not_homogeneous")
    invertible = abs(_determinant(matrix)) > 1e-12
    result["matrix_invertible"] = invertible
    if not invertible:
        reasons.append("transform_matrix_not_invertible")
    result["valid"] = not reasons
    return result


def _normalize_transform_format(value: str) -> str:
    normalized = _string(value).lower().lstrip(".")
    return {"itk": "tfm", "itk_tfm": "tfm", "numpy": "npy"}.get(normalized, normalized)


def _load_transform_matrix(path: Path, transform_format: str) -> list[list[float]]:
    if transform_format == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("matrix") or payload.get("transform_matrix") or payload.get("affine")
        return _coerce_matrix(payload)
    if transform_format == "csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = [[float(value) for value in row if value.strip()] for row in csv.reader(handle)]
        return _coerce_matrix(rows)
    if transform_format == "txt":
        return _matrix_from_numeric_text(path.read_text(encoding="utf-8-sig"))
    if transform_format == "tfm":
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"^Parameters:\s*(.+)$", text, flags=re.MULTILINE)
        if match:
            values = [float(value) for value in match.group(1).split()]
            if len(values) == 12:
                return [values[0:3] + [values[9]], values[3:6] + [values[10]], values[6:9] + [values[11]], [0, 0, 0, 1]]
            if len(values) == 16:
                return [values[index : index + 4] for index in range(0, 16, 4)]
        return _matrix_from_numeric_text(text)
    if transform_format == "npy":
        import numpy as np

        return _coerce_matrix(np.load(path, allow_pickle=False).tolist())
    raise ValueError(f"Unsupported transform format: {transform_format}")


def _matrix_from_numeric_text(value: str) -> list[list[float]]:
    numbers = [float(item) for item in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", value)]
    if len(numbers) != 16:
        raise ValueError("Expected 16 matrix values")
    return [numbers[index : index + 4] for index in range(0, 16, 4)]


def _coerce_matrix(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        raise ValueError("Matrix must be a list")
    if len(value) == 16 and not any(isinstance(item, list) for item in value):
        values = [float(item) for item in value]
        return [values[index : index + 4] for index in range(0, 16, 4)]
    return [[float(item) for item in row] for row in value if isinstance(row, list)]


def _determinant(matrix: list[list[float]]) -> float:
    work = [row[:] for row in matrix]
    determinant = 1.0
    for column in range(4):
        pivot = max(range(column, 4), key=lambda row: abs(work[row][column]))
        if abs(work[pivot][column]) <= 1e-15:
            return 0.0
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            determinant *= -1.0
        pivot_value = work[column][column]
        determinant *= pivot_value
        for row in range(column + 1, 4):
            factor = work[row][column] / pivot_value
            for item in range(column + 1, 4):
                work[row][item] -= factor * work[column][item]
    return determinant


def _validate_transform_chain(chain: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    if not chain:
        reasons.append("coordinate_chain_missing")
        return {"valid": False, "step_count": 0, "failure_reasons": reasons}

    normalized_steps: list[dict[str, str]] = []
    for step in chain:
        from_space = _string(step.get("from_space"))
        to_space = _string(step.get("to_space"))
        direction = _string(step.get("direction")).lower()
        shared_unit = _normalize_unit(step.get("unit"))
        from_unit = _normalize_unit(step.get("from_unit")) or shared_unit
        to_unit = _normalize_unit(step.get("to_unit")) or shared_unit
        status = _string(step.get("status")).lower()
        if not from_space or not to_space:
            reasons.append("coordinate_chain_space_missing")
        if not direction:
            reasons.append("coordinate_chain_direction_missing")
        elif direction not in {"forward", "from_to"}:
            reasons.append("coordinate_chain_direction_invalid")
        if not from_unit or not to_unit:
            reasons.append("coordinate_chain_unit_missing")
        if from_unit and to_unit and from_unit != to_unit and not bool(step.get("unit_conversion_recorded")):
            reasons.append("coordinate_chain_unit_conversion_missing")
        if status not in {"ready", "verified", "accepted"}:
            reasons.append("coordinate_chain_step_not_ready")
        normalized_steps.append(
            {
                "from_space": from_space,
                "to_space": to_space,
                "direction": direction,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "status": status,
            }
        )

    for previous, current in zip(normalized_steps, normalized_steps[1:]):
        if previous["to_space"] and current["from_space"] and previous["to_space"] != current["from_space"]:
            reasons.append("coordinate_chain_discontinuous")
        if previous["to_unit"] and current["from_unit"] and previous["to_unit"] != current["from_unit"]:
            reasons.append("coordinate_chain_unit_discontinuous")

    reasons = list(dict.fromkeys(reasons))
    return {
        "valid": not reasons,
        "step_count": len(chain),
        "normalized_steps": normalized_steps,
        "failure_reasons": reasons,
    }


def _normalize_unit(value: Any) -> str:
    normalized = _string(value).lower().replace(" ", "_")
    return {
        "millimeter": "mm",
        "millimeters": "mm",
        "millimetre": "mm",
        "millimetres": "mm",
        "centimeter": "cm",
        "centimeters": "cm",
        "pixel": "px",
        "pixels": "px",
    }.get(normalized, normalized)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _demo_evidence(parameters: dict[str, Any]) -> dict[str, Any]:
    demo = _string(parameters.get("three_d_evidence_demo")).lower()
    if demo not in {"d024", "d024_mandible", "d024_mandible_surface"}:
        return {}
    model_path = D024_RUNTIME_REFERENCE_MODEL_PATH
    boundary = (
        "D024 DentVoxel public CBCT-derived mandible surface; non-target-domain anatomy reference only. "
        "It is not a real jaw osteomyelitis intraoperative ICG case, not registered to video, and not surgical navigation."
    )
    return {
        "model_path": model_path,
        "model_format": "stl",
        "model_file_name": "mandible_d024_0001.stl",
        "model_source": "D024 DentVoxel public CBCT derived mandible label",
        "exported_from": "scripts/export_cbct_mandible_surface.py marching_cubes",
        "segmentation_source": "D024 DentVoxel label value 2 mandible",
        "segmentation_review_status": "public_dataset_annotation_not_case_reviewed",
        "registration_status": "unregistered",
        "coordinate_space": "cbct_label_voxel_spacing_mm",
        "doctor_review_status": "not_reviewed",
        "navigation_ready": False,
        "scene_manifest": _demo_scene_manifest(),
        "scene_manifest_v2": _demo_scene_manifest_v2(),
        "geometry_manifest_path": D024_RUNTIME_REFERENCE_GEOMETRY_MANIFEST_PATH,
        "boundary_note": boundary,
    }


def _demo_scene_manifest() -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-three-d-scene-v1",
        "source_project": "SlicerBoneReconstructionPlanner-inspired scene semantics",
        "scene_id": "d024_mandible_reference_scene",
        "coordinate_space": "cbct_label_voxel_spacing_mm",
        "mandibular_curve": {
            "id": "d024_mandibular_reference_curve",
            "label": "D024 mandibular reference curve",
            "source": "derived from STL manifest for display; not physician markups",
            "display_points": [
                [-1.9, 0.02, -0.08],
                [-1.42, -0.12, 0.16],
                [-0.72, -0.28, 0.34],
                [0.0, -0.36, 0.42],
                [0.72, -0.28, 0.34],
                [1.42, -0.12, 0.16],
                [1.9, 0.02, -0.08],
            ],
        },
        "review_planes": [
            {
                "id": "d024_review_plane_left",
                "label": "Reference review plane left",
                "display_position": [-0.95, 0.18, 0.12],
                "display_rotation": [0.0, 1.44, -0.16],
                "display_scale": [1.0, 1.85, 1.0],
                "status": "illustrative_unregistered",
            },
            {
                "id": "d024_review_plane_mid",
                "label": "Reference review plane middle",
                "display_position": [0.0, 0.21, 0.12],
                "display_rotation": [0.0, 1.57, 0.0],
                "display_scale": [1.0, 1.85, 1.0],
                "status": "illustrative_unregistered",
            },
            {
                "id": "d024_review_plane_right",
                "label": "Reference review plane right",
                "display_position": [0.95, 0.24, 0.12],
                "display_rotation": [0.0, 1.70, 0.16],
                "display_scale": [1.0, 1.85, 1.0],
                "status": "illustrative_unregistered",
            },
        ],
        "fibula_reference": {
            "label": "BRP fibula line and miter boxes reference",
            "display_curve": [
                [-1.92, -1.34, -0.26],
                [-0.72, -1.24, -0.18],
                [0.62, -1.28, -0.10],
                [1.84, -1.36, -0.20],
            ],
            "segment_lengths_mm": [29.49, 28.95],
        },
    }


def _demo_scene_manifest_v2() -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-three-d-scene-v2",
        "source_project": "3D Slicer MRML and SlicerBoneReconstructionPlanner-inspired evidence scene",
        "case_id": "d024_0001",
        "dataset_id": "D024",
        "scene_id": "d024_mandible_slicer_like_scene",
        "scene": {
            "coordinate_space": "cbct_label_voxel_spacing_mm",
            "registration_status": "unregistered",
            "registration_error_mm": None,
            "navigation_ready": False,
            "doctor_review_status": "not_reviewed",
        },
        "subject_hierarchy": [
            {"id": "case_root", "name": "病例 / 体数据", "children": ["d024_label_volume"]},
            {
                "id": "segmentation_models",
                "name": "分割 / 模型",
                "children": ["d024_mandible_segmentation", "d024_mandible_surface"],
            },
            {
                "id": "markups_review",
                "name": "标注 / 平面",
                "children": ["d024_mandibular_reference_curve", "d024_review_plane_left"],
            },
            {"id": "geometry_jobs", "name": "几何任务", "children": ["d024_surface_export_job"]},
        ],
        "nodes": [
            {
                "id": "d024_label_volume",
                "type": "volume",
                "role": "source_cbct_label_volume",
                "name": "D024 label volume",
                "source": "D024 DentVoxel nnU-Net preprocessed jaw ROI labels",
                "review_status": "public_dataset_annotation_not_case_reviewed",
            },
            {
                "id": "d024_mandible_segmentation",
                "type": "segmentation",
                "role": "mandible_label",
                "name": "D024 mandible label",
                "source": "label value 2",
                "review_status": "public_dataset_annotation_not_case_reviewed",
            },
            {
                "id": "d024_mandible_surface",
                "type": "model",
                "role": "cbct_derived_mandible_surface",
                "name": "mandible_d024_0001.stl",
                "path": D024_RUNTIME_REFERENCE_MODEL_PATH,
                "format": "stl",
                "source": "marching_cubes from mandible label",
                "review_status": "reference_only_not_physician_reviewed",
            },
        ],
        "markups": [
            {
                "id": "d024_mandibular_reference_curve",
                "type": "curve",
                "role": "mandibular_reference_curve",
                "name": "D024 mandibular reference curve",
                "review_status": "illustrative_not_physician_reviewed",
            },
            {
                "id": "d024_review_plane_left",
                "type": "plane",
                "role": "review_plane",
                "name": "Reference review plane left",
                "review_status": "illustrative_unregistered",
            },
        ],
        "transforms": [
            {
                "id": "surface_to_video",
                "type": "cross_modal_registration",
                "from_node": "d024_mandible_surface",
                "to_node": "fluorescence_video_keyframes",
                "status": "missing",
                "error_mm": None,
            }
        ],
        "geometry_jobs": [{"id": "d024_surface_export_job", "type": "surface_export", "status": "completed"}],
        "review_state": {
            "segmentation": "public_dataset_annotation_not_case_reviewed",
            "model": "reference_only_not_physician_reviewed",
            "markups": "illustrative_not_physician_reviewed",
            "fluorescence_video_mapping": "missing_registration",
        },
        "data_boundary": (
            "D024 DentVoxel public CBCT-derived mandible surface; non-target-domain anatomy reference only. "
            "It is not a real jaw osteomyelitis intraoperative ICG case, not registered to video, and not surgical navigation."
        ),
    }


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else ""


def _file_name(path: str) -> str:
    return Path(path).name if path else ""


def _format_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".") if path else ""
    return suffix if suffix in {"stl", "glb", "gltf", "obj", "ply"} else ""


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _number_or_string(value: Any) -> float | str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _string(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return text
