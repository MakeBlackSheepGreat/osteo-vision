from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from osteo_vision_core.navigation.rigid_registration import (
    RigidRegistrationError,
    apply_rigid_transform,
    export_rigid_transform,
    register_rigid_points,
)

MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}


def _frame(name: str, axis_convention: str) -> dict:
    return {
        "name": name,
        "handedness": "right_handed",
        "axis_convention": axis_convention,
        "unit": "mm",
        "source": "unit_test_checksum_bound_points",
    }


def _rotation_z(angle_degrees: float) -> np.ndarray:
    angle = np.deg2rad(angle_degrees)
    return np.asarray(
        [[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]],
        dtype=np.float64,
    )


def test_register_rigid_points_recovers_transform_and_independent_tre() -> None:
    source = np.asarray([[0, 0, 0], [20, 0, 0], [0, 15, 0], [0, 0, 10], [10, 8, 4]], dtype=np.float64)
    validation_source = np.asarray([[5, 4, 2], [12, -3, 8], [-2, 7, 6]], dtype=np.float64)
    rotation = _rotation_z(32)
    translation = np.asarray([14.0, -8.0, 22.0])
    target = (rotation @ source.T).T + translation
    validation_target = (rotation @ validation_source.T).T + translation

    result = register_rigid_points(
        source,
        target,
        source_space="cbct_ras",
        target_space="phantom_reference",
        validation_source_points=validation_source,
        validation_target_points=validation_target,
    )

    assert result.valid is True
    assert result.method == "kabsch_svd_rigid_point_registration"
    assert result.fre_mm == pytest.approx(0.0, abs=1e-10)
    assert result.tre_mm == pytest.approx(0.0, abs=1e-10)
    assert result.registration_error_mm == result.tre_mm
    assert result.registration_error_source == "independent_target_points"
    assert np.asarray(result.rotation) == pytest.approx(rotation, abs=1e-10)
    assert np.asarray(result.translation) == pytest.approx(translation, abs=1e-10)
    assert np.linalg.det(np.asarray(result.rotation)) == pytest.approx(1.0, abs=1e-10)
    assert apply_rigid_transform(validation_source, result.matrix) == pytest.approx(validation_target, abs=1e-10)


def test_register_rigid_points_keeps_fre_when_independent_points_are_absent() -> None:
    source = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
    target = source + np.asarray([1.0, 2.0, 3.0])

    result = register_rigid_points(source, target, source_space="cbct", target_space="camera")

    assert result.fre_mm == pytest.approx(0.0, abs=1e-10)
    assert result.tre_mm is None
    assert result.registration_error_mm is None
    assert result.registration_error_source is None


def test_export_rigid_transform_writes_matrix_metadata_and_sha256(tmp_path: Path) -> None:
    source = np.asarray([[0, 0, 0], [2, 0, 0], [0, 3, 0], [0, 0, 4]], dtype=np.float64)
    target = source + np.asarray([5.0, -2.0, 9.0])
    result = register_rigid_points(
        source,
        target,
        source_space="cbct_ras",
        target_space="phantom_reference",
        validation_source_points=np.asarray([[1, 1, 1]], dtype=np.float64),
        validation_target_points=np.asarray([[6, -1, 10]], dtype=np.float64),
        source_frame_metadata=_frame("cbct_ras", "ras_x_right_y_anterior_z_superior"),
        target_frame_metadata=_frame(
            "phantom_reference",
            "phantom_x_right_y_anterior_z_superior",
        ),
        matrix_convention=MATRIX_CONVENTION,
    )

    artifact = export_rigid_transform(result, tmp_path / "cbct_to_phantom.json")
    output_path = Path(artifact["path"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert artifact["sha256"] == hashlib.sha256(output_path.read_bytes()).hexdigest()
    assert Path(artifact["sha256_path"]).read_text(encoding="utf-8").split()[0] == artifact["sha256"]
    assert payload["matrix"] == result.matrix
    assert payload["coordinate_transform"]["from_space"] == "cbct_ras"
    assert payload["coordinate_transform"]["to_space"] == "phantom_reference"
    assert payload["coordinate_transform"]["direction"] == "forward"
    assert payload["coordinate_transform"]["unit"] == "mm"
    assert payload["coordinate_transform"]["source_frame"] == result.source_frame
    assert payload["coordinate_transform"]["target_frame"] == result.target_frame
    assert payload["coordinate_transform"]["matrix_convention"] == MATRIX_CONVENTION
    assert payload["metrics"]["tre_mm"] == pytest.approx(0.0, abs=1e-10)


@pytest.mark.parametrize(
    ("source", "target", "code"),
    [
        ([[0, 0, 0], [1, 0, 0]], [[0, 0, 0], [1, 0, 0]], "insufficient_correspondences"),
        (
            [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            [[1, 1, 1], [2, 1, 1], [3, 1, 1]],
            "degenerate_registration_geometry",
        ),
        (
            [[0, 0, 0], [1, 0, 0], [0, 1, float("nan")]],
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "non_finite_points",
        ),
    ],
)
def test_register_rigid_points_rejects_unsafe_inputs(
    source: list[list[float]], target: list[list[float]], code: str
) -> None:
    with pytest.raises(RigidRegistrationError) as exc_info:
        register_rigid_points(source, target, source_space="source", target_space="target")
    assert exc_info.value.code == code


def test_register_rigid_points_rejects_validation_pair_mismatch() -> None:
    source = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    with pytest.raises(RigidRegistrationError) as exc_info:
        register_rigid_points(
            source,
            source,
            source_space="source",
            target_space="target",
            validation_source_points=[[0, 0, 0]],
        )
    assert exc_info.value.code == "validation_pair_incomplete"
