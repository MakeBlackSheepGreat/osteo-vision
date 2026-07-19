from __future__ import annotations

import numpy as np
import pytest

from src.navigation.offline_pose_replay import (
    DYNAMIC_AR_MODE,
    MAX_PROJECTION_POINT_COUNT,
    POSE_ONLY_MODE,
    OfflinePoseReplayConfig,
    OfflinePoseReplayError,
    replay_offline_poses,
)

MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}


def _frame(name: str, axis_convention: str, source: str) -> dict[str, object]:
    return {
        "name": name,
        "handedness": "right_handed",
        "axis_convention": axis_convention,
        "unit": "mm",
        "source": source,
    }


def _matrix(
    translation_x: float = 0.0,
    translation_z: float = 0.0,
) -> list[list[float]]:
    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 3] = translation_x
    matrix[2, 3] = translation_z
    return matrix.tolist()


def _poses() -> list[dict[str, object]]:
    records: list[dict[str, object]] = [
        {
            "timestamp_s": 0.002,
            "matrix": _matrix(0.0),
            "magnification": 4.0,
            "working_distance_mm": 250.0,
            "tracking_status": "tracking",
            "tracking_drift_mm": 0.05,
            "tracking_drift_source": "independent_tracker_residual",
            "dynamic_target_error_mm": 0.2,
            "dynamic_target_error_source": "independent_phantom_target",
        },
        {
            "timestamp_s": 0.098,
            "matrix": _matrix(0.1),
            "magnification": 4.0,
            "working_distance_mm": 250.0,
            "tracking_status": "tracking",
            "tracking_drift_mm": 0.05,
            "tracking_drift_source": "independent_tracker_residual",
            "dynamic_target_error_mm": 0.2,
            "dynamic_target_error_source": "independent_phantom_target",
        },
        {
            "timestamp_s": 0.203,
            "matrix": _matrix(0.2),
            "magnification": 4.0,
            "working_distance_mm": 250.0,
            "tracking_status": "tracking",
            "tracking_drift_mm": 0.05,
            "tracking_drift_source": "independent_tracker_residual",
            "dynamic_target_error_mm": 0.2,
            "dynamic_target_error_source": "independent_phantom_target",
        },
    ]
    for frame_index, record in enumerate(records):
        record.update(
            {
                "frame_index": frame_index,
                "from_space": "phantom_reference",
                "to_space": "camera_optical",
                "direction": "forward",
                "unit": "mm",
                "handedness": "right_handed",
                "axis_convention": "opencv_camera_x_right_y_down_z_forward",
                "source_frame": _frame(
                    "phantom_reference",
                    "phantom_x_right_y_anterior_z_superior",
                    "unit_test_l1_contract",
                ),
                "target_frame": _frame(
                    "camera_optical",
                    "opencv_camera_x_right_y_down_z_forward",
                    "unit_test_pose_manifest",
                ),
                "matrix_convention": MATRIX_CONVENTION,
            }
        )
    return records


def _calibration_table() -> list[dict[str, object]]:
    return [
        {
            "intrinsics_id": "scope-4x-wd250",
            "calibration_table_id": "scope-zoom-table-v1",
            "selection_method": "nearest_validated_entry_v1",
            "magnification_reference": 4.0,
            "magnification_min": 3.5,
            "magnification_max": 4.5,
            "working_distance_reference_mm": 250.0,
            "working_distance_min_mm": 225.0,
            "working_distance_max_mm": 275.0,
            "camera_matrix": [
                [920.0, 0.0, 640.0],
                [0.0, 910.0, 360.0],
                [0.0, 0.0, 1.0],
            ],
            "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
            "image_size_px": [1280, 720],
            "artifact_sha256": "a" * 64,
            "verification_status": "verified",
        }
    ]


def _config() -> OfflinePoseReplayConfig:
    return OfflinePoseReplayConfig(
        max_time_offset_ms=20.0,
        drift_threshold_mm=0.5,
        tre_proxy_threshold_mm=1.0,
        dynamic_target_error_threshold_mm=0.5,
        minimum_visible_projection_points=4,
        max_magnification_rate_per_s=25.0,
        max_working_distance_rate_mm_per_s=600.0,
        max_intrinsics_switch_rate_hz=10.0,
        calibration_ambiguity_margin=0.05,
    )


def _dynamic_kwargs(
    frame_count: int = 3,
    *,
    source_space: str = "cbct_reference",
    reference_space: str = "phantom_reference",
    camera_space: str = "camera_optical",
) -> dict[str, object]:
    return {
        "validation_mode": DYNAMIC_AR_MODE,
        "frame_indices": list(range(frame_count)),
        "projection_points_3d": [
            [0.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [20.0, 20.0, 0.0],
            [0.0, 20.0, 0.0],
        ],
        "source_frame_metadata": _frame(
            source_space,
            "dicom_lps_x_left_y_posterior_z_superior",
            "unit_test_l1_contract",
        ),
        "reference_frame_metadata": _frame(
            reference_space,
            "phantom_x_right_y_anterior_z_superior",
            "unit_test_l1_contract",
        ),
        "camera_frame_metadata": _frame(
            camera_space,
            "opencv_camera_x_right_y_down_z_forward",
            "unit_test_pose_manifest",
        ),
        "matrix_convention": MATRIX_CONVENTION,
    }


def test_replay_synchronizes_nearest_pose_and_composes_coordinate_chain() -> None:
    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        _poses(),
        calibration_table=_calibration_table(),
        static_l1_transform={"matrix": _matrix(10.0, 500.0)},
        l1_tre_mm=0.5,
        source_space="cbct_ras",
        reference_space="phantom_reference",
        camera_space="camera_optical",
        config=_config(),
        **_dynamic_kwargs(source_space="cbct_ras"),
    )

    assert result.navigation_ready is True
    assert result.navigation_level == "L2"
    assert result.safe_frame_count == 3
    assert result.degraded_frame_count == 0
    assert [frame.pose_index for frame in result.frames] == [0, 1, 2]
    assert result.frames[1].time_offset_ms == pytest.approx(-2.0)
    assert result.frames[1].drift_proxy_mm == pytest.approx(0.05)
    assert result.frames[1].tre_proxy_mm == pytest.approx(np.sqrt(0.5**2 + 0.05**2))
    assert result.frames[0].intrinsics_id == "scope-4x-wd250"
    assert np.asarray(result.frames[0].composed_transform)[:3, 3] == pytest.approx([10.0, 0.0, 500.0])
    assert result.frames[0].transform_chain[0]["from_space"] == "cbct_ras"
    assert result.frames[0].transform_chain[-1]["to_space"] == "camera_optical"


def test_pose_only_engineering_never_unlocks_navigation() -> None:
    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        _poses(),
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        validation_mode=POSE_ONLY_MODE,
    )

    assert result.navigation_ready is False
    assert result.navigation_level == "L0"
    assert result.safe_frame_count == 0
    assert "pose_only_engineering_no_navigation" in result.failure_reasons


def test_pose_only_nearest_pose_tie_selects_earlier_record() -> None:
    poses = _poses()
    poses[0]["timestamp_s"] = 0.0
    poses[1]["timestamp_s"] = 0.2
    poses[2]["timestamp_s"] = 0.4

    result = replay_offline_poses(
        [0.1, 0.3],
        poses,
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        validation_mode=POSE_ONLY_MODE,
    )

    assert [frame.pose_index for frame in result.frames] == [0, 1]


def test_pose_only_nearest_pose_tie_selects_first_duplicate_record() -> None:
    poses = _poses()
    poses[0]["timestamp_s"] = 0.0
    poses[1]["timestamp_s"] = 0.0
    poses[2]["timestamp_s"] = 0.2

    result = replay_offline_poses(
        [0.0, 0.1],
        poses,
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        validation_mode=POSE_ONLY_MODE,
    )

    assert [frame.pose_index for frame in result.frames] == [0, 0]


def test_dynamic_ar_rejects_unbounded_projection_point_payload() -> None:
    points = [[float(index), float(index % 17), 0.0] for index in range(MAX_PROJECTION_POINT_COUNT + 1)]

    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0],
            [_poses()[0]],
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            projection_points_3d=points,
            frame_indices=[0],
            validation_mode=DYNAMIC_AR_MODE,
        )

    assert exc_info.value.code == "projection_points_limit_exceeded"


def test_dynamic_ar_selects_nearest_bounded_intrinsics_per_frame() -> None:
    calibration_table = _calibration_table()
    calibration_table.append(
        {
            **calibration_table[0],
            "intrinsics_id": "scope-6x-wd300",
            "magnification_reference": 6.0,
            "magnification_min": 5.5,
            "magnification_max": 6.5,
            "working_distance_reference_mm": 300.0,
            "working_distance_min_mm": 290.0,
            "working_distance_max_mm": 310.0,
            "camera_matrix": [
                [1180.0, 0.0, 640.0],
                [0.0, 1170.0, 360.0],
                [0.0, 0.0, 1.0],
            ],
        }
    )
    poses = _poses()
    poses[1]["magnification"] = 6.0
    poses[1]["working_distance_mm"] = 300.0
    poses[2]["magnification"] = 6.0
    poses[2]["working_distance_mm"] = 300.0

    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        poses,
        calibration_table=calibration_table,
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(),
    )

    assert result.navigation_ready is True
    assert [frame.intrinsics_id for frame in result.frames] == [
        "scope-4x-wd250",
        "scope-6x-wd300",
        "scope-6x-wd300",
    ]
    assert result.calibration_transition_summary["switch_count"] == 1
    assert result.calibration_transition_summary["oscillation_count"] == 0
    assert result.calibration_transition_summary["status"] == "passed"


def test_dynamic_ar_rejects_intrinsics_a_b_a_oscillation() -> None:
    calibration_table = _calibration_table()
    calibration_table.append(
        {
            **calibration_table[0],
            "intrinsics_id": "scope-6x-wd300",
            "magnification_reference": 6.0,
            "magnification_min": 5.5,
            "magnification_max": 6.5,
            "working_distance_reference_mm": 300.0,
            "working_distance_min_mm": 290.0,
            "working_distance_max_mm": 310.0,
        }
    )
    poses = _poses()
    poses[1]["magnification"] = 6.0
    poses[1]["working_distance_mm"] = 300.0

    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        poses,
        calibration_table=calibration_table,
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(),
    )

    assert result.navigation_ready is False
    assert result.navigation_level == "L0"
    assert "calibration_selection_oscillation" in result.failure_reasons
    assert result.calibration_transition_summary["switch_count"] == 2
    assert result.calibration_transition_summary["oscillation_count"] == 1
    assert result.calibration_transition_summary["status"] == "failed_closed"
    assert result.calibration_transition_summary["intrinsics_transitions"][-1]["oscillation"] is True


def test_dynamic_ar_rejects_ambiguous_overlapping_calibration_entries_independent_of_order() -> None:
    primary = _calibration_table()[0]
    competing = {
        **primary,
        "intrinsics_id": "scope-4x-wd250-competing",
        "camera_matrix": [
            [930.0, 0.0, 640.0],
            [0.0, 920.0, 360.0],
            [0.0, 0.0, 1.0],
        ],
    }

    results = [
        replay_offline_poses(
            [0.0, 0.1, 0.2],
            _poses(),
            calibration_table=table,
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            config=_config(),
            **_dynamic_kwargs(),
        )
        for table in ([primary, competing], [competing, primary])
    ]

    assert all(result.navigation_ready is False for result in results)
    assert all("calibration_selection_ambiguous" in result.failure_reasons for result in results)
    assert all(result.calibration_transition_summary["ambiguous_frame_count"] == 3 for result in results)
    assert [result.frames[0].intrinsics_id for result in results] == [
        "scope-4x-wd250",
        "scope-4x-wd250",
    ]


def test_dynamic_ar_rejects_magnification_and_working_distance_rate_spikes() -> None:
    calibration_table = _calibration_table()
    calibration_table.append(
        {
            **calibration_table[0],
            "intrinsics_id": "scope-8x-wd400",
            "magnification_reference": 8.0,
            "magnification_min": 7.5,
            "magnification_max": 8.5,
            "working_distance_reference_mm": 400.0,
            "working_distance_min_mm": 390.0,
            "working_distance_max_mm": 410.0,
        }
    )
    poses = _poses()
    poses[1]["magnification"] = 8.0
    poses[1]["working_distance_mm"] = 400.0
    poses[2]["magnification"] = 8.0
    poses[2]["working_distance_mm"] = 400.0

    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        poses,
        calibration_table=calibration_table,
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(),
    )

    assert result.navigation_ready is False
    assert "magnification_rate_exceeded" in result.failure_reasons
    assert "working_distance_rate_exceeded" in result.failure_reasons
    assert result.calibration_transition_summary["max_magnification_rate_per_s"] == pytest.approx(40.0)
    assert result.calibration_transition_summary["max_working_distance_rate_mm_per_s"] == pytest.approx(1500.0)


def test_dynamic_ar_rejects_legacy_single_range_intrinsics() -> None:
    legacy = _calibration_table()
    for field in (
        "calibration_table_id",
        "selection_method",
        "magnification_reference",
        "working_distance_reference_mm",
    ):
        legacy[0].pop(field)

    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        _poses(),
        calibration_table=legacy,
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(),
    )

    assert result.navigation_ready is False
    assert "camera_calibration_table_id_missing" in result.failure_reasons
    assert "camera_calibration_selection_method_invalid" in result.failure_reasons


@pytest.mark.parametrize(
    ("injection", "reason"),
    [
        ("tracking_lost", "tracking_lost"),
        ("time_offset", "pose_time_offset_exceeded"),
        ("magnification_out_of_range", "magnification_out_of_calibration_range"),
        ("working_distance_out_of_range", "working_distance_out_of_calibration_range"),
        ("corrupt_transform", "transform_chain_invalid"),
        ("coordinate_error", "coordinate_chain_invalid"),
        ("drift_exceeded", "drift_threshold_exceeded"),
        ("tre_exceeded", "tre_proxy_threshold_exceeded"),
        ("frame_drop", "frame_dropped"),
    ],
)
def test_failure_injections_remove_spatial_transform_and_close_to_l0(
    injection: str,
    reason: str,
) -> None:
    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        _poses(),
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        failure_injections={1: [injection]},
        **_dynamic_kwargs(),
    )

    frame = result.frames[1]
    assert frame.navigation_ready is False
    assert frame.navigation_level == "L0"
    assert frame.fallback_mode == "unregistered_3d_reference"
    assert frame.composed_transform is None
    assert reason in frame.failure_reasons
    assert result.navigation_ready is False
    assert result.navigation_level == "L0"
    assert reason in result.failure_reasons


def test_real_tracking_and_calibration_failures_close_to_l0() -> None:
    poses = [_poses()[1]]
    poses[0]["frame_index"] = 0
    poses[0]["tracking_status"] = "lost"
    poses[0]["magnification"] = 12.0
    poses[0]["working_distance_mm"] = 400.0
    result = replay_offline_poses(
        [0.1],
        poses,
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(1),
    )

    frame = result.frames[0]
    assert frame.navigation_ready is False
    assert frame.composed_transform is None
    assert "tracking_lost" in frame.failure_reasons
    assert "magnification_out_of_calibration_range" in frame.failure_reasons
    assert "working_distance_out_of_calibration_range" in frame.failure_reasons


def test_real_corrupt_pose_degrades_affected_frame_without_aborting_evidence() -> None:
    poses = _poses()
    poses[1]["matrix"] = [[1.0, 0.0], [0.0, 1.0]]
    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        poses,
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(),
    )

    assert result.safe_frame_count == 2
    assert result.degraded_frame_count == 1
    assert result.frames[1].composed_transform is None
    assert "transform_chain_invalid" in result.frames[1].failure_reasons


def test_explicit_tracking_drift_is_used_instead_of_camera_motion_proxy() -> None:
    poses = [_poses()[1]]
    poses[0]["frame_index"] = 0
    poses[0]["matrix"] = _matrix(100.0)
    poses[0]["tracking_drift_mm"] = 0.1
    result = replay_offline_poses(
        [0.1],
        poses,
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(1),
    )

    assert result.frames[0].navigation_ready is True
    assert result.frames[0].drift_proxy_mm == pytest.approx(0.1)


def test_dynamic_ar_rejects_duplicate_pose_timestamps() -> None:
    poses = _poses()
    poses[1]["timestamp_s"] = poses[0]["timestamp_s"]
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0, 0.1, 0.2],
            poses,
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            config=_config(),
            **_dynamic_kwargs(),
        )

    assert exc_info.value.code == "pose_timestamps_not_strictly_increasing"


def test_dynamic_ar_rejects_pose_reuse_across_video_frames() -> None:
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0, 0.1, 0.2],
            _poses()[:1],
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            config=_config(),
            **_dynamic_kwargs(),
        )

    assert exc_info.value.code == "pose_frame_binding_invalid"


def test_dynamic_ar_rejects_duplicate_pose_frame_binding() -> None:
    poses = _poses()
    poses[1]["frame_index"] = 0
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0, 0.1, 0.2],
            poses,
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            config=_config(),
            **_dynamic_kwargs(),
        )

    assert exc_info.value.code == "pose_frame_binding_duplicate"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("from_space", "attacker_space"),
        ("to_space", "attacker_space"),
        ("direction", "inverse"),
        ("unit", "cm"),
        ("handedness", "left_handed"),
        ("axis_convention", "unknown"),
    ],
)
def test_dynamic_ar_rejects_invalid_pose_coordinate_contract(
    field: str,
    value: str,
) -> None:
    poses = _poses()
    poses[1][field] = value
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0, 0.1, 0.2],
            poses,
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            config=_config(),
            **_dynamic_kwargs(),
        )

    assert exc_info.value.code == "pose_coordinate_contract_invalid"


@pytest.mark.parametrize(
    ("points", "code"),
    [
        (
            [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]],
            "projection_points_duplicate",
        ),
        (
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]],
            "projection_points_degenerate",
        ),
        (
            [[0.0, 0.0, 0.0], [0.0005, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]],
            "projection_points_too_close",
        ),
    ],
)
def test_dynamic_ar_rejects_unsafe_projection_point_sets(
    points: list[list[float]],
    code: str,
) -> None:
    kwargs = _dynamic_kwargs()
    kwargs["projection_points_3d"] = points
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0, 0.1, 0.2],
            _poses(),
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(0.0, 500.0),
            l1_tre_mm=0.2,
            config=_config(),
            **kwargs,
        )

    assert exc_info.value.code == code


def test_dynamic_ar_rejects_projection_with_negligible_image_coverage() -> None:
    kwargs = _dynamic_kwargs()
    kwargs["projection_points_3d"] = [
        [0.0, 0.0, 0.0],
        [0.1, 0.0, 0.0],
        [0.1, 0.1, 0.0],
        [0.0, 0.1, 0.0],
    ]
    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        _poses(),
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **kwargs,
    )

    assert result.navigation_ready is False
    assert "projection_geometry_too_small" in result.failure_reasons


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("tracking_drift_source", "tracking_drift_source_missing"),
        ("dynamic_target_error_mm", "dynamic_target_error_missing_or_invalid"),
        ("dynamic_target_error_source", "dynamic_target_error_source_missing"),
    ],
)
def test_dynamic_ar_missing_independent_measurement_evidence_fails_closed(
    field: str,
    reason: str,
) -> None:
    poses = _poses()
    poses[1].pop(field)
    result = replay_offline_poses(
        [0.0, 0.1, 0.2],
        poses,
        calibration_table=_calibration_table(),
        static_l1_transform=_matrix(0.0, 500.0),
        l1_tre_mm=0.2,
        config=_config(),
        **_dynamic_kwargs(),
    )

    assert result.navigation_ready is False
    assert reason in result.frames[1].failure_reasons


@pytest.mark.parametrize(
    ("frames", "code"),
    [
        ([], "frame_timestamps_empty"),
        ([0.1, 0.0], "frame_timestamps_not_monotonic"),
        ([float("nan")], "frame_timestamp_non_finite"),
    ],
)
def test_invalid_frame_timestamp_sequences_are_rejected(
    frames: list[float],
    code: str,
) -> None:
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            frames,
            _poses(),
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(),
            l1_tre_mm=0.2,
        )
    assert exc_info.value.code == code


def test_non_monotonic_pose_log_is_rejected() -> None:
    poses = _poses()
    poses[1]["timestamp_s"] = -1.0
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0],
            poses,
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(),
            l1_tre_mm=0.2,
        )
    assert exc_info.value.code == "pose_timestamps_not_monotonic"


@pytest.mark.parametrize(
    ("l1_tre_mm", "config", "code"),
    [
        (-0.1, None, "l1_tre_invalid"),
        (
            0.1,
            OfflinePoseReplayConfig(max_time_offset_ms=-1.0),
            "replay_threshold_invalid",
        ),
    ],
)
def test_negative_error_evidence_or_threshold_is_rejected(
    l1_tre_mm: float,
    config: OfflinePoseReplayConfig | None,
    code: str,
) -> None:
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0],
            _poses(),
            calibration_table=_calibration_table(),
            static_l1_transform=_matrix(),
            l1_tre_mm=l1_tre_mm,
            config=config,
        )
    assert exc_info.value.code == code


def test_non_rigid_static_transform_is_rejected() -> None:
    scaled = np.eye(4, dtype=np.float64)
    scaled[0, 0] = 2.0
    with pytest.raises(OfflinePoseReplayError) as exc_info:
        replay_offline_poses(
            [0.0],
            _poses(),
            calibration_table=_calibration_table(),
            static_l1_transform=scaled.tolist(),
            l1_tre_mm=0.2,
        )
    assert exc_info.value.code == "transform_chain_invalid"
