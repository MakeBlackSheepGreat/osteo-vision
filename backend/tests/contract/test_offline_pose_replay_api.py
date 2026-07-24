from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import backend.osteo_vision_api.services.offline_pose_replay_service as replay_service_module
from backend.osteo_vision_api.api.app import create_app

TOKEN = "physician-pose-review-token-001"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
REVIEW_ACTOR = {
    "actor_id": "doctor-pose-001",
    "role": "physician",
    "institution": "Example Stomatology Hospital",
    "auth_source": "verified_identity_token",
}
MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}


def _frame(name: str, *, axis_convention: str, source: str) -> dict[str, Any]:
    return {
        "name": name,
        "handedness": "right_handed",
        "axis_convention": axis_convention,
        "unit": "mm",
        "source": source,
    }


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_JOB_STORE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv(
        "OSTEO_REVIEW_IDENTITIES_JSON",
        json.dumps({TOKEN: REVIEW_ACTOR}),
    )
    return TestClient(create_app())


def _write_test_mp4(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (1280, 720),
    )
    assert writer.isOpened()
    for index in range(3):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[:, :, 1] = 35 + index * 45
        cv2.circle(frame, (640 + index * 4, 360), 70, (20, 180, 240), -1)
        writer.write(frame)
    writer.release()
    payload = path.read_bytes()
    assert payload
    return payload


def _upload_mp4(client: TestClient, tmp_path: Path) -> dict[str, Any]:
    payload = _write_test_mp4(tmp_path / "source" / "l2_phantom.mp4")
    response = client.post(
        "/uploads/raw?keyframe_mode=none",
        content=payload,
        headers={"content-type": "video/mp4", "x-filename": "l2_phantom.mp4"},
    )
    assert response.status_code == 200
    uploaded = response.json()
    assert uploaded["sha256"] == hashlib.sha256(payload).hexdigest()
    return uploaded


def _admit_video(
    client: TestClient,
    tmp_path: Path,
) -> tuple[str, str, str, Path]:
    uploaded = _upload_mp4(client, tmp_path)
    response = client.post(
        "/hospital-intake/batches",
        json={
            "batch_id": "l2-batch-001",
            "handover_id": "l2-handover-001",
            "source_organization": "Example Stomatology Hospital",
            "received_by": "project_receiver",
            "received_at": datetime.now(timezone.utc).isoformat(),
            "authorization_status": "approved",
            "usage_scope": "offline_dynamic_ar_engineering_validation",
            "deidentification_confirmed": True,
            "deidentification_method": "institutional export review",
            "mapping_held_by_institution": True,
            "target_condition_confirmed": False,
            "files": [
                {
                    "external_case_id": "L2_CASE_001",
                    "path": uploaded["path"],
                    "channel": "video",
                    "acquisition_mode": "mode_switching",
                    "channel_relationship": "single_channel",
                    "original_filename": uploaded["original_filename"],
                    "metadata": {"device": "offline engineering camera"},
                    "missing_fields": ["exposure", "gain", "illumination"],
                }
            ],
        },
    )
    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["status"] == "admitted"
    case_id = record["platform_case_id"]
    case = client.get(f"/cases/{case_id}").json()
    video = next(item for item in case["inputs"] if item["channel"] == "video")
    assert video["metadata"]["admission_status"] == "admitted"
    return case_id, video["input_id"], uploaded["sha256"], Path(uploaded["path"])


def _hybrid_l1_request(case_id: str, model_path: Path) -> dict[str, Any]:
    source = [
        [0.0, 0.0, 0.0],
        [20.0, 0.0, 0.0],
        [0.0, 20.0, 0.0],
        [0.0, 0.0, 20.0],
    ]
    target = [
        [5.0, -3.0, 2.0],
        [25.0, -3.0, 2.0],
        [5.0, 17.0, 2.0],
        [5.0, -3.0, 22.0],
    ]
    objects = np.asarray(
        [
            [-30, -20, 0],
            [30, -20, 0],
            [30, 20, 0],
            [-30, 20, 0],
            [-20, -10, 25],
            [20, 10, 30],
            [0, -25, 15],
            [0, 25, 20],
            [15, -25, 35],
        ],
        dtype=np.float64,
    )
    camera = np.asarray(
        [[920.0, 0.0, 640.0], [0.0, 910.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    pixels, _ = cv2.projectPoints(
        objects,
        np.asarray([0.08, -0.04, 0.03], dtype=np.float64),
        np.asarray([5.0, -4.0, 520.0], dtype=np.float64),
        camera,
        np.zeros(5),
    )
    return {
        "case_id": case_id,
        "input_mode": "manual_metadata",
        "registration_method": "rigid_points_with_pnp",
        "model_path": str(model_path),
        "source_points": source,
        "target_points": target,
        "validation_source_points": [[10.0, 10.0, 10.0], [5.0, 5.0, 12.0], [12.0, 6.0, 5.0]],
        "validation_target_points": [[15.0, 7.0, 12.0], [10.0, 2.0, 14.0], [17.0, 3.0, 7.0]],
        "source_space": "cbct_lps_mm",
        "target_space": "phantom_reference_mm",
        "unit": "mm",
        "fre_threshold_mm": 1.0,
        "tre_threshold_mm": 1.0,
        "threshold_source": "phantom_protocol_v1",
        "camera_object_points": objects[:6].tolist(),
        "camera_image_points": pixels.reshape(-1, 2)[:6].tolist(),
        "validation_camera_object_points": objects[6:].tolist(),
        "validation_camera_image_points": pixels.reshape(-1, 2)[6:].tolist(),
        "camera_matrix": camera.tolist(),
        "distortion_coefficients": [0, 0, 0, 0, 0],
        "image_size_px": [1280, 720],
        "intrinsics_id": "scope_4x_250mm",
        "camera_space": "camera_optical",
        "reprojection_threshold_px": 0.5,
        "doctor_review_status": "accepted",
        "microscope_pose_evidence": {
            "magnification": 4.0,
            "working_distance_mm": 250.0,
            "depth_source": "offline_phantom_scale",
            "depth_status": "valid",
        },
    }


def _attach_l1_safety_evidence(request: dict[str, Any], artifact_root: Path) -> None:
    calibration_path = artifact_root / "calibration" / "scope_4x_250mm.json"
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration = {
        "schema_version": "osteo-vision-camera-calibration-v2",
        "intrinsics_id": request["intrinsics_id"],
        "calibration_table_id": "scope_zoom_wd_table_v1",
        "selection_method": "nearest_validated_entry_v1",
        "camera_matrix": request["camera_matrix"],
        "distortion_coefficients": request["distortion_coefficients"],
        "image_size_px": request["image_size_px"],
        "calibrated_at": "2026-07-01T08:00:00+00:00",
        "calibration_method": "checkerboard_phantom_opencv_v1",
        "calibration_reprojection_error_px": 0.18,
        "calibration_reprojection_threshold_px": 0.5,
        "magnification_range": [3.5, 6.5],
        "working_distance_range_mm": [240.0, 310.0],
        "calibration_entries": [
            {
                "intrinsics_id": "scope_4x_250mm",
                "magnification_reference": 4.0,
                "magnification_range": [3.5, 4.5],
                "working_distance_reference_mm": 250.0,
                "working_distance_range_mm": [240.0, 260.0],
                "camera_matrix": request["camera_matrix"],
                "distortion_coefficients": request["distortion_coefficients"],
                "image_size_px": request["image_size_px"],
                "calibrated_at": "2026-07-01T08:00:00+00:00",
                "calibration_method": "checkerboard_phantom_opencv_v1",
                "calibration_reprojection_error_px": 0.18,
                "calibration_reprojection_threshold_px": 0.5,
            },
            {
                "intrinsics_id": "scope_6x_300mm",
                "magnification_reference": 6.0,
                "magnification_range": [5.5, 6.5],
                "working_distance_reference_mm": 300.0,
                "working_distance_range_mm": [290.0, 310.0],
                "camera_matrix": [
                    [1180.0, 0.0, 640.0],
                    [0.0, 1170.0, 360.0],
                    [0.0, 0.0, 1.0],
                ],
                "distortion_coefficients": request["distortion_coefficients"],
                "image_size_px": request["image_size_px"],
                "calibrated_at": "2026-07-01T08:30:00+00:00",
                "calibration_method": "checkerboard_phantom_opencv_v1",
                "calibration_reprojection_error_px": 0.21,
                "calibration_reprojection_threshold_px": 0.5,
            },
        ],
    }
    calibration_path.write_text(
        json.dumps(calibration, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    request["camera_calibration_evidence"] = {
        "artifact_path": str(calibration_path),
        "artifact_sha256": hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
    }
    request["threshold_approval"] = {
        "status": "approved",
        "protocol_version": "phantom_protocol_v1.0",
        "data_version": "phantom_validation_20260701",
        "approved_by": "Osteo Vision Navigation Safety Board",
        "approved_at": "2026-07-02T08:00:00+00:00",
        "fre_threshold_mm": request["fre_threshold_mm"],
        "tre_threshold_mm": request["tre_threshold_mm"],
        "reprojection_threshold_px": request["reprojection_threshold_px"],
    }


def _attach_l1_input_provenance(request: dict[str, Any], artifact_root: Path) -> None:
    model_path = Path(request["model_path"])
    request["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    request["model_format"] = "stl"
    artifact_path = artifact_root / "registration_inputs" / f"{request['case_id']}_l1_points.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema_version": "osteo-vision-l1-point-correspondence-v1",
        "case_id": request["case_id"],
        "registration_method": request["registration_method"],
        "coordinate_transform": {
            "from_space": request["source_space"],
            "to_space": request["target_space"],
            "direction": "forward",
            "unit": "mm",
            "source_frame": _frame(
                request["source_space"],
                axis_convention="dicom_lps_x_left_y_posterior_z_superior",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "target_frame": _frame(
                request["target_space"],
                axis_convention="phantom_x_right_y_anterior_z_superior",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "matrix_convention": MATRIX_CONVENTION,
        },
        "point_sets": {
            "registration": {"source": request["source_points"], "target": request["target_points"]},
            "validation": {
                "source": request["validation_source_points"],
                "target": request["validation_target_points"],
            },
        },
        "camera_coordinate_transform": {
            "from_space": request["target_space"],
            "to_space": request["camera_space"],
            "direction": "forward",
            "unit": "mm",
            "source_frame": _frame(
                request["target_space"],
                axis_convention="phantom_x_right_y_anterior_z_superior",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "target_frame": _frame(
                request["camera_space"],
                axis_convention="opencv_camera_x_right_y_down_z_forward",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "matrix_convention": MATRIX_CONVENTION,
        },
        "camera_point_sets": {
            "registration": {
                "object": request["camera_object_points"],
                "image": request["camera_image_points"],
            },
            "validation": {
                "object": request["validation_camera_object_points"],
                "image": request["validation_camera_image_points"],
            },
        },
    }
    artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
    request["point_correspondence_artifact_path"] = str(artifact_path)
    request["point_correspondence_artifact_sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()


def _accept_l1(client: TestClient, tmp_path: Path, case_id: str) -> None:
    model_path = tmp_path / "artifacts" / "models" / f"{case_id}.stl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        """solid mandible
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 20 0 0
vertex 0 20 0
endloop
endfacet
endsolid mandible
""",
        encoding="utf-8",
    )
    request = _hybrid_l1_request(case_id, model_path)
    _attach_l1_input_provenance(request, tmp_path / "artifacts")
    _attach_l1_safety_evidence(request, tmp_path / "artifacts")
    started = client.post(
        "/three-d/registration-jobs",
        json=request,
        headers=HEADERS,
    )
    assert started.status_code == 200
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()
    assert job["status"] == "completed"
    assert job["result"]["three_d_evidence"]["navigation_ready"] is True
    assert job["result"]["three_d_evidence"]["navigation_level"] == "L1"


def _accepted_l1_case(
    client: TestClient,
    tmp_path: Path,
) -> tuple[str, str, str, Path]:
    case_id, video_input_id, video_sha256, video_path = _admit_video(client, tmp_path)
    _accept_l1(client, tmp_path, case_id)
    return case_id, video_input_id, video_sha256, video_path


def _pose_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, timestamp in enumerate([0.0, 0.1, 0.2]):
        matrix = np.eye(4, dtype=np.float64)
        matrix[0, 3] = index * 0.1
        records.append(
            {
                "frame_index": index,
                "timestamp_s": timestamp,
                "matrix": matrix.tolist(),
                "from_space": "camera_optical",
                "to_space": "camera_optical_dynamic",
                "direction": "forward",
                "unit": "mm",
                "handedness": "right_handed",
                "axis_convention": "opencv_camera_x_right_y_down_z_forward",
                "source_frame": _frame(
                    "camera_optical",
                    axis_convention="opencv_camera_x_right_y_down_z_forward",
                    source="checksum_bound_point_correspondence_artifact",
                ),
                "target_frame": _frame(
                    "camera_optical_dynamic",
                    axis_convention="opencv_camera_x_right_y_down_z_forward",
                    source="checksum_bound_pose_manifest_tracker",
                ),
                "matrix_convention": MATRIX_CONVENTION,
                "magnification": 4.0,
                "working_distance_mm": 250.0,
                "tracking_status": "tracking",
                "tracking_drift_mm": 0.05,
                "tracking_drift_source": "independent_tracker_residual",
                "dynamic_target_error_mm": 0.2,
                "dynamic_target_error_source": "independent_phantom_target",
            }
        )
    return records


def _dynamic_manifest(
    client: TestClient,
    case_id: str,
    video_input_id: str,
    video_sha256: str,
    *,
    failure_injections: dict[int, list[str]] | None = None,
) -> dict[str, Any]:
    case = client.get(f"/cases/{case_id}").json()
    l1_evidence = case["three_d_evidence"]
    if l1_evidence.get("analysis_mode") == "l2_offline_pose_replay":
        l1_evidence = l1_evidence["l1_evidence_snapshot"]
    input_provenance = l1_evidence["registration_input_provenance"]
    return {
        "schema_version": "osteo-vision-l2-pose-input-v3",
        "case_id": case_id,
        "replay_mode": "dynamic_ar_validation",
        "video_input_id": video_input_id,
        "video_sha256": video_sha256,
        "video_frame_count": 3,
        "intrinsics_id": "scope_4x_250mm",
        "calibration_table_id": "scope_zoom_wd_table_v1",
        "l1_registration_run_id": l1_evidence["run_id"],
        "l1_model_sha256": l1_evidence["model_sha256"],
        "l1_input_artifact_sha256": input_provenance["artifact_sha256"],
        "l1_registration_output_sha256": l1_evidence["registration_output_manifest_sha256"],
        "l1_transform_sha256": l1_evidence["transform_sha256"],
        "projection_point_space": "cbct_lps_mm",
        "projection_point_frame": _frame(
            "cbct_lps_mm",
            axis_convention="dicom_lps_x_left_y_posterior_z_superior",
            source="checksum_bound_point_correspondence_artifact",
        ),
        "projection_points_3d": [
            [0.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [20.0, 20.0, 0.0],
            [0.0, 20.0, 0.0],
        ],
        "poses": _pose_records(),
        "failure_injections": failure_injections or {},
        "max_time_offset_ms": 50.0,
        "drift_threshold_mm": 1.0,
        "tre_proxy_threshold_mm": 2.0,
        "dynamic_target_error_threshold_mm": 2.0,
        "minimum_visible_projection_points": 4,
        "max_magnification_rate_per_s": 25.0,
        "max_working_distance_rate_mm_per_s": 600.0,
        "max_intrinsics_switch_rate_hz": 10.0,
        "calibration_ambiguity_margin": 0.05,
        "l2_threshold_approval": {
            "status": "approved",
            "protocol_version": "l2_phantom_protocol_v1.0",
            "data_version": "l2_phantom_validation_20260701",
            "approved_by": REVIEW_ACTOR["actor_id"],
            "approved_at": "2026-07-02T08:00:00+00:00",
            "max_time_offset_ms": 50.0,
            "drift_threshold_mm": 1.0,
            "tre_proxy_threshold_mm": 2.0,
            "dynamic_target_error_threshold_mm": 2.0,
            "minimum_visible_projection_points": 4,
            "max_magnification_rate_per_s": 25.0,
            "max_working_distance_rate_mm_per_s": 600.0,
            "max_intrinsics_switch_rate_hz": 10.0,
            "calibration_ambiguity_margin": 0.05,
        },
        "doctor_review_status": "accepted",
    }


def _write_pose_manifest(
    tmp_path: Path,
    manifest: dict[str, Any],
    *,
    name: str = "pose_manifest.json",
    attach_safety_artifacts: bool = True,
) -> tuple[Path, str]:
    path = tmp_path / "artifacts" / "pose_inputs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if attach_safety_artifacts and manifest.get("replay_mode") == "dynamic_ar_validation":
        stem = Path(name).stem
        measurement_path = path.parent / f"{stem}_independent_measurements.json"
        measurement = {
            "schema_version": "osteo-vision-l2-independent-measurements-v1",
            "case_id": manifest["case_id"],
            "video_input_id": manifest["video_input_id"],
            "video_sha256": manifest["video_sha256"],
            "frame_count": len(manifest.get("poses") or []),
            "measurement_method_id": "independent_tracker_and_phantom_target_v1",
            "source_type": "independent_phantom_measurement",
            "review_status": "accepted",
            "reviewed_by": REVIEW_ACTOR,
            "reviewed_at": "2026-07-02T08:00:00+00:00",
            "records": [
                {
                    "frame_index": pose.get("frame_index"),
                    "timestamp_s": pose.get("timestamp_s"),
                    "tracking_drift_mm": pose.get("tracking_drift_mm"),
                    "dynamic_target_error_mm": pose.get("dynamic_target_error_mm"),
                }
                for pose in manifest.get("poses") or []
            ],
        }
        measurement_path.write_text(
            json.dumps(measurement, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        measurement_sha256 = hashlib.sha256(measurement_path.read_bytes()).hexdigest()
        manifest["measurement_artifact_path"] = str(measurement_path)
        manifest["measurement_artifact_sha256"] = measurement_sha256
        source_reference = f"independent_tracker_and_phantom_target_v1:{measurement_sha256}"
        for pose in manifest.get("poses") or []:
            pose["tracking_drift_source"] = source_reference
            pose["dynamic_target_error_source"] = source_reference

        policy_path = path.parent / f"{stem}_threshold_policy.json"
        thresholds = {
            field: manifest[field]
            for field in (
                "max_time_offset_ms",
                "drift_threshold_mm",
                "tre_proxy_threshold_mm",
                "dynamic_target_error_threshold_mm",
                "minimum_visible_projection_points",
                "max_magnification_rate_per_s",
                "max_working_distance_rate_mm_per_s",
                "max_intrinsics_switch_rate_hz",
                "calibration_ambiguity_margin",
            )
        }
        policy = {
            "schema_version": "osteo-vision-l2-threshold-policy-v2",
            "policy_id": "l2-platform-safety-ceiling",
            "policy_version": "1.0.0",
            "status": "approved",
            "protocol_version": "l2_phantom_protocol_v1.0",
            "data_version": "l2_phantom_validation_20260701",
            "approved_by": REVIEW_ACTOR,
            "approved_at": "2026-07-02T08:00:00+00:00",
            "thresholds": thresholds,
        }
        policy_path.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        policy_sha256 = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        manifest["threshold_policy_artifact_path"] = str(policy_path)
        manifest["threshold_policy_artifact_sha256"] = policy_sha256
        manifest["l2_threshold_approval"] = {
            "status": "approved",
            "policy_id": policy["policy_id"],
            "policy_version": policy["policy_version"],
            "artifact_sha256": policy_sha256,
            "protocol_version": policy["protocol_version"],
            "data_version": policy["data_version"],
            "approved_by": REVIEW_ACTOR["actor_id"],
            "approved_at": policy["approved_at"],
            **thresholds,
        }
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _dynamic_request(
    case_id: str,
    video_input_id: str,
    manifest_path: Path,
    manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "replay_mode": "dynamic_ar_validation",
        "input_mode": "offline_manifest",
        "pose_manifest_path": str(manifest_path),
        "pose_manifest_sha256": manifest_sha256,
        "video_input_id": video_input_id,
        "doctor_review_status": "accepted",
    }


def _start_and_get_job(
    client: TestClient,
    request: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = client.post(
        "/three-d/pose-replay-jobs",
        json=request,
        headers=headers or HEADERS,
    )
    assert started.status_code == 200
    return client.get(f"/three-d/pose-replay-jobs/{started.json()['job_id']}").json()


def test_pose_only_replay_is_permanently_l0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, _, _, _ = _accepted_l1_case(client, tmp_path)
    request = {
        "case_id": case_id,
        "replay_mode": "pose_only_engineering",
        "input_mode": "manual_metadata",
        "frame_timestamps_s": [0.0, 0.1, 0.2],
        "poses": _pose_records(),
        "calibration_table": [
            {
                "intrinsics_id": "scope-4x-250mm",
                "magnification_min": 3.5,
                "magnification_max": 4.5,
                "working_distance_min_mm": 240.0,
                "working_distance_max_mm": 260.0,
            }
        ],
        "doctor_review_status": "accepted",
    }

    job = _start_and_get_job(client, request)

    assert job["status"] == "completed"
    result = job["result"]
    assert result["navigation_ready"] is False
    assert result["navigation_level"] == "L0"
    assert result["overlay_video_path"] is None
    assert "pose_only_engineering_no_navigation" in result["failure_reasons"]


def test_dynamic_ar_replay_persists_checksum_bound_overlay_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["poses"][1]["magnification"] = 6.0
    manifest["poses"][1]["working_distance_mm"] = 300.0
    manifest["poses"][2]["magnification"] = 6.0
    manifest["poses"][2]["working_distance_mm"] = 300.0
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        manifest,
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "completed"
    result = job["result"]
    assert result["replay_status"] == "completed"
    assert result["navigation_ready"] is True
    assert result["navigation_level"] == "L2"
    assert result["safe_frame_count"] == 3
    assert result["degraded_frame_count"] == 0
    assert result["video_timestamp_source"] == "ffprobe_best_effort_timestamp_time"
    assert Path(result["pose_replay_manifest_path"]).is_file()
    assert Path(result["pose_replay_frames_csv_path"]).is_file()
    assert Path(result["overlay_video_path"]).is_file()
    assert len(result["overlay_video_sha256"]) == 64
    assert result["three_d_evidence"]["overlay_evidence"]["memory_mode"] == ("streaming_two_pass_v1")
    evidence = result["three_d_evidence"]
    binding = evidence["l1_chain_binding"]
    assert binding["status"] == "verified_same_l1_chain"
    assert binding["l1_registration_run_id"] == evidence["l1_evidence_snapshot"]["run_id"]
    assert binding["l1_model_sha256"] == evidence["l1_evidence_snapshot"]["model_sha256"]
    assert binding["l1_transform_sha256"] == evidence["l1_evidence_snapshot"]["transform_sha256"]
    assert evidence["video_evidence"]["pts_derived_fps"] == pytest.approx(10.0)
    assert evidence["video_evidence"]["fps_consistent"] is True
    assert evidence["overlay_evidence"]["source_pts_derived_fps"] == pytest.approx(10.0)
    assert evidence["overlay_evidence"]["timestamp_source"] == "ffprobe_best_effort_timestamp_time"
    assert evidence["l2_measurement_evidence"]["artifact_sha256"] == manifest["measurement_artifact_sha256"]
    assert evidence["l2_threshold_policy_evidence"]["artifact_sha256"] == (manifest["threshold_policy_artifact_sha256"])
    assert evidence["artifact_lifecycle"]["status"] == "active"
    selection = result["calibration_selection"]
    assert selection["calibration_table_id"] == "scope_zoom_wd_table_v1"
    assert selection["selection_method"] == "nearest_validated_entry_v1"
    assert [item["intrinsics_id"] for item in selection["per_frame"]] == [
        "scope_4x_250mm",
        "scope_6x_300mm",
        "scope_6x_300mm",
    ]
    assert selection["switch_count"] == 1
    assert selection["oscillation_count"] == 0
    assert selection["status"] == "passed"
    assert selection["max_magnification_rate_per_s"] == pytest.approx(20.0)
    assert selection["max_working_distance_rate_mm_per_s"] == pytest.approx(500.0)

    case = client.get(f"/cases/{case_id}").json()
    assert case["three_d_evidence"]["navigation_ready"] is True
    assert case["three_d_evidence"]["navigation_level"] == "L2"
    artifact_kinds = {item["kind"] for item in case["artifacts"]}
    assert "three_d_pose_replay_manifest" in artifact_kinds
    assert "three_d_pose_replay_frames" in artifact_kinds
    assert "three_d_ar_overlay" in artifact_kinds

    rerun = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )
    assert rerun["status"] == "completed"
    assert rerun["result"]["navigation_level"] == "L2"


def test_dynamic_replay_rejects_pose_manifest_bound_to_different_l1_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["l1_model_sha256"] = "0" * 64
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        manifest,
        name="wrong_l1_model_binding.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "l1_chain_binding_mismatch"
    assert job["result"]["three_d_evidence"]["navigation_level"] == "L0"
    assert job["result"]["three_d_evidence"]["overlay_evidence"] is None


def test_dynamic_replay_calibration_oscillation_revokes_l2_and_persists_temporal_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["poses"][1]["magnification"] = 6.0
    manifest["poses"][1]["working_distance_mm"] = 300.0
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        manifest,
        name="calibration_oscillation.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "completed"
    result = job["result"]
    assert result["navigation_level"] == "L0"
    assert result["navigation_ready"] is False
    assert result["overlay_video_path"] is None
    assert "calibration_selection_oscillation" in result["failure_reasons"]
    selection = result["calibration_selection"]
    assert selection["status"] == "failed_closed"
    assert selection["switch_count"] == 2
    assert selection["oscillation_count"] == 1
    assert selection["intrinsics_transitions"][1]["oscillation"] is True
    csv_text = Path(result["pose_replay_frames_csv_path"]).read_text(encoding="utf-8")
    assert "calibration_selection_ambiguous" in csv_text
    assert "intrinsics_switch_rate_hz" in csv_text
    case_evidence = client.get(f"/cases/{case_id}").json()["three_d_evidence"]
    assert case_evidence["navigation_level"] == "L0"
    assert case_evidence["artifact_lifecycle"]["status"] == "failed_closed"
    assert case_evidence["calibration_selection"]["oscillation_count"] == 1


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("legacy_schema", "l2_threshold_policy_schema_unsupported"),
        ("missing_temporal_threshold", "l2_threshold_policy_value_invalid"),
    ],
)
def test_dynamic_replay_rejects_obsolete_or_incomplete_temporal_threshold_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_error: str,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest_path, _ = _write_pose_manifest(
        tmp_path,
        manifest,
        name=f"temporal_policy_{mutation}.json",
    )
    policy_path = Path(manifest["threshold_policy_artifact_path"])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if mutation == "legacy_schema":
        policy["schema_version"] = "osteo-vision-l2-threshold-policy-v1"
    else:
        policy["thresholds"].pop("max_magnification_rate_per_s")
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    policy_sha256 = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    manifest["threshold_policy_artifact_sha256"] = policy_sha256
    manifest["l2_threshold_approval"]["artifact_sha256"] = policy_sha256
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == expected_error
    assert job["result"]["navigation_level"] == "L0"
    case_evidence = client.get(f"/cases/{case_id}").json()["three_d_evidence"]
    assert case_evidence["navigation_level"] == "L0"
    assert case_evidence["artifact_lifecycle"]["status"] == "failed_closed"


def test_dynamic_replay_rejects_temporal_threshold_above_platform_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["max_magnification_rate_per_s"] = 25.1
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        manifest,
        name="relaxed_temporal_threshold.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "l2_threshold_exceeds_platform_safety_ceiling"
    assert job["result"]["navigation_level"] == "L0"
    case_evidence = client.get(f"/cases/{case_id}").json()["three_d_evidence"]
    assert case_evidence["navigation_level"] == "L0"
    assert case_evidence["artifact_lifecycle"]["status"] == "failed_closed"


def test_dynamic_replay_rejects_persisted_l1_frame_metadata_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    case_store = tmp_path / "cases.json"
    rows = json.loads(case_store.read_text(encoding="utf-8"))
    case_row = next(row for row in rows if row["case_id"] == case_id)
    case_row["three_d_evidence"]["coordinate_frame_contracts"]["camera"]["target_frame"][
        "axis_convention"
    ] = "conflicting_camera_axis"
    case_store.write_text(json.dumps(rows), encoding="utf-8")
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(client, case_id, video_input_id, video_sha256),
        name="l1_frame_conflict.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "l1_evidence_coordinate_contract_mismatch"
    assert job["result"]["three_d_evidence"]["navigation_level"] == "L0"
    assert job["result"]["three_d_evidence"]["overlay_evidence"] is None


def test_dynamic_replay_rejects_pose_manifest_with_incomplete_frame_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["poses"][1]["source_frame"].pop("handedness")
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        manifest,
        name="pose_frame_metadata_missing.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "pose_coordinate_contract_invalid"
    assert job["result"]["three_d_evidence"]["navigation_level"] == "L0"


def test_dynamic_failure_injection_revokes_overlay_and_degrades_case_to_l0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    successful_manifest_path, successful_manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(client, case_id, video_input_id, video_sha256),
        name="successful_before_failure.json",
    )
    successful = _start_and_get_job(
        client,
        _dynamic_request(
            case_id,
            video_input_id,
            successful_manifest_path,
            successful_manifest_sha256,
        ),
    )
    assert successful["status"] == "completed"
    assert successful["result"]["navigation_level"] == "L2"
    old_overlay_path = Path(successful["result"]["overlay_video_path"])
    assert old_overlay_path.is_file()
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(
            client,
            case_id,
            video_input_id,
            video_sha256,
            failure_injections={1: ["tracking_lost"]},
        ),
        name="failed_rerun.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "completed"
    result = job["result"]
    assert result["navigation_ready"] is False
    assert result["navigation_level"] == "L0"
    assert result["overlay_video_path"] is None
    assert "tracking_lost" in result["failure_reasons"]
    assert not (Path(result["pose_replay_manifest_path"]).parent / "dynamic_ar_overlay.mp4").exists()
    case_evidence = client.get(f"/cases/{case_id}").json()["three_d_evidence"]
    assert case_evidence["overlay_evidence"] is None
    assert case_evidence["artifact_lifecycle"]["status"] == "failed_closed"
    assert case_evidence["artifact_lifecycle"]["overlay_active"] is False
    assert case_evidence["l1_evidence_snapshot"]["analysis_mode"] == "l1_static_registration"
    assert case_evidence["l1_evidence_snapshot"]["navigation_level"] == "L1"
    assert old_overlay_path.is_file()


def test_dynamic_replay_rejects_tampered_pose_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(client, case_id, video_input_id, video_sha256),
    )
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "pose_manifest_sha256_mismatch"
    assert job["result"]["navigation_level"] == "L0"


@pytest.mark.parametrize(
    ("path_field", "error_code"),
    [
        ("measurement_artifact_path", "l2_measurement_artifact_sha256_mismatch"),
        ("threshold_policy_artifact_path", "l2_threshold_policy_artifact_sha256_mismatch"),
    ],
)
def test_dynamic_replay_rejects_tampered_independent_safety_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_field: str,
    error_code: str,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest_path, manifest_sha256 = _write_pose_manifest(tmp_path, manifest)
    artifact_path = Path(manifest[path_field])
    artifact_path.write_text(
        artifact_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == error_code
    assert job["result"]["navigation_level"] == "L0"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("projection", "dynamic_pose_manifest_fields_missing"),
        ("dynamic_error", "l2_measurement_value_invalid"),
    ],
)
def test_dynamic_replay_fails_closed_when_required_spatial_evidence_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected: str,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    if mutation == "projection":
        manifest.pop("projection_points_3d")
    else:
        manifest["poses"][1].pop("dynamic_target_error_mm")
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        manifest,
        name=f"missing_{mutation}.json",
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == expected
    assert job["result"]["navigation_level"] == "L0"


def test_dynamic_replay_rejects_unadmitted_mp4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    uploaded = _upload_mp4(client, tmp_path)
    case_id = client.post("/cases", json={"title": "unadmitted L2 video"}).json()["case_id"]
    case = client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {
                "channel": "video",
                "path": uploaded["path"],
                "mime_type": "video/mp4",
                "metadata": {"sha256": uploaded["sha256"]},
            }
        ],
    ).json()
    video_input_id = case["inputs"][0]["input_id"]
    _accept_l1(client, tmp_path, case_id)
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(client, case_id, video_input_id, uploaded["sha256"]),
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "video_input_not_admitted"


def test_dynamic_replay_without_verified_pts_stays_l0_and_hides_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(client, case_id, video_input_id, video_sha256),
    )
    monkeypatch.setattr(replay_service_module, "find_runtime_executable", lambda _name: None)

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "completed"
    assert job["result"]["navigation_level"] == "L0"
    assert "video_pts_unverified" in job["result"]["failure_reasons"]
    assert job["result"]["overlay_video_path"] is None


def test_dynamic_replay_rejects_variable_frame_rate_pts_and_hides_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["poses"][2]["timestamp_s"] = 0.25
    manifest_path, manifest_sha256 = _write_pose_manifest(tmp_path, manifest)
    monkeypatch.setattr(
        replay_service_module,
        "_ffprobe_frame_timestamps",
        lambda _path: ([0.0, 0.1, 0.25], None),
    )

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "completed"
    result = job["result"]
    assert result["navigation_level"] == "L0"
    assert "video_variable_frame_rate_unsupported" in result["failure_reasons"]
    assert result["overlay_video_path"] is None
    assert result["three_d_evidence"]["video_evidence"]["timing_mode"] == ("variable_frame_rate_verified")


def test_dynamic_replay_rejects_manifest_calibration_table_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["calibration_table_id"] = "unbound_table"
    manifest_path, manifest_sha256 = _write_pose_manifest(tmp_path, manifest)

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "l1_camera_calibration_table_mismatch"
    assert job["result"]["navigation_level"] == "L0"


def test_dynamic_replay_rejects_projection_space_not_bound_to_l1_transform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest = _dynamic_manifest(client, case_id, video_input_id, video_sha256)
    manifest["projection_point_space"] = "attacker_controlled_space"
    manifest_path, manifest_sha256 = _write_pose_manifest(tmp_path, manifest)

    job = _start_and_get_job(
        client,
        _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256),
    )

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "projection_coordinate_space_mismatch"
    assert job["result"]["navigation_level"] == "L0"


def test_dynamic_request_rejects_client_supplied_safety_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, video_input_id, video_sha256, _ = _accepted_l1_case(client, tmp_path)
    manifest_path, manifest_sha256 = _write_pose_manifest(
        tmp_path,
        _dynamic_manifest(client, case_id, video_input_id, video_sha256),
    )
    request = _dynamic_request(case_id, video_input_id, manifest_path, manifest_sha256)
    request["dynamic_target_error_threshold_mm"] = 999.0

    response = client.post(
        "/three-d/pose-replay-jobs",
        json=request,
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_pose_replay_invalid_pose_log_fails_closed_and_persists_l0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, _, _, _ = _accepted_l1_case(client, tmp_path)
    request = {
        "case_id": case_id,
        "replay_mode": "pose_only_engineering",
        "input_mode": "manual_metadata",
        "frame_timestamps_s": [0.0],
        "poses": [],
        "calibration_table": [],
        "doctor_review_status": "accepted",
    }

    job = _start_and_get_job(client, request)

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "pose_log_empty"
    assert job["result"]["navigation_level"] == "L0"
    case = client.get(f"/cases/{case_id}").json()
    assert case["three_d_evidence"]["navigation_ready"] is False
    assert case["three_d_evidence"]["navigation_level"] == "L0"


def test_pose_replay_rejects_untrusted_accepted_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "untrusted L2 review"}).json()["case_id"]
    request = {
        "case_id": case_id,
        "replay_mode": "pose_only_engineering",
        "input_mode": "manual_metadata",
        "frame_timestamps_s": [0.0],
        "poses": _pose_records()[:1],
        "calibration_table": [],
        "doctor_review_status": "accepted",
    }

    response = client.post("/three-d/pose-replay-jobs", json=request)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "l2_pose_replay_review_forbidden"
