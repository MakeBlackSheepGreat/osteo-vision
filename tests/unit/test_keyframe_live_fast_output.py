from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from src.models.keyframe_segmenter import TinyKeyframeSegmenter2D, predict_keyframe_image
from src.models.video_signal_masks import risk_from_signal
from tools.run_keyframe_live_fast_output_gate import (
    _latency_summary,
    _protocol_comparison,
    prepare_browser_profile_jpeg,
)


def test_live_fast_output_keeps_renderable_masks_and_uses_jpeg_overlay(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    Image.fromarray(np.full((48, 64, 3), 110, dtype=np.uint8)).save(image_path)

    result = predict_keyframe_image(
        TinyKeyframeSegmenter2D(base_channels=4),
        image_path,
        device=torch.device("cpu"),
        output_dir=tmp_path / "outputs",
        case_id="live_case",
        fast_output=True,
        overlay_format="jpeg",
        overlay_jpeg_quality=80,
    )

    evidence = result["lesion_evidence"]
    assert Path(result["segmentation_mask"]["path"]).exists()
    assert Path(evidence["risk_mask_path"]).exists()
    assert Path(evidence["uncertain_mask_path"]).exists()
    assert Path(evidence["overlay_path"]).suffix == ".jpg"
    assert Path(evidence["overlay_path"]).exists()
    assert evidence["probability_path"] is None
    assert evidence["uncertainty_path"] is None
    assert evidence["pseudo_color_path"] is None
    assert result["quantification"]["inference"]["output_profile"] == "live_fast"
    for path in (
        result["segmentation_mask"]["path"],
        evidence["risk_mask_path"],
        evidence["uncertain_mask_path"],
    ):
        with Image.open(path) as saved:
            assert saved.size == (64, 48)


def test_risk_map_matches_signal_and_uncertainty_formula() -> None:
    probability = np.asarray([[0.2, 0.8], [0.5, 1.0]], dtype=np.float32)
    mask = np.asarray([[0, 1], [1, 0]], dtype=np.uint8)
    uncertainty = np.asarray([[0.1, 0.4], [0.9, 0.6]], dtype=np.float32)

    result = risk_from_signal(probability=probability, mask=mask, uncertainty=uncertainty)
    expected = np.clip(
        0.75 * probability * np.maximum((mask > 0).astype(np.float32), 0.35)
        + 0.25 * uncertainty * np.maximum((mask > 0).astype(np.float32), 0.25),
        0.0,
        1.0,
    ).astype(np.float32)

    np.testing.assert_allclose(result, expected)


def test_browser_profile_and_same_protocol_comparison(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    Image.fromarray(np.full((1080, 1920, 3), 120, dtype=np.uint8)).save(source)

    capture = prepare_browser_profile_jpeg(source, tmp_path / "browser.jpg")
    shared_protocol = {
        "mode": "whole_frame",
        "tile_size": None,
        "tile_overlap": None,
        "tile_count": 1,
        "tile_batch_size": 1,
        "max_whole_pixels": 1048576,
        "input_width": 960,
        "input_height": 540,
        "tta_enabled": False,
        "use_amp": True,
        "output_profile": "live_fast",
    }
    candidate = {"timed_frame_count": 5, "protocol": shared_protocol}
    mainline = {"timed_frame_count": 5, "protocol": dict(shared_protocol)}

    assert capture["prepared_width"] == 960
    assert capture["prepared_height"] == 540
    assert all(_protocol_comparison(candidate, mainline).values())
    assert _latency_summary([10.0, 20.0, 30.0, 40.0, 50.0])["p95"] == 48.0
