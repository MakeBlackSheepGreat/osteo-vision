from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from osteo_vision_core.models.lesion_boundary import assess_candidate_boundaries
from osteo_vision_core.preprocess.fusion_ai_contract import build_task3_fused_input_contract


def test_task3_fused_input_contract_binds_task2_provenance(tmp_path: Path) -> None:
    white = tmp_path / "white.jpg"
    fluorescence = tmp_path / "fluorescence.jpg"
    fused = tmp_path / "fused.png"
    Image.fromarray(np.full((48, 64, 3), 120, dtype=np.uint8)).save(white)
    Image.fromarray(np.full((48, 64), 80, dtype=np.uint8)).save(fluorescence)
    Image.fromarray(np.full((48, 64, 3), 100, dtype=np.uint8)).save(fused)
    report = {
        "outputs": {"overlay_path": str(fused)},
        "task2_synchronization_context": {
            "schema_version": "osteo-vision-task2-synchronization-context-v1",
            "synchronization_verified": True,
            "white_fluorescence_delta_ms": 3.0,
            "tolerance_ms": 33.34,
        },
        "fusion": {
            "algorithm_version": "fluorescence_fusion_v2",
            "registration_details": {
                "method": "adaptive_multiscale_registration_v1",
                "applied": True,
                "matrix_2x3": [[1.0, 0.0, -2.0], [0.0, 1.0, 1.0]],
                "elapsed_ms": 40.0,
                "quality": 0.8,
            },
            "acceleration": {"backend": "torch_cuda", "elapsed_ms": 30.0},
            "performance": {"registration_ms": 41.0},
        },
    }

    contract = build_task3_fused_input_contract(
        case_id="case-fused",
        white_light_path=white,
        fluorescence_path=fluorescence,
        fused_overlay_path=fused,
        fusion_report=report,
        output_dir=tmp_path / "contract",
    )

    assert contract["engineering_input_eligible"] is True
    assert contract["spatial_interpretation_eligible"] is True
    assert contract["checks"]["task2_compute_under_100ms"] is True
    assert contract["task2_provenance"]["registration_fusion_compute_ms"] == 70.0
    assert contract["model_input"]["sha256"]
    assert Path(contract["contract_path"]).is_file()


def test_task3_fused_input_contract_closes_spatial_use_without_synchronization(tmp_path: Path) -> None:
    white = tmp_path / "white.jpg"
    fluorescence = tmp_path / "fluorescence.jpg"
    fused = tmp_path / "fused.png"
    Image.fromarray(np.full((32, 48, 3), 120, dtype=np.uint8)).save(white)
    Image.fromarray(np.full((32, 48), 80, dtype=np.uint8)).save(fluorescence)
    Image.fromarray(np.full((32, 48, 3), 100, dtype=np.uint8)).save(fused)

    contract = build_task3_fused_input_contract(
        case_id="case-unsynchronized",
        white_light_path=white,
        fluorescence_path=fluorescence,
        fused_overlay_path=fused,
        fusion_report={
            "outputs": {"overlay_path": str(fused)},
            "fusion": {
                "algorithm_version": "fluorescence_fusion_v2",
                "registration_details": {
                    "method": "adaptive_multiscale_registration_v1",
                    "applied": True,
                    "matrix_2x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    "elapsed_ms": 20.0,
                },
                "acceleration": {"backend": "torch_cuda", "elapsed_ms": 20.0},
            },
        },
        output_dir=tmp_path / "contract-unsynchronized",
    )

    assert contract["engineering_input_eligible"] is True
    assert contract["checks"]["task2_synchronization_verified"] is False
    assert contract["spatial_interpretation_eligible"] is False
    assert "task2_synchronization_verified" in contract["degraded_reasons"]


def test_candidate_boundary_assessment_reports_type_and_review_confidence(tmp_path: Path) -> None:
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[16:48, 18:46] = 255
    risk = np.zeros_like(mask)
    risk[14:50, 16:48] = 255
    uncertain = np.zeros_like(mask)
    mask_path = tmp_path / "mask.png"
    risk_path = tmp_path / "risk.png"
    uncertain_path = tmp_path / "uncertain.png"
    Image.fromarray(mask).save(mask_path)
    Image.fromarray(risk).save(risk_path)
    Image.fromarray(uncertain).save(uncertain_path)

    result = assess_candidate_boundaries(
        {
            "mask_path": str(mask_path),
            "risk_mask_path": str(risk_path),
            "uncertain_mask_path": str(uncertain_path),
            "candidates": [
                {
                    "candidate_id": "model_component_1",
                    "bbox_xyxy": [18, 16, 46, 48],
                    "area_px": 896,
                    "score": 0.9,
                    "confidence": 0.95,
                }
            ],
        },
        output_dir=tmp_path / "boundary",
        case_id="case-boundary",
    )

    assert result["available"] is True
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["boundary_type"] == "high_risk_transition_boundary"
    assert 0.0 <= result["candidates"][0]["review_confidence"] <= 1.0
    assert Path(result["summary_path"]).is_file()


def test_candidate_boundary_assessment_caps_each_type_and_reports_suppression(tmp_path: Path) -> None:
    mask = np.zeros((96, 128), dtype=np.uint8)
    candidates: list[dict[str, object]] = []
    for index in range(10):
        x = 4 + index * 11
        mask[20:28, x : x + 8] = 255
        candidates.append(
            {
                "candidate_id": f"model_component_{index + 1}",
                "bbox_xyxy": [x, 20, x + 8, 28],
                "area_px": 64,
                "score": 0.8 + index * 0.01,
                "confidence": 0.9,
            }
        )
    mask_path = tmp_path / "many-mask.png"
    risk_path = tmp_path / "many-risk.png"
    uncertain_path = tmp_path / "many-uncertain.png"
    Image.fromarray(mask).save(mask_path)
    Image.fromarray(np.zeros_like(mask)).save(risk_path)
    Image.fromarray(np.zeros_like(mask)).save(uncertain_path)

    result = assess_candidate_boundaries(
        {
            "mask_path": str(mask_path),
            "risk_mask_path": str(risk_path),
            "uncertain_mask_path": str(uncertain_path),
            "candidates": candidates,
        },
        output_dir=tmp_path / "boundary-cap",
        case_id="case-boundary-cap",
        max_candidates_per_type=3,
    )

    assert result["evaluated_candidate_count"] == 10
    assert result["candidate_count"] == 3
    assert result["suppressed_candidate_count"] == 7
    assert result["evaluated_boundary_type_counts"]["signal_candidate_boundary"] == 10
    assert result["boundary_type_counts"]["signal_candidate_boundary"] == 3
    assert result["candidate_retention"]["max_candidates_per_type"] == 3


def test_candidate_boundary_assessment_attaches_reviewed_activity_class(tmp_path: Path) -> None:
    mask = np.zeros((64, 80), dtype=np.uint8)
    mask[12:44, 16:48] = 255
    mask_path = tmp_path / "activity-mask.png"
    risk_path = tmp_path / "activity-risk.png"
    uncertain_path = tmp_path / "activity-uncertain.png"
    activity_path = tmp_path / "activity-classes.png"
    Image.fromarray(mask).save(mask_path)
    Image.fromarray(np.zeros_like(mask)).save(risk_path)
    Image.fromarray(np.zeros_like(mask)).save(uncertain_path)
    activity = np.zeros_like(mask)
    activity[12:44, 16:40] = 1
    activity[12:44, 40:48] = 2
    Image.fromarray(activity).save(activity_path)

    result = assess_candidate_boundaries(
        {
            "mask_path": str(mask_path),
            "risk_mask_path": str(risk_path),
            "uncertain_mask_path": str(uncertain_path),
            "candidates": [
                {
                    "candidate_id": "model_component_1",
                    "bbox_xyxy": [16, 12, 48, 44],
                    "area_px": 1024,
                    "score": 0.85,
                    "confidence": 0.9,
                }
            ],
        },
        output_dir=tmp_path / "activity-boundary",
        case_id="case-activity-boundary",
        activity_spectrum={
            "available": True,
            "status": "available_for_physician_review",
            "activity_class_map_path": str(activity_path),
            "calibration_status": "pending_target_domain_validation",
        },
    )

    candidate = result["candidates"][0]
    assert result["activity_evidence"]["available"] is True
    assert candidate["activity_class"] == "low_activity_candidate"
    assert candidate["activity_overlap_fraction"] == 0.75
