from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from src.models.keyframe_segmenter import TinyKeyframeSegmenter2D, predict_keyframe_image


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
    assert result["quantification"]["uncertainty"]["method"] == "threshold_proximity"
