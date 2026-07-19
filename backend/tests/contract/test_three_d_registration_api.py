from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import create_app

TOKEN = "physician-l1-review-token-001"
MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}


def _frame(name: str, *, axis_convention: str, source: str) -> dict:
    return {
        "name": name,
        "handedness": "right_handed",
        "axis_convention": axis_convention,
        "unit": "mm",
        "source": source,
    }


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_JOB_STORE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv(
        "OSTEO_REVIEW_IDENTITIES_JSON",
        json.dumps(
            {
                TOKEN: {
                    "actor_id": "doctor-l1-001",
                    "role": "physician",
                    "institution": "Example Stomatology Hospital",
                    "auth_source": "verified_identity_token",
                }
            }
        ),
    )
    return TestClient(create_app())


def _write_valid_stl(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(case_id: str, model_path: Path) -> dict:
    source = [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [0.0, 20.0, 0.0], [0.0, 0.0, 20.0]]
    target = [[5.0, -3.0, 2.0], [25.0, -3.0, 2.0], [5.0, 17.0, 2.0], [5.0, -3.0, 22.0]]
    return {
        "case_id": case_id,
        "input_mode": "manual_metadata",
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
        "doctor_review_status": "review_required",
        "microscope_pose_evidence": {
            "calibration_status": "valid",
            "magnification": 4.0,
            "calibration_magnification_min": 2.0,
            "calibration_magnification_max": 8.0,
            "working_distance_mm": 250.0,
            "calibration_working_distance_min_mm": 200.0,
            "calibration_working_distance_max_mm": 300.0,
            "depth_source": "offline_phantom_scale",
            "depth_status": "valid",
        },
    }


def _hybrid_request(case_id: str, model_path: Path) -> dict:
    request = _request(case_id, model_path)
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
    request.update(
        {
            "registration_method": "rigid_points_with_pnp",
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
        }
    )
    return request


def _point_artifact_payload(request: dict) -> dict:
    payload = {
        "schema_version": "osteo-vision-l1-point-correspondence-v1",
        "case_id": request["case_id"],
        "registration_method": request.get("registration_method", "rigid_points"),
        "coordinate_transform": {
            "from_space": request["source_space"],
            "to_space": request["target_space"],
            "direction": "forward",
            "unit": request["unit"],
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
    }
    if request.get("registration_method") == "rigid_points_with_pnp":
        payload.update(
            {
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
        )
    return payload


def _attach_input_provenance(request: dict, artifact_root: Path) -> Path:
    model_path = Path(request["model_path"])
    request["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    request["model_format"] = model_path.suffix.lstrip(".").lower()
    artifact_path = artifact_root / "registration_inputs" / f"{request['case_id']}_points.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(_point_artifact_payload(request), sort_keys=True), encoding="utf-8")
    request["point_correspondence_artifact_path"] = str(artifact_path)
    request["point_correspondence_artifact_sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return artifact_path


def _structured_manifest(request: dict) -> dict:
    point_artifact = _point_artifact_payload(request)
    manifest = {
        "schema_version": "osteo-vision-l1-registration-input-v1",
        "case_id": request["case_id"],
        "registration_method": point_artifact["registration_method"],
        "model": {
            "path": request["model_path"],
            "sha256": hashlib.sha256(Path(request["model_path"]).read_bytes()).hexdigest(),
            "format": Path(request["model_path"]).suffix.lstrip(".").lower(),
        },
        "coordinate_transform": point_artifact["coordinate_transform"],
        "point_sets": point_artifact["point_sets"],
        "thresholds": {
            "fre_threshold_mm": request["fre_threshold_mm"],
            "tre_threshold_mm": request["tre_threshold_mm"],
            "source": request["threshold_source"],
        },
        "microscope_pose_evidence": request["microscope_pose_evidence"],
    }
    for field in (
        "camera_coordinate_transform",
        "camera_point_sets",
        "camera_matrix",
        "distortion_coefficients",
        "image_size_px",
        "intrinsics_id",
        "reprojection_threshold_px",
        "camera_calibration_evidence",
        "threshold_approval",
    ):
        if field in point_artifact:
            manifest[field] = point_artifact[field]
        elif field in request:
            manifest[field] = request[field]
    return manifest


def _attach_verified_calibration_and_threshold(
    request: dict,
    artifact_root: Path,
) -> Path:
    calibration_path = artifact_root / "calibration" / "scope_4x_250mm.json"
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration = {
        "schema_version": "osteo-vision-camera-calibration-v1",
        "intrinsics_id": request["intrinsics_id"],
        "camera_matrix": request["camera_matrix"],
        "distortion_coefficients": request["distortion_coefficients"],
        "image_size_px": request["image_size_px"],
        "calibrated_at": "2026-07-01T08:00:00+00:00",
        "calibration_method": "checkerboard_phantom_opencv_v1",
        "calibration_reprojection_error_px": 0.18,
        "calibration_reprojection_threshold_px": 0.5,
        "magnification_range": [2.0, 8.0],
        "working_distance_range_mm": [200.0, 300.0],
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
    return calibration_path


def test_l1_registration_job_persists_transform_and_safety_evidence(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 registration"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)

    started = client.post("/three-d/registration-jobs", json=_request(case_id, model_path))

    assert started.status_code == 200
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}")
    assert job.status_code == 200
    payload = job.json()
    assert payload["status"] == "completed"
    result = payload["result"]
    assert result["registration_status"] == "registered"
    assert result["fre_mm"] < 1e-6
    assert result["tre_mm"] < 1e-6
    assert Path(result["transform_path"]).is_file()
    assert len(result["transform_sha256"]) == 64

    case = client.get(f"/cases/{case_id}").json()
    evidence = case["three_d_evidence"]
    assert evidence["requested_navigation_level"] == "L1"
    assert evidence["registration_status"] == "registered"
    assert evidence["fre_mm"] < 1e-6
    assert evidence["tre_mm"] < 1e-6
    assert evidence["registration_threshold_source"] == "phantom_protocol_v1"
    assert evidence["doctor_review_status"] == "review_required"
    assert evidence["navigation_ready"] is False
    assert "doctor_review_not_accepted" in evidence["failure_reasons"]


def test_l1_registration_job_fails_closed_with_structured_error(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 invalid registration"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _request(case_id, model_path)
    request["source_points"] = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]
    request["target_points"] = [[1.0, 0.0, 0.0], [2.0, 1.0, 1.0], [3.0, 2.0, 2.0]]

    started = client.post("/three-d/registration-jobs", json=request)
    payload = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert payload["status"] == "failed"
    assert payload["result"]["error_code"] == "degenerate_registration_geometry"
    assert payload["result"]["fallback_mode"] == "unregistered_3d_reference"
    case = client.get(f"/cases/{case_id}").json()
    assert case["three_d_evidence"]["registration_status"] == "failed"
    assert case["three_d_evidence"]["navigation_ready"] is False
    assert case["three_d_evidence"]["navigation_level"] == "L0"


def test_l1_hybrid_pnp_persists_intrinsics_and_reprojection_evidence(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 calibrated PnP"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)

    started = client.post(
        "/three-d/registration-jobs",
        json=_hybrid_request(case_id, model_path),
    )
    assert started.status_code == 200
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "completed"
    result = job["result"]
    assert result["camera_registration_status"] == "estimated"
    assert result["reprojection_error_px"] < 1e-4
    assert Path(result["transform_path"]).is_file()
    evidence = result["three_d_evidence"]
    assert evidence["camera_intrinsics_id"] == "scope_4x_250mm"
    assert evidence["reprojection_error_source"] == ("independent_camera_validation_points")
    assert evidence["coordinate_chain_validation"]["valid"] is True
    assert len(evidence["transform_chain"]) == 2
    assert evidence["navigation_ready"] is False
    assert "doctor_review_not_accepted" in evidence["failure_reasons"]
    manifest = json.loads(Path(result["registration_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "osteo-vision-l1-static-registration-v2"
    assert manifest["camera_registration"]["intrinsics_id"] == "scope_4x_250mm"


def test_l1_hybrid_pnp_requires_verified_calibration_and_threshold_approval_for_readiness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 complete safety evidence"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _hybrid_request(case_id, model_path)
    _attach_input_provenance(request, tmp_path / "artifacts")
    calibration_path = _attach_verified_calibration_and_threshold(
        request,
        tmp_path / "artifacts",
    )
    request["doctor_review_status"] = "accepted"

    started = client.post(
        "/three-d/registration-jobs",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=request,
    )
    assert started.status_code == 200
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "completed"
    evidence = job["result"]["three_d_evidence"]
    assert evidence["navigation_ready"] is True
    assert evidence["navigation_level"] == "L1"
    assert evidence["failure_reasons"] == []
    assert evidence["model_provenance"]["valid"] is True
    assert evidence["model_provenance"]["parse_summary"]["triangle_count"] == 1
    assert evidence["registration_input_provenance"]["valid"] is True
    assert evidence["registration_input_provenance"]["point_set_counts"] == {
        "registration": 4,
        "validation": 3,
    }
    output_manifest = Path(evidence["registration_output_manifest_path"])
    assert output_manifest == Path(job["result"]["registration_manifest_path"])
    assert evidence["registration_output_manifest_sha256"] == hashlib.sha256(output_manifest.read_bytes()).hexdigest()
    assert job["result"]["registration_manifest_sha256"] == evidence["registration_output_manifest_sha256"]
    calibration = evidence["camera_calibration_evidence"]
    assert calibration["artifact_validation"]["valid"] is True
    assert calibration["artifact_path"] == str(calibration_path)
    assert evidence["threshold_approval"]["protocol_version"] == "phantom_protocol_v1.0"


def test_l1_hybrid_pnp_fails_closed_when_calibration_checksum_is_tampered(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 tampered calibration"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _hybrid_request(case_id, model_path)
    calibration_path = _attach_verified_calibration_and_threshold(
        request,
        tmp_path / "artifacts",
    )
    calibration_path.write_text(
        calibration_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    request["doctor_review_status"] = "accepted"

    started = client.post(
        "/three-d/registration-jobs",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=request,
    )
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "completed"
    evidence = job["result"]["three_d_evidence"]
    assert evidence["navigation_ready"] is False
    assert evidence["navigation_level"] == "L0"
    assert "camera_calibration_artifact_sha256_mismatch" in evidence["failure_reasons"]


def test_l1_hybrid_pnp_degrades_when_independent_reprojection_exceeds_threshold(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 PnP threshold"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _hybrid_request(case_id, model_path)
    request["validation_camera_image_points"][0][0] += 12.0

    started = client.post("/three-d/registration-jobs", json=request)
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "completed"
    evidence = job["result"]["three_d_evidence"]
    assert evidence["navigation_ready"] is False
    assert "reprojection_error_threshold_exceeded" in evidence["failure_reasons"]


def test_l1_registration_accepts_offline_manifest(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 manifest"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    manifest = tmp_path / "artifacts" / "registration_inputs" / "case.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(_structured_manifest(_request(case_id, model_path)), ensure_ascii=False), encoding="utf-8"
    )

    started = client.post(
        "/three-d/registration-jobs",
        json={
            "case_id": case_id,
            "input_mode": "offline_manifest",
            "registration_manifest_path": str(manifest),
            "registration_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "doctor_review_status": "review_required",
        },
    )
    payload = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert payload["status"] == "completed"
    assert payload["result"]["input_mode"] == "offline_manifest"
    assert payload["result"]["input_manifest_path"] == str(manifest)
    assert payload["result"]["input_provenance"]["valid"] is True


def test_l1_registration_offline_manifest_requires_checksum_at_api_boundary(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 manifest checksum required"}).json()["case_id"]

    response = client.post(
        "/three-d/registration-jobs",
        json={
            "case_id": case_id,
            "input_mode": "offline_manifest",
            "registration_manifest_path": str(tmp_path / "artifacts" / "registration.json"),
        },
    )

    assert response.status_code == 422
    assert "registration_manifest_sha256 is required" in response.text


def test_l1_registration_fails_when_checksum_bound_manifest_is_tampered(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 tampered manifest"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    manifest = tmp_path / "artifacts" / "registration_inputs" / "tampered.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(_structured_manifest(_request(case_id, model_path))), encoding="utf-8")
    expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    started = client.post(
        "/three-d/registration-jobs",
        json={
            "case_id": case_id,
            "input_mode": "offline_manifest",
            "registration_manifest_path": str(manifest),
            "registration_manifest_sha256": expected,
        },
    )
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "registration_manifest_sha256_mismatch"
    assert job["result"]["three_d_evidence"]["navigation_level"] == "L0"


def test_l1_registration_degrades_when_model_checksum_or_mesh_is_invalid(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 invalid model provenance"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    model_path.parent.mkdir(parents=True)
    model_path.write_text("solid mandible\nendsolid mandible\n", encoding="utf-8")
    request = _request(case_id, model_path)
    _attach_input_provenance(request, tmp_path / "artifacts")
    request["model_sha256"] = "0" * 64

    started = client.post("/three-d/registration-jobs", json=request)
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "completed"
    evidence = job["result"]["three_d_evidence"]
    assert evidence["navigation_ready"] is False
    assert evidence["navigation_level"] == "L0"
    assert "model_sha256_mismatch" in evidence["failure_reasons"]
    assert "model_parse_stl_empty_or_incomplete" in evidence["failure_reasons"]


def test_l1_registration_rejects_point_artifact_with_single_validation_point(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 insufficient validation"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _request(case_id, model_path)
    artifact_path = _attach_input_provenance(request, tmp_path / "artifacts")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["point_sets"]["validation"] = {
        "source": request["validation_source_points"][:1],
        "target": request["validation_target_points"][:1],
    }
    artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
    request["point_correspondence_artifact_sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    started = client.post("/three-d/registration-jobs", json=request)
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == "validation_source_count_or_shape_invalid"
    assert job["result"]["three_d_evidence"]["navigation_ready"] is False


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing_handedness", "rigid_frame_handedness_invalid"),
        ("matrix_convention_conflict", "rigid_matrix_convention_invalid"),
    ],
)
def test_l1_registration_rejects_incomplete_or_conflicting_frame_metadata(
    tmp_path: Path,
    monkeypatch,
    mutation: str,
    expected_code: str,
) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 frame metadata gate"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _request(case_id, model_path)
    artifact_path = _attach_input_provenance(request, tmp_path / "artifacts")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if mutation == "missing_handedness":
        artifact["coordinate_transform"]["source_frame"].pop("handedness")
    else:
        artifact["coordinate_transform"]["matrix_convention"]["storage_order"] = "column_major"
    artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
    request["point_correspondence_artifact_sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    started = client.post("/three-d/registration-jobs", json=request)
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "failed"
    assert job["result"]["error_code"] == expected_code
    assert job["result"]["three_d_evidence"]["navigation_level"] == "L0"


def test_failed_l1_registration_revokes_prior_l2_active_references(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 revokes stale L2"}).json()["case_id"]
    case_store = tmp_path / "cases.json"
    rows = json.loads(case_store.read_text(encoding="utf-8"))
    rows[0]["three_d_evidence"] = {
        "analysis_mode": "l2_offline_pose_replay",
        "navigation_ready": True,
        "navigation_level": "L2",
        "overlay_evidence": {"path": "historical-overlay.mp4"},
        "pose_manifest_path": "historical-input.json",
        "pose_manifest_sha256": "a" * 64,
        "pose_replay_manifest_path": "historical-replay.json",
        "pose_replay_manifest_sha256": "b" * 64,
        "pose_replay_frames_csv_path": "historical-frames.csv",
        "pose_replay_frames_csv_sha256": "c" * 64,
        "l1_evidence_snapshot": {"navigation_level": "L1"},
        "artifact_lifecycle": {"status": "active", "overlay_active": True},
    }
    case_store.write_text(json.dumps(rows), encoding="utf-8")
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _request(case_id, model_path)
    request["source_points"] = [[0, 0, 0], [1, 1, 1], [2, 2, 2]]
    request["target_points"] = [[1, 0, 0], [2, 1, 1], [3, 2, 2]]

    started = client.post("/three-d/registration-jobs", json=request)
    job = client.get(f"/three-d/registration-jobs/{started.json()['job_id']}").json()

    assert job["status"] == "failed"
    evidence = client.get(f"/cases/{case_id}").json()["three_d_evidence"]
    assert evidence["analysis_mode"] == "l1_static_registration"
    assert evidence["overlay_evidence"] is None
    assert evidence["pose_manifest_path"] is None
    assert evidence["pose_replay_manifest_path"] is None
    assert evidence["pose_replay_frames_csv_path"] is None
    assert evidence["l1_evidence_snapshot"] is None
    assert evidence["artifact_lifecycle"]["overlay_active"] is False
    assert evidence["artifact_lifecycle"]["prior_l2_active_references_revoked"] is True


def test_l1_registration_rejects_untrusted_accepted_review(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "L1 trusted review"}).json()["case_id"]
    model_path = tmp_path / "artifacts" / "models" / "mandible.stl"
    _write_valid_stl(model_path)
    request = _request(case_id, model_path)
    request["doctor_review_status"] = "accepted"

    response = client.post("/three-d/registration-jobs", json=request)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "l1_registration_review_forbidden"
