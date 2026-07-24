from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import ArrayLike, NDArray

from osteo_vision_core.navigation.coordinate_contract import (
    MATRIX_CONVENTION,
    CoordinateContractError,
    unbound_frame_metadata,
    validate_frame_metadata,
    validate_matrix_convention,
)

METHOD_ID = "opencv_solvepnp_iterative"
SCHEMA_VERSION = "osteo-vision-camera-pnp-registration-v1"


class CameraRegistrationError(ValueError):
    """Structured failure raised when calibrated camera registration is unsafe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CameraRegistrationResult:
    matrix: list[list[float]]
    rotation_vector: list[float]
    translation: list[float]
    reprojection_rmse_px: float
    validation_reprojection_rmse_px: float | None
    correspondence_count: int
    validation_count: int
    positive_depth_count: int
    object_space: str
    camera_space: str
    intrinsics_id: str
    image_size_px: tuple[int, int]
    camera_matrix: list[list[float]]
    distortion_coefficients: list[float]
    magnification: float
    working_distance_mm: float
    object_frame: dict[str, Any] = field(default_factory=dict)
    camera_frame: dict[str, Any] = field(default_factory=dict)
    matrix_convention: dict[str, str] = field(default_factory=lambda: dict(MATRIX_CONVENTION))
    method: str = METHOD_ID

    def to_manifest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SCHEMA_VERSION
        payload["coordinate_transform"] = {
            "from_space": self.object_space,
            "to_space": self.camera_space,
            "direction": "forward",
            "unit": "mm",
            "source_frame": self.object_frame,
            "target_frame": self.camera_frame,
            "matrix_convention": self.matrix_convention,
        }
        payload["metrics"] = {
            "reprojection_rmse_px": self.reprojection_rmse_px,
            "validation_reprojection_rmse_px": self.validation_reprojection_rmse_px,
            "correspondence_count": self.correspondence_count,
            "validation_count": self.validation_count,
            "positive_depth_count": self.positive_depth_count,
        }
        return payload


def register_camera_pnp(
    object_points: ArrayLike,
    image_points: ArrayLike,
    *,
    camera_matrix: ArrayLike,
    distortion_coefficients: ArrayLike | None,
    image_size_px: tuple[int, int] | list[int],
    object_space: str,
    camera_space: str = "camera_optical",
    intrinsics_id: str,
    magnification: float,
    working_distance_mm: float,
    validation_object_points: ArrayLike | None = None,
    validation_image_points: ArrayLike | None = None,
    object_frame_metadata: dict[str, Any] | None = None,
    camera_frame_metadata: dict[str, Any] | None = None,
    matrix_convention: dict[str, Any] | None = None,
) -> CameraRegistrationResult:
    """Estimate a metric object-to-camera pose and independent pixel error."""
    objects = _points_3d(object_points, label="camera_object")
    images = _points_2d(image_points, label="camera_image")
    _same_count(objects, images, code="camera_correspondence_count_mismatch")
    if np.linalg.matrix_rank(objects - objects.mean(axis=0)) < 2:
        raise CameraRegistrationError(
            "degenerate_camera_geometry",
            "PnP object landmarks must contain at least four non-collinear points.",
        )

    size = _image_size(image_size_px)
    intrinsics = _camera_matrix(camera_matrix, image_size_px=size)
    distortion = _distortion(distortion_coefficients)
    _inside_image(images, size, label="camera_image")
    normalized_object_space = _required_text(object_space, field="object_space")
    normalized_camera_space = _required_text(camera_space, field="camera_space")
    normalized_object_frame = _frame_metadata(object_frame_metadata, name=normalized_object_space)
    normalized_camera_frame = _frame_metadata(camera_frame_metadata, name=normalized_camera_space)
    normalized_matrix_convention = _matrix_convention(matrix_convention)
    normalized_intrinsics_id = _required_text(intrinsics_id, field="intrinsics_id")
    normalized_magnification = _positive_number(magnification, code="magnification_invalid", label="magnification")
    normalized_working_distance = _positive_number(
        working_distance_mm,
        code="working_distance_invalid",
        label="working_distance_mm",
    )

    success, rotation_vector, translation = cv2.solvePnP(
        objects,
        images,
        intrinsics,
        distortion,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        raise CameraRegistrationError("camera_pose_solution_failed", "OpenCV solvePnP did not return a pose.")
    rotation_vector = np.asarray(rotation_vector, dtype=np.float64).reshape(3, 1)
    translation = np.asarray(translation, dtype=np.float64).reshape(3, 1)
    if not np.isfinite(rotation_vector).all() or not np.isfinite(translation).all():
        raise CameraRegistrationError("camera_pose_non_finite", "PnP returned a non-finite camera pose.")
    rotation, _ = cv2.Rodrigues(rotation_vector)
    transformed = (rotation @ objects.T + translation).T
    positive_depth_count = int(np.count_nonzero(transformed[:, 2] > 0))
    if positive_depth_count != int(objects.shape[0]):
        raise CameraRegistrationError(
            "camera_points_behind_camera",
            "Every PnP correspondence must project in front of the camera.",
        )
    reprojection_rmse = _reprojection_rmse(
        objects,
        images,
        rotation_vector,
        translation,
        intrinsics,
        distortion,
    )

    validation_objects, validation_images = _validation_pairs(
        validation_object_points,
        validation_image_points,
        image_size_px=size,
    )
    validation_rmse = None
    validation_count = 0
    if validation_objects is not None and validation_images is not None:
        validation_count = int(validation_objects.shape[0])
        validation_transformed = (rotation @ validation_objects.T + translation).T
        if np.any(validation_transformed[:, 2] <= 0):
            raise CameraRegistrationError(
                "validation_points_behind_camera",
                "Every independent PnP validation point must project in front of the camera.",
            )
        validation_rmse = _reprojection_rmse(
            validation_objects,
            validation_images,
            rotation_vector,
            translation,
            intrinsics,
            distortion,
        )

    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation[:, 0]
    return CameraRegistrationResult(
        matrix=_matrix_list(matrix),
        rotation_vector=[float(value) for value in rotation_vector[:, 0]],
        translation=[float(value) for value in translation[:, 0]],
        reprojection_rmse_px=reprojection_rmse,
        validation_reprojection_rmse_px=validation_rmse,
        correspondence_count=int(objects.shape[0]),
        validation_count=validation_count,
        positive_depth_count=positive_depth_count,
        object_space=normalized_object_space,
        camera_space=normalized_camera_space,
        intrinsics_id=normalized_intrinsics_id,
        image_size_px=size,
        camera_matrix=_matrix_list(intrinsics),
        distortion_coefficients=[float(value) for value in distortion.reshape(-1)],
        magnification=normalized_magnification,
        working_distance_mm=normalized_working_distance,
        object_frame=normalized_object_frame,
        camera_frame=normalized_camera_frame,
        matrix_convention=normalized_matrix_convention,
    )


def compose_transforms(
    target_from_intermediate: ArrayLike,
    intermediate_from_source: ArrayLike,
) -> list[list[float]]:
    first = _transform(target_from_intermediate, label="target_from_intermediate")
    second = _transform(intermediate_from_source, label="intermediate_from_source")
    composed = first @ second
    if not np.isfinite(composed).all():
        raise CameraRegistrationError("composed_transform_non_finite", "Composed camera transform is non-finite.")
    return _matrix_list(composed)


def export_camera_transform(
    result: CameraRegistrationResult,
    output_path: str | Path,
    *,
    composed_matrix: ArrayLike | None = None,
    composed_source_space: str | None = None,
    composed_source_frame_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise CameraRegistrationError(
            "unsupported_camera_transform_format",
            "Camera transforms must be exported as JSON.",
        )
    payload = result.to_manifest()
    if composed_matrix is not None:
        composed_source = _required_text(composed_source_space, field="composed_source_space")
        composed_source_frame = _frame_metadata(composed_source_frame_metadata, name=composed_source)
        payload["pnp_object_to_camera_matrix"] = payload["matrix"]
        payload["matrix"] = _matrix_list(_transform(composed_matrix, label="composed_matrix"))
        payload["coordinate_transform"] = {
            "from_space": composed_source,
            "to_space": result.camera_space,
            "direction": "forward",
            "unit": "mm",
            "source_frame": composed_source_frame,
            "target_frame": result.camera_frame,
            "matrix_convention": result.matrix_convention,
        }
        payload["composed_transform"] = {
            "matrix": payload["matrix"],
            "from_space": composed_source,
            "to_space": result.camera_space,
            "direction": "forward",
            "unit": "mm",
            "source_frame": composed_source_frame,
            "target_frame": result.camera_frame,
            "matrix_convention": result.matrix_convention,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(encoded)
    temporary.replace(path)
    checksum = hashlib.sha256(encoded).hexdigest()
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
    return {
        "path": str(path),
        "format": "json",
        "size_bytes": len(encoded),
        "sha256": checksum,
        "sha256_path": str(checksum_path),
        "matrix_shape": [4, 4],
        "source_space": composed_source_space or result.object_space,
        "target_space": result.camera_space,
        "direction": "forward",
        "unit": "mm",
        "source_frame": (
            payload["coordinate_transform"].get("source_frame")
            if isinstance(payload.get("coordinate_transform"), dict)
            else None
        ),
        "target_frame": result.camera_frame,
        "matrix_convention": result.matrix_convention,
    }


def _points_3d(values: ArrayLike, *, label: str) -> NDArray[np.float64]:
    array = _numeric_array(values, label=label)
    if array.ndim != 2 or array.shape[1] != 3 or array.shape[0] < 4:
        raise CameraRegistrationError(
            "invalid_camera_object_points",
            f"{label} points must contain at least four numeric Nx3 values.",
        )
    return array


def _points_2d(values: ArrayLike, *, label: str, minimum_count: int = 4) -> NDArray[np.float64]:
    array = _numeric_array(values, label=label)
    if array.ndim != 2 or array.shape[1] != 2 or array.shape[0] < minimum_count:
        raise CameraRegistrationError(
            "invalid_camera_image_points",
            f"{label} points must contain at least {minimum_count} numeric Nx2 values.",
        )
    return array


def _numeric_array(values: ArrayLike, *, label: str) -> NDArray[np.float64]:
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise CameraRegistrationError("camera_points_non_numeric", f"{label} points must be numeric.") from exc
    if not np.isfinite(array).all():
        raise CameraRegistrationError("camera_points_non_finite", f"{label} points contain non-finite values.")
    return array


def _same_count(first: NDArray[np.float64], second: NDArray[np.float64], *, code: str) -> None:
    if first.shape[0] != second.shape[0]:
        raise CameraRegistrationError(code, "PnP 3D and 2D point counts must match.")


def _image_size(value: tuple[int, int] | list[int]) -> tuple[int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise CameraRegistrationError("image_size_invalid", "image_size_px must contain width and height.")
    try:
        width, height = (int(value[0]), int(value[1]))
    except (TypeError, ValueError) as exc:
        raise CameraRegistrationError("image_size_invalid", "image_size_px must contain integer dimensions.") from exc
    if width <= 0 or height <= 0:
        raise CameraRegistrationError("image_size_invalid", "image_size_px dimensions must be positive.")
    return width, height


def _camera_matrix(values: ArrayLike, *, image_size_px: tuple[int, int]) -> NDArray[np.float64]:
    matrix = _numeric_array(values, label="camera_matrix")
    if matrix.shape != (3, 3):
        raise CameraRegistrationError("camera_matrix_shape_invalid", "camera_matrix must have shape 3x3.")
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or not np.allclose(matrix[2], [0.0, 0.0, 1.0], atol=1e-9):
        raise CameraRegistrationError("camera_matrix_invalid", "Camera focal lengths and homogeneous row are invalid.")
    width, height = image_size_px
    if not 0 <= matrix[0, 2] < width or not 0 <= matrix[1, 2] < height:
        raise CameraRegistrationError(
            "camera_principal_point_out_of_bounds",
            "Camera principal point must fall inside the declared image dimensions.",
        )
    return matrix


def _distortion(values: ArrayLike | None) -> NDArray[np.float64]:
    if values is None:
        return np.zeros((5, 1), dtype=np.float64)
    array = _numeric_array(values, label="distortion_coefficients").reshape(-1, 1)
    if array.size not in {4, 5, 8, 12, 14}:
        raise CameraRegistrationError(
            "distortion_coefficients_invalid",
            "OpenCV distortion coefficients must contain 4, 5, 8, 12, or 14 values.",
        )
    return array


def _inside_image(points: NDArray[np.float64], size: tuple[int, int], *, label: str) -> None:
    width, height = size
    if np.any(points[:, 0] < 0) or np.any(points[:, 0] >= width):
        raise CameraRegistrationError("camera_image_point_out_of_bounds", f"{label} x coordinates exceed image bounds.")
    if np.any(points[:, 1] < 0) or np.any(points[:, 1] >= height):
        raise CameraRegistrationError("camera_image_point_out_of_bounds", f"{label} y coordinates exceed image bounds.")


def _validation_pairs(
    object_points: ArrayLike | None,
    image_points: ArrayLike | None,
    *,
    image_size_px: tuple[int, int],
) -> tuple[NDArray[np.float64] | None, NDArray[np.float64] | None]:
    if (object_points is None) != (image_points is None):
        raise CameraRegistrationError(
            "camera_validation_pair_incomplete",
            "Independent reprojection validation requires both 3D and 2D points.",
        )
    if object_points is None or image_points is None:
        return None, None
    objects = _numeric_array(object_points, label="validation_camera_object")
    images = _points_2d(image_points, label="validation_camera_image", minimum_count=1)
    if objects.ndim != 2 or objects.shape[1] != 3 or objects.shape[0] < 1:
        raise CameraRegistrationError(
            "invalid_camera_validation_object_points",
            "Independent camera object points must contain numeric Nx3 values.",
        )
    _same_count(objects, images, code="camera_validation_count_mismatch")
    _inside_image(images, image_size_px, label="validation_camera_image")
    return objects, images


def _reprojection_rmse(
    objects: NDArray[np.float64],
    expected: NDArray[np.float64],
    rotation_vector: NDArray[np.float64],
    translation: NDArray[np.float64],
    camera_matrix: NDArray[np.float64],
    distortion: NDArray[np.float64],
) -> float:
    projected, _ = cv2.projectPoints(objects, rotation_vector, translation, camera_matrix, distortion)
    residual = np.linalg.norm(projected.reshape(-1, 2) - expected, axis=1)
    value = float(np.sqrt(np.mean(np.square(residual))))
    if not np.isfinite(value):
        raise CameraRegistrationError("reprojection_error_non_finite", "Reprojection error is non-finite.")
    return value


def _transform(values: ArrayLike, *, label: str) -> NDArray[np.float64]:
    matrix = _numeric_array(values, label=label)
    if matrix.shape != (4, 4) or not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
        raise CameraRegistrationError("camera_transform_invalid", f"{label} must be a finite 4x4 homogeneous matrix.")
    if abs(float(np.linalg.det(matrix[:3, :3]))) < 1e-12:
        raise CameraRegistrationError("camera_transform_singular", f"{label} rotation block is singular.")
    return matrix


def _required_text(value: object, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise CameraRegistrationError("camera_metadata_missing", f"{field} is required for calibrated PnP.")
    return normalized


def _frame_metadata(value: dict[str, Any] | None, *, name: str) -> dict[str, Any]:
    if value is None:
        return unbound_frame_metadata(name)
    try:
        return validate_frame_metadata(value, expected_name=name)
    except CoordinateContractError as exc:
        raise CameraRegistrationError(exc.code, str(exc)) from exc


def _matrix_convention(value: dict[str, Any] | None) -> dict[str, str]:
    if value is None:
        return dict(MATRIX_CONVENTION)
    try:
        return validate_matrix_convention(value)
    except CoordinateContractError as exc:
        raise CameraRegistrationError(exc.code, str(exc)) from exc


def _positive_number(value: object, *, code: str, label: str) -> float:
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise CameraRegistrationError(code, f"{label} must be numeric.") from exc
    if not np.isfinite(number) or number <= 0:
        raise CameraRegistrationError(code, f"{label} must be finite and positive.")
    return number


def _matrix_list(value: NDArray[np.float64]) -> list[list[float]]:
    return [[float(item) for item in row] for row in value]
