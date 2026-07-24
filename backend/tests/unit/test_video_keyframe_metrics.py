from __future__ import annotations

from backend.osteo_vision_api.services.video_keyframe_metrics import (
    attach_video_temporal_context,
    normalized_bbox,
    scaled_bbox,
    video_temporal_summary,
)


def test_video_keyframe_metrics_add_temporal_context_without_changing_masks() -> None:
    details = [
        {
            "positive_area_fraction": 0.10,
            "top_component_bbox_xyxy": [0, 0, 10, 10],
            "spatial_mapping": {"source_video_width": 100, "source_video_height": 100},
        },
        {
            "positive_area_fraction": 0.20,
            "top_component_bbox_xyxy": [10, 10, 20, 20],
            "spatial_mapping": {"source_video_width": 100, "source_video_height": 100},
        },
    ]

    enriched = attach_video_temporal_context(details)
    summary = video_temporal_summary(enriched)

    assert enriched[1]["temporal_stability"]["smoothing_applied_to_mask"] is False
    assert enriched[1]["temporal_stability"]["positive_area_fraction_delta_previous"] == 0.1
    assert summary["frame_count"] == 2
    assert summary["smoothing_applied_to_mask"] is False


def test_video_keyframe_bbox_helpers_map_mask_coordinates() -> None:
    assert scaled_bbox([10, 20, 30, 40], from_width=100, from_height=100, to_width=200, to_height=50) == [
        20,
        10,
        60,
        20,
    ]
    assert normalized_bbox([10, 20, 30, 40], width=100, height=200) == {
        "type": "rect",
        "coordinate_space": "normalized",
        "x": 0.1,
        "y": 0.1,
        "width": 0.2,
        "height": 0.1,
    }
