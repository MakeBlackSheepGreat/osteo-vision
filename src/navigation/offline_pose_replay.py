from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from src.navigation.coordinate_contract import (
    CoordinateContractError,
    validate_frame_metadata,
    validate_matrix_convention,
)
from src.navigation.ocamcalib import (
    OCAMCALIB_POLYNOMIAL_V1,
    OcamCalibError,
    OcamCalibPolynomialV1,
)

POSE_ONLY_MODE = "pose_only_engineering"
DYNAMIC_AR_MODE = "dynamic_ar_validation"
RIGHT_HANDED = "right_handed"
CAMERA_AXIS_CONVENTION = "opencv_camera_x_right_y_down_z_forward"
MIN_PROJECTED_HULL_AREA_PX2 = 16.0


class OfflinePoseReplayError(ValueError):
    """Structured failure raised when an offline replay input is unusable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OfflinePoseReplayConfig:
    max_time_offset_ms: float = 50.0
    drift_threshold_mm: float = 1.0
    tre_proxy_threshold_mm: float = 2.0
    dynamic_target_error_threshold_mm: float = 2.0
    minimum_visible_projection_points: int = 4
    max_magnification_rate_per_s: float = 25.0
    max_working_distance_rate_mm_per_s: float = 600.0
    max_intrinsics_switch_rate_hz: float = 10.0
    calibration_ambiguity_margin: float = 0.05


@dataclass(frozen=True)
class OfflinePoseFrame:
    frame_index: int
    frame_timestamp_s: float
    pose_index: int
    pose_timestamp_s: float
    time_offset_ms: float
    intrinsics_id: str | None
    magnification: float
    working_distance_mm: float
    magnification_rate_per_s: float | None
    working_distance_rate_mm_per_s: float | None
    intrinsics_switched: bool
    intrinsics_switch_rate_hz: float | None
    calibration_candidate_count: int
    calibration_selection_distance: float | None
    calibration_selection_ambiguous: bool
    drift_proxy_mm: float
    tre_proxy_mm: float
    dynamic_target_error_mm: float | None
    projected_points_px: list[list[float]]
    projected_point_count: int
    visible_projected_point_count: int
    composed_transform: list[list[float]] | None
    transform_chain: list[dict[str, Any]]
    navigation_ready: bool
    navigation_level: str
    fallback_mode: str | None
    failure_reasons: list[str]


@dataclass(frozen=True)
class OfflinePoseReplayResult:
    frames: list[OfflinePoseFrame]
    navigation_ready: bool
    safe_frame_count: int
    degraded_frame_count: int
    failure_reasons: list[str]
    validation_mode: str
    calibration_transition_summary: dict[str, Any]
    schema_version: str = "osteo-vision-offline-pose-replay-v3"
    navigation_level: str = "L0"


def replay_offline_poses(
    frame_timestamps_s: Sequence[float],
    poses: Sequence[Mapping[str, Any]],
    *,
    calibration_table: Sequence[Mapping[str, Any]],
    static_l1_transform: Any,
    l1_tre_mm: float,
    source_space: str = "cbct_reference",
    reference_space: str = "phantom_reference",
    camera_space: str = "camera_optical",
    config: OfflinePoseReplayConfig | None = None,
    failure_injections: Mapping[int, Sequence[str]] | None = None,
    validation_mode: str = POSE_ONLY_MODE,
    projection_points_3d: Sequence[Sequence[float]] | None = None,
    frame_indices: Sequence[int] | None = None,
    source_frame_metadata: Mapping[str, Any] | None = None,
    reference_frame_metadata: Mapping[str, Any] | None = None,
    camera_frame_metadata: Mapping[str, Any] | None = None,
    matrix_convention: Mapping[str, Any] | None = None,
) -> OfflinePoseReplayResult:
    """Synchronize decoded video frames to poses and fail closed per frame."""
    mode = _validation_mode(validation_mode)
    cfg = _validated_config(config or OfflinePoseReplayConfig())
    frames = _timestamps(frame_timestamps_s, label="frame")
    if not frames:
        raise OfflinePoseReplayError(
            "frame_timestamps_empty",
            "At least one video frame timestamp is required for replay.",
        )
    if not poses:
        raise OfflinePoseReplayError("pose_log_empty", "Offline pose log is empty.")

    indices = _frame_indices(frame_indices, frame_count=len(frames), mode=mode)
    sequence_failures = _frame_sequence_failures(indices, frames, mode=mode)
    projection_points = _projection_points(projection_points_3d, mode=mode)
    pose_times = np.asarray(
        [_required_float(item.get("timestamp_s"), code="pose_timestamp_invalid") for item in poses],
        dtype=np.float64,
    )
    pose_differences = np.diff(pose_times)
    if mode == DYNAMIC_AR_MODE and np.any(pose_differences <= 0):
        raise OfflinePoseReplayError(
            "pose_timestamps_not_strictly_increasing",
            "Dynamic AR pose timestamps must be strictly increasing.",
        )
    if np.any(pose_differences < 0):
        raise OfflinePoseReplayError(
            "pose_timestamps_not_monotonic",
            "Pose timestamps must be monotonic.",
        )

    static_matrix = _matrix(static_l1_transform)
    l1_tre = _nonnegative_float(l1_tre_mm, code="l1_tre_invalid", label="L1 TRE")
    spaces = (
        _coordinate_space(source_space, field="source_space"),
        _coordinate_space(reference_space, field="reference_space"),
        _coordinate_space(camera_space, field="camera_space"),
    )
    strict_frames = (
        (
            _strict_frame_metadata(source_frame_metadata, expected_name=spaces[0]),
            _strict_frame_metadata(reference_frame_metadata, expected_name=spaces[1]),
            _strict_frame_metadata(camera_frame_metadata, expected_name=spaces[2]),
        )
        if mode == DYNAMIC_AR_MODE
        else (None, None, None)
    )
    strict_matrix_convention = _strict_matrix_convention(matrix_convention) if mode == DYNAMIC_AR_MODE else None
    dynamic_pose_indices = (
        _dynamic_pose_indices(
            poses,
            indices,
            expected_from_space=spaces[1],
            expected_to_space=spaces[2],
            expected_source_frame=strict_frames[1],
            expected_target_frame=strict_frames[2],
            expected_matrix_convention=strict_matrix_convention,
        )
        if mode == DYNAMIC_AR_MODE
        else None
    )
    pose_matrices = [_optional_matrix(item.get("matrix")) for item in poses]
    baseline_translation = next(
        (matrix[:3, 3] for matrix in pose_matrices if matrix is not None),
        None,
    )

    output: list[OfflinePoseFrame] = []
    all_reasons: list[str] = []
    prior_timestamp: float | None = None
    prior_magnification: float | None = None
    prior_working_distance: float | None = None
    prior_intrinsics_id: str | None = None
    intrinsics_history: list[str | None] = []
    intrinsics_transitions: list[dict[str, Any]] = []
    switch_count = 0
    ambiguous_frame_count = 0
    oscillation_count = 0
    max_magnification_rate = 0.0
    max_working_distance_rate = 0.0
    max_switch_rate = 0.0
    for position, timestamp in enumerate(frames):
        frame_index = indices[position]
        pose_index = (
            dynamic_pose_indices[position]
            if dynamic_pose_indices is not None
            else int(np.argmin(np.abs(pose_times - timestamp)))
        )
        pose = poses[pose_index]
        pose_matrix = pose_matrices[pose_index]
        injections = set((failure_injections or {}).get(frame_index, []))
        reasons = list(sequence_failures.get(frame_index, []))
        time_offset_ms = float((pose_times[pose_index] - timestamp) * 1000.0)
        magnification = _optional_float(pose.get("magnification"))
        working_distance = _optional_float(pose.get("working_distance_mm"))
        tracking = str(pose.get("tracking_status") or "").strip().lower()

        if tracking not in {"tracking", "valid", "synchronized"} or "tracking_lost" in injections:
            reasons.append("tracking_lost")
        if abs(time_offset_ms) > cfg.max_time_offset_ms or "time_offset" in injections:
            reasons.append("pose_time_offset_exceeded")

        calibration_candidates = _calibration_candidates(calibration_table, magnification, working_distance)
        calibration = calibration_candidates[0][0] if calibration_candidates else None
        calibration_distance = calibration_candidates[0][1] if calibration_candidates else None
        calibration_ambiguous = _calibration_selection_ambiguous(
            calibration_candidates,
            margin=cfg.calibration_ambiguity_margin,
        )
        if not _value_in_calibration_range(calibration_table, "magnification", magnification):
            reasons.append("magnification_out_of_calibration_range")
        if "magnification_out_of_range" in injections:
            reasons.append("magnification_out_of_calibration_range")
        if not _value_in_calibration_range(
            calibration_table,
            "working_distance_mm",
            working_distance,
        ):
            reasons.append("working_distance_out_of_calibration_range")
        if "working_distance_out_of_range" in injections:
            reasons.append("working_distance_out_of_calibration_range")
        if calibration is None and not any(reason.endswith("out_of_calibration_range") for reason in reasons):
            reasons.append("calibration_pair_unavailable")
        intrinsics_id = str(calibration.get("intrinsics_id") or "").strip() if calibration else ""
        if calibration is not None and not intrinsics_id:
            reasons.append("calibration_intrinsics_missing")
        if mode == DYNAMIC_AR_MODE:
            reasons.extend(_dynamic_calibration_failures(calibration))
            if calibration_ambiguous:
                reasons.append("calibration_selection_ambiguous")

        magnification_rate: float | None = None
        working_distance_rate: float | None = None
        intrinsics_switch_rate: float | None = None
        intrinsics_switched = bool(prior_intrinsics_id and intrinsics_id and prior_intrinsics_id != intrinsics_id)
        if prior_timestamp is not None:
            interval_s = timestamp - prior_timestamp
            if interval_s > 0:
                if prior_magnification is not None and np.isfinite(magnification) and np.isfinite(prior_magnification):
                    magnification_rate = abs(magnification - prior_magnification) / interval_s
                    max_magnification_rate = max(max_magnification_rate, magnification_rate)
                    if mode == DYNAMIC_AR_MODE and magnification_rate > cfg.max_magnification_rate_per_s:
                        reasons.append("magnification_rate_exceeded")
                if (
                    prior_working_distance is not None
                    and np.isfinite(working_distance)
                    and np.isfinite(prior_working_distance)
                ):
                    working_distance_rate = abs(working_distance - prior_working_distance) / interval_s
                    max_working_distance_rate = max(max_working_distance_rate, working_distance_rate)
                    if mode == DYNAMIC_AR_MODE and working_distance_rate > cfg.max_working_distance_rate_mm_per_s:
                        reasons.append("working_distance_rate_exceeded")
                if intrinsics_switched:
                    intrinsics_switch_rate = 1.0 / interval_s
                    switch_count += 1
                    max_switch_rate = max(max_switch_rate, intrinsics_switch_rate)
                    if mode == DYNAMIC_AR_MODE and intrinsics_switch_rate > cfg.max_intrinsics_switch_rate_hz:
                        reasons.append("calibration_switch_rate_exceeded")
                    intrinsics_transitions.append(
                        {
                            "from_frame_index": indices[position - 1],
                            "to_frame_index": frame_index,
                            "from_intrinsics_id": prior_intrinsics_id,
                            "to_intrinsics_id": intrinsics_id,
                            "delta_time_s": interval_s,
                            "magnification_rate_per_s": magnification_rate,
                            "working_distance_rate_mm_per_s": working_distance_rate,
                            "intrinsics_switch_rate_hz": intrinsics_switch_rate,
                            "oscillation": False,
                        }
                    )
        if (
            mode == DYNAMIC_AR_MODE
            and len(intrinsics_history) >= 2
            and intrinsics_id
            and intrinsics_history[-2] == intrinsics_id
            and intrinsics_history[-1] != intrinsics_id
        ):
            reasons.append("calibration_selection_oscillation")
            oscillation_count += 1
            if intrinsics_transitions and intrinsics_transitions[-1]["to_frame_index"] == frame_index:
                intrinsics_transitions[-1]["oscillation"] = True
        if calibration_ambiguous:
            ambiguous_frame_count += 1

        drift = _drift_measurement(
            pose,
            pose_matrix,
            baseline_translation,
            require_explicit=mode == DYNAMIC_AR_MODE,
        )
        if not np.isfinite(drift) or drift < 0:
            reasons.append(
                "tracking_drift_missing_or_invalid" if mode == DYNAMIC_AR_MODE else "drift_measurement_invalid"
            )
            drift = float("inf")
        if mode == DYNAMIC_AR_MODE and not str(pose.get("tracking_drift_source") or "").strip():
            reasons.append("tracking_drift_source_missing")
        if drift > cfg.drift_threshold_mm or "drift_exceeded" in injections:
            reasons.append("drift_threshold_exceeded")

        tre_proxy = float(np.sqrt(l1_tre**2 + drift**2))
        if tre_proxy > cfg.tre_proxy_threshold_mm or "tre_exceeded" in injections:
            reasons.append("tre_proxy_threshold_exceeded")
        dynamic_target_error = _optional_float(pose.get("dynamic_target_error_mm"))
        if mode == DYNAMIC_AR_MODE:
            if not np.isfinite(dynamic_target_error) or dynamic_target_error < 0:
                reasons.append("dynamic_target_error_missing_or_invalid")
                dynamic_target_error_value: float | None = None
            else:
                dynamic_target_error_value = dynamic_target_error
                if dynamic_target_error > cfg.dynamic_target_error_threshold_mm:
                    reasons.append("dynamic_target_error_threshold_exceeded")
            if not str(pose.get("dynamic_target_error_source") or "").strip():
                reasons.append("dynamic_target_error_source_missing")
        else:
            dynamic_target_error_value = dynamic_target_error if np.isfinite(dynamic_target_error) else None

        if pose_matrix is None or "corrupt_transform" in injections:
            reasons.append("transform_chain_invalid")
        if "coordinate_error" in injections or "coordinate_space_error" in injections:
            reasons.append("coordinate_chain_invalid")
        if "frame_drop" in injections:
            reasons.append("frame_dropped")
        if "proxy_domain_claim_closed" in injections:
            reasons.append("proxy_domain_navigation_claim_closed")

        composed = pose_matrix @ static_matrix if pose_matrix is not None else None
        if composed is None or not np.isfinite(composed).all():
            reasons.append("transform_chain_invalid")

        projected_points: list[list[float]] = []
        visible_projected_count = 0
        if mode == DYNAMIC_AR_MODE:
            if composed is None or calibration is None or projection_points is None:
                reasons.append("projection_evidence_missing")
            else:
                try:
                    projected_points, visible_projected_count = _project_points(
                        projection_points,
                        composed,
                        calibration,
                    )
                except OfflinePoseReplayError as exc:
                    reasons.append(exc.code)
                if visible_projected_count < cfg.minimum_visible_projection_points:
                    reasons.append("projection_visible_points_insufficient")
        else:
            reasons.append("pose_only_engineering_no_navigation")

        reasons = list(dict.fromkeys(reasons))
        safe = mode == DYNAMIC_AR_MODE and not reasons
        chain = [
            {
                "from_space": spaces[0],
                "to_space": spaces[1],
                "direction": "forward",
                "unit": "mm",
                "source_frame": strict_frames[0],
                "target_frame": strict_frames[1],
                "matrix_convention": strict_matrix_convention,
            },
            {
                "from_space": spaces[1],
                "to_space": spaces[2],
                "direction": "forward",
                "unit": "mm",
                "source_frame": strict_frames[1],
                "target_frame": strict_frames[2],
                "matrix_convention": strict_matrix_convention,
            },
        ]
        output.append(
            OfflinePoseFrame(
                frame_index=frame_index,
                frame_timestamp_s=timestamp,
                pose_index=pose_index,
                pose_timestamp_s=float(pose_times[pose_index]),
                time_offset_ms=time_offset_ms,
                intrinsics_id=intrinsics_id or None,
                magnification=magnification,
                working_distance_mm=working_distance,
                magnification_rate_per_s=magnification_rate,
                working_distance_rate_mm_per_s=working_distance_rate,
                intrinsics_switched=intrinsics_switched,
                intrinsics_switch_rate_hz=intrinsics_switch_rate,
                calibration_candidate_count=len(calibration_candidates),
                calibration_selection_distance=calibration_distance,
                calibration_selection_ambiguous=calibration_ambiguous,
                drift_proxy_mm=drift,
                tre_proxy_mm=tre_proxy,
                dynamic_target_error_mm=dynamic_target_error_value,
                projected_points_px=projected_points,
                projected_point_count=len(projected_points),
                visible_projected_point_count=visible_projected_count,
                composed_transform=composed.tolist() if safe and composed is not None else None,
                transform_chain=chain,
                navigation_ready=safe,
                navigation_level="L2" if safe else "L0",
                fallback_mode=None if safe else "unregistered_3d_reference",
                failure_reasons=reasons,
            )
        )
        all_reasons.extend(reasons)
        prior_timestamp = timestamp
        prior_magnification = magnification if np.isfinite(magnification) else None
        prior_working_distance = working_distance if np.isfinite(working_distance) else None
        prior_intrinsics_id = intrinsics_id or None
        intrinsics_history.append(intrinsics_id or None)

    safe_count = sum(frame.navigation_ready for frame in output)
    all_safe = mode == DYNAMIC_AR_MODE and safe_count == len(output)
    temporal_failure_codes = {
        "calibration_selection_ambiguous",
        "calibration_selection_oscillation",
        "calibration_switch_rate_exceeded",
        "magnification_rate_exceeded",
        "working_distance_rate_exceeded",
    }
    temporal_failures = [reason for reason in dict.fromkeys(all_reasons) if reason in temporal_failure_codes]
    return OfflinePoseReplayResult(
        frames=output,
        navigation_ready=all_safe,
        safe_frame_count=safe_count,
        degraded_frame_count=len(output) - safe_count,
        failure_reasons=list(dict.fromkeys(all_reasons)),
        validation_mode=mode,
        calibration_transition_summary={
            "status": "passed" if mode == DYNAMIC_AR_MODE and not temporal_failures else "failed_closed",
            "switch_count": switch_count,
            "ambiguous_frame_count": ambiguous_frame_count,
            "oscillation_count": oscillation_count,
            "max_magnification_rate_per_s": max_magnification_rate,
            "max_working_distance_rate_mm_per_s": max_working_distance_rate,
            "max_intrinsics_switch_rate_hz_observed": max_switch_rate,
            "approved_thresholds": {
                "max_magnification_rate_per_s": cfg.max_magnification_rate_per_s,
                "max_working_distance_rate_mm_per_s": cfg.max_working_distance_rate_mm_per_s,
                "max_intrinsics_switch_rate_hz": cfg.max_intrinsics_switch_rate_hz,
                "calibration_ambiguity_margin": cfg.calibration_ambiguity_margin,
            },
            "intrinsics_transitions": intrinsics_transitions,
            "failure_reasons": temporal_failures,
        },
        navigation_level="L2" if all_safe else "L0",
    )


def _validation_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in {POSE_ONLY_MODE, DYNAMIC_AR_MODE}:
        raise OfflinePoseReplayError(
            "replay_mode_invalid",
            "Replay mode must be pose_only_engineering or dynamic_ar_validation.",
        )
    return normalized


def _validated_config(config: OfflinePoseReplayConfig) -> OfflinePoseReplayConfig:
    for field, value in (
        ("max_time_offset_ms", config.max_time_offset_ms),
        ("drift_threshold_mm", config.drift_threshold_mm),
        ("tre_proxy_threshold_mm", config.tre_proxy_threshold_mm),
        ("dynamic_target_error_threshold_mm", config.dynamic_target_error_threshold_mm),
        ("max_magnification_rate_per_s", config.max_magnification_rate_per_s),
        ("max_working_distance_rate_mm_per_s", config.max_working_distance_rate_mm_per_s),
        ("max_intrinsics_switch_rate_hz", config.max_intrinsics_switch_rate_hz),
    ):
        parsed = _nonnegative_float(value, code="replay_threshold_invalid", label=field)
        if parsed <= 0:
            raise OfflinePoseReplayError(
                "replay_threshold_invalid",
                f"{field} must be positive.",
            )
    if int(config.minimum_visible_projection_points) < 1:
        raise OfflinePoseReplayError(
            "replay_threshold_invalid",
            "minimum_visible_projection_points must be positive.",
        )
    ambiguity_margin = _nonnegative_float(
        config.calibration_ambiguity_margin,
        code="replay_threshold_invalid",
        label="calibration_ambiguity_margin",
    )
    if ambiguity_margin > 1.0:
        raise OfflinePoseReplayError(
            "replay_threshold_invalid",
            "calibration_ambiguity_margin must be within [0, 1].",
        )
    return config


def _timestamps(values: Sequence[float], *, label: str) -> list[float]:
    try:
        timestamps = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            f"{label}_timestamp_invalid",
            f"{label.capitalize()} timestamps must be numeric.",
        ) from exc
    if any(not np.isfinite(value) for value in timestamps):
        raise OfflinePoseReplayError(
            f"{label}_timestamp_non_finite",
            f"{label.capitalize()} timestamps must be finite.",
        )
    if any(current < previous for previous, current in zip(timestamps, timestamps[1:])):
        raise OfflinePoseReplayError(
            f"{label}_timestamps_not_monotonic",
            f"{label.capitalize()} timestamps must be monotonic.",
        )
    return timestamps


def _frame_indices(
    values: Sequence[int] | None,
    *,
    frame_count: int,
    mode: str,
) -> list[int]:
    if values is None:
        if mode == DYNAMIC_AR_MODE:
            raise OfflinePoseReplayError(
                "video_frame_indices_missing",
                "Decoded video frame indexes are required for dynamic AR validation.",
            )
        return list(range(frame_count))
    try:
        indices = [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            "video_frame_indices_invalid",
            "Video frame indexes must be integers.",
        ) from exc
    if len(indices) != frame_count or any(value < 0 for value in indices):
        raise OfflinePoseReplayError(
            "video_frame_indices_invalid",
            "Video frame indexes must match the decoded timestamp count.",
        )
    return indices


def _frame_sequence_failures(
    indices: Sequence[int],
    timestamps: Sequence[float],
    *,
    mode: str,
) -> dict[int, list[str]]:
    if mode != DYNAMIC_AR_MODE:
        return {}
    failures: dict[int, list[str]] = {}
    for position in range(1, len(indices)):
        current_index = indices[position]
        reasons: list[str] = []
        if current_index != indices[position - 1] + 1:
            reasons.append("video_frame_sequence_gap")
        if timestamps[position] <= timestamps[position - 1]:
            reasons.append("video_frame_timestamp_not_increasing")
        if reasons:
            failures[current_index] = reasons
    return failures


def _projection_points(
    values: Sequence[Sequence[float]] | None,
    *,
    mode: str,
) -> NDArray[np.float64] | None:
    if values is None:
        if mode == DYNAMIC_AR_MODE:
            raise OfflinePoseReplayError(
                "projection_evidence_missing",
                "Dynamic AR validation requires 3D projection points.",
            )
        return None
    try:
        points = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            "projection_points_invalid",
            "Projection points must be a numeric Nx3 array.",
        ) from exc
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] < 4:
        raise OfflinePoseReplayError(
            "projection_points_invalid",
            "At least four 3D projection points are required.",
        )
    if not np.isfinite(points).all():
        raise OfflinePoseReplayError(
            "projection_points_invalid",
            "Projection points must be finite.",
        )
    if np.unique(points, axis=0).shape[0] != points.shape[0]:
        raise OfflinePoseReplayError(
            "projection_points_duplicate",
            "Projection points must contain unique 3D locations.",
        )
    centered = points - points.mean(axis=0)
    if np.linalg.matrix_rank(centered, tol=1e-8) < 2:
        raise OfflinePoseReplayError(
            "projection_points_degenerate",
            "Projection points must span a non-collinear 3D surface region.",
        )
    pairwise = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    nonzero_distances = pairwise[pairwise > 0]
    if nonzero_distances.size == 0 or float(nonzero_distances.min()) < 1e-3:
        raise OfflinePoseReplayError(
            "projection_points_too_close",
            "Projection points must be separated by at least 0.001 mm.",
        )
    return points


def _dynamic_pose_indices(
    poses: Sequence[Mapping[str, Any]],
    frame_indices: Sequence[int],
    *,
    expected_from_space: str,
    expected_to_space: str,
    expected_source_frame: dict[str, Any] | None,
    expected_target_frame: dict[str, Any] | None,
    expected_matrix_convention: dict[str, str] | None,
) -> list[int]:
    if len(poses) != len(frame_indices):
        raise OfflinePoseReplayError(
            "pose_frame_binding_invalid",
            "Dynamic AR requires exactly one pose record for every video frame.",
        )
    by_frame: dict[int, int] = {}
    for pose_index, pose in enumerate(poses):
        raw_frame_index = pose.get("frame_index")
        if isinstance(raw_frame_index, bool) or not isinstance(raw_frame_index, (int, str)):
            raise OfflinePoseReplayError(
                "pose_frame_binding_invalid",
                "Every dynamic pose requires an integer frame_index.",
            )
        try:
            frame_index = int(raw_frame_index)
        except (TypeError, ValueError) as exc:
            raise OfflinePoseReplayError(
                "pose_frame_binding_invalid",
                "Every dynamic pose requires an integer frame_index.",
            ) from exc
        if frame_index in by_frame:
            raise OfflinePoseReplayError(
                "pose_frame_binding_duplicate",
                "Dynamic pose frame indexes must be unique.",
            )
        by_frame[frame_index] = pose_index
        expected_metadata = {
            "from_space": expected_from_space,
            "to_space": expected_to_space,
            "direction": "forward",
            "unit": "mm",
            "handedness": RIGHT_HANDED,
            "axis_convention": CAMERA_AXIS_CONVENTION,
        }
        for field, expected in expected_metadata.items():
            if str(pose.get(field) or "").strip() != expected:
                raise OfflinePoseReplayError(
                    "pose_coordinate_contract_invalid",
                    f"Pose {field} must equal {expected} for the validated coordinate chain.",
                )
        try:
            pose_source_frame = validate_frame_metadata(
                pose.get("source_frame"),
                expected_name=expected_from_space,
            )
            pose_target_frame = validate_frame_metadata(
                pose.get("target_frame"),
                expected_name=expected_to_space,
            )
            pose_matrix_convention = validate_matrix_convention(pose.get("matrix_convention"))
        except CoordinateContractError as exc:
            raise OfflinePoseReplayError(
                "pose_coordinate_contract_invalid",
                f"Pose frame metadata is invalid: {exc.code}.",
            ) from exc
        if (
            pose_source_frame != expected_source_frame
            or pose_target_frame != expected_target_frame
            or pose_matrix_convention != expected_matrix_convention
        ):
            raise OfflinePoseReplayError(
                "pose_coordinate_contract_invalid",
                "Pose frame metadata and matrix convention must match the validated coordinate chain.",
            )
    if set(by_frame) != set(frame_indices):
        raise OfflinePoseReplayError(
            "pose_frame_binding_invalid",
            "Dynamic pose frame indexes must match the decoded video frame indexes one-to-one.",
        )
    return [by_frame[frame_index] for frame_index in frame_indices]


def _strict_frame_metadata(value: Mapping[str, Any] | None, *, expected_name: str) -> dict[str, Any]:
    try:
        return validate_frame_metadata(value, expected_name=expected_name)
    except CoordinateContractError as exc:
        raise OfflinePoseReplayError(
            "pose_coordinate_contract_invalid",
            f"Dynamic coordinate frame metadata is invalid: {exc.code}.",
        ) from exc


def _strict_matrix_convention(value: Mapping[str, Any] | None) -> dict[str, str]:
    try:
        return validate_matrix_convention(value)
    except CoordinateContractError as exc:
        raise OfflinePoseReplayError(
            "pose_coordinate_contract_invalid",
            f"Dynamic matrix convention is invalid: {exc.code}.",
        ) from exc


def _matrix(value: Any) -> NDArray[np.float64]:
    if isinstance(value, Mapping):
        value = value.get("matrix")
    try:
        matrix = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            "transform_chain_invalid",
            "Pose and L1 transforms must be numeric rigid 4x4 matrices.",
        ) from exc
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise OfflinePoseReplayError(
            "transform_chain_invalid",
            "Pose and L1 transforms must be finite rigid 4x4 matrices.",
        )
    rotation = matrix[:3, :3]
    if (
        not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-9)
        or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6)
        or not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-6)
    ):
        raise OfflinePoseReplayError(
            "transform_chain_invalid",
            "Pose and L1 transforms must be proper rigid homogeneous matrices.",
        )
    return matrix


def _optional_matrix(value: Any) -> NDArray[np.float64] | None:
    try:
        return _matrix(value)
    except OfflinePoseReplayError:
        return None


def _required_float(value: Any, *, code: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            code,
            "Required numeric replay metadata is invalid.",
        ) from exc
    if not np.isfinite(parsed):
        raise OfflinePoseReplayError(
            code,
            "Required numeric replay metadata must be finite.",
        )
    return parsed


def _nonnegative_float(value: Any, *, code: str, label: str) -> float:
    parsed = _required_float(value, code=code)
    if parsed < 0:
        raise OfflinePoseReplayError(code, f"{label} must be non-negative.")
    return parsed


def _optional_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed if np.isfinite(parsed) else float("nan")


def _coordinate_space(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise OfflinePoseReplayError(
            "coordinate_space_missing",
            f"{field} is required.",
        )
    return normalized


def _drift_measurement(
    pose: Mapping[str, Any],
    pose_matrix: NDArray[np.float64] | None,
    baseline_translation: NDArray[np.float64] | None,
    *,
    require_explicit: bool,
) -> float:
    explicit = pose.get("tracking_drift_mm", pose.get("drift_mm"))
    if explicit is not None:
        return _optional_float(explicit)
    if require_explicit or pose_matrix is None or baseline_translation is None:
        return float("inf")
    return float(np.linalg.norm(pose_matrix[:3, 3] - baseline_translation))


def _calibration(
    table: Sequence[Mapping[str, Any]],
    magnification: float,
    working_distance: float,
) -> Mapping[str, Any] | None:
    candidates = _calibration_candidates(table, magnification, working_distance)
    if not candidates:
        return None
    return candidates[0][0]


def _calibration_candidates(
    table: Sequence[Mapping[str, Any]],
    magnification: float,
    working_distance: float,
) -> list[tuple[Mapping[str, Any], float]]:
    candidates = [
        (
            item,
            _calibration_selection_distance(
                item,
                magnification=magnification,
                working_distance=working_distance,
            ),
        )
        for item in table
        if _in_range(item, "magnification", magnification) and _in_range(item, "working_distance_mm", working_distance)
    ]
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate[1],
            str(candidate[0].get("intrinsics_id") or ""),
        ),
    )


def _calibration_selection_ambiguous(
    candidates: Sequence[tuple[Mapping[str, Any], float]],
    *,
    margin: float,
) -> bool:
    if len(candidates) < 2:
        return False
    first, second = candidates[0], candidates[1]
    first_id = str(first[0].get("intrinsics_id") or "").strip()
    second_id = str(second[0].get("intrinsics_id") or "").strip()
    return bool(first_id and second_id and first_id != second_id and abs(second[1] - first[1]) <= margin)


def _calibration_selection_distance(
    item: Mapping[str, Any],
    *,
    magnification: float,
    working_distance: float,
) -> float:
    magnification_min = _optional_float(item.get("magnification_min"))
    magnification_max = _optional_float(item.get("magnification_max"))
    distance_min = _optional_float(item.get("working_distance_min_mm"))
    distance_max = _optional_float(item.get("working_distance_max_mm"))
    magnification_reference = _optional_float(
        item.get(
            "magnification_reference",
            (magnification_min + magnification_max) / 2.0,
        )
    )
    distance_reference = _optional_float(
        item.get(
            "working_distance_reference_mm",
            (distance_min + distance_max) / 2.0,
        )
    )
    magnification_scale = max(magnification_max - magnification_min, 1e-9)
    distance_scale = max(distance_max - distance_min, 1e-9)
    return float(
        ((magnification - magnification_reference) / magnification_scale) ** 2
        + ((working_distance - distance_reference) / distance_scale) ** 2
    )


def _value_in_calibration_range(
    table: Sequence[Mapping[str, Any]],
    field: str,
    value: float,
) -> bool:
    return any(_in_range(item, field, value) for item in table)


def _in_range(item: Mapping[str, Any], field: str, value: float) -> bool:
    if not np.isfinite(value):
        return False
    minimum_key = f"{field}_min" if field == "magnification" else "working_distance_min_mm"
    maximum_key = f"{field}_max" if field == "magnification" else "working_distance_max_mm"
    minimum = _optional_float(item.get(minimum_key))
    maximum = _optional_float(item.get(maximum_key))
    return np.isfinite(minimum) and np.isfinite(maximum) and minimum <= value <= maximum


def _dynamic_calibration_failures(calibration: Mapping[str, Any] | None) -> list[str]:
    if calibration is None:
        return ["verified_camera_calibration_missing"]
    reasons: list[str] = []
    if str(calibration.get("verification_status") or "").lower() != "verified":
        reasons.append("camera_calibration_not_verified")
    if not str(calibration.get("calibration_table_id") or "").strip():
        reasons.append("camera_calibration_table_id_missing")
    if str(calibration.get("selection_method") or "").strip() != "nearest_validated_entry_v1":
        reasons.append("camera_calibration_selection_method_invalid")
    if not np.isfinite(_optional_float(calibration.get("magnification_reference"))):
        reasons.append("camera_calibration_reference_missing")
    if not np.isfinite(_optional_float(calibration.get("working_distance_reference_mm"))):
        reasons.append("camera_calibration_reference_missing")
    checksum = str(calibration.get("artifact_sha256") or "").strip().lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        reasons.append("camera_calibration_sha256_missing_or_invalid")
    camera_model = str(calibration.get("camera_model") or "pinhole_opencv").strip().lower()
    if camera_model == OCAMCALIB_POLYNOMIAL_V1:
        try:
            OcamCalibPolynomialV1.from_mapping(calibration)
        except OcamCalibError as exc:
            reasons.append(exc.code)
    else:
        try:
            _camera_matrix(calibration.get("camera_matrix"), calibration.get("image_size_px"))
        except OfflinePoseReplayError as exc:
            reasons.append(exc.code)
        try:
            _distortion(calibration.get("distortion_coefficients"))
        except OfflinePoseReplayError as exc:
            reasons.append(exc.code)
    return reasons


def _project_points(
    points: NDArray[np.float64],
    composed_transform: NDArray[np.float64],
    calibration: Mapping[str, Any],
) -> tuple[list[list[float]], int]:
    image_size = _image_size(calibration.get("image_size_px"))
    rotation = composed_transform[:3, :3]
    translation = composed_transform[:3, 3].reshape(3, 1)
    camera_points = (rotation @ points.T + translation).T
    camera_model = str(calibration.get("camera_model") or "pinhole_opencv").strip().lower()
    pixels: NDArray[np.float64]
    if camera_model == OCAMCALIB_POLYNOMIAL_V1:
        try:
            pixels = OcamCalibPolynomialV1.from_mapping(calibration).project_camera_points(camera_points)
        except OcamCalibError as exc:
            raise OfflinePoseReplayError(exc.code, str(exc)) from exc
    else:
        camera_matrix = _camera_matrix(calibration.get("camera_matrix"), image_size)
        distortion = _distortion(calibration.get("distortion_coefficients"))
        if np.any(camera_points[:, 2] <= 0):
            raise OfflinePoseReplayError(
                "projection_points_behind_camera",
                "All projection points must lie in front of the camera.",
            )
        rotation_vector, _ = cv2.Rodrigues(rotation)
        projected, _ = cv2.projectPoints(
            points,
            rotation_vector,
            translation,
            camera_matrix,
            distortion,
        )
        pixels = np.asarray(projected, dtype=np.float64).reshape(-1, 2)
    if not np.isfinite(pixels).all():
        raise OfflinePoseReplayError(
            "projection_pixels_non_finite",
            "Projected pixels must be finite.",
        )
    width, height = image_size
    visible = (pixels[:, 0] >= 0) & (pixels[:, 0] < width) & (pixels[:, 1] >= 0) & (pixels[:, 1] < height)
    visible_pixels = pixels[visible]
    if visible_pixels.shape[0] >= 3:
        unique_visible = np.unique(np.round(visible_pixels, decimals=3), axis=0)
        if unique_visible.shape[0] < 3:
            raise OfflinePoseReplayError(
                "projection_geometry_degenerate",
                "Visible projected points collapse to duplicate image locations.",
            )
        hull = cv2.convexHull(unique_visible.astype(np.float32))
        if float(cv2.contourArea(hull)) < MIN_PROJECTED_HULL_AREA_PX2:
            raise OfflinePoseReplayError(
                "projection_geometry_too_small",
                "Visible projected points do not cover the minimum image area.",
            )
    return [[float(value) for value in row] for row in pixels], int(np.count_nonzero(visible))


def _image_size(value: Any) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise OfflinePoseReplayError(
            "camera_image_size_missing_or_invalid",
            "Verified camera image size must contain width and height.",
        )
    try:
        width, height = int(value[0]), int(value[1])
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            "camera_image_size_missing_or_invalid",
            "Verified camera image size must contain integer dimensions.",
        ) from exc
    if width <= 0 or height <= 0:
        raise OfflinePoseReplayError(
            "camera_image_size_missing_or_invalid",
            "Verified camera image dimensions must be positive.",
        )
    return width, height


def _camera_matrix(value: Any, image_size: Any) -> NDArray[np.float64]:
    width, height = _image_size(image_size)
    try:
        matrix = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            "camera_matrix_missing_or_invalid",
            "Verified camera matrix must be numeric.",
        ) from exc
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise OfflinePoseReplayError(
            "camera_matrix_missing_or_invalid",
            "Verified camera matrix must be a finite 3x3 matrix.",
        )
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0:
        raise OfflinePoseReplayError(
            "camera_matrix_missing_or_invalid",
            "Verified camera focal lengths must be positive.",
        )
    if not 0 <= matrix[0, 2] < width or not 0 <= matrix[1, 2] < height:
        raise OfflinePoseReplayError(
            "camera_matrix_missing_or_invalid",
            "Verified camera principal point must be inside the image.",
        )
    return matrix


def _distortion(value: Any) -> NDArray[np.float64]:
    try:
        array = np.asarray(value, dtype=np.float64).reshape(-1, 1)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayError(
            "camera_distortion_missing_or_invalid",
            "Verified distortion coefficients must be numeric.",
        ) from exc
    if array.size not in {4, 5, 8, 12, 14} or not np.isfinite(array).all():
        raise OfflinePoseReplayError(
            "camera_distortion_missing_or_invalid",
            "Verified distortion coefficients have an unsupported shape.",
        )
    return array
