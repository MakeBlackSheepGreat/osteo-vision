from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from src.navigation.coordinate_contract import (
    MATRIX_CONVENTION,
    CoordinateContractError,
    unbound_frame_metadata,
    validate_frame_metadata,
    validate_matrix_convention,
)

METHOD_ID = "kabsch_svd_rigid_point_registration"
SCHEMA_VERSION = "osteo-vision-rigid-registration-v1"


class RigidRegistrationError(ValueError):
    """Structured failure raised when point registration evidence is unsafe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RigidRegistrationResult:
    matrix: list[list[float]]
    rotation: list[list[float]]
    translation: list[float]
    fre_mm: float
    tre_mm: float | None
    registration_count: int
    validation_count: int
    source_space: str
    target_space: str
    unit: str
    source_frame: dict[str, Any] = field(default_factory=dict)
    target_frame: dict[str, Any] = field(default_factory=dict)
    matrix_convention: dict[str, str] = field(default_factory=lambda: dict(MATRIX_CONVENTION))
    method: str = METHOD_ID
    valid: bool = True
    failure_reasons: tuple[str, ...] = ()

    @property
    def registration_error_mm(self) -> float | None:
        return self.tre_mm

    @property
    def registration_error_source(self) -> str | None:
        return "independent_target_points" if self.tre_mm is not None else None

    def to_manifest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SCHEMA_VERSION
        payload["registration_error_mm"] = self.registration_error_mm
        payload["registration_error_source"] = self.registration_error_source
        payload["coordinate_transform"] = {
            "from_space": self.source_space,
            "to_space": self.target_space,
            "direction": "forward",
            "unit": self.unit,
            "source_frame": self.source_frame,
            "target_frame": self.target_frame,
            "matrix_convention": self.matrix_convention,
        }
        payload["metrics"] = {
            "fre_mm": self.fre_mm,
            "tre_mm": self.tre_mm,
            "registration_count": self.registration_count,
            "validation_count": self.validation_count,
        }
        return payload


def register_rigid_points(
    source_points: ArrayLike,
    target_points: ArrayLike,
    *,
    source_space: str,
    target_space: str,
    unit: str = "mm",
    validation_source_points: ArrayLike | None = None,
    validation_target_points: ArrayLike | None = None,
    source_frame_metadata: dict[str, Any] | None = None,
    target_frame_metadata: dict[str, Any] | None = None,
    matrix_convention: dict[str, Any] | None = None,
) -> RigidRegistrationResult:
    """Estimate a proper 3D rigid transform using paired landmarks and Kabsch SVD."""
    normalized_source_space = _coordinate_space(source_space, field="source_space")
    normalized_target_space = _coordinate_space(target_space, field="target_space")
    normalized_unit = _unit(unit)
    normalized_source_frame = _frame_metadata(
        source_frame_metadata,
        name=normalized_source_space,
        unit=normalized_unit,
    )
    normalized_target_frame = _frame_metadata(
        target_frame_metadata,
        name=normalized_target_space,
        unit=normalized_unit,
    )
    normalized_matrix_convention = _matrix_convention(matrix_convention)
    source = _points(source_points, label="source")
    target = _points(target_points, label="target")
    _validate_registration_pairs(source, target)

    source_centroid = source.mean(axis=0)
    target_centroid = target.mean(axis=0)
    source_centered = source - source_centroid
    target_centered = target - target_centroid
    if np.linalg.matrix_rank(source_centered) < 2 or np.linalg.matrix_rank(target_centered) < 2:
        raise RigidRegistrationError(
            "degenerate_registration_geometry",
            "Registration landmarks must contain at least three non-collinear points in both spaces.",
        )

    covariance = source_centered.T @ target_centered
    left, _, right_transposed = np.linalg.svd(covariance)
    rotation = right_transposed.T @ left.T
    if np.linalg.det(rotation) < 0:
        right_transposed[-1, :] *= -1
        rotation = right_transposed.T @ left.T
    if not np.isfinite(rotation).all() or np.linalg.det(rotation) <= 0:
        raise RigidRegistrationError(
            "invalid_rotation_solution",
            "Rigid registration did not produce a finite proper rotation.",
        )

    translation = target_centroid - rotation @ source_centroid
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    transformed_registration = apply_rigid_transform(source, matrix)
    fre = _rmse(transformed_registration, target)

    validation_source, validation_target = _validation_pairs(
        validation_source_points,
        validation_target_points,
    )
    tre = None
    validation_count = 0
    if validation_source is not None and validation_target is not None:
        validation_count = int(validation_source.shape[0])
        transformed_validation = apply_rigid_transform(validation_source, matrix)
        tre = _rmse(transformed_validation, validation_target)

    return RigidRegistrationResult(
        matrix=_lists(matrix),
        rotation=_lists(rotation),
        translation=[float(value) for value in translation],
        fre_mm=fre,
        tre_mm=tre,
        registration_count=int(source.shape[0]),
        validation_count=validation_count,
        source_space=normalized_source_space,
        target_space=normalized_target_space,
        unit=normalized_unit,
        source_frame=normalized_source_frame,
        target_frame=normalized_target_frame,
        matrix_convention=normalized_matrix_convention,
    )


def apply_rigid_transform(points: ArrayLike, matrix: ArrayLike) -> NDArray[np.float64]:
    point_array = _points(points, label="points", minimum_count=1)
    matrix_array = np.asarray(matrix, dtype=np.float64)
    if matrix_array.shape != (4, 4):
        raise RigidRegistrationError("invalid_transform_shape", "Transform matrix must have shape 4x4.")
    if not np.isfinite(matrix_array).all():
        raise RigidRegistrationError("non_finite_transform", "Transform matrix contains non-finite values.")
    if not np.allclose(matrix_array[3], np.asarray([0.0, 0.0, 0.0, 1.0]), atol=1e-9):
        raise RigidRegistrationError(
            "invalid_homogeneous_transform",
            "Transform matrix must use a [0, 0, 0, 1] homogeneous final row.",
        )
    homogeneous = np.concatenate([point_array, np.ones((point_array.shape[0], 1), dtype=np.float64)], axis=1)
    transformed = (matrix_array @ homogeneous.T).T
    return transformed[:, :3]


def export_rigid_transform(result: RigidRegistrationResult, output_path: str | Path) -> dict[str, Any]:
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise RigidRegistrationError(
            "unsupported_transform_export_format",
            "Rigid transforms must be exported as JSON for evidence validation.",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_manifest()
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary_path = path.with_suffix(path.suffix + ".part")
    temporary_path.write_bytes(encoded)
    temporary_path.replace(path)
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
        "source_space": result.source_space,
        "target_space": result.target_space,
        "direction": "forward",
        "unit": result.unit,
        "source_frame": result.source_frame,
        "target_frame": result.target_frame,
        "matrix_convention": result.matrix_convention,
        "registration_error_mm": result.registration_error_mm,
        "registration_error_source": result.registration_error_source,
    }


def _points(points: ArrayLike, *, label: str, minimum_count: int = 3) -> NDArray[np.float64]:
    try:
        array = np.asarray(points, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise RigidRegistrationError("invalid_point_shape", f"{label} points must be numeric Nx3 values.") from exc
    if array.ndim != 2 or array.shape[1] != 3:
        raise RigidRegistrationError("invalid_point_shape", f"{label} points must have shape Nx3.")
    if array.shape[0] < minimum_count:
        raise RigidRegistrationError(
            "insufficient_correspondences",
            f"{label} requires at least {minimum_count} point correspondences.",
        )
    if not np.isfinite(array).all():
        raise RigidRegistrationError("non_finite_points", f"{label} points contain non-finite values.")
    return array


def _validate_registration_pairs(source: NDArray[np.float64], target: NDArray[np.float64]) -> None:
    if source.shape != target.shape:
        raise RigidRegistrationError(
            "registration_pair_count_mismatch",
            "Source and target registration point arrays must have the same shape.",
        )


def _validation_pairs(
    source_points: ArrayLike | None,
    target_points: ArrayLike | None,
) -> tuple[NDArray[np.float64] | None, NDArray[np.float64] | None]:
    if (source_points is None) != (target_points is None):
        raise RigidRegistrationError(
            "validation_pair_incomplete",
            "Independent TRE requires both source and target validation points.",
        )
    if source_points is None or target_points is None:
        return None, None
    source = _points(source_points, label="validation_source", minimum_count=1)
    target = _points(target_points, label="validation_target", minimum_count=1)
    if source.shape != target.shape:
        raise RigidRegistrationError(
            "validation_pair_count_mismatch",
            "Source and target validation point arrays must have the same shape.",
        )
    return source, target


def _rmse(predicted: NDArray[np.float64], expected: NDArray[np.float64]) -> float:
    residual = np.linalg.norm(predicted - expected, axis=1)
    value = float(np.sqrt(np.mean(np.square(residual))))
    if not np.isfinite(value):
        raise RigidRegistrationError("non_finite_registration_error", "Registration error is non-finite.")
    return value


def _coordinate_space(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise RigidRegistrationError("coordinate_space_missing", f"{field} is required.")
    return normalized


def _frame_metadata(value: dict[str, Any] | None, *, name: str, unit: str) -> dict[str, Any]:
    if value is None:
        return unbound_frame_metadata(name, unit)
    try:
        return validate_frame_metadata(value, expected_name=name, expected_unit=unit)
    except CoordinateContractError as exc:
        raise RigidRegistrationError(exc.code, str(exc)) from exc


def _matrix_convention(value: dict[str, Any] | None) -> dict[str, str]:
    if value is None:
        return dict(MATRIX_CONVENTION)
    try:
        return validate_matrix_convention(value)
    except CoordinateContractError as exc:
        raise RigidRegistrationError(exc.code, str(exc)) from exc


def _unit(value: str) -> str:
    normalized = str(value).strip().lower()
    aliases = {"millimeter": "mm", "millimeters": "mm", "millimetre": "mm", "millimetres": "mm"}
    normalized = aliases.get(normalized, normalized)
    if normalized != "mm":
        raise RigidRegistrationError(
            "unsupported_coordinate_unit",
            "L1 rigid registration currently requires physical coordinates in millimetres.",
        )
    return normalized


def _lists(value: NDArray[np.float64]) -> list[list[float]]:
    return [[float(item) for item in row] for row in value]
