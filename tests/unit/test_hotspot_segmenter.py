from __future__ import annotations

import numpy as np
from PIL import Image

from src.models.hotspot_segmenter import connected_hotspot_candidates, segment_2d_fluorescence_hotspots


def test_connected_hotspot_candidates_reports_vectorized_component_statistics() -> None:
    mask = np.zeros((8, 10), dtype=np.uint8)
    mask[1:3, 1:4] = 1
    mask[5:7, 6:9] = 1
    intensity = np.zeros_like(mask, dtype=np.float32)
    intensity[1:3, 1:4] = np.asarray([[0.2, 0.4, 0.6], [0.3, 0.5, 0.7]], dtype=np.float32)
    intensity[5:7, 6:9] = np.asarray([[0.8, 0.4, 0.2], [0.9, 0.5, 0.3]], dtype=np.float32)

    candidates = connected_hotspot_candidates(
        mask,
        intensity,
        min_component_area=4,
        model_id="hotspot_test",
    )

    assert len(candidates) == 2
    assert candidates[0]["bbox_xyxy"] == [6, 5, 9, 7]
    assert candidates[0]["area_px"] == 6
    assert np.isclose(candidates[0]["score"], 31 / 60)
    assert np.isclose(candidates[0]["confidence"], 0.9)
    assert candidates[1]["bbox_xyxy"] == [1, 1, 4, 3]
    assert np.isclose(candidates[1]["score"], 0.45)


def test_connected_hotspot_candidates_handles_many_components() -> None:
    mask = np.zeros((1024, 1024), dtype=np.uint8)
    mask[::32, ::32] = 1
    intensity = np.zeros_like(mask, dtype=np.float32)
    intensity[mask > 0] = 0.75

    candidates = connected_hotspot_candidates(
        mask,
        intensity,
        min_component_area=1,
        model_id="many_components",
    )

    assert len(candidates) == 1024
    assert all(candidate["area_px"] == 1 for candidate in candidates)
    assert all(np.isclose(candidate["score"], 0.75) for candidate in candidates)


def test_hotspot_evidence_reuses_enhanced_map_as_activity_score(tmp_path) -> None:
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 12:36, 1] = 230
    image_path = tmp_path / "source.png"
    Image.fromarray(image).save(image_path)

    result = segment_2d_fluorescence_hotspots(
        image_path,
        output_dir=tmp_path / "output",
        case_id="reuse",
        min_component_area=1,
    )

    assert (
        result["signal_masks"]["bone_activity_spectrum"]["activity_score"]["path"]
        == result["lesion_evidence"]["enhanced_path"]
    )
    assert Image.open(result["lesion_evidence"]["enhanced_path"]).size == (48, 32)


def test_hotspot_segmenter_accepts_predecoded_rgb_without_reopening_source(tmp_path) -> None:
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    image[5:15, 8:22, 1] = 230

    result = segment_2d_fluorescence_hotspots(
        tmp_path / "source_does_not_need_to_exist.jpg",
        output_dir=tmp_path / "output",
        case_id="predecoded",
        min_component_area=1,
        rgb=image,
    )

    assert result["segmentation_mask"]["width"] == 30
    assert result["segmentation_mask"]["height"] == 20
