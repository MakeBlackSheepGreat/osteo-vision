from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from src.models.keyframe_segmenter import (
    TinyKeyframeSegmenter2D,
    connected_probability_candidates,
    predict_keyframe_image,
    predict_keyframe_probability_with_uncertainty,
)


def test_predict_keyframe_image_writes_tiled_full_size_outputs(tmp_path: Path) -> None:
    torch.manual_seed(20260705)
    image_path = tmp_path / "keyframe.jpg"
    image = np.zeros((64, 96, 3), dtype=np.uint8)
    image[18:42, 24:68, 1] = 230
    Image.fromarray(image).save(image_path)

    model = TinyKeyframeSegmenter2D(base_channels=4)
    result = predict_keyframe_image(
        model,
        image_path,
        device=torch.device("cpu"),
        output_dir=tmp_path / "outputs",
        case_id="tiling_case",
        threshold=0.5,
        tile_size=32,
        tile_overlap=8,
        force_tiled=True,
        max_whole_pixels=1,
        temperature=1.2,
        tta_enabled=True,
    )

    mask = result["segmentation_mask"]
    inference = mask["inference"]
    assert mask["width"] == 96
    assert mask["height"] == 64
    assert inference["mode"] == "tiled"
    assert inference["tile_size"] == 32
    assert inference["tile_overlap"] == 8
    assert inference["tile_count"] > 1
    assert result["prediction"]["inference_mode"] == "tiled"
    assert result["prediction"]["review_priority"] == "high"
    assert result["prediction"]["target_domain_flag"] is False
    assert Path(mask["path"]).exists()
    assert Path(mask["uncertainty_path"]).exists()
    assert Path(result["lesion_evidence"]["probability_path"]).exists()
    assert Path(result["lesion_evidence"]["uncertainty_path"]).exists()
    assert Path(result["lesion_evidence"]["overlay_path"]).exists()
    assert result["quantification"]["uncertainty"]["method"] == "predictive_entropy_plus_tta_variance"
    assert result["quantification"]["inference"]["elapsed_ms"] > 0
    assert result["quantification"]["inference"]["tta_enabled"] is True


def test_tiled_batch_inference_matches_single_tile_results() -> None:
    torch.manual_seed(20260714)
    model = TinyKeyframeSegmenter2D(base_channels=4).eval()
    image = np.zeros((64, 96, 3), dtype=np.uint8)
    image[18:42, 24:68, 1] = 230

    single_probability, single_variance, single_meta = predict_keyframe_probability_with_uncertainty(
        model,
        image,
        device=torch.device("cpu"),
        tile_size=32,
        tile_overlap=8,
        tile_batch_size=1,
        force_tiled=True,
        max_whole_pixels=1,
        temperature=1.2,
        tta_enabled=True,
    )
    batched_probability, batched_variance, batched_meta = predict_keyframe_probability_with_uncertainty(
        model,
        image,
        device=torch.device("cpu"),
        tile_size=32,
        tile_overlap=8,
        tile_batch_size=3,
        force_tiled=True,
        max_whole_pixels=1,
        temperature=1.2,
        tta_enabled=True,
    )

    np.testing.assert_allclose(batched_probability, single_probability, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(batched_variance, single_variance, rtol=1e-6, atol=1e-6)
    assert single_meta["tile_batch_size"] == 1
    assert batched_meta["tile_batch_size"] == 3


def test_tiled_batch_inference_falls_back_to_single_tiles_on_oom() -> None:
    class BatchLimitedSegmenter(TinyKeyframeSegmenter2D):
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            if x.shape[0] > 1:
                raise torch.OutOfMemoryError("simulated tile-batch limit")
            return super().forward(x)

    torch.manual_seed(20260714)
    model = BatchLimitedSegmenter(base_channels=4).eval()
    image = np.zeros((64, 96, 3), dtype=np.uint8)
    image[18:42, 24:68, 1] = 230

    probability, variance, metadata = predict_keyframe_probability_with_uncertainty(
        model,
        image,
        device=torch.device("cpu"),
        tile_size=32,
        tile_overlap=8,
        tile_batch_size=3,
        force_tiled=True,
        max_whole_pixels=1,
        temperature=1.2,
        tta_enabled=False,
    )

    assert probability.shape == image.shape[:2]
    assert variance.shape == image.shape[:2]
    assert metadata["tile_batch_size"] == 3


def test_predict_keyframe_image_accepts_predecoded_rgb_without_changing_output(tmp_path: Path) -> None:
    torch.manual_seed(20260714)
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[14:34, 18:46, 1] = 230
    image_path = tmp_path / "keyframe.png"
    Image.fromarray(image).save(image_path)
    model = TinyKeyframeSegmenter2D(base_channels=4).eval()

    from_path = predict_keyframe_image(
        model,
        image_path,
        device=torch.device("cpu"),
        output_dir=tmp_path / "from_path",
        case_id="from_path",
        threshold=0.5,
    )
    from_rgb = predict_keyframe_image(
        model,
        image_path,
        device=torch.device("cpu"),
        output_dir=tmp_path / "from_rgb",
        case_id="from_rgb",
        threshold=0.5,
        rgb=image,
    )

    assert from_rgb["quantification"]["positive_area_px"] == from_path["quantification"]["positive_area_px"]
    assert from_rgb["quantification"]["mean_probability"] == from_path["quantification"]["mean_probability"]


def test_connected_probability_candidates_reports_component_statistics() -> None:
    mask = np.zeros((8, 10), dtype=np.uint8)
    mask[1:3, 1:4] = 1
    mask[5:7, 6:9] = 1
    probability = np.zeros_like(mask, dtype=np.float32)
    probability[1:3, 1:4] = np.asarray([[0.2, 0.4, 0.6], [0.3, 0.5, 0.7]], dtype=np.float32)
    probability[5:7, 6:9] = np.asarray([[0.8, 0.4, 0.2], [0.9, 0.5, 0.3]], dtype=np.float32)

    candidates = connected_probability_candidates(
        mask,
        probability,
        min_component_area=4,
        model_id="candidate_test",
    )

    assert len(candidates) == 2
    assert candidates[0]["bbox_xyxy"] == [6, 5, 9, 7]
    assert candidates[0]["area_px"] == 6
    assert np.isclose(candidates[0]["score"], 31 / 60)
    assert np.isclose(candidates[0]["confidence"], 0.9)
    assert candidates[1]["bbox_xyxy"] == [1, 1, 4, 3]
    assert np.isclose(candidates[1]["score"], 0.45)
