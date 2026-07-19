from __future__ import annotations

import hashlib

import numpy as np

from tools.materialize_c3vd_l2_proxy import bind_frames, parse_and_deduplicate_poses


def _pose_row(timestamp: float, translation_x: float) -> str:
    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 3] = translation_x
    return ",".join([f"{timestamp:.6f}", *(f"{value:.6f}" for value in matrix.reshape(-1))])


def test_duplicate_pose_timestamp_keeps_last_with_row_hash_audit() -> None:
    first = _pose_row(0.0, 1.0)
    discarded = _pose_row(0.016, 2.0)
    kept = _pose_row(0.016, 3.0)
    final = _pose_row(0.032, 4.0)
    poses, audit = parse_and_deduplicate_poses(("\n".join([first, discarded, kept, final]) + "\n").encode("utf-8"))

    assert len(poses) == 3
    assert poses[1]["source_row_index"] == 2
    assert poses[1]["matrix"][0, 3] == 3.0
    assert audit == [
        {
            "timestamp_s": 0.016,
            "policy": "keep_last_source_row_to_mirror_official_std_map_assignment",
            "kept_source_row_index": 2,
            "kept_source_row_sha256": hashlib.sha256((kept + "\n").encode("utf-8")).hexdigest(),
            "discarded": [
                {
                    "source_row_index": 1,
                    "source_row_sha256": hashlib.sha256((discarded + "\n").encode("utf-8")).hexdigest(),
                    "matrix_equal_to_kept": False,
                }
            ],
        }
    ]


def test_frame_pose_binding_records_unmatched_and_ambiguous_states() -> None:
    pose_text = (
        "\n".join(
            [
                _pose_row(3.120, 1.0),
                _pose_row(3.152, 2.0),
                _pose_row(3.500, 3.0),
            ]
        )
        + "\n"
    ).encode("utf-8")
    poses, _ = parse_and_deduplicate_poses(pose_text)
    bindings = bind_frames([0, 1], poses, pose_start_time_s=3.136)

    assert bindings[0]["binding_status"] == "ambiguous"
    assert bindings[0]["match_tolerance_ms"] == 10.0
    assert bindings[1]["binding_status"] == "unmatched"
    assert bindings[1]["absolute_time_offset_ms"] > 10.0
