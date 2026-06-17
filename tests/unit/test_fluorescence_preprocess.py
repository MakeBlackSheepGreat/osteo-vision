from __future__ import annotations

import numpy as np
from PIL import Image

from src.preprocess.fluorescence import (
    apply_fluorescence_colormap,
    fluorescence_quantification,
    fuse_white_light_fluorescence,
    normalize_fluorescence,
)


def test_normalize_fluorescence_uses_robust_unit_range() -> None:
    image = np.array([[0, 5], [10, 20]], dtype=np.float32)

    normalized = normalize_fluorescence(image, lower_percentile=0, upper_percentile=100)

    assert normalized.min() == 0
    assert normalized.max() == 1


def test_apply_fluorescence_colormap_returns_rgb() -> None:
    normalized = np.array([[0.0, 1.0]], dtype=np.float32)

    heatmap = apply_fluorescence_colormap(normalized, "amber")

    assert heatmap.shape == (1, 2, 3)
    assert heatmap.dtype == np.uint8
    assert heatmap[0, 1, 0] == 255


def test_fluorescence_quantification_counts_positive_area() -> None:
    normalized = np.array([[0.1, 0.8], [0.7, 0.2]], dtype=np.float32)

    quantification = fluorescence_quantification(normalized, threshold=0.6)

    assert set(quantification) >= {
        "threshold",
        "mean_intensity",
        "max_intensity",
        "p95_intensity",
        "positive_area_px",
        "positive_area_fraction",
    }
    assert quantification["positive_area_px"] == 2
    assert quantification["positive_area_fraction"] == 0.5


def test_fuse_white_light_fluorescence_writes_visual_outputs(tmp_path) -> None:
    white = np.zeros((16, 16, 3), dtype=np.uint8)
    white[..., 0] = 110
    white[..., 1] = 95
    white[..., 2] = 80
    fluorescence = np.zeros((8, 8), dtype=np.uint8)
    fluorescence[2:6, 2:6] = 220
    white_path = tmp_path / "white.png"
    fluorescence_path = tmp_path / "fluorescence.png"
    Image.fromarray(white).save(white_path)
    Image.fromarray(fluorescence).save(fluorescence_path)

    report = fuse_white_light_fluorescence(
        white_path,
        fluorescence_path,
        tmp_path / "out",
        case_id="case 001",
        alpha=0.5,
        threshold=0.6,
    )

    assert report["case_id"] == "case_001"
    assert report["fusion"]["fluorescence_resized_to_white_light"]
    assert report["quantification"]["positive_area_px"] > 0
    assert report["outputs"]["markdown_report_path"].endswith(".md")
    for output_path in report["outputs"].values():
        assert output_path
        assert (tmp_path / "out" / output_path.split("\\")[-1].split("/")[-1]).exists()
