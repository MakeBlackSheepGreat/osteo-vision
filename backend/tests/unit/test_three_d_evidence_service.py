from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.schemas import CaseInputAsset
from backend.src.services.three_d_evidence import build_three_d_evidence, three_d_evidence_summary


def _write_transform(path: Path, matrix: list[list[float]] | None = None) -> str:
    payload = matrix or [
        [1.0, 0.0, 0.0, 10.0],
        [0.0, 1.0, 0.0, 20.0],
        [0.0, 0.0, 1.0, 30.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    path.write_text(json.dumps({"matrix": payload}), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_transform_chain() -> list[dict[str, object]]:
    return [
        {
            "name": "CBCT RAS to phantom",
            "from_space": "cbct_ras",
            "to_space": "phantom_reference",
            "direction": "forward",
            "unit": "mm",
            "status": "verified",
        },
        {
            "name": "phantom to camera",
            "from_space": "phantom_reference",
            "to_space": "camera_optical",
            "direction": "forward",
            "unit": "mm",
            "status": "verified",
        },
    ]


def test_three_d_evidence_defaults_to_non_navigation_reference() -> None:
    evidence = build_three_d_evidence(
        parameters={},
        source_inputs=[
            CaseInputAsset(input_id="video_1", channel=InputChannel.VIDEO, path="case.mp4", mime_type="video/mp4")
        ],
        analysis_mode="video_file_keyframes",
        run_id="run_001",
    )

    assert evidence["schema_version"] == "osteo-vision-three-d-evidence-v2"
    assert evidence["model_path"] is None
    assert evidence["registration_status"] == "unregistered"
    assert evidence["navigation_ready"] is False
    assert evidence["source_inputs"][0]["channel"] == "video"
    assert evidence["transform_chain"][-1]["status"] == "missing"
    assert "not intraoperative navigation" in evidence["boundary_note"]


def test_three_d_evidence_rejects_self_reported_navigation_readiness(tmp_path: Path) -> None:
    transform_path = tmp_path / "case_001.json"
    transform_sha256 = _write_transform(transform_path)
    evidence = build_three_d_evidence(
        parameters={
            "three_d_evidence": {
                "model_path": "artifacts/models/case_001_mandible.glb",
                "registration_status": "registered",
                "registration_error_mm": "0.72",
                "registration_error_threshold_mm": 1.0,
                "registration_error_source": "independent_target_points",
                "navigation_ready": "true",
                "coordinate_space": "cbct_ras",
                "transform_path": str(transform_path),
                "transform_sha256": transform_sha256,
                "transform_chain": _valid_transform_chain(),
                "doctor_review_status": "accepted",
                "microscope_pose_evidence": {
                    "calibration_status": "valid",
                    "magnification": 4.0,
                    "calibration_magnification_min": 2.0,
                    "calibration_magnification_max": 8.0,
                    "working_distance_mm": 250.0,
                    "calibration_working_distance_min_mm": 200.0,
                    "calibration_working_distance_max_mm": 300.0,
                    "pose_tracking_status": "tracking",
                    "time_offset_ms": 12,
                    "depth_status": "valid",
                    "tre_mm": 0.8,
                    "tre_threshold_mm": 1.5,
                    "drift_mm": 0.2,
                    "drift_threshold_mm": 0.5,
                },
                "registration_markups": [{"id": "F1", "status": "accepted"}],
            }
        },
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_002",
    )
    summary = three_d_evidence_summary(evidence)

    assert evidence["model_format"] == "glb"
    assert evidence["model_file_name"] == "case_001_mandible.glb"
    assert evidence["registration_error_mm"] == 0.72
    assert evidence["navigation_ready"] is False
    assert evidence["navigation_level"] == "L0"
    assert "camera_calibration_artifact_not_verified" in evidence["failure_reasons"]
    assert "threshold_approval_missing" in evidence["failure_reasons"]
    assert "camera_registration_not_verified" in evidence["failure_reasons"]
    assert evidence["transform_validation"]["sha256"] == transform_sha256
    assert evidence["transform_validation"]["matrix_invertible"] is True
    assert evidence["coordinate_chain_validation"]["valid"] is True
    assert evidence["registration_markups"] == [{"id": "F1", "status": "accepted"}]
    assert summary["model_available"] is True
    assert summary["navigation_ready"] is False


def test_three_d_evidence_degrades_when_tracking_or_tre_evidence_is_missing() -> None:
    evidence = build_three_d_evidence(
        parameters={"three_d_evidence": {"registration_status": "registered", "transform_path": "case.tfm"}},
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_safe",
    )
    assert evidence["navigation_ready"] is False
    assert evidence["navigation_level"] == "L0"
    assert evidence["fallback_mode"] == "unregistered_3d_reference"
    assert "tre_not_recorded" in evidence["failure_reasons"]


def test_three_d_evidence_rejects_missing_or_tampered_transform(tmp_path: Path) -> None:
    transform_path = tmp_path / "transform.json"
    _write_transform(transform_path)

    evidence = build_three_d_evidence(
        parameters={
            "three_d_evidence": {
                "registration_status": "registered",
                "registration_error_mm": 0.5,
                "registration_error_threshold_mm": 1.0,
                "registration_error_source": "phantom_ground_truth",
                "coordinate_space": "cbct_ras",
                "transform_path": str(transform_path),
                "transform_sha256": "0" * 64,
                "transform_chain": _valid_transform_chain(),
                "doctor_review_status": "accepted",
                "navigation_level": "L1",
                "microscope_pose_evidence": {
                    "calibration_status": "verified",
                    "magnification": 4,
                    "calibration_magnification_min": 2,
                    "calibration_magnification_max": 8,
                    "working_distance_mm": 250,
                    "calibration_working_distance_min_mm": 200,
                    "calibration_working_distance_max_mm": 300,
                    "depth_status": "verified",
                },
            }
        },
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_tampered",
    )

    assert evidence["navigation_ready"] is False
    assert evidence["navigation_level"] == "L0"
    assert "transform_sha256_mismatch" in evidence["failure_reasons"]


def test_three_d_evidence_rejects_invalid_matrix_and_chain(tmp_path: Path) -> None:
    transform_path = tmp_path / "singular.json"
    transform_sha256 = _write_transform(
        transform_path,
        [
            [1.0, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    )
    chain = _valid_transform_chain()
    chain[1]["from_space"] = "tracker_reference"
    chain[1]["unit"] = "cm"

    evidence = build_three_d_evidence(
        parameters={
            "three_d_evidence": {
                "registration_status": "registered",
                "registration_error_mm": 0.5,
                "registration_error_threshold_mm": 1.0,
                "registration_error_source": "phantom_ground_truth",
                "coordinate_space": "cbct_ras",
                "transform_path": str(transform_path),
                "transform_sha256": transform_sha256,
                "transform_chain": chain,
                "doctor_review_status": "accepted",
                "navigation_level": "L1",
                "microscope_pose_evidence": {
                    "calibration_status": "verified",
                    "magnification": 4,
                    "calibration_magnification_min": 2,
                    "calibration_magnification_max": 8,
                    "working_distance_mm": 250,
                    "calibration_working_distance_min_mm": 200,
                    "calibration_working_distance_max_mm": 300,
                    "depth_status": "verified",
                },
            }
        },
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_invalid",
    )

    assert evidence["navigation_ready"] is False
    assert "transform_matrix_not_invertible" in evidence["failure_reasons"]
    assert "coordinate_chain_discontinuous" in evidence["failure_reasons"]
    assert "coordinate_chain_unit_discontinuous" in evidence["failure_reasons"]


def test_three_d_evidence_l1_requires_registration_error_and_calibration_ranges(tmp_path: Path) -> None:
    transform_path = tmp_path / "transform.json"
    transform_sha256 = _write_transform(transform_path)
    evidence = build_three_d_evidence(
        parameters={
            "three_d_evidence": {
                "registration_status": "registered",
                "registration_error_mm": 1.2,
                "registration_error_threshold_mm": 1.0,
                "coordinate_space": "cbct_ras",
                "transform_path": str(transform_path),
                "transform_sha256": transform_sha256,
                "transform_chain": _valid_transform_chain(),
                "doctor_review_status": "accepted",
                "navigation_level": "L1",
                "microscope_pose_evidence": {
                    "calibration_status": "verified",
                    "magnification": 10,
                    "calibration_magnification_min": 2,
                    "calibration_magnification_max": 8,
                    "working_distance_mm": 350,
                    "calibration_working_distance_min_mm": 200,
                    "calibration_working_distance_max_mm": 300,
                    "depth_status": "verified",
                },
            }
        },
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_ranges",
    )

    assert evidence["navigation_ready"] is False
    assert evidence["navigation_level"] == "L0"
    assert "registration_error_source_missing" in evidence["failure_reasons"]
    assert "registration_error_threshold_exceeded" in evidence["failure_reasons"]
    assert "magnification_out_of_calibration_range" in evidence["failure_reasons"]
    assert "working_distance_out_of_calibration_range" in evidence["failure_reasons"]


def test_three_d_evidence_demo_entry_is_public_cbct_non_navigation_reference() -> None:
    evidence = build_three_d_evidence(
        parameters={"three_d_evidence_demo": "d024_mandible"},
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_demo",
    )

    reference_directory = "artifacts/platform/three_d_runtime/references/d024"
    assert evidence["model_path"] == f"{reference_directory}/mandible_d024_0001.stl"
    assert evidence["geometry_manifest_path"] == f"{reference_directory}/mandible_d024_0001.brp_geometry_manifest.json"
    assert evidence["model_format"] == "stl"
    assert evidence["model_source"] == "D024 DentVoxel public CBCT derived mandible label"
    assert evidence["registration_status"] == "unregistered"
    assert evidence["navigation_ready"] is False
    assert evidence["doctor_review_status"] == "not_reviewed"
    assert evidence["scene_manifest"]["schema_version"] == "osteo-vision-three-d-scene-v1"
    assert evidence["scene_manifest"]["mandibular_curve"]["label"] == "D024 mandibular reference curve"
    assert evidence["scene_manifest"]["review_planes"][0]["status"] == "illustrative_unregistered"
    assert evidence["scene_manifest_v2"]["schema_version"] == "osteo-vision-three-d-scene-v2"
    assert evidence["scene_manifest_v2"]["scene"]["navigation_ready"] is False
    assert evidence["scene_manifest_v2"]["nodes"][2]["path"] == f"{reference_directory}/mandible_d024_0001.stl"
    assert "non-target-domain" in evidence["boundary_note"]
