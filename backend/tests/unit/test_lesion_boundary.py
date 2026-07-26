from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from osteo_vision_core.models.lesion_boundary import (
    _retain_review_candidates,
    assess_candidate_boundaries,
)


def test_retention_suppresses_overlaps_and_preserves_each_boundary_type() -> None:
    rows: list[dict[str, object]] = []
    for index, boundary_type in enumerate(
        (
            "signal_candidate_boundary",
            "high_risk_transition_boundary",
            "uncertain_boundary",
        )
    ):
        offset = index * 200
        rows.extend(
            [
                _candidate(
                    f"{boundary_type}_top",
                    boundary_type,
                    0.99,
                    [offset, 0, offset + 40, 40],
                ),
                _candidate(
                    f"{boundary_type}_overlap",
                    boundary_type,
                    0.98,
                    [offset + 2, 2, offset + 42, 42],
                ),
                _candidate(
                    f"{boundary_type}_far",
                    boundary_type,
                    0.80,
                    [offset + 100, 100, offset + 140, 140],
                ),
            ]
        )

    retained, audit = _retain_review_candidates(
        rows,
        max_per_type=2,
        max_total_candidates=6,
        spatial_iou_threshold=0.35,
        min_center_distance_px=8.0,
    )

    assert len(retained) == 6
    assert audit == {
        "spatial_overlap_suppressed_count": 3,
        "spatial_comparison_count": 6,
        "spatially_diverse_retained_count": 6,
    }
    retained_types = {str(item["boundary_type"]) for item in retained}
    assert retained_types == {
        "signal_candidate_boundary",
        "high_risk_transition_boundary",
        "uncertain_boundary",
    }
    assert all(not str(item["candidate_id"]).endswith("_overlap") for item in retained)


def test_retention_uses_center_distance_and_stops_at_total_limit() -> None:
    rows = [
        _candidate("top", "signal_candidate_boundary", 0.99, [0, 0, 10, 10]),
        _candidate("near", "signal_candidate_boundary", 0.95, [9, 0, 19, 10]),
        *[
            _candidate(
                f"far_{index}",
                "signal_candidate_boundary",
                0.90 - index * 0.01,
                [100 + index * 20, 100, 110 + index * 20, 110],
            )
            for index in range(20)
        ],
    ]

    retained, audit = _retain_review_candidates(
        rows,
        max_per_type=64,
        max_total_candidates=4,
        spatial_iou_threshold=0.95,
        min_center_distance_px=10.0,
    )

    assert [item["candidate_id"] for item in retained] == [
        "top",
        "far_0",
        "far_1",
        "far_2",
    ]
    assert audit["spatial_overlap_suppressed_count"] == 1
    assert audit["spatial_comparison_count"] == 7


def test_assessment_skips_malformed_candidate_bbox_without_failing(
    tmp_path: Path,
) -> None:
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[10:30, 10:30] = 255
    mask_path = tmp_path / "mask.png"
    risk_path = tmp_path / "risk.png"
    uncertain_path = tmp_path / "uncertain.png"
    Image.fromarray(mask).save(mask_path)
    Image.fromarray(np.zeros_like(mask)).save(risk_path)
    Image.fromarray(np.zeros_like(mask)).save(uncertain_path)

    result = assess_candidate_boundaries(
        {
            "mask_path": str(mask_path),
            "risk_mask_path": str(risk_path),
            "uncertain_mask_path": str(uncertain_path),
            "candidates": [
                {
                    "candidate_id": "malformed",
                    "bbox_xyxy": ["bad", 10, 30, 30],
                    "score": "invalid",
                },
                {
                    "candidate_id": "valid",
                    "bbox_xyxy": [10, 10, 30, 30],
                    "score": 0.8,
                    "area_px": 400,
                },
            ],
        },
        output_dir=tmp_path / "output",
        case_id="case_bbox_robustness",
    )

    assert result["available"] is True
    assert result["evaluated_candidate_count"] == 1
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["candidate_id"] == "valid"
    assert Path(result["summary_path"]).is_file()


def test_assessment_sanitizes_invalid_retention_options(tmp_path: Path) -> None:
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[5:20, 5:20] = 255
    mask_path = tmp_path / "mask.png"
    zero_path = tmp_path / "zero.png"
    Image.fromarray(mask).save(mask_path)
    Image.fromarray(np.zeros_like(mask)).save(zero_path)

    result = assess_candidate_boundaries(
        {
            "mask_path": str(mask_path),
            "risk_mask_path": str(zero_path),
            "uncertain_mask_path": str(zero_path),
            "candidates": [{"candidate_id": "valid", "bbox_xyxy": [5, 5, 20, 20], "score": 0.7}],
        },
        output_dir=tmp_path / "output",
        case_id="case_option_robustness",
        max_candidates_per_type=0,
        max_total_candidates=0,
        spatial_iou_threshold=float("nan"),
        spatial_distance_fraction=float("nan"),
    )

    retention = result["candidate_retention"]
    assert retention["max_candidates_per_type"] == 1
    assert retention["max_total_candidates"] == 1
    assert retention["spatial_iou_threshold"] == 0.35
    assert retention["min_center_distance_px"] == 4.0


def _candidate(
    candidate_id: str,
    boundary_type: str,
    ranking_score: float,
    bbox: list[int],
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "boundary_type": boundary_type,
        "review_ranking_score": ranking_score,
        "review_confidence": ranking_score,
        "area_px": max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])),
        "bbox_xyxy": bbox,
    }
