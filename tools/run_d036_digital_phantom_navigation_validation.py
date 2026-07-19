from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import shutil
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence, TypeAlias
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MODEL = (
    ROOT
    / "artifacts/platform/three_d_models/ToothFairy2F_036_0000"
    / "ToothFairy2F_036_d036_public_lower_jaw_label_surface.stl"
)
DEFAULT_OUTPUT = ROOT / "artifacts/navigation/d036_digital_phantom_navigation_validation_20260719"
EXPECTED_MODEL_SHA256 = "dfa8b5b5c2c1c9fa961e93757238421ec13ea23299423117ece67a58fb114be9"
FRAME_COUNT = 6
FPS = 8.0
IMAGE_SIZE = (1280, 720)
REVIEW_TOKEN = "d036-synthetic-physician-fixture-token-001"
REVIEW_ACTOR = {
    "actor_id": "d036-synthetic-physician-fixture-001",
    "role": "physician",
    "institution": "Osteo Vision Engineering Test Fixture",
    "auth_source": "verified_identity_token",
}
HEADERS = {"Authorization": f"Bearer {REVIEW_TOKEN}"}
MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}
L2_THRESHOLDS: dict[str, float | int] = {
    "max_time_offset_ms": 50.0,
    "drift_threshold_mm": 1.0,
    "tre_proxy_threshold_mm": 2.0,
    "dynamic_target_error_threshold_mm": 2.0,
    "minimum_visible_projection_points": 4,
    "max_magnification_rate_per_s": 25.0,
    "max_working_distance_rate_mm_per_s": 600.0,
    "max_intrinsics_switch_rate_hz": 10.0,
    "calibration_ambiguity_margin": 0.05,
}

FloatArray: TypeAlias = NDArray[np.float64]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_hashed_json(path: Path, value: Any) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_bytes(value)
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return {
        "path": str(path.resolve()),
        "size_bytes": len(payload),
        "sha256": digest,
    }


def _frame(name: str, *, axis_convention: str, source: str) -> dict[str, Any]:
    return {
        "name": name,
        "handedness": "right_handed",
        "axis_convention": axis_convention,
        "unit": "mm",
        "source": source,
    }


def load_binary_stl_candidate_vertices(
    path: Path,
    *,
    max_candidates: int = 50_000,
) -> tuple[FloatArray, dict[str, Any]]:
    """Read a bounded, deterministic vertex sample while retaining axis extrema."""
    if max_candidates < 100:
        raise ValueError("max_candidates_too_small")
    with path.open("rb") as handle:
        header = handle.read(84)
    if len(header) != 84:
        raise ValueError("stl_header_incomplete")
    triangle_count = struct.unpack_from("<I", header, 80)[0]
    expected_size = 84 + triangle_count * 50
    actual_size = path.stat().st_size
    if triangle_count <= 0 or actual_size != expected_size:
        raise ValueError("binary_stl_size_mismatch")

    facet_dtype = np.dtype(
        [
            ("normal", "<f4", (3,)),
            ("vertices", "<f4", (3, 3)),
            ("attribute", "<u2"),
        ]
    )
    facets: Any = np.memmap(path, dtype=facet_dtype, mode="r", offset=84, shape=(triangle_count,))
    vertices = facets["vertices"].reshape(-1, 3)
    stride = max(1, math.ceil(vertices.shape[0] / max_candidates))
    sampled = np.asarray(vertices[::stride], dtype=np.float64)
    extreme_indices: list[int] = []
    for axis in range(3):
        extreme_indices.extend(
            [
                int(np.argmin(vertices[:, axis])),
                int(np.argmax(vertices[:, axis])),
            ]
        )
    extrema = np.asarray(vertices[extreme_indices], dtype=np.float64)
    candidates = np.unique(np.concatenate([sampled, extrema], axis=0), axis=0)
    if candidates.shape[0] < 12 or not np.isfinite(candidates).all():
        raise ValueError("stl_candidate_vertices_invalid")
    header_text = header[:80].rstrip(b"\x00").decode("ascii", errors="replace")
    metadata = {
        "encoding": "binary",
        "header_text": header_text,
        "triangle_count": triangle_count,
        "raw_vertex_count": int(vertices.shape[0]),
        "candidate_vertex_count": int(candidates.shape[0]),
        "sampling_stride": stride,
        "bounds_min_xyz_mm": candidates.min(axis=0).tolist(),
        "bounds_max_xyz_mm": candidates.max(axis=0).tolist(),
        "header_identity_warning": "D036" not in header_text,
    }
    del facets
    return candidates, metadata


def select_spatially_distributed_points(points: FloatArray, count: int) -> FloatArray:
    """Select deterministic farthest points in normalized model coordinates."""
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3 or values.shape[0] < count:
        raise ValueError("point_selection_shape_invalid")
    unique = np.unique(values, axis=0)
    if unique.shape[0] < count or not np.isfinite(unique).all():
        raise ValueError("point_selection_values_invalid")
    minimum = unique.min(axis=0)
    extent = np.ptp(unique, axis=0)
    if np.count_nonzero(extent > 1e-9) < 3:
        raise ValueError("point_selection_geometry_degenerate")
    normalized = (unique - minimum) / extent
    center = normalized.mean(axis=0)
    selected = [int(np.argmax(np.sum((normalized - center) ** 2, axis=1)))]
    minimum_distance = np.sum((normalized - normalized[selected[0]]) ** 2, axis=1)
    while len(selected) < count:
        next_index = int(np.argmax(minimum_distance))
        if next_index in selected or minimum_distance[next_index] <= 1e-12:
            raise ValueError("point_selection_exhausted")
        selected.append(next_index)
        distance = np.sum((normalized - normalized[next_index]) ** 2, axis=1)
        minimum_distance = np.minimum(minimum_distance, distance)
    result = unique[np.asarray(selected, dtype=np.int64)]
    if np.linalg.matrix_rank(result - result.mean(axis=0)) < 3:
        raise ValueError("point_selection_rank_invalid")
    return result


def rigid_matrix(rvec: Sequence[float], translation: Sequence[float]) -> FloatArray:
    rotation, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64))
    matrix: FloatArray = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = np.asarray(translation, dtype=np.float64)
    return matrix


def transform_points(points: FloatArray, matrix: FloatArray) -> FloatArray:
    homogeneous = np.concatenate([np.asarray(points, dtype=np.float64), np.ones((len(points), 1))], axis=1)
    transformed = (np.asarray(matrix, dtype=np.float64) @ homogeneous.T).T
    return transformed[:, :3] / transformed[:, 3:4]


def build_geometry(model_path: Path) -> dict[str, Any]:
    candidates, stl_metadata = load_binary_stl_candidate_vertices(model_path)
    source_points = select_spatially_distributed_points(candidates, 12)
    registration_source = source_points[:7]
    validation_source = source_points[7:]
    if (
        min(
            np.linalg.matrix_rank(registration_source - registration_source.mean(axis=0)),
            np.linalg.matrix_rank(validation_source - validation_source.mean(axis=0)),
        )
        < 2
    ):
        raise ValueError("registration_validation_split_degenerate")

    source_to_phantom = rigid_matrix([0.08, -0.04, 0.03], [18.0, -12.0, 24.0])
    target_points = transform_points(source_points, source_to_phantom)
    camera_matrix_4x = np.asarray(
        [[920.0, 0.0, 640.0], [0.0, 910.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    camera_matrix_6x = np.asarray(
        [[1180.0, 0.0, 640.0], [0.0, 1170.0, 360.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    camera_rotation_vector = np.asarray([0.04, -0.06, 0.02], dtype=np.float64)
    camera_rotation, _ = cv2.Rodrigues(camera_rotation_vector)
    camera_translation = np.asarray([0.0, 0.0, 650.0], dtype=np.float64) - camera_rotation @ target_points.mean(axis=0)
    projected, _ = cv2.projectPoints(
        target_points,
        camera_rotation_vector,
        camera_translation,
        camera_matrix_4x,
        np.zeros(5, dtype=np.float64),
    )
    image_points = projected.reshape(-1, 2)
    inside = (
        (image_points[:, 0] >= 0)
        & (image_points[:, 0] < IMAGE_SIZE[0])
        & (image_points[:, 1] >= 0)
        & (image_points[:, 1] < IMAGE_SIZE[1])
    )
    if int(inside.sum()) < 10:
        raise ValueError("pnp_projection_visibility_insufficient")
    camera_to_reference = rigid_matrix(camera_rotation_vector.tolist(), camera_translation.tolist())
    return {
        "stl_metadata": stl_metadata,
        "source_points": source_points,
        "target_points": target_points,
        "registration_source_points": registration_source,
        "registration_target_points": target_points[:7],
        "validation_source_points": validation_source,
        "validation_target_points": target_points[7:],
        "camera_registration_object_points": target_points[:7],
        "camera_registration_image_points": image_points[:7],
        "camera_validation_object_points": target_points[7:],
        "camera_validation_image_points": image_points[7:],
        "projection_points": source_points,
        "source_to_phantom_matrix": source_to_phantom,
        "phantom_to_camera_matrix": camera_to_reference,
        "source_to_camera_matrix": camera_to_reference @ source_to_phantom,
        "camera_matrix_4x": camera_matrix_4x,
        "camera_matrix_6x": camera_matrix_6x,
        "camera_rotation_vector": camera_rotation_vector,
        "camera_translation": camera_translation,
    }


def build_pose_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(FRAME_COUNT):
        matrix: FloatArray = np.eye(4, dtype=np.float64)
        matrix[0, 3] = 0.12 * index
        matrix[1, 3] = 0.03 * math.sin(index * 0.5)
        magnification = 4.0 if index < 3 else 6.0
        working_distance_mm = 250.0 if index < 3 else 300.0
        records.append(
            {
                "frame_index": index,
                "timestamp_s": index / FPS,
                "matrix": matrix.tolist(),
                "from_space": "camera_optical",
                "to_space": "camera_optical_dynamic",
                "direction": "forward",
                "unit": "mm",
                "handedness": "right_handed",
                "axis_convention": "opencv_camera_x_right_y_down_z_forward",
                "source_frame": _frame(
                    "camera_optical",
                    axis_convention="opencv_camera_x_right_y_down_z_forward",
                    source="checksum_bound_point_correspondence_artifact",
                ),
                "target_frame": _frame(
                    "camera_optical_dynamic",
                    axis_convention="opencv_camera_x_right_y_down_z_forward",
                    source="checksum_bound_pose_manifest_tracker",
                ),
                "matrix_convention": MATRIX_CONVENTION,
                "magnification": magnification,
                "working_distance_mm": working_distance_mm,
                "tracking_status": "tracking",
                "tracking_drift_mm": 0.05 + index * 0.005,
                "tracking_drift_source": "pending_checksum_binding",
                "dynamic_target_error_mm": 0.20 + index * 0.01,
                "dynamic_target_error_source": "pending_checksum_binding",
            }
        )
    return records


def write_digital_phantom_video(path: Path, geometry: Mapping[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        FPS,
        IMAGE_SIZE,
    )
    if not writer.isOpened():
        raise RuntimeError("digital_phantom_video_writer_unavailable")
    source_points = np.asarray(geometry["projection_points"], dtype=np.float64)
    static_transform = np.asarray(geometry["source_to_camera_matrix"], dtype=np.float64)
    poses = build_pose_records()
    width, height = IMAGE_SIZE
    try:
        for pose in poses:
            frame: NDArray[np.uint8] = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :, 0] = np.linspace(28, 54, width, dtype=np.uint8)[None, :]
            frame[:, :, 1] = np.linspace(34, 62, height, dtype=np.uint8)[:, None]
            frame[:, :, 2] = 42
            dynamic = np.asarray(pose["matrix"], dtype=np.float64)
            transformed = transform_points(source_points, dynamic @ static_transform)
            intrinsics = (
                np.asarray(geometry["camera_matrix_4x"], dtype=np.float64)
                if pose["magnification"] == 4.0
                else np.asarray(geometry["camera_matrix_6x"], dtype=np.float64)
            )
            pixels = (intrinsics @ transformed.T).T
            pixels = pixels[:, :2] / pixels[:, 2:3]
            hull = cv2.convexHull(np.rint(pixels).astype(np.int32))
            cv2.polylines(frame, [hull], True, (70, 190, 230), 2, cv2.LINE_AA)
            for point_index, point in enumerate(pixels):
                x, y = int(round(point[0])), int(round(point[1]))
                if 0 <= x < width and 0 <= y < height:
                    cv2.circle(frame, (x, y), 6, (60, 220, 160), -1, cv2.LINE_AA)
                    cv2.putText(
                        frame,
                        str(point_index + 1),
                        (x + 7, y - 7),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.42,
                        (235, 245, 245),
                        1,
                        cv2.LINE_AA,
                    )
            cv2.putText(
                frame,
                "D036 DIGITAL PHANTOM / ENGINEERING EVIDENCE",
                (36, 54),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.82,
                (245, 245, 245),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"frame={pose['frame_index']}  mag={pose['magnification']:.1f}x  wd={pose['working_distance_mm']:.0f}mm",
                (36, 88),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (160, 225, 205),
                1,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("digital_phantom_video_empty")
    capture = cv2.VideoCapture(str(path))
    try:
        decoded_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        decoded_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        decoded_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        decoded_fps = float(capture.get(cv2.CAP_PROP_FPS))
    finally:
        capture.release()
    if (decoded_frame_count, decoded_width, decoded_height) != (FRAME_COUNT, *IMAGE_SIZE):
        raise RuntimeError("digital_phantom_video_decode_mismatch")
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "frame_count": decoded_frame_count,
        "fps": decoded_fps,
        "image_size_px": [decoded_width, decoded_height],
        "source_type": "deterministic_d036_digital_phantom",
        "target_domain_flag": False,
    }


def verify_d036_model_provenance(model_path: Path, *, expected_sha256: str | None) -> dict[str, Any]:
    actual_sha256 = sha256_file(model_path)
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise RuntimeError("d036_model_sha256_mismatch")
    evidence_path = model_path.with_suffix(".three_d_evidence.json")
    evidence: dict[str, Any] = {}
    if evidence_path.is_file():
        loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError("d036_model_evidence_invalid")
        evidence = loaded
        surface = evidence.get("surface_model")
        if not isinstance(surface, dict) or surface.get("sha256") != actual_sha256:
            raise RuntimeError("d036_model_evidence_sha256_mismatch")
        if str(evidence.get("case_id") or "") != "ToothFairy2F_036":
            raise RuntimeError("d036_model_evidence_case_mismatch")
    elif expected_sha256:
        raise RuntimeError("d036_model_evidence_missing")
    return {
        "model_path": str(model_path.resolve()),
        "model_sha256": actual_sha256,
        "model_size_bytes": model_path.stat().st_size,
        "adjacent_evidence_path": str(evidence_path.resolve()) if evidence_path.is_file() else None,
        "adjacent_evidence_sha256": sha256_file(evidence_path) if evidence_path.is_file() else None,
        "case_id": evidence.get("case_id"),
        "segmentation_surface_source": evidence.get("segmentation_surface_source"),
        "source_domain": "public_cbct_anatomy_label_reference",
        "target_domain_flag": False,
    }


def write_l1_calibration(path: Path, geometry: Mapping[str, Any]) -> dict[str, Any]:
    camera_matrix_4x = np.asarray(geometry["camera_matrix_4x"], dtype=np.float64).tolist()
    camera_matrix_6x = np.asarray(geometry["camera_matrix_6x"], dtype=np.float64).tolist()
    calibration = {
        "schema_version": "osteo-vision-camera-calibration-v2",
        "intrinsics_id": "d036_scope_4x_250mm",
        "calibration_table_id": "d036_digital_phantom_zoom_wd_table_v1",
        "selection_method": "nearest_validated_entry_v1",
        "camera_matrix": camera_matrix_4x,
        "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
        "image_size_px": list(IMAGE_SIZE),
        "calibrated_at": "2026-07-01T08:00:00+00:00",
        "calibration_method": "deterministic_digital_checkerboard_fixture_v1",
        "calibration_reprojection_error_px": 0.18,
        "calibration_reprojection_threshold_px": 0.5,
        "magnification_range": [3.5, 6.5],
        "working_distance_range_mm": [240.0, 310.0],
        "calibration_entries": [
            {
                "intrinsics_id": "d036_scope_4x_250mm",
                "magnification_reference": 4.0,
                "magnification_range": [3.5, 4.5],
                "working_distance_reference_mm": 250.0,
                "working_distance_range_mm": [240.0, 260.0],
                "camera_matrix": camera_matrix_4x,
                "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
                "image_size_px": list(IMAGE_SIZE),
                "calibrated_at": "2026-07-01T08:00:00+00:00",
                "calibration_method": "deterministic_digital_checkerboard_fixture_v1",
                "calibration_reprojection_error_px": 0.18,
                "calibration_reprojection_threshold_px": 0.5,
            },
            {
                "intrinsics_id": "d036_scope_6x_300mm",
                "magnification_reference": 6.0,
                "magnification_range": [5.5, 6.5],
                "working_distance_reference_mm": 300.0,
                "working_distance_range_mm": [290.0, 310.0],
                "camera_matrix": camera_matrix_6x,
                "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
                "image_size_px": list(IMAGE_SIZE),
                "calibrated_at": "2026-07-01T08:30:00+00:00",
                "calibration_method": "deterministic_digital_checkerboard_fixture_v1",
                "calibration_reprojection_error_px": 0.21,
                "calibration_reprojection_threshold_px": 0.5,
            },
        ],
    }
    return write_hashed_json(path, calibration)


def write_l1_point_artifact(
    path: Path,
    *,
    case_id: str,
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    source_space = "cbct_lps_mm"
    target_space = "phantom_reference_mm"
    camera_space = "camera_optical"
    artifact = {
        "schema_version": "osteo-vision-l1-point-correspondence-v1",
        "case_id": case_id,
        "registration_method": "rigid_points_with_pnp",
        "coordinate_transform": {
            "from_space": source_space,
            "to_space": target_space,
            "direction": "forward",
            "unit": "mm",
            "source_frame": _frame(
                source_space,
                axis_convention="dicom_lps_x_left_y_posterior_z_superior",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "target_frame": _frame(
                target_space,
                axis_convention="phantom_x_right_y_anterior_z_superior",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "matrix_convention": MATRIX_CONVENTION,
        },
        "point_sets": {
            "registration": {
                "source": np.asarray(geometry["registration_source_points"], dtype=np.float64).tolist(),
                "target": np.asarray(geometry["registration_target_points"], dtype=np.float64).tolist(),
            },
            "validation": {
                "source": np.asarray(geometry["validation_source_points"], dtype=np.float64).tolist(),
                "target": np.asarray(geometry["validation_target_points"], dtype=np.float64).tolist(),
            },
        },
        "camera_coordinate_transform": {
            "from_space": target_space,
            "to_space": camera_space,
            "direction": "forward",
            "unit": "mm",
            "source_frame": _frame(
                target_space,
                axis_convention="phantom_x_right_y_anterior_z_superior",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "target_frame": _frame(
                camera_space,
                axis_convention="opencv_camera_x_right_y_down_z_forward",
                source="checksum_bound_point_correspondence_artifact",
            ),
            "matrix_convention": MATRIX_CONVENTION,
        },
        "camera_point_sets": {
            "registration": {
                "object": np.asarray(geometry["camera_registration_object_points"], dtype=np.float64).tolist(),
                "image": np.asarray(geometry["camera_registration_image_points"], dtype=np.float64).tolist(),
            },
            "validation": {
                "object": np.asarray(geometry["camera_validation_object_points"], dtype=np.float64).tolist(),
                "image": np.asarray(geometry["camera_validation_image_points"], dtype=np.float64).tolist(),
            },
        },
        "source_asset": {
            "dataset_id": "D036",
            "dataset_name": "ToothFairy2",
            "case_id": "ToothFairy2F_036",
            "domain": "public_cbct_anatomy_label_reference",
            "target_domain_flag": False,
        },
        "generation_method": "deterministic_farthest_vertex_selection_and_known_rigid_transform_v1",
    }
    return write_hashed_json(path, artifact)


def build_l1_request(
    *,
    case_id: str,
    model_path: Path,
    model_sha256: str,
    geometry: Mapping[str, Any],
    point_artifact: Mapping[str, Any],
    calibration_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "input_mode": "manual_metadata",
        "registration_method": "rigid_points_with_pnp",
        "model_path": str(model_path.resolve()),
        "model_sha256": model_sha256,
        "model_format": "stl",
        "point_correspondence_artifact_path": point_artifact["path"],
        "point_correspondence_artifact_sha256": point_artifact["sha256"],
        "source_points": np.asarray(geometry["registration_source_points"], dtype=np.float64).tolist(),
        "target_points": np.asarray(geometry["registration_target_points"], dtype=np.float64).tolist(),
        "validation_source_points": np.asarray(geometry["validation_source_points"], dtype=np.float64).tolist(),
        "validation_target_points": np.asarray(geometry["validation_target_points"], dtype=np.float64).tolist(),
        "source_space": "cbct_lps_mm",
        "target_space": "phantom_reference_mm",
        "unit": "mm",
        "fre_threshold_mm": 1.0,
        "tre_threshold_mm": 1.0,
        "threshold_source": "d036_digital_phantom_protocol_v1",
        "camera_object_points": np.asarray(geometry["camera_registration_object_points"], dtype=np.float64).tolist(),
        "camera_image_points": np.asarray(geometry["camera_registration_image_points"], dtype=np.float64).tolist(),
        "validation_camera_object_points": np.asarray(
            geometry["camera_validation_object_points"], dtype=np.float64
        ).tolist(),
        "validation_camera_image_points": np.asarray(
            geometry["camera_validation_image_points"], dtype=np.float64
        ).tolist(),
        "camera_matrix": np.asarray(geometry["camera_matrix_4x"], dtype=np.float64).tolist(),
        "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
        "image_size_px": list(IMAGE_SIZE),
        "intrinsics_id": "d036_scope_4x_250mm",
        "camera_space": "camera_optical",
        "reprojection_threshold_px": 0.5,
        "camera_calibration_evidence": {
            "artifact_path": calibration_artifact["path"],
            "artifact_sha256": calibration_artifact["sha256"],
        },
        "threshold_approval": {
            "status": "approved",
            "protocol_version": "d036_digital_phantom_protocol_v1.0",
            "data_version": "d036_public_label_geometry_20260719",
            "approved_by": REVIEW_ACTOR["actor_id"],
            "approved_at": "2026-07-02T08:00:00+00:00",
            "fre_threshold_mm": 1.0,
            "tre_threshold_mm": 1.0,
            "reprojection_threshold_px": 0.5,
        },
        "doctor_review_status": "accepted",
        "microscope_pose_evidence": {
            "magnification": 4.0,
            "working_distance_mm": 250.0,
            "depth_source": "deterministic_d036_digital_phantom_scale",
            "depth_status": "valid",
        },
    }


def build_tampered_l1_binding_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    tampered = json.loads(json.dumps(manifest))
    tampered["l1_model_sha256"] = "0" * 64
    return tampered


@contextlib.contextmanager
def runtime_environment(runtime_root: Path) -> Iterator[None]:
    updates = {
        "OSTEO_ARTIFACT_ROOT": str(runtime_root.resolve()),
        "OSTEO_CASE_STORE_PATH": str((runtime_root / "cases.json").resolve()),
        "OSTEO_JOB_STORE_PATH": str((runtime_root / "jobs.json").resolve()),
        "OSTEO_ANNOTATION_STORE_PATH": str((runtime_root / "manual_annotations.json").resolve()),
        "OSTEO_PROMOTION_APPROVAL_STORE_PATH": str((runtime_root / "promotion_approvals.json").resolve()),
        "OSTEO_CASE_STORE_BACKEND": "json",
        "OSTEO_JOB_EXECUTION_MODE": "background",
        "OSTEO_REVIEW_IDENTITIES_JSON": json.dumps({REVIEW_TOKEN: REVIEW_ACTOR}),
    }
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def require_response(response: Any, *, expected_status: int = 200) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise RuntimeError(
            f"api_request_failed:{response.request.method}:{response.request.url.path}:"
            f"{response.status_code}:{response.text}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("api_response_invalid")
    return payload


def dict_value(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def upload_and_admit_video(
    client: TestClient,
    *,
    video_path: Path,
    run_token: str,
) -> dict[str, Any]:
    payload = video_path.read_bytes()
    uploaded = require_response(
        client.post(
            "/uploads/raw?keyframe_mode=none",
            content=payload,
            headers={
                "content-type": "video/mp4",
                "x-filename": "d036_digital_phantom.mp4",
            },
        )
    )
    if uploaded.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise RuntimeError("uploaded_video_sha256_mismatch")
    admitted = require_response(
        client.post(
            "/hospital-intake/batches",
            json={
                "batch_id": f"d036-nav-{run_token}",
                "handover_id": f"d036-nav-handover-{run_token}",
                "source_organization": "Osteo Vision Engineering Digital Phantom Fixture",
                "received_by": "automated_navigation_validation",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "authorization_status": "approved",
                "usage_scope": "offline_dynamic_ar_engineering_validation",
                "deidentification_confirmed": True,
                "deidentification_method": "public_dataset_digital_phantom_no_patient_identity",
                "mapping_held_by_institution": True,
                "target_condition_confirmed": False,
                "files": [
                    {
                        "external_case_id": f"D036NAV{run_token.upper()}",
                        "path": uploaded["path"],
                        "channel": "video",
                        "acquisition_mode": "mode_switching",
                        "channel_relationship": "single_channel",
                        "original_filename": uploaded["original_filename"],
                        "metadata": {
                            "device": "deterministic_digital_phantom_renderer",
                            "device_source": "project_offline_fixture",
                            "source_type": "deterministic_d036_digital_phantom",
                            "dataset_id": "D036",
                            "target_domain_flag": False,
                        },
                        "missing_fields": ["physical_device_model", "firmware_version", "exposure", "gain"],
                    }
                ],
            },
        )
    )
    records = admitted.get("records")
    if not isinstance(records, list) or len(records) != 1 or records[0].get("status") != "admitted":
        raise RuntimeError(f"digital_phantom_video_admission_failed:{records}")
    case_id = str(records[0]["platform_case_id"])
    case = require_response(client.get(f"/cases/{case_id}"))
    video_inputs = [item for item in case.get("inputs", []) if item.get("channel") == "video"]
    if len(video_inputs) != 1:
        raise RuntimeError("admitted_video_input_missing")
    return {
        "case_id": case_id,
        "input_id": video_inputs[0]["input_id"],
        "sha256": uploaded["sha256"],
        "controlled_path": uploaded["path"],
        "intake_report_path": admitted.get("report_path"),
        "target_domain_flag": False,
    }


def start_and_get_job(
    client: TestClient,
    *,
    start_path: str,
    get_path_prefix: str,
    request: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    started = require_response(client.post(start_path, json=dict(request), headers=dict(headers or {})))
    job_id = str(started.get("job_id") or "")
    if not job_id:
        raise RuntimeError("job_id_missing")
    return require_response(client.get(f"{get_path_prefix}/{job_id}"))


def _l1_evidence(case: Mapping[str, Any]) -> dict[str, Any]:
    evidence = case.get("three_d_evidence")
    if not isinstance(evidence, dict):
        raise RuntimeError("l1_case_evidence_missing")
    if evidence.get("analysis_mode") == "l2_offline_pose_replay":
        snapshot = evidence.get("l1_evidence_snapshot")
        if isinstance(snapshot, dict):
            evidence = snapshot
    if evidence.get("navigation_ready") is not True or evidence.get("navigation_level") != "L1":
        raise RuntimeError("l1_case_evidence_not_ready")
    return dict(evidence)


def write_l2_manifest(
    inputs_dir: Path,
    *,
    name: str,
    case_id: str,
    video_input_id: str,
    video_sha256: str,
    l1_evidence: Mapping[str, Any],
    geometry: Mapping[str, Any],
    doctor_review_status: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    poses = build_pose_records()
    measurement_path = inputs_dir / f"{name}_independent_measurements.json"
    measurement = {
        "schema_version": "osteo-vision-l2-independent-measurements-v1",
        "case_id": case_id,
        "video_input_id": video_input_id,
        "video_sha256": video_sha256,
        "frame_count": len(poses),
        "measurement_method_id": "independent_tracker_and_phantom_target_v1",
        "source_type": "independent_phantom_measurement",
        "review_status": "accepted",
        "reviewed_by": REVIEW_ACTOR,
        "reviewed_at": "2026-07-02T08:00:00+00:00",
        "records": [
            {
                "frame_index": pose["frame_index"],
                "timestamp_s": pose["timestamp_s"],
                "tracking_drift_mm": pose["tracking_drift_mm"],
                "dynamic_target_error_mm": pose["dynamic_target_error_mm"],
            }
            for pose in poses
        ],
        "evidence_boundary": "deterministic digital phantom measurement fixture",
        "target_domain_flag": False,
    }
    measurement_artifact = write_hashed_json(measurement_path, measurement)
    measurement_reference = "independent_tracker_and_phantom_target_v1:" + str(measurement_artifact["sha256"])
    for pose in poses:
        pose["tracking_drift_source"] = measurement_reference
        pose["dynamic_target_error_source"] = measurement_reference

    threshold_path = inputs_dir / f"{name}_threshold_policy.json"
    threshold_policy = {
        "schema_version": "osteo-vision-l2-threshold-policy-v2",
        "policy_id": "d036-digital-phantom-platform-safety-ceiling",
        "policy_version": "1.0.0",
        "status": "approved",
        "protocol_version": "d036_l2_digital_phantom_protocol_v1.0",
        "data_version": "d036_public_label_geometry_20260719",
        "approved_by": REVIEW_ACTOR,
        "approved_at": "2026-07-02T08:00:00+00:00",
        "thresholds": L2_THRESHOLDS,
        "target_domain_flag": False,
    }
    threshold_artifact = write_hashed_json(threshold_path, threshold_policy)
    input_provenance = l1_evidence.get("registration_input_provenance")
    if not isinstance(input_provenance, dict):
        raise RuntimeError("l1_input_provenance_missing")
    manifest = {
        "schema_version": "osteo-vision-l2-pose-input-v3",
        "case_id": case_id,
        "replay_mode": "dynamic_ar_validation",
        "video_input_id": video_input_id,
        "video_sha256": video_sha256,
        "video_frame_count": FRAME_COUNT,
        "intrinsics_id": "d036_scope_4x_250mm",
        "calibration_table_id": "d036_digital_phantom_zoom_wd_table_v1",
        "l1_registration_run_id": l1_evidence["run_id"],
        "l1_model_sha256": l1_evidence["model_sha256"],
        "l1_input_artifact_sha256": input_provenance["artifact_sha256"],
        "l1_registration_output_sha256": l1_evidence["registration_output_manifest_sha256"],
        "l1_transform_sha256": l1_evidence["transform_sha256"],
        "projection_point_space": "cbct_lps_mm",
        "projection_point_frame": _frame(
            "cbct_lps_mm",
            axis_convention="dicom_lps_x_left_y_posterior_z_superior",
            source="checksum_bound_point_correspondence_artifact",
        ),
        "projection_points_3d": np.asarray(geometry["projection_points"], dtype=np.float64).tolist(),
        "poses": poses,
        "failure_injections": {},
        **L2_THRESHOLDS,
        "measurement_artifact_path": measurement_artifact["path"],
        "measurement_artifact_sha256": measurement_artifact["sha256"],
        "threshold_policy_artifact_path": threshold_artifact["path"],
        "threshold_policy_artifact_sha256": threshold_artifact["sha256"],
        "l2_threshold_approval": {
            "status": "approved",
            "policy_id": threshold_policy["policy_id"],
            "policy_version": threshold_policy["policy_version"],
            "artifact_sha256": threshold_artifact["sha256"],
            "protocol_version": threshold_policy["protocol_version"],
            "data_version": threshold_policy["data_version"],
            "approved_by": REVIEW_ACTOR["actor_id"],
            "approved_at": threshold_policy["approved_at"],
            **L2_THRESHOLDS,
        },
        "doctor_review_status": doctor_review_status,
        "evidence_boundary": {
            "dataset_id": "D036",
            "source_domain": "public_cbct_anatomy_label_reference",
            "target_domain_flag": False,
            "physical_phantom_flag": False,
            "synthetic_pose_and_video_flag": True,
        },
    }
    manifest_artifact = write_hashed_json(inputs_dir / f"{name}_pose_manifest.json", manifest)
    artifacts = {
        "pose_manifest": manifest_artifact,
        "measurement": measurement_artifact,
        "threshold_policy": threshold_artifact,
    }
    return manifest, artifacts


def l2_request(
    *,
    case_id: str,
    video_input_id: str,
    manifest_artifact: Mapping[str, Any],
    doctor_review_status: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "replay_mode": "dynamic_ar_validation",
        "input_mode": "offline_manifest",
        "pose_manifest_path": manifest_artifact["path"],
        "pose_manifest_sha256": manifest_artifact["sha256"],
        "video_input_id": video_input_id,
        "doctor_review_status": doctor_review_status,
    }


def archive_software_gate_result(
    audit_dir: Path,
    *,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    audit_dir.mkdir(parents=True, exist_ok=True)
    archived: dict[str, Any] = {}
    for key, filename in (
        ("overlay_video_path", "revoked_software_gate_overlay.mp4"),
        ("pose_replay_manifest_path", "software_gate_pose_replay_manifest.json"),
        ("pose_replay_frames_csv_path", "software_gate_pose_replay_frames.csv"),
    ):
        source_value = result.get(key)
        if not str(source_value or "").strip():
            raise RuntimeError(f"software_gate_artifact_missing:{key}")
        source = Path(str(source_value)).resolve()
        if not source.is_file():
            raise RuntimeError(f"software_gate_artifact_file_missing:{key}")
        destination = audit_dir / filename
        shutil.copy2(source, destination)
        archived[key] = {
            "path": str(destination.resolve()),
            "sha256": sha256_file(destination),
            "size_bytes": destination.stat().st_size,
            "lifecycle": "revoked_engineering_audit_copy",
            "display_eligible": False,
        }
    result_snapshot = write_hashed_json(
        audit_dir / "software_gate_l2_result_snapshot.json",
        dict(result),
    )
    archived["result_snapshot"] = result_snapshot
    return archived


def collect_file_inventory(root: Path, *, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude_names or set()
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name in excluded or path.suffix == ".sha256":
            continue
        records.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records


def render_markdown_summary(summary: Mapping[str, Any]) -> str:
    l1 = summary["validation_results"]["l1_static_registration"]
    l2 = summary["validation_results"]["l2_software_gate"]
    tamper = summary["validation_results"]["l1_binding_tamper_injection"]
    fallback = summary["validation_results"]["review_required_fallback"]
    final_state = summary["final_persisted_case_state"]
    lines = [
        "# D036 数字下颌仿体 L1/L2 导航工程验证",
        "",
        f"- 生成时间：`{summary['created_at_utc']}`",
        f"- 病例：`{summary['case_id']}`",
        "- 数据域：D036 ToothFairy2 公开 CBCT 下颌标签面，`target_domain_flag=false`。",
        "- 位姿、视频、独立测量和复核身份均为受控工程测试夹具。",
        "- 术中导航声称：禁止；`navigation_claim_allowed=false`。",
        "",
        "## 核验结果",
        "",
        f"- L1：`{l1['job_status']}`，FRE `{l1['fre_mm']:.6f} mm`，TRE `{l1['tre_mm']:.6f} mm`，"
        f"独立重投影误差 `{l1['reprojection_error_px']:.6f} px`。",
        f"- L2 软件门：`{l2['job_status']}`，级别 `{l2['navigation_level']}`，安全帧 "
        f"`{l2['safe_frame_count']}/{FRAME_COUNT}`，同一 L1 链绑定 `{l2['l1_chain_binding_status']}`。",
        f"- 绑定篡改：`{tamper['job_status']}`，原因码 `{tamper['error_code']}`。",
        f"- 复核缺失回退：级别 `{fallback['navigation_level']}`，原因码 "
        f"`{', '.join(fallback['failure_reasons'])}`。",
        f"- 最终持久化：`{final_state['navigation_level']}`，`navigation_ready="
        f"{str(final_state['navigation_ready']).lower()}`。",
        "",
        "## 安全边界",
        "",
        "- 软件门通过只验证受控契约、坐标链、误差计算、PTS、倍率/工作距离标定项选择和失败闭合。",
        "- 真实下颌物理仿体、真实显微镜标定、独立光学跟踪、真实手术场景和医生临床复核仍需后续完成。",
        "- 首次 L2 叠加图已归档为撤销状态审计副本，`display_eligible=false`。",
        "- 当前病例最终保持 L0，平台不会把测试夹具结果暴露为可用导航状态。",
        "",
    ]
    warnings = summary.get("provenance_warnings") or []
    if warnings:
        lines.extend(["## 来源警告", ""])
        lines.extend(f"- `{warning}`" for warning in warnings)
        lines.append("")
    return "\n".join(lines)


def validate_summary_safety_contract(summary: Mapping[str, Any]) -> None:
    if summary.get("navigation_claim_allowed") is not False:
        raise RuntimeError("summary_navigation_claim_boundary_missing")
    if summary.get("target_domain_flag") is not False:
        raise RuntimeError("summary_target_domain_boundary_missing")
    l2 = summary.get("validation_results", {}).get("l2_software_gate", {})
    if l2.get("navigation_level") != "L2" or l2.get("l1_chain_binding_status") != "verified_same_l1_chain":
        raise RuntimeError("summary_l2_software_gate_invalid")
    tamper = summary.get("validation_results", {}).get("l1_binding_tamper_injection", {})
    if tamper.get("error_code") != "l1_chain_binding_mismatch":
        raise RuntimeError("summary_tamper_gate_invalid")
    final_state = summary.get("final_persisted_case_state", {})
    if final_state.get("navigation_level") != "L0" or final_state.get("navigation_ready") is not False:
        raise RuntimeError("summary_final_fail_closed_state_invalid")


def verify_validation_bundle(summary_path: Path) -> dict[str, Any]:
    summary_path = summary_path.resolve()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise RuntimeError("validation_summary_invalid")
    validate_summary_safety_contract(summary)
    run_directory = Path(str(summary.get("run_directory") or "")).resolve()
    if run_directory not in summary_path.parents:
        raise RuntimeError("validation_summary_run_directory_mismatch")
    inventory = summary.get("artifact_inventory")
    if not isinstance(inventory, list) or not inventory:
        raise RuntimeError("validation_summary_inventory_missing")
    verified_bytes = 0
    for record in inventory:
        if not isinstance(record, dict):
            raise RuntimeError("validation_summary_inventory_record_invalid")
        relative_path = Path(str(record.get("relative_path") or ""))
        artifact_path = (run_directory / relative_path).resolve()
        if run_directory not in artifact_path.parents or not artifact_path.is_file():
            raise RuntimeError(f"validation_artifact_missing:{relative_path.as_posix()}")
        size_bytes = artifact_path.stat().st_size
        if size_bytes != int(record.get("size_bytes") or -1):
            raise RuntimeError(f"validation_artifact_size_mismatch:{relative_path.as_posix()}")
        if sha256_file(artifact_path) != str(record.get("sha256") or ""):
            raise RuntimeError(f"validation_artifact_sha256_mismatch:{relative_path.as_posix()}")
        verified_bytes += size_bytes
    model = summary.get("model_provenance")
    if not isinstance(model, dict):
        raise RuntimeError("validation_model_provenance_missing")
    model_path = Path(str(model.get("model_path") or "")).resolve()
    if not model_path.is_file() or sha256_file(model_path) != str(model.get("model_sha256") or ""):
        raise RuntimeError("validation_model_provenance_mismatch")
    return {
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "verified_artifact_count": len(inventory),
        "verified_bytes": verified_bytes,
        "model_sha256": model["model_sha256"],
        "navigation_claim_allowed": summary["navigation_claim_allowed"],
        "final_navigation_level": summary["final_persisted_case_state"]["navigation_level"],
        "status": "verified",
    }


def run_validation(
    *,
    model_path: Path,
    output_root: Path,
    expected_model_sha256: str | None = EXPECTED_MODEL_SHA256,
) -> dict[str, Any]:
    model_path = model_path.resolve()
    output_root = output_root.resolve()
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    output_root.mkdir(parents=True, exist_ok=True)
    run_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + uuid4().hex[:6]
    run_dir = output_root / "runs" / run_token
    inputs_dir = run_dir / "inputs"
    audit_dir = run_dir / "audit"
    runtime_root = run_dir / "runtime"
    inputs_dir.mkdir(parents=True, exist_ok=False)

    model_provenance = verify_d036_model_provenance(
        model_path,
        expected_sha256=expected_model_sha256,
    )
    geometry = build_geometry(model_path)
    geometry_artifact = write_hashed_json(
        inputs_dir / "d036_digital_phantom_geometry.json",
        {
            "schema_version": "osteo-vision-d036-digital-phantom-geometry-v1",
            "model_provenance": model_provenance,
            "stl_metadata": geometry["stl_metadata"],
            "source_points": np.asarray(geometry["source_points"], dtype=np.float64).tolist(),
            "target_points": np.asarray(geometry["target_points"], dtype=np.float64).tolist(),
            "source_to_phantom_matrix": np.asarray(geometry["source_to_phantom_matrix"], dtype=np.float64).tolist(),
            "phantom_to_camera_matrix": np.asarray(geometry["phantom_to_camera_matrix"], dtype=np.float64).tolist(),
            "camera_matrix_4x": np.asarray(geometry["camera_matrix_4x"], dtype=np.float64).tolist(),
            "camera_matrix_6x": np.asarray(geometry["camera_matrix_6x"], dtype=np.float64).tolist(),
            "target_domain_flag": False,
            "physical_phantom_flag": False,
            "synthetic_pose_and_video_flag": True,
        },
    )
    source_video_path = inputs_dir / "d036_digital_phantom.mp4"
    video_artifact = write_digital_phantom_video(source_video_path, geometry)
    calibration_artifact = write_l1_calibration(inputs_dir / "d036_camera_calibration.json", geometry)

    with runtime_environment(runtime_root):
        from backend.src.api.app import create_app

        with TestClient(create_app()) as client:
            admitted_video = upload_and_admit_video(
                client,
                video_path=source_video_path,
                run_token=run_token[-24:],
            )
            case_id = str(admitted_video["case_id"])
            point_artifact = write_l1_point_artifact(
                inputs_dir / "d036_l1_point_correspondence.json",
                case_id=case_id,
                geometry=geometry,
            )
            l1_job = start_and_get_job(
                client,
                start_path="/three-d/registration-jobs",
                get_path_prefix="/three-d/registration-jobs",
                request=build_l1_request(
                    case_id=case_id,
                    model_path=model_path,
                    model_sha256=str(model_provenance["model_sha256"]),
                    geometry=geometry,
                    point_artifact=point_artifact,
                    calibration_artifact=calibration_artifact,
                ),
                headers=HEADERS,
            )
            l1_result = dict_value(l1_job.get("result"))
            l1_three_d = dict_value(l1_result.get("three_d_evidence"))
            if (
                l1_job.get("status") != "completed"
                or l1_three_d.get("navigation_level") != "L1"
                or l1_three_d.get("navigation_ready") is not True
            ):
                raise RuntimeError(f"d036_l1_validation_failed:{json.dumps(l1_job, ensure_ascii=False)}")

            accepted_manifest, accepted_artifacts = write_l2_manifest(
                inputs_dir,
                name="accepted_software_gate",
                case_id=case_id,
                video_input_id=str(admitted_video["input_id"]),
                video_sha256=str(admitted_video["sha256"]),
                l1_evidence=l1_three_d,
                geometry=geometry,
                doctor_review_status="accepted",
            )
            l2_job = start_and_get_job(
                client,
                start_path="/three-d/pose-replay-jobs",
                get_path_prefix="/three-d/pose-replay-jobs",
                request=l2_request(
                    case_id=case_id,
                    video_input_id=str(admitted_video["input_id"]),
                    manifest_artifact=accepted_artifacts["pose_manifest"],
                    doctor_review_status="accepted",
                ),
                headers=HEADERS,
            )
            l2_result = dict_value(l2_job.get("result"))
            l2_binding = dict_value(dict_value(l2_result.get("three_d_evidence")).get("l1_chain_binding"))
            if (
                l2_job.get("status") != "completed"
                or l2_result.get("navigation_level") != "L2"
                or l2_binding.get("status") != "verified_same_l1_chain"
            ):
                raise RuntimeError(f"d036_l2_software_gate_failed:{json.dumps(l2_job, ensure_ascii=False)}")
            archived_gate = archive_software_gate_result(audit_dir, result=l2_result)

            tampered_manifest = build_tampered_l1_binding_manifest(accepted_manifest)
            tampered_artifact = write_hashed_json(
                inputs_dir / "tampered_l1_binding_pose_manifest.json",
                tampered_manifest,
            )
            tamper_job = start_and_get_job(
                client,
                start_path="/three-d/pose-replay-jobs",
                get_path_prefix="/three-d/pose-replay-jobs",
                request=l2_request(
                    case_id=case_id,
                    video_input_id=str(admitted_video["input_id"]),
                    manifest_artifact=tampered_artifact,
                    doctor_review_status="accepted",
                ),
                headers=HEADERS,
            )
            tamper_result = dict_value(tamper_job.get("result"))
            if (
                tamper_job.get("status") != "failed"
                or tamper_result.get("error_code") != "l1_chain_binding_mismatch"
                or tamper_result.get("navigation_level") != "L0"
            ):
                raise RuntimeError(f"d036_l1_binding_tamper_gate_failed:{json.dumps(tamper_job, ensure_ascii=False)}")
            tamper_snapshot = write_hashed_json(audit_dir / "l1_binding_tamper_result.json", tamper_job)

            current_case = require_response(client.get(f"/cases/{case_id}"))
            current_l1 = _l1_evidence(current_case)
            _, fallback_artifacts = write_l2_manifest(
                inputs_dir,
                name="review_required_fallback",
                case_id=case_id,
                video_input_id=str(admitted_video["input_id"]),
                video_sha256=str(admitted_video["sha256"]),
                l1_evidence=current_l1,
                geometry=geometry,
                doctor_review_status="review_required",
            )
            fallback_job = start_and_get_job(
                client,
                start_path="/three-d/pose-replay-jobs",
                get_path_prefix="/three-d/pose-replay-jobs",
                request=l2_request(
                    case_id=case_id,
                    video_input_id=str(admitted_video["input_id"]),
                    manifest_artifact=fallback_artifacts["pose_manifest"],
                    doctor_review_status="review_required",
                ),
                headers=HEADERS,
            )
            fallback_result = dict_value(fallback_job.get("result"))
            if (
                fallback_job.get("status") != "completed"
                or fallback_result.get("navigation_level") != "L0"
                or "doctor_review_not_accepted" not in (fallback_result.get("failure_reasons") or [])
                or fallback_result.get("overlay_video_path") is not None
            ):
                raise RuntimeError(f"d036_review_fallback_failed:{json.dumps(fallback_job, ensure_ascii=False)}")
            fallback_snapshot = write_hashed_json(audit_dir / "review_required_fallback_result.json", fallback_job)
            final_case = require_response(client.get(f"/cases/{case_id}"))
            final_evidence = dict_value(final_case.get("three_d_evidence"))
            if final_evidence.get("navigation_level") != "L0" or final_evidence.get("navigation_ready") is not False:
                raise RuntimeError("d036_final_case_did_not_fail_closed")
            final_case_snapshot = write_hashed_json(audit_dir / "final_case_snapshot.json", final_case)

    provenance_warnings: list[str] = []
    if geometry["stl_metadata"].get("header_identity_warning"):
        provenance_warnings.append("stl_header_dataset_token_inconsistent_with_d036_evidence_manifest")
    summary: dict[str, Any] = {
        "schema_version": "osteo-vision-d036-digital-phantom-navigation-validation-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_token": run_token,
        "run_directory": str(run_dir.resolve()),
        "case_id": case_id,
        "fixed_priority_capability": "l1_static_phantom_registration_and_l2_offline_dynamic_ar",
        "model_provenance": model_provenance,
        "geometry_artifact": geometry_artifact,
        "video_artifact": video_artifact,
        "admitted_video": admitted_video,
        "validation_results": {
            "l1_static_registration": {
                "job_id": l1_job["job_id"],
                "job_status": l1_job["status"],
                "navigation_level": l1_three_d["navigation_level"],
                "navigation_ready": l1_three_d["navigation_ready"],
                "fre_mm": l1_result["fre_mm"],
                "tre_mm": l1_result["tre_mm"],
                "reprojection_error_px": l1_result["reprojection_error_px"],
                "model_sha256": l1_three_d["model_sha256"],
                "input_artifact_sha256": l1_three_d["registration_input_provenance"]["artifact_sha256"],
                "registration_output_sha256": l1_three_d["registration_output_manifest_sha256"],
                "transform_sha256": l1_three_d["transform_sha256"],
            },
            "l2_software_gate": {
                "job_id": l2_job["job_id"],
                "job_status": l2_job["status"],
                "navigation_level": l2_result["navigation_level"],
                "navigation_ready": l2_result["navigation_ready"],
                "safe_frame_count": l2_result["safe_frame_count"],
                "degraded_frame_count": l2_result["degraded_frame_count"],
                "l1_chain_binding_status": l2_binding["status"],
                "video_timestamp_source": l2_result["video_timestamp_source"],
                "calibration_selection": l2_result["calibration_selection"],
                "archived_revoked_artifacts": archived_gate,
            },
            "l1_binding_tamper_injection": {
                "job_id": tamper_job["job_id"],
                "job_status": tamper_job["status"],
                "navigation_level": tamper_result["navigation_level"],
                "error_code": tamper_result["error_code"],
                "tampered_field": "l1_model_sha256",
                "result_snapshot": tamper_snapshot,
            },
            "review_required_fallback": {
                "job_id": fallback_job["job_id"],
                "job_status": fallback_job["status"],
                "navigation_level": fallback_result["navigation_level"],
                "navigation_ready": fallback_result["navigation_ready"],
                "failure_reasons": fallback_result["failure_reasons"],
                "overlay_video_path": fallback_result["overlay_video_path"],
                "result_snapshot": fallback_snapshot,
            },
        },
        "final_persisted_case_state": {
            "navigation_level": final_evidence["navigation_level"],
            "navigation_ready": final_evidence["navigation_ready"],
            "fallback_mode": final_evidence.get("fallback_mode"),
            "failure_reasons": final_evidence.get("failure_reasons"),
            "doctor_review_status": final_evidence.get("doctor_review_status"),
            "case_snapshot": final_case_snapshot,
        },
        "review_identity_boundary": {
            "identity": REVIEW_ACTOR,
            "identity_type": "synthetic_engineering_test_fixture",
            "clinical_reviewer_flag": False,
        },
        "provenance_warnings": provenance_warnings,
        "target_domain_flag": False,
        "physical_phantom_flag": False,
        "real_device_flag": False,
        "clinical_reviewer_flag": False,
        "navigation_claim_allowed": False,
        "allowed_claim": "offline software contract and fail-closed engineering validation",
        "outside_supported_claims": [
            "target-domain navigation performance",
            "physical phantom accuracy",
            "real microscope calibration accuracy",
            "real-time intraoperative tracking",
            "resection boundary guidance",
        ],
    }
    summary["artifact_inventory"] = collect_file_inventory(
        run_dir,
        exclude_names={"validation_summary.json", "validation_summary.md"},
    )
    validate_summary_safety_contract(summary)
    summary_artifact = write_hashed_json(run_dir / "validation_summary.json", summary)
    markdown_path = run_dir / "validation_summary.md"
    markdown_path.write_text(render_markdown_summary(summary), encoding="utf-8")
    markdown_sha256 = sha256_file(markdown_path)
    markdown_path.with_suffix(".md.sha256").write_text(
        f"{markdown_sha256}  {markdown_path.name}\n",
        encoding="utf-8",
    )
    latest = {
        "schema_version": "osteo-vision-navigation-validation-latest-v1",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_token": run_token,
        "summary": summary_artifact,
        "markdown": {
            "path": str(markdown_path.resolve()),
            "sha256": markdown_sha256,
            "size_bytes": markdown_path.stat().st_size,
        },
        "navigation_claim_allowed": False,
        "target_domain_flag": False,
    }
    write_hashed_json(output_root / "latest_validation.json", latest)
    return {
        **summary,
        "summary_artifact": summary_artifact,
        "markdown_path": str(markdown_path.resolve()),
        "markdown_sha256": markdown_sha256,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run checksum-bound D036 digital-phantom L1/L2 navigation engineering validation."
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--allow-custom-model-hash",
        action="store_true",
        help="Disable the fixed D036 SHA256 guard for isolated development fixtures.",
    )
    parser.add_argument(
        "--verify-summary",
        type=Path,
        help="Verify an existing summary and every checksum-bound inventory artifact, then exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_summary is not None:
        print(json.dumps(verify_validation_bundle(args.verify_summary), ensure_ascii=False, indent=2))
        return 0
    summary = run_validation(
        model_path=args.model,
        output_root=args.output,
        expected_model_sha256=None if args.allow_custom_model_hash else EXPECTED_MODEL_SHA256,
    )
    print(
        json.dumps(
            {
                "summary_path": summary["summary_artifact"]["path"],
                "summary_sha256": summary["summary_artifact"]["sha256"],
                "markdown_path": summary["markdown_path"],
                "case_id": summary["case_id"],
                "l1_navigation_level": summary["validation_results"]["l1_static_registration"]["navigation_level"],
                "l2_software_gate_level": summary["validation_results"]["l2_software_gate"]["navigation_level"],
                "tamper_error_code": summary["validation_results"]["l1_binding_tamper_injection"]["error_code"],
                "final_navigation_level": summary["final_persisted_case_state"]["navigation_level"],
                "navigation_claim_allowed": summary["navigation_claim_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
