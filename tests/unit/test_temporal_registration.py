from __future__ import annotations

import cv2
import numpy as np

from osteo_vision_core.preprocess.accelerated_fusion import (
    _stabilize_registration_matrix,
    register_adaptive_multiscale,
)
from osteo_vision_core.preprocess.temporal_registration import TemporalRegistrationSession


def test_temporal_registration_smooths_stable_sequence_and_resets_on_zoom_change() -> None:
    rng = np.random.default_rng(20260724)
    texture = cv2.GaussianBlur(rng.integers(0, 256, size=(240, 320), dtype=np.uint8), (5, 5), 0)
    reference = np.repeat(texture[..., None], 3, axis=2)
    first = _translated(texture, shift_x=8.0, shift_y=-5.0)
    second = _translated(texture, shift_x=10.0, shift_y=-4.0)
    session = TemporalRegistrationSession(temporal_smoothing_alpha=0.6)

    _, first_report = session.register(
        reference,
        first.astype(np.float32),
        magnification=2.0,
        working_distance_mm=300.0,
        prefer_gpu=False,
    )
    _, second_report = session.register(
        reference,
        second.astype(np.float32),
        magnification=2.0,
        working_distance_mm=305.0,
        prefer_gpu=False,
    )
    _, zoom_report = session.register(
        reference,
        second.astype(np.float32),
        magnification=3.0,
        working_distance_mm=305.0,
        prefer_gpu=False,
    )

    assert first_report["temporal_stabilization"]["reason"] == "no_previous_transform"
    assert second_report["temporal_stabilization"]["reason"] == "exponential_transform_smoothing"
    assert second_report["temporal_stabilization"]["applied"] is True
    assert second_report["temporal_session"]["context_reset"] is False
    assert zoom_report["temporal_session"]["context_reset"] is True
    assert zoom_report["temporal_session"]["context_reset_reason"] == "magnification_change"
    assert zoom_report["temporal_stabilization"]["reason"] == "no_previous_transform"


def test_temporal_registration_holds_previous_transform_for_low_quality_jump() -> None:
    previous = np.asarray([[1.0, 0.0, -4.0], [0.0, 1.0, 3.0]], dtype=np.float32)
    current = np.asarray([[1.0, 0.0, -120.0], [0.0, 1.0, 90.0]], dtype=np.float32)

    stabilized, report = _stabilize_registration_matrix(
        current,
        previous_matrix=previous,
        quality=0.12,
        image_size=(640, 480),
        alpha=0.7,
        max_jump_fraction=0.03,
    )

    assert np.array_equal(stabilized, previous)
    assert report["applied"] is True
    assert report["reason"] == "previous_transform_held_after_low_quality_jump"


def test_temporal_registration_resets_on_working_distance_change() -> None:
    rng = np.random.default_rng(17)
    texture = rng.integers(0, 256, size=(160, 224), dtype=np.uint8)
    reference = np.repeat(texture[..., None], 3, axis=2)
    moving = _translated(texture, shift_x=5.0, shift_y=-3.0)
    session = TemporalRegistrationSession(working_distance_reset_mm=20.0)

    session.register(
        reference,
        moving.astype(np.float32),
        magnification=4.0,
        working_distance_mm=200.0,
        prefer_gpu=False,
    )
    _, report = session.register(
        reference,
        moving.astype(np.float32),
        magnification=4.0,
        working_distance_mm=630.0,
        prefer_gpu=False,
    )

    assert report["temporal_session"]["context_reset"] is True
    assert report["temporal_session"]["context_reset_reason"] == "working_distance_change"
    assert report["temporal_stabilization"]["reason"] == "no_previous_transform"


def test_local_deformation_compensation_improves_smooth_nonrigid_alignment() -> None:
    rng = np.random.default_rng(20260725)
    height, width = 360, 480
    texture = cv2.GaussianBlur(
        rng.integers(0, 256, size=(height, width), dtype=np.uint8),
        (5, 5),
        0,
    )
    reference = np.repeat(texture[..., None], 3, axis=2)
    moving = _smoothly_deformed(texture, shift_x=8.0, shift_y=-5.0)

    affine_only, affine_report = register_adaptive_multiscale(
        reference,
        moving,
        max_registration_side=480,
        prefer_gpu=False,
        enable_local_deformation=False,
    )
    compensated, compensated_report = register_adaptive_multiscale(
        reference,
        moving,
        max_registration_side=480,
        prefer_gpu=False,
        enable_local_deformation=True,
    )

    affine_mae = float(np.mean(np.abs(affine_only - texture)))
    compensated_mae = float(np.mean(np.abs(compensated - texture)))
    deformation = compensated_report["local_deformation"]
    assert affine_report["method"] == "adaptive_multiscale_registration_v2"
    assert deformation["applied"] is True
    assert deformation["model"] == "smooth_quadratic_residual_grid"
    assert deformation["residual_p95_after_px"] < deformation["residual_p95_before_px"]
    assert compensated_mae < affine_mae * 0.8
    assert compensated_report["deformation_review_required"] is False


def test_local_deformation_gate_stays_off_for_rigid_translation() -> None:
    rng = np.random.default_rng(25)
    texture = cv2.GaussianBlur(
        rng.integers(0, 256, size=(240, 320), dtype=np.uint8),
        (5, 5),
        0,
    )
    reference = np.repeat(texture[..., None], 3, axis=2)

    _, report = register_adaptive_multiscale(
        reference,
        _translated(texture, shift_x=8.0, shift_y=-5.0).astype(np.float32),
        max_registration_side=320,
        prefer_gpu=False,
    )

    assert report["local_deformation"]["applied"] is False
    assert report["local_deformation"]["reason"] == "local_residual_below_activation_gate"


def _translated(image: np.ndarray, *, shift_x: float, shift_y: float) -> np.ndarray:
    matrix = np.asarray([[1.0, 0.0, shift_x], [0.0, 1.0, shift_y]], dtype=np.float32)
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REFLECT)


def _smoothly_deformed(image: np.ndarray, *, shift_x: float, shift_y: float) -> np.ndarray:
    height, width = image.shape
    output_y, output_x = np.mgrid[0:height, 0:width].astype(np.float32)
    normalized_x = (output_x - (width - 1) * 0.5) / max(1.0, (width - 1) * 0.5)
    normalized_y = (output_y - (height - 1) * 0.5) / max(1.0, (height - 1) * 0.5)
    displacement_x = shift_x + 8.0 * (normalized_x**2 - 0.33)
    displacement_y = shift_y + 6.0 * normalized_x * normalized_y
    return cv2.remap(
        image.astype(np.float32),
        output_x - displacement_x,
        output_y - displacement_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )
