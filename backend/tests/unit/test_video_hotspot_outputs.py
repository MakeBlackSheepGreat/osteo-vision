from __future__ import annotations

from pathlib import Path

from backend.osteo_vision_api.domains.cases.enums import ArtifactKind
from backend.osteo_vision_api.services.video_hotspot_outputs import (
    build_hotspot_candidate_regions,
    hotspot_artifacts,
    summarize_hotspot_outputs,
    video_manifest_artifacts,
    video_segmentation_artifacts,
)


def test_summary_skips_malformed_and_non_finite_values() -> None:
    summary = summarize_hotspot_outputs(
        [
            {
                "quantification": {
                    "positive_area_fraction": 0.2,
                    "roi_positive_area_fraction": 0.5,
                    "component_count": 2,
                }
            },
            {
                "quantification": {
                    "positive_area_fraction": "nan",
                    "roi_positive_area_fraction": "inf",
                    "component_count": "bad",
                }
            },
            {
                "quantification": {
                    "positive_area_fraction": -1,
                    "roi_positive_area_fraction": -2,
                    "component_count": -3,
                }
            },
            {},
        ]
    )

    assert summary == {
        "hotspot_frame_count": 4,
        "hotspot_candidate_count": 2,
        "hotspot_max_positive_area_fraction": 0.2,
        "hotspot_mean_positive_area_fraction": 0.05,
        "hotspot_roi_max_positive_area_fraction": 0.5,
        "hotspot_roi_mean_positive_area_fraction": 0.125,
    }


def test_candidate_selection_uses_highest_valid_scores_and_ignores_invalid_values() -> None:
    candidates = build_hotspot_candidate_regions(
        "run_001",
        [
            {"frame_index": 1, "quantification": {"positive_area_fraction": "nan"}},
            {"frame_index": 2, "quantification": {"positive_area_fraction": 0.1}},
            {"frame_index": 3, "quantification": {"positive_area_fraction": 0.9, "max_probability": "inf"}},
            {"frame_index": 4, "quantification": {"positive_area_fraction": 0.4, "mean_probability": 0.7}},
            {"frame_index": 5, "quantification": {"positive_area_fraction": 0.2}},
            {"frame_index": 6, "quantification": {"positive_area_fraction": 0.3}},
        ],
        frame_details=[
            {"frame_index": 3, "frame_key": "key-3", "spatial_mapping": {"source_video_width": 1920}},
            "malformed",
        ],
    )

    assert [candidate.score for candidate in candidates] == [0.9, 0.4, 0.3]
    assert candidates[0].confidence == 0.0
    assert candidates[0].metadata["frame_key"] == "key-3"
    assert candidates[1].confidence == 0.7


def test_artifact_builders_deduplicate_and_skip_missing_paths(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.png"
    artifact_path.write_bytes(b"evidence")
    missing = tmp_path / "missing.png"

    hotspot = hotspot_artifacts(
        "case_001",
        "run_001",
        [
            {"segmentation_mask": {"path": str(artifact_path)}},
            {
                "segmentation_mask": {"path": str(artifact_path)},
                "lesion_evidence": {"overlay_path": str(missing)},
            },
        ],
    )
    manifests = video_manifest_artifacts("case_001", "run_001", [artifact_path, artifact_path, missing])
    videos = video_segmentation_artifacts(
        "case_001",
        "run_001",
        {"video_segmentation_manifest_path": artifact_path, "mask_review_video_path": missing},
    )

    assert len(hotspot) == 1
    assert hotspot[0].kind == ArtifactKind.ROI_MASK
    assert len(manifests) == 1
    assert len(videos) == 1
    assert hotspot[0].checksum == manifests[0].checksum == videos[0].checksum
