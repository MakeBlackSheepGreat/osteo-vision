from __future__ import annotations

from typing import Any, Mapping

SUPPORTED_HANDEDNESS = {"right_handed", "left_handed"}
SUPPORTED_UNIT = "mm"
MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}
KNOWN_AXIS_CONVENTIONS = {
    "dicom_lps_x_left_y_posterior_z_superior": (["left", "posterior", "superior"], "right_handed"),
    "ras_x_right_y_anterior_z_superior": (["right", "anterior", "superior"], "right_handed"),
    "phantom_x_right_y_anterior_z_superior": (["right", "anterior", "superior"], "right_handed"),
    "opencv_camera_x_right_y_down_z_forward": (["right", "down", "forward"], "right_handed"),
}


class CoordinateContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_frame_metadata(
    value: object,
    *,
    expected_name: str | None = None,
    expected_unit: str = SUPPORTED_UNIT,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CoordinateContractError("frame_metadata_missing", "Coordinate frame metadata must be an object.")
    name = str(value.get("name") or "").strip()
    handedness = str(value.get("handedness") or "").strip().lower()
    unit = str(value.get("unit") or "").strip().lower()
    source = str(value.get("source") or "").strip()
    axis_convention = str(value.get("axis_convention") or "").strip()
    axis_value = value.get("axis_directions")
    axis_directions: list[str] | None = None
    if axis_value is not None:
        if not isinstance(axis_value, (list, tuple)) or len(axis_value) != 3:
            raise CoordinateContractError(
                "frame_axis_directions_invalid",
                "axis_directions must contain exactly three axis direction labels.",
            )
        axis_directions = [str(item or "").strip() for item in axis_value]
        if any(not item for item in axis_directions) or len(set(axis_directions)) != 3:
            raise CoordinateContractError(
                "frame_axis_directions_invalid",
                "axis_directions labels must be present and unique.",
            )
    if not name or (expected_name is not None and name != expected_name):
        raise CoordinateContractError("frame_name_mismatch", "Coordinate frame name is missing or inconsistent.")
    if handedness not in SUPPORTED_HANDEDNESS:
        raise CoordinateContractError(
            "frame_handedness_invalid",
            "Coordinate frame handedness must be right_handed or left_handed.",
        )
    if unit != expected_unit:
        raise CoordinateContractError("frame_unit_invalid", f"Coordinate frame unit must be {expected_unit}.")
    if not source:
        raise CoordinateContractError("frame_source_missing", "Coordinate frame source must be recorded.")
    if not axis_convention and axis_directions is None:
        raise CoordinateContractError(
            "frame_axis_metadata_missing",
            "Coordinate frame requires axis_convention or axis_directions.",
        )
    known_axis = KNOWN_AXIS_CONVENTIONS.get(axis_convention)
    if known_axis is not None:
        expected_directions, expected_handedness = known_axis
        if handedness != expected_handedness:
            raise CoordinateContractError(
                "frame_axis_handedness_conflict",
                "Coordinate frame handedness conflicts with its axis convention.",
            )
        if axis_directions is not None and axis_directions != expected_directions:
            raise CoordinateContractError(
                "frame_axis_metadata_conflict",
                "axis_directions conflicts with axis_convention.",
            )
    return {
        "name": name,
        "handedness": handedness,
        "axis_directions": axis_directions,
        "axis_convention": axis_convention or None,
        "unit": unit,
        "source": source,
    }


def validate_matrix_convention(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise CoordinateContractError(
            "matrix_convention_missing",
            "Transform matrix convention must be recorded.",
        )
    normalized = {field: str(value.get(field) or "").strip() for field in MATRIX_CONVENTION}
    if normalized != MATRIX_CONVENTION:
        raise CoordinateContractError(
            "matrix_convention_invalid",
            "Transform must use row-major storage with left-multiplied homogeneous column vectors.",
        )
    return normalized


def validate_coordinate_transform(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CoordinateContractError(
            "coordinate_transform_missing",
            "coordinate_transform must be an object.",
        )
    from_space = str(value.get("from_space") or value.get("source_frame_name") or "").strip()
    to_space = str(value.get("to_space") or value.get("target_frame_name") or "").strip()
    direction = str(value.get("direction") or "").strip().lower()
    unit = str(value.get("unit") or "").strip().lower()
    if not from_space or not to_space or from_space == to_space:
        raise CoordinateContractError(
            "coordinate_space_invalid",
            "Transform source and target frame names must be present and distinct.",
        )
    if direction != "forward":
        raise CoordinateContractError("coordinate_direction_invalid", "Transform direction must be forward.")
    if unit != SUPPORTED_UNIT:
        raise CoordinateContractError("coordinate_unit_invalid", "Transform unit must be mm.")
    source_frame = validate_frame_metadata(value.get("source_frame"), expected_name=from_space)
    target_frame = validate_frame_metadata(value.get("target_frame"), expected_name=to_space)
    matrix_convention = validate_matrix_convention(value.get("matrix_convention"))
    return {
        "from_space": from_space,
        "to_space": to_space,
        "direction": direction,
        "unit": unit,
        "source_frame": source_frame,
        "target_frame": target_frame,
        "matrix_convention": matrix_convention,
    }


def unbound_frame_metadata(name: str, unit: str = SUPPORTED_UNIT) -> dict[str, Any]:
    return {
        "name": str(name).strip(),
        "handedness": "unspecified",
        "axis_directions": None,
        "axis_convention": "unspecified",
        "unit": str(unit).strip().lower(),
        "source": "legacy_unbound_call",
    }
