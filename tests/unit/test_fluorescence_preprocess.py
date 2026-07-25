from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from osteo_vision_core.preprocess.accelerated_fusion import accelerated_normalize_pseudocolor_blend
from osteo_vision_core.preprocess.fluorescence import (
    apply_fluorescence_colormap,
    fluorescence_colorbar,
    fluorescence_quantification,
    fluorescence_time_intensity_curve,
    fuse_white_light_fluorescence,
    normalize_fluorescence,
    register_fluorescence_to_reference,
    subtract_fluorescence_background,
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


def test_accelerated_normalize_blend_has_deterministic_cpu_fallback() -> None:
    white = np.full((24, 32, 3), 100, dtype=np.uint8)
    fluorescence = np.tile(np.linspace(0, 200, 32, dtype=np.float32), (24, 1))

    normalized, pseudo, overlay, report = accelerated_normalize_pseudocolor_blend(
        white,
        fluorescence,
        alpha=0.4,
        colormap="green",
        lower_percentile=0,
        upper_percentile=100,
        prefer_gpu=False,
    )

    assert normalized.shape == fluorescence.shape
    assert normalized.min() == 0
    assert normalized.max() == 1
    assert pseudo.shape == white.shape
    assert overlay.shape == white.shape
    assert report["backend"] == "numpy"
    assert report["normalization"]["method"] == "sampled_percentile_robust"


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


def test_fluorescence_time_intensity_curve_reports_dynamic_metrics() -> None:
    result = fluorescence_time_intensity_curve(
        [
            {"timestamp_sec": 0.0, "p95_intensity": 0.2, "background_intensity": 0.1},
            {"timestamp_sec": 2.0, "p95_intensity": 0.5, "background_intensity": 0.1},
            {"timestamp_sec": 5.0, "p95_intensity": 0.9, "background_intensity": 0.1},
            {"timestamp_sec": 8.0, "p95_intensity": 0.6, "background_intensity": 0.1},
        ]
    )

    assert result["available"] is True
    assert result["time_to_peak_sec"] == 5.0
    assert result["normalized_auc"] > 0
    assert result["max_normalized_rise_slope_per_sec"] > 0
    assert result["curve_quality"]["sparse_keyframe_curve"] is True


def test_subtract_fluorescence_background_reports_baseline() -> None:
    image = np.array([[10, 10], [10, 90]], dtype=np.float32)

    corrected, report = subtract_fluorescence_background(image, percentile=5)

    assert report["method"] == "percentile_floor_subtraction"
    assert report["applied"] is True
    assert corrected.min() == 0
    assert corrected.max() > 0


def test_fluorescence_colorbar_adds_threshold_marker() -> None:
    colorbar = fluorescence_colorbar(colormap="green", threshold=0.5, width=64, height=16)

    assert colorbar.shape == (16, 64, 3)
    assert colorbar.dtype == np.uint8
    assert colorbar[:, 31:34].max() == 255


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
    assert report["fusion"]["algorithm_version"] == "fluorescence_fusion_v2"
    assert report["fusion"]["registration"] == "adaptive_multiscale_registration_v2"
    assert "registration_details" in report["fusion"]
    assert report["fusion"]["performance"]["total_ms"] >= 0
    assert report["fusion"]["acceleration"]["backend"] in {"numpy", "torch_cuda"}
    assert report["fusion"]["background_correction"]["method"] == "percentile_floor_subtraction"
    assert report["fusion"]["fluorescence_resized_to_white_light"]
    assert report["quantification"]["positive_area_px"] > 0
    assert report["outputs"]["colorbar_path"].endswith("_fluorescence_colorbar.png")
    assert report["outputs"]["markdown_report_path"].endswith(".md")
    for output_path in report["outputs"].values():
        assert output_path
        assert (tmp_path / "out" / output_path.split("\\")[-1].split("/")[-1]).exists()


def test_adaptive_multiscale_registration_recovers_translation_with_occlusion() -> None:
    reference = np.zeros((320, 480, 3), dtype=np.uint8)
    reference[60:240, 80:390, 0] = 90
    reference[90:220, 120:360, 1] = 210
    reference[130:190, 180:300, 2] = 255
    moving = np.roll(np.asarray(Image.fromarray(reference).convert("L")), shift=(7, -11), axis=(0, 1))
    moving[0:80, 360:480] = 0

    registered, report = register_fluorescence_to_reference(
        reference.astype(np.float32),
        moving.astype(np.float32),
        method="adaptive_multiscale",
        prefer_gpu=False,
    )

    assert report["applied"] is True
    assert report["selected_candidate"]
    assert report["candidate_count"] >= 2
    assert registered.shape == moving.shape
    assert (
        np.mean(
            np.abs(registered[40:-40, 40:-40] - np.asarray(Image.fromarray(reference).convert("L"))[40:-40, 40:-40])
        )
        < 35
    )


def test_adaptive_multiscale_registration_adds_tile_affine_candidate_for_zoom_and_rotation() -> None:
    rng = np.random.default_rng(20260724)
    texture = cv2.GaussianBlur(rng.integers(0, 256, size=(480, 640), dtype=np.uint8), (7, 7), 0)
    cv2.circle(texture, (210, 220), 70, 245, 5)
    cv2.rectangle(texture, (330, 110), (520, 360), 35, 7)
    reference = np.repeat(texture[..., None], 3, axis=2)
    transform = cv2.getRotationMatrix2D((320, 240), 2.0, 1.02).astype(np.float32)
    transform[:, 2] += np.asarray([9.0, -6.0], dtype=np.float32)
    moving = cv2.warpAffine(texture, transform, (640, 480), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    moving[30:135, 480:620] = 0

    registered, report = register_fluorescence_to_reference(
        reference,
        moving.astype(np.float32),
        method="adaptive_multiscale",
        prefer_gpu=False,
    )

    crop = np.s_[60:-60, 60:-60]
    before_error = float(np.mean(np.abs(moving[crop].astype(np.float32) - texture[crop].astype(np.float32))))
    after_error = float(np.mean(np.abs(registered[crop] - texture[crop].astype(np.float32))))
    assert report["applied"] is True
    assert report["candidate_count"] >= 4
    assert report["transform_model"] in {"translation", "similarity"}
    assert after_error < before_error * 0.8
