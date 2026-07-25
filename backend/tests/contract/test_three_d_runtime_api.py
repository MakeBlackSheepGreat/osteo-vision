from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app
from backend.osteo_vision_api.domains.cases.enums import ReviewState
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import AnalysisRun, CandidateRegion, CaseRecord, ClinicalContext
from backend.osteo_vision_api.services import three_d_runtime_snapshot


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_JOB_STORE_PATH", str(tmp_path / "jobs.json"))
    return TestClient(create_app())


def _write_case_with_model(tmp_path: Path) -> tuple[CaseRecord, Path]:
    model_path = tmp_path / "artifacts" / "three_d_models" / "case_runtime.stl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        "solid runtime\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid runtime\n",
        encoding="utf-8",
    )
    case = CaseRecord(
        case_id="case_runtime_001",
        title="Sensitive patient title excluded from renderer snapshot",
        clinical_context=ClinicalContext(
            age_years=77,
            sex_at_birth="female",
            comorbidities=["diabetes"],
            medications=["drug-a"],
            labs=[{"name": "CRP", "value": 18.2, "unit": "mg/L", "abnormal_flag": "high"}],
        ),
        three_d_evidence={
            "schema_version": "osteo-vision-three-d-evidence-v2",
            "model_path": str(model_path),
            "model_format": "stl",
            "model_file_name": model_path.name,
            "model_source": f"uploaded from {model_path}",
            "registration_status": "unregistered",
            "navigation_level": "L0",
            "navigation_ready": False,
            "doctor_review_status": "review_required",
            "fallback_mode": "unregistered_3d_reference",
            "failure_reasons": ["registration_evidence_missing"],
            "boundary_note": "三维检查仅提供医生复核证据，保持 L0 未配准参考。",
            "scene_manifest_v2": {
                "schema_version": "osteo-vision-three-d-scene-v2",
                "nodes": [{"id": "model", "name": "mandible", "path": str(model_path)}],
                "transforms": [{"name": "surface_to_video", "path": str(model_path)}],
            },
            "camera_calibration_evidence": {"artifact_path": str(model_path)},
        },
        analysis_runs=[
            AnalysisRun(
                run_id="run_runtime_001",
                case_id="case_runtime_001",
                candidate_regions=[
                    CandidateRegion(
                        candidate_id="candidate_runtime_001",
                        run_id="run_runtime_001",
                        risk_type="boundary_risk",
                        score=0.42,
                        confidence=0.88,
                        status=ReviewState.REVIEW_REQUIRED,
                        metadata={
                            "frame_key": "frame_12",
                            "frame_index": 12,
                            "timestamp_sec": 1.2,
                            "bbox_normalized": [0.2, 0.3, 0.5, 0.7],
                            "source_path": str(model_path),
                            "clinical_context": {"age_years": 77},
                        },
                    )
                ],
                fused_outputs={"mode": "video_file_keyframes"},
                quantitative_summary={
                    "frame_count": 10,
                    "hotspot_candidate_count": 1,
                    "patient_conditioning": {"age_years": 77},
                    "clinical_context": {"labs": ["CRP"]},
                    "artifact_path": str(model_path),
                },
            )
        ],
    )
    JsonCaseRepository(tmp_path / "cases.json").create(case)
    return case, model_path


def test_case_runtime_snapshot_excludes_patient_context_and_raw_paths(tmp_path: Path, monkeypatch) -> None:
    case, model_path = _write_case_with_model(tmp_path)
    client = _client(tmp_path, monkeypatch)

    response = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "osteo-vision-three-d-runtime-snapshot-v2"
    assert payload["case_id"] == case.case_id
    assert payload["case_version"] == 1
    assert len(payload["snapshot_sha256"]) == 64
    assert payload["mode_label"] == "MP4 候选区空间证据"
    assert payload["model_asset"] == {
        "asset_id": "model",
        "url": f"/three-d-runtime/v1/cases/{case.case_id}/assets/model",
        "format": "stl",
        "file_name": model_path.name,
        "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "size_bytes": model_path.stat().st_size,
        "rendering_status": "ready",
        "rendering_failure_reason": None,
    }
    assert payload["spatial_mapping"] == {
        "schema_version": "osteo-vision-three-d-runtime-spatial-mapping-v1",
        "model_coordinate_space": None,
        "transform_sha256": None,
        "status": "unavailable",
        "failure_reasons": [
            "model_coordinate_space_missing",
            "transform_sha256_missing",
            "transform_validation_unverified",
            "coordinate_chain_validation_unverified",
        ],
    }
    assert payload["safety"] == {
        "navigation_level": "L0",
        "navigation_ready": False,
        "registration_status": "unregistered",
        "doctor_review_status": "review_required",
        "fallback_mode": "unregistered_3d_reference",
        "failure_reasons": ["registration_evidence_missing"],
        "boundary": "三维检查仅提供医生复核证据，保持 L0 未配准参考。",
    }
    assert payload["candidate_regions"] == [
        {
            "candidate_id": "candidate_runtime_001",
            "risk_type": "boundary_risk",
            "score": 0.42,
            "confidence": 0.88,
            "status": "review_required",
            "frame_key": "frame_12",
            "frame_index": 12,
            "timestamp_sec": 1.2,
            "bbox_normalized": [0.2, 0.3, 0.5, 0.7],
        }
    ]
    assert payload["metrics"] == {"frame_count": 10, "hotspot_candidate_count": 1}
    assert "model_path" not in payload["three_d_evidence"]
    assert "model_file_name" not in payload["three_d_evidence"]
    assert "camera_calibration_evidence" not in payload["three_d_evidence"]
    assert "path" not in payload["three_d_evidence"]["scene_manifest_v2"]["nodes"][0]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "clinical_context" not in serialized
    assert "diabetes" not in serialized
    assert "drug-a" not in serialized
    assert str(model_path) not in serialized
    assert case.title not in serialized


def test_case_runtime_model_asset_download_is_case_bound(tmp_path: Path, monkeypatch) -> None:
    case, model_path = _write_case_with_model(tmp_path)
    client = _client(tmp_path, monkeypatch)

    response = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/assets/model")

    assert response.status_code == 200
    assert response.content == model_path.read_bytes()
    assert response.headers["content-type"].startswith("model/stl")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["etag"] == f'"{hashlib.sha256(model_path.read_bytes()).hexdigest()}"'
    assert client.get(f"/three-d-runtime/v1/cases/{case.case_id}/assets/geometry_manifest").status_code == 404


def test_case_runtime_rejects_model_paths_outside_controlled_roots(tmp_path: Path, monkeypatch) -> None:
    case, _ = _write_case_with_model(tmp_path)
    outside_path = tmp_path / "outside.stl"
    outside_path.write_text("solid outside\nendsolid outside\n", encoding="utf-8")
    stored = JsonCaseRepository(tmp_path / "cases.json").get(case.case_id)
    assert stored is not None
    JsonCaseRepository(tmp_path / "cases.json").save(
        stored.model_copy(update={"three_d_evidence": {**stored.three_d_evidence, "model_path": str(outside_path)}})
    )
    client = _client(tmp_path, monkeypatch)

    snapshot = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/snapshot")

    assert snapshot.status_code == 200
    assert snapshot.json()["model_asset"] is None
    assert client.get(f"/three-d-runtime/v1/cases/{case.case_id}/assets/model").status_code == 404
    assert str(outside_path) not in snapshot.text


def test_case_runtime_marks_gltf_as_non_renderable_without_hiding_the_evidence(tmp_path: Path, monkeypatch) -> None:
    case, model_path = _write_case_with_model(tmp_path)
    gltf_path = model_path.with_suffix(".gltf")
    gltf_path.write_text(
        json.dumps(
            {
                "asset": {"version": "2.0"},
                "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
            }
        ),
        encoding="utf-8",
    )
    stored = JsonCaseRepository(tmp_path / "cases.json").get(case.case_id)
    assert stored is not None
    JsonCaseRepository(tmp_path / "cases.json").save(
        stored.model_copy(update={"three_d_evidence": {**stored.three_d_evidence, "model_path": str(gltf_path)}})
    )
    client = _client(tmp_path, monkeypatch)

    payload = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/snapshot").json()

    assert payload["model_asset"]["format"] == "gltf"
    assert payload["model_asset"]["rendering_status"] == "unsupported_format"
    assert payload["model_asset"]["rendering_failure_reason"] == "gltf_not_supported_by_isolated_renderer"
    assert client.get(payload["model_asset"]["url"]).status_code == 200


def test_case_runtime_safety_rejects_incomplete_navigation_claims(tmp_path: Path, monkeypatch) -> None:
    case, _ = _write_case_with_model(tmp_path)
    stored = JsonCaseRepository(tmp_path / "cases.json").get(case.case_id)
    assert stored is not None
    JsonCaseRepository(tmp_path / "cases.json").save(
        stored.model_copy(
            update={
                "three_d_evidence": {
                    **stored.three_d_evidence,
                    "navigation_ready": True,
                    "navigation_level": "L2",
                    "registration_status": "unregistered",
                }
            }
        )
    )
    client = _client(tmp_path, monkeypatch)

    safety = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/snapshot").json()["safety"]

    assert safety["navigation_ready"] is False
    assert "navigation_prerequisites_incomplete" in safety["failure_reasons"]


def test_case_runtime_safety_requires_the_versioned_coordinate_and_review_gate(tmp_path: Path, monkeypatch) -> None:
    case, _ = _write_case_with_model(tmp_path)
    stored = JsonCaseRepository(tmp_path / "cases.json").get(case.case_id)
    assert stored is not None
    JsonCaseRepository(tmp_path / "cases.json").save(
        stored.model_copy(
            update={
                "three_d_evidence": {
                    **stored.three_d_evidence,
                    "navigation_ready": True,
                    "navigation_level": "L1",
                    "registration_status": "registered",
                    "doctor_review_status": "not_reviewed",
                    "transform_chain": [],
                }
            }
        )
    )
    client = _client(tmp_path, monkeypatch)

    payload = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/snapshot").json()

    assert payload["safety"]["navigation_ready"] is False
    assert payload["safety"]["navigation_level"] == "L0"
    assert "runtime_navigation_safety_gate_version_unverified" in payload["safety"]["failure_reasons"]
    assert "runtime_doctor_review_not_accepted" in payload["safety"]["failure_reasons"]
    assert "runtime_transform_validation_unverified" in payload["safety"]["failure_reasons"]
    assert "runtime_coordinate_chain_validation_unverified" in payload["safety"]["failure_reasons"]
    assert "runtime_spatial_mapping_unverified" in payload["safety"]["failure_reasons"]


def test_case_runtime_keeps_the_checksum_bound_candidate_coordinate_contract(tmp_path: Path, monkeypatch) -> None:
    case, _ = _write_case_with_model(tmp_path)
    stored = JsonCaseRepository(tmp_path / "cases.json").get(case.case_id)
    assert stored is not None
    run = stored.analysis_runs[0].model_copy(
        update={
            "candidate_regions": [
                stored.analysis_runs[0].candidate_regions[0].model_copy(
                    update={
                        "metadata": {
                            "surface_point_mm": [10.0, 20.0, 30.0],
                            "coordinate_space": "cbct_ras",
                            "spatial_mapping_status": "verified",
                            "coordinate_transform_sha256": "a" * 64,
                        }
                    }
                )
            ]
        }
    )
    JsonCaseRepository(tmp_path / "cases.json").save(stored.model_copy(update={"analysis_runs": [run]}))
    client = _client(tmp_path, monkeypatch)

    candidate = client.get(f"/three-d-runtime/v1/cases/{case.case_id}/snapshot").json()["candidate_regions"][0]

    assert candidate["surface_point_mm"] == [10.0, 20.0, 30.0]
    assert candidate["coordinate_space"] == "cbct_ras"
    assert candidate["spatial_mapping_status"] == "verified"
    assert candidate["coordinate_transform_sha256"] == "a" * 64


def test_public_d024_reference_uses_same_snapshot_contract_and_controlled_asset(tmp_path: Path, monkeypatch) -> None:
    reference_path = tmp_path / "artifacts" / "public_d024.stl"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text("solid d024\nendsolid d024\n", encoding="utf-8")
    monkeypatch.setattr(three_d_runtime_snapshot, "D024_REFERENCE_MODEL_PATH", reference_path)
    client = _client(tmp_path, monkeypatch)

    response = client.get("/three-d-runtime/v1/references/d024/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "osteo-vision-three-d-runtime-snapshot-v2"
    assert payload["case_id"] == "reference_d024"
    assert payload["mode_label"] == "公开 D024 下颌参考"
    assert payload["candidate_regions"] == []
    assert payload["three_d_evidence"]["input_domain"] == "public_reference_non_target_domain"
    assert payload["three_d_evidence"]["view_space_mapping"]["display_up_axis"] == "-physical_z"
    assert payload["three_d_evidence"]["view_space_mapping"]["frontend_rotation_x_degrees"] == 90
    assert payload["three_d_evidence"]["view_space_mapping"]["frontend_rotation_z_degrees"] == 180
    assert payload["three_d_evidence"]["view_space_mapping"]["frontend_rotation_order"] == "ZXY"
    assert payload["safety"]["navigation_level"] == "L0"
    assert payload["safety"]["navigation_ready"] is False
    assert payload["model_asset"]["url"] == "/three-d-runtime/v1/references/d024/assets/model"
    assert str(reference_path) not in response.text

    asset = client.get(payload["model_asset"]["url"])
    assert asset.status_code == 200
    assert asset.content == reference_path.read_bytes()
    assert client.get("/three-d-runtime/v1/references/unknown/snapshot").status_code == 404


def test_snapshot_hash_uses_versioned_cross_runtime_encoding(tmp_path: Path, monkeypatch) -> None:
    reference_path = tmp_path / "artifacts" / "public_d024.stl"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_text("solid d024\nendsolid d024\n", encoding="utf-8")
    monkeypatch.setattr(three_d_runtime_snapshot, "D024_REFERENCE_MODEL_PATH", reference_path)
    client = _client(tmp_path, monkeypatch)

    payload = client.get("/three-d-runtime/v1/references/d024/snapshot").json()
    unsigned = {key: value for key, value in payload.items() if key != "snapshot_sha256"}
    assert three_d_runtime_snapshot._payload_sha256(unsigned) == payload["snapshot_sha256"]

    vector = {
        "schema_version": "osteo-vision-three-d-runtime-snapshot-v2",
        "numbers": [-0.0, 0.0, 1e-7, 1e-6, 1e20, 1e21],
        "integer_keys": {"10": 1, "2": 2},
        "unicode_keys": {"\ue000": "BMP", "😀": "emoji", "边界": "医生复核"},
        "nested": [{"active": True, "value": None}],
    }

    assert (
        three_d_runtime_snapshot._payload_sha256(vector)
        == "680bb7c661eff18fe2b3512b46ad6d15831aa54df59d578d5df59ffd04325a1e"
    )
