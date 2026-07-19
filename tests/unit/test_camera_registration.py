from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.navigation.camera_registration import (
    CameraRegistrationError,
    compose_transforms,
    export_camera_transform,
    register_camera_pnp,
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


def _fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    objects = np.asarray(
        [
            [-30, -20, 0],
            [30, -20, 0],
            [30, 20, 0],
            [-30, 20, 0],
            [-20, -10, 25],
            [20, 10, 30],
            [0, -25, 15],
            [0, 25, 20],
        ],
        dtype=np.float64,
    )
    camera = np.asarray(
        [[920.0, 0.0, 640.0], [0.0, 910.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    rotation = np.asarray([0.08, -0.04, 0.03], dtype=np.float64)
    translation = np.asarray([5.0, -4.0, 520.0], dtype=np.float64)
    projected, _ = cv2.projectPoints(objects, rotation, translation, camera, np.zeros(5))
    return objects, projected.reshape(-1, 2), camera, rotation, translation


def test_register_camera_pnp_recovers_pose_and_independent_reprojection() -> None:
    objects, pixels, camera, _, _ = _fixture()
    result = register_camera_pnp(
        objects[:6],
        pixels[:6],
        camera_matrix=camera,
        distortion_coefficients=[0, 0, 0, 0, 0],
        image_size_px=(1280, 720),
        object_space="phantom_reference_mm",
        intrinsics_id="scope_4x_250mm",
        magnification=4.0,
        working_distance_mm=250.0,
        object_frame_metadata=_frame(
            "phantom_reference_mm",
            "phantom_x_right_y_anterior_z_superior",
        ),
        camera_frame_metadata=_frame(
            "camera_optical",
            "opencv_camera_x_right_y_down_z_forward",
        ),
        matrix_convention=MATRIX_CONVENTION,
        validation_object_points=objects[6:],
        validation_image_points=pixels[6:],
    )

    assert result.reprojection_rmse_px == pytest.approx(0.0, abs=1e-5)
    assert result.validation_reprojection_rmse_px == pytest.approx(0.0, abs=1e-5)
    assert result.positive_depth_count == 6
    assert result.intrinsics_id == "scope_4x_250mm"
    assert np.asarray(result.matrix).shape == (4, 4)


def test_camera_transform_composition_and_export_are_traceable(tmp_path: Path) -> None:
    objects, pixels, camera, _, _ = _fixture()
    result = register_camera_pnp(
        objects[:6],
        pixels[:6],
        camera_matrix=camera,
        distortion_coefficients=None,
        image_size_px=(1280, 720),
        object_space="phantom_reference_mm",
        intrinsics_id="scope_4x_250mm",
        magnification=4.0,
        working_distance_mm=250.0,
        object_frame_metadata=_frame(
            "phantom_reference_mm",
            "phantom_x_right_y_anterior_z_superior",
        ),
        camera_frame_metadata=_frame(
            "camera_optical",
            "opencv_camera_x_right_y_down_z_forward",
        ),
        matrix_convention=MATRIX_CONVENTION,
    )
    reference_from_cbct = np.eye(4)
    reference_from_cbct[:3, 3] = [2.0, -1.0, 3.0]
    composed = compose_transforms(result.matrix, reference_from_cbct)
    artifact = export_camera_transform(
        result,
        tmp_path / "camera_transform.json",
        composed_matrix=composed,
        composed_source_space="cbct_lps_mm",
        composed_source_frame_metadata=_frame(
            "cbct_lps_mm",
            "dicom_lps_x_left_y_posterior_z_superior",
        ),
    )
    path = Path(artifact["path"])
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert payload["composed_transform"]["from_space"] == "cbct_lps_mm"
    assert payload["composed_transform"]["to_space"] == "camera_optical"
    assert payload["composed_transform"]["source_frame"]["name"] == "cbct_lps_mm"
    assert payload["composed_transform"]["target_frame"] == result.camera_frame
    assert payload["composed_transform"]["matrix_convention"] == MATRIX_CONVENTION


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("out_of_bounds", "camera_image_point_out_of_bounds"),
        ("bad_intrinsics", "camera_matrix_invalid"),
        ("incomplete_validation", "camera_validation_pair_incomplete"),
    ],
)
def test_register_camera_pnp_rejects_unsafe_evidence(mutation: str, code: str) -> None:
    objects, pixels, camera, _, _ = _fixture()
    kwargs: dict[str, object] = {}
    if mutation == "out_of_bounds":
        pixels = pixels.copy()
        pixels[0, 0] = 1400
    elif mutation == "bad_intrinsics":
        camera = camera.copy()
        camera[0, 0] = 0
    else:
        kwargs["validation_object_points"] = objects[6:]

    with pytest.raises(CameraRegistrationError) as exc_info:
        register_camera_pnp(
            objects[:6],
            pixels[:6],
            camera_matrix=camera,
            distortion_coefficients=None,
            image_size_px=(1280, 720),
            object_space="phantom_reference_mm",
            intrinsics_id="scope_4x_250mm",
            magnification=4.0,
            working_distance_mm=250.0,
            **kwargs,
        )
    assert exc_info.value.code == code
