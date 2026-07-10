from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.src.domains.cases.schemas import CaseInputAsset

SCHEMA_VERSION = "osteo-vision-three-d-evidence-v1"


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
    navigation_ready = _navigation_ready(explicit, registration_status=registration_status)
    registration_error = explicit.get("registration_error_mm", parameters.get("three_d_registration_error_mm"))
    transform_path = _string(explicit.get("transform_path") or parameters.get("three_d_transform_path"))
    coordinate_space = _string(explicit.get("coordinate_space") or parameters.get("three_d_coordinate_space"))
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
        "fiducial_count": _positive_int(explicit.get("fiducial_count") or parameters.get("three_d_fiducial_count")),
        "surface_point_count": _positive_int(
            explicit.get("surface_point_count") or parameters.get("three_d_surface_point_count")
        ),
        "coordinate_space": coordinate_space or None,
        "transform_path": transform_path or None,
        "registration_markups": markups,
        "transform_chain": transform_chain,
        "doctor_review_status": _string(explicit.get("doctor_review_status")) or "not_reviewed",
        "navigation_ready": navigation_ready,
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
        "coordinate_space": payload.get("coordinate_space"),
        "navigation_ready": bool(payload.get("navigation_ready")) is True,
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


def _navigation_ready(payload: dict[str, Any], *, registration_status: str) -> bool:
    raw = payload.get("navigation_ready")
    if isinstance(raw, bool):
        return raw and registration_status == "registered"
    if isinstance(raw, str):
        return raw.strip().lower() in {"true", "yes", "ready", "1"} and registration_status == "registered"
    return False


def _demo_evidence(parameters: dict[str, Any]) -> dict[str, Any]:
    demo = _string(parameters.get("three_d_evidence_demo")).lower()
    if demo not in {"d024", "d024_mandible", "d024_mandible_surface"}:
        return {}
    model_path = "frontend/public/models/local/mandible_d024_0001.stl"
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
        "geometry_manifest_path": "frontend/public/models/local/mandible_d024_0001.brp_geometry_manifest.json",
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
                "path": "frontend/public/models/local/mandible_d024_0001.stl",
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
