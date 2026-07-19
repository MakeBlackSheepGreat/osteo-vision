from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from tools.run_d036_digital_phantom_navigation_validation import (
    FRAME_COUNT,
    build_geometry,
    build_tampered_l1_binding_manifest,
    load_binary_stl_candidate_vertices,
    rigid_matrix,
    select_spatially_distributed_points,
    sha256_file,
    transform_points,
    validate_summary_safety_contract,
    verify_validation_bundle,
    write_digital_phantom_video,
)


def _write_binary_stl(path: Path) -> Path:
    triangles: list[np.ndarray] = []
    for index in range(24):
        base = np.asarray(
            [
                float(index % 6) * 4.0,
                float((index // 6) % 4) * 5.0,
                float((index * 3) % 7) * 2.0,
            ],
            dtype=np.float32,
        )
        triangles.append(
            np.stack(
                [
                    base,
                    base + np.asarray([1.5, 0.2, 0.4], dtype=np.float32),
                    base + np.asarray([0.1, 1.7, 0.8], dtype=np.float32),
                ]
            )
        )
    header = b"D036 deterministic binary STL unit fixture".ljust(80, b"\x00")
    payload = bytearray(header)
    payload.extend(struct.pack("<I", len(triangles)))
    for triangle in triangles:
        normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        normal /= np.linalg.norm(normal)
        payload.extend(struct.pack("<12fH", *normal.tolist(), *triangle.reshape(-1).tolist(), 0))
    path.write_bytes(payload)
    return path


def test_binary_stl_candidates_and_spatial_point_selection(tmp_path: Path) -> None:
    model_path = _write_binary_stl(tmp_path / "fixture.stl")

    candidates, metadata = load_binary_stl_candidate_vertices(model_path, max_candidates=100)
    selected = select_spatially_distributed_points(candidates, 12)

    assert metadata["triangle_count"] == 24
    assert metadata["raw_vertex_count"] == 72
    assert metadata["header_identity_warning"] is False
    assert selected.shape == (12, 3)
    assert np.linalg.matrix_rank(selected - selected.mean(axis=0)) == 3


def test_known_rigid_transform_is_applied_in_homogeneous_coordinates() -> None:
    points = np.asarray([[0.0, 0.0, 0.0], [5.0, 2.0, -1.0], [1.0, 7.0, 3.0]])
    matrix = rigid_matrix([0.0, 0.0, 0.0], [4.0, -3.0, 2.0])

    transformed = transform_points(points, matrix)

    np.testing.assert_allclose(transformed, points + np.asarray([4.0, -3.0, 2.0]))


def test_digital_phantom_video_has_deterministic_contract(tmp_path: Path) -> None:
    model_path = _write_binary_stl(tmp_path / "fixture.stl")
    geometry = build_geometry(model_path)

    artifact = write_digital_phantom_video(tmp_path / "phantom.mp4", geometry)

    assert artifact["frame_count"] == FRAME_COUNT
    assert artifact["image_size_px"] == [1280, 720]
    assert artifact["target_domain_flag"] is False
    assert len(artifact["sha256"]) == 64


def test_tamper_builder_changes_only_l1_model_binding() -> None:
    manifest = {
        "schema_version": "osteo-vision-l2-pose-input-v3",
        "l1_model_sha256": "a" * 64,
        "l1_transform_sha256": "b" * 64,
        "poses": [{"frame_index": 0}],
    }

    tampered = build_tampered_l1_binding_manifest(manifest)

    assert tampered["l1_model_sha256"] == "0" * 64
    assert tampered["l1_transform_sha256"] == manifest["l1_transform_sha256"]
    assert tampered["poses"] == manifest["poses"]
    assert manifest["l1_model_sha256"] == "a" * 64


def test_summary_safety_contract_requires_l2_gate_tamper_rejection_and_final_l0() -> None:
    summary: dict[str, Any] = {
        "navigation_claim_allowed": False,
        "target_domain_flag": False,
        "validation_results": {
            "l2_software_gate": {
                "navigation_level": "L2",
                "l1_chain_binding_status": "verified_same_l1_chain",
            },
            "l1_binding_tamper_injection": {
                "error_code": "l1_chain_binding_mismatch",
            },
        },
        "final_persisted_case_state": {
            "navigation_level": "L0",
            "navigation_ready": False,
        },
    }

    validate_summary_safety_contract(summary)
    summary["final_persisted_case_state"]["navigation_level"] = "L2"

    with pytest.raises(RuntimeError, match="summary_final_fail_closed_state_invalid"):
        validate_summary_safety_contract(summary)


def test_validation_bundle_verifier_recomputes_inventory_hashes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifact_path = run_dir / "artifact.json"
    artifact_path.write_text('{"status":"ok"}\n', encoding="utf-8")
    model_path = tmp_path / "model.stl"
    model_path.write_bytes(b"model-fixture")
    summary = {
        "run_directory": str(run_dir),
        "navigation_claim_allowed": False,
        "target_domain_flag": False,
        "validation_results": {
            "l2_software_gate": {
                "navigation_level": "L2",
                "l1_chain_binding_status": "verified_same_l1_chain",
            },
            "l1_binding_tamper_injection": {
                "error_code": "l1_chain_binding_mismatch",
            },
        },
        "final_persisted_case_state": {
            "navigation_level": "L0",
            "navigation_ready": False,
        },
        "artifact_inventory": [
            {
                "relative_path": "artifact.json",
                "size_bytes": artifact_path.stat().st_size,
                "sha256": sha256_file(artifact_path),
            }
        ],
        "model_provenance": {
            "model_path": str(model_path),
            "model_sha256": sha256_file(model_path),
        },
    }
    summary_path = run_dir / "validation_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    result = verify_validation_bundle(summary_path)

    assert result["status"] == "verified"
    assert result["verified_artifact_count"] == 1
    artifact_path.write_text('{"status":"changed"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="validation_artifact_size_mismatch"):
        verify_validation_bundle(summary_path)
