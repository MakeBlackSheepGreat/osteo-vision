from __future__ import annotations

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.schemas import CaseInputAsset
from backend.src.services.three_d_evidence import build_three_d_evidence, three_d_evidence_summary


def test_three_d_evidence_defaults_to_non_navigation_reference() -> None:
    evidence = build_three_d_evidence(
        parameters={},
        source_inputs=[
            CaseInputAsset(input_id="video_1", channel=InputChannel.VIDEO, path="case.mp4", mime_type="video/mp4")
        ],
        analysis_mode="video_file_keyframes",
        run_id="run_001",
    )

    assert evidence["schema_version"] == "osteo-vision-three-d-evidence-v1"
    assert evidence["model_path"] is None
    assert evidence["registration_status"] == "unregistered"
    assert evidence["navigation_ready"] is False
    assert evidence["source_inputs"][0]["channel"] == "video"
    assert evidence["transform_chain"][-1]["status"] == "missing"
    assert "not intraoperative navigation" in evidence["boundary_note"]


def test_three_d_evidence_sanitizes_explicit_registered_model() -> None:
    evidence = build_three_d_evidence(
        parameters={
            "three_d_evidence": {
                "model_path": "artifacts/models/case_001_mandible.glb",
                "registration_status": "registered",
                "registration_error_mm": "0.72",
                "navigation_ready": "true",
                "coordinate_space": "cbct_ras",
                "transform_path": "artifacts/transforms/case_001.tfm",
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
    assert evidence["navigation_ready"] is True
    assert evidence["registration_markups"] == [{"id": "F1", "status": "accepted"}]
    assert summary["model_available"] is True
    assert summary["navigation_ready"] is True


def test_three_d_evidence_demo_entry_is_public_cbct_non_navigation_reference() -> None:
    evidence = build_three_d_evidence(
        parameters={"three_d_evidence_demo": "d024_mandible"},
        source_inputs=[],
        analysis_mode="video_file_keyframes",
        run_id="run_demo",
    )

    assert evidence["model_path"] == "frontend/public/models/local/mandible_d024_0001.stl"
    assert evidence["model_format"] == "stl"
    assert evidence["model_source"] == "D024 DentVoxel public CBCT derived mandible label"
    assert evidence["registration_status"] == "unregistered"
    assert evidence["navigation_ready"] is False
    assert evidence["doctor_review_status"] == "not_reviewed"
    assert evidence["scene_manifest"]["schema_version"] == "osteo-vision-three-d-scene-v1"
    assert evidence["scene_manifest"]["mandibular_curve"]["label"] == "D024 mandibular reference curve"
    assert evidence["scene_manifest"]["review_planes"][0]["status"] == "illustrative_unregistered"
    assert "non-target-domain" in evidence["boundary_note"]
