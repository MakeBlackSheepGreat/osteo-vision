from pathlib import Path

import numpy as np
from PIL import Image

from src.preprocess.three_channel_quality import assess_three_channel_quality


def _save(path: Path, array: np.ndarray) -> Path:
    Image.fromarray(array.astype(np.uint8)).save(path)
    return path


def test_three_channel_quality_writes_metrics_and_heatmap(tmp_path: Path) -> None:
    base = np.zeros((48, 64, 3), dtype=np.uint8)
    base[12:36, 16:48] = [80, 180, 40]
    white = _save(tmp_path / "white.png", base)
    fluorescence = _save(tmp_path / "fluor.png", base)
    software = _save(tmp_path / "software.png", base)
    device = _save(tmp_path / "device.png", base.copy())

    result = assess_three_channel_quality(
        white,
        fluorescence,
        device,
        tmp_path / "qc",
        metadata={
            "white_light": {"capture_timestamp_ms": 1000},
            "fluorescence": {"capture_timestamp_ms": 1040},
            "device_overlay": {"capture_timestamp_ms": 1050},
        },
        software_overlay_path=software,
    )

    assert result["overall"]["status"] == "pass"
    assert result["overall"]["device_overlay_used_for_inference"] is False
    assert result["synchronization"]["white_fluorescence_delta_ms"] == 40.0
    assert result["overlay_comparison"]["ssim_luma"] == 1.0
    assert Path(result["overlay_comparison"]["difference_heatmap_path"]).exists()
    assert Path(result["report_path"]).exists()


def test_three_channel_quality_requires_review_when_timestamps_missing(tmp_path: Path) -> None:
    image = np.full((20, 30, 3), 90, dtype=np.uint8)
    white = _save(tmp_path / "white.png", image)
    fluorescence = _save(tmp_path / "fluor.png", image)

    result = assess_three_channel_quality(white, fluorescence, None, tmp_path / "qc")

    assert result["overall"]["status"] == "review_required"
    assert result["synchronization"]["status"] == "review_required"
    assert result["overlay_comparison"]["available"] is False


def test_three_channel_quality_skips_pixel_metrics_for_aspect_ratio_mismatch(tmp_path: Path) -> None:
    white = _save(tmp_path / "white.png", np.zeros((40, 80, 3), dtype=np.uint8))
    fluorescence = _save(tmp_path / "fluor.png", np.zeros((40, 80, 3), dtype=np.uint8))
    device = _save(tmp_path / "device.png", np.zeros((80, 40, 3), dtype=np.uint8))
    software = _save(tmp_path / "software.png", np.zeros((40, 80, 3), dtype=np.uint8))

    result = assess_three_channel_quality(
        white,
        fluorescence,
        device,
        tmp_path / "qc",
        metadata={
            "white_light": {"timestamp_ms": 1},
            "fluorescence": {"timestamp_ms": 1},
            "device_overlay": {"timestamp_ms": 1},
        },
        software_overlay_path=software,
    )

    assert result["geometry"]["pixel_comparison_allowed"] is False
    assert result["overlay_comparison"]["reason"] == "geometry_unusable"
