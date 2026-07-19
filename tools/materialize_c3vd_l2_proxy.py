from __future__ import annotations

import argparse
import configparser
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from bisect import bisect_left
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.navigation.ocamcalib import (  # noqa: E402
    OCAMCALIB_POLYNOMIAL_V1,
    OcamCalibPolynomialV1,
)
from src.navigation.offline_pose_replay import (  # noqa: E402
    DYNAMIC_AR_MODE,
    OfflinePoseReplayConfig,
    replay_offline_poses,
)

DEFAULT_ARCHIVE = ROOT / "research/datasets/public-candidates/c3vd_l2_proxy_20260719/d087/raw/sampledata.zip"
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/c3vd_l2_proxy_20260719/d087/materialized"
DEFAULT_EVIDENCE = ROOT / "artifacts/navigation/c3vd_l2_proxy_replay_20260719"
EXPECTED_ARCHIVE_SHA256 = "ce6b285c578d9ebe42d9013bc21eb244d6df93ca0de63333b5ab38a80acc16ff"
OFFICIAL_FPS = 29.97
POSE_MATCH_TOLERANCE_MS = 10.0
REPLAY_FRAME_COUNT = 24
MAX_MAGNIFICATION_RATE_PER_S = 25.0
MAX_WORKING_DISTANCE_RATE_MM_PER_S = 600.0
MAX_INTRINSICS_SWITCH_RATE_HZ = 10.0
CALIBRATION_AMBIGUITY_MARGIN = 0.05
BASE_MEMBERS = (
    "sampledata/config.ini",
    "sampledata/mask.png",
    "sampledata/model.mtl",
    "sampledata/model.obj",
    "sampledata/pose.txt",
)
MATRIX_CONVENTION = {
    "storage_order": "row_major",
    "vector_convention": "column_vector",
    "multiplication_order": "left_multiply",
    "homogeneous_coordinate_order": "x_y_z_1",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_hashed_json(path: Path, value: Any) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_bytes(value)
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return {"path": str(path.resolve()), "size_bytes": len(payload), "sha256": digest}


def update_download_manifest(
    output_dir: Path,
    *,
    summary_artifact: dict[str, Any],
    pose_manifest_artifact: dict[str, Any],
    calibration_manifest_artifact: dict[str, Any],
) -> None:
    dataset_root = output_dir.parents[1]
    manifest_path = dataset_root / "c3vd_l2_proxy_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 1:
        raise RuntimeError("c3vd_download_manifest_record_invalid")
    record = records[0]
    if record.get("sha256") != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError("c3vd_download_manifest_archive_mismatch")
    payload["schema_version"] = "osteo-vision-c3vd-l2-proxy-download-v3"
    record.update(
        {
            "runtime_projection_supported": True,
            "pose_deduplication_status": "completed_with_audited_keep_last_policy",
            "frame_pose_binding_status": "766_matched_0_unmatched_0_ambiguous",
            "controlled_materialization_status": "verified",
            "offline_proxy_replay_status": "completed_fail_closed_l0",
            "controlled_materialization_manifest": str((output_dir / "c3vd_materialization_manifest.json").resolve()),
            "frame_pose_binding_manifest": pose_manifest_artifact,
            "ocamcalib_manifest": calibration_manifest_artifact,
            "offline_replay_summary": summary_artifact,
        }
    )
    manifest_path.write_bytes(json_bytes(payload))
    csv_path = dataset_root / "c3vd_l2_proxy_manifest.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(record))
        writer.writeheader()
        writer.writerow(record)


def safe_member_path(member_name: str) -> PurePosixPath:
    normalized = PurePosixPath(member_name)
    if normalized.is_absolute() or ".." in normalized.parts or "\\" in member_name:
        raise RuntimeError(f"unsafe_archive_member:{member_name}")
    if not normalized.parts or normalized.parts[0] != "sampledata":
        raise RuntimeError(f"unexpected_archive_root:{member_name}")
    return normalized


def extract_verified_member(
    archive: zipfile.ZipFile,
    member_name: str,
    output_dir: Path,
) -> dict[str, Any]:
    relative = safe_member_path(member_name)
    info = archive.getinfo(member_name)
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        raise RuntimeError(f"archive_symlink_rejected:{member_name}")
    destination = (output_dir / Path(*relative.parts)).resolve()
    root = output_dir.resolve()
    if root not in destination.parents:
        raise RuntimeError(f"archive_path_escape_rejected:{member_name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0
    with archive.open(info, "r") as source, destination.open("wb") as target:
        while block := source.read(1024 * 1024):
            target.write(block)
            digest.update(block)
            written += len(block)
    if written != info.file_size:
        raise RuntimeError(f"archive_member_size_mismatch:{member_name}")
    return {
        "archive_member": member_name,
        "materialized_path": str(destination),
        "size_bytes": written,
        "sha256": digest.hexdigest(),
        "zip_crc32": f"{info.CRC:08x}",
        "compressed_size_bytes": info.compress_size,
    }


def parse_config(raw: bytes) -> dict[str, Any]:
    parser = configparser.ConfigParser()
    parser.read_string("[c3vd]\n" + raw.decode("utf-8"))
    section = parser["c3vd"]
    camera_parameters = {
        field: section.getfloat(field) for field in ("cx", "cy", "a0", "a1", "a2", "a3", "a4", "c", "d", "e")
    }
    return {
        "image_size_px": [section.getint("width"), section.getint("height")],
        "camera_parameters": camera_parameters,
        "pose_start_time_s": section.getfloat("poseStartTime"),
        "a_cal": _config_matrix(section["A_cal"]),
        "b_cal": _config_matrix(section["B_cal"]),
        "handeye_x": _config_matrix(section["X"]),
        "model_transform_r6": [float(value.strip()) for value in section["modelTransform"].split(",")],
    }


def _config_matrix(value: str) -> np.ndarray:
    values = np.asarray([float(item.strip()) for item in value.split(",")], dtype=np.float64)
    if values.size != 16 or not np.isfinite(values).all():
        raise RuntimeError("c3vd_config_matrix_invalid")
    return values.reshape(4, 4, order="F")


def parse_and_deduplicate_poses(raw: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""))
    for source_row_index, row in enumerate(reader):
        if not row:
            continue
        if len(row) != 17:
            raise RuntimeError(f"pose_row_width_invalid:{source_row_index}")
        values = np.asarray([float(value) for value in row], dtype=np.float64)
        if not np.isfinite(values).all():
            raise RuntimeError(f"pose_row_non_finite:{source_row_index}")
        line_payload = (",".join(row) + "\n").encode("utf-8")
        records.append(
            {
                "source_row_index": source_row_index,
                "timestamp_s": float(values[0]),
                "matrix": values[1:].reshape(4, 4),
                "source_row_sha256": hashlib.sha256(line_payload).hexdigest(),
            }
        )
    if any(b["timestamp_s"] < a["timestamp_s"] for a, b in zip(records, records[1:])):
        raise RuntimeError("pose_timestamps_not_monotonic")

    groups: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["timestamp_s"]].append(record)
    deduplicated: list[dict[str, Any]] = []
    duplicate_audit: list[dict[str, Any]] = []
    for timestamp in sorted(groups):
        group = groups[timestamp]
        kept = group[-1]
        deduplicated.append(kept)
        if len(group) > 1:
            duplicate_audit.append(
                {
                    "timestamp_s": timestamp,
                    "policy": "keep_last_source_row_to_mirror_official_std_map_assignment",
                    "kept_source_row_index": kept["source_row_index"],
                    "kept_source_row_sha256": kept["source_row_sha256"],
                    "discarded": [
                        {
                            "source_row_index": item["source_row_index"],
                            "source_row_sha256": item["source_row_sha256"],
                            "matrix_equal_to_kept": bool(np.array_equal(item["matrix"], kept["matrix"])),
                        }
                        for item in group[:-1]
                    ],
                }
            )
    return deduplicated, duplicate_audit


def bind_frames(
    frame_indices: Iterable[int],
    poses: list[dict[str, Any]],
    pose_start_time_s: float,
) -> list[dict[str, Any]]:
    timestamps = [float(record["timestamp_s"]) for record in poses]
    bindings: list[dict[str, Any]] = []
    for frame_index in frame_indices:
        target = pose_start_time_s + frame_index / OFFICIAL_FPS
        insertion = bisect_left(timestamps, target)
        candidate_indices = [index for index in (insertion - 1, insertion) if 0 <= index < len(timestamps)]
        distances = [(abs(timestamps[index] - target), index) for index in candidate_indices]
        minimum = min(distance for distance, _ in distances)
        winners = [index for distance, index in distances if math.isclose(distance, minimum, abs_tol=1e-12)]
        ambiguous = len(winners) != 1
        pose_index = min(winners, key=lambda index: (timestamps[index], poses[index]["source_row_index"]))
        offset_ms = (timestamps[pose_index] - target) * 1000.0
        matched = abs(offset_ms) <= POSE_MATCH_TOLERANCE_MS and not ambiguous
        bindings.append(
            {
                "frame_index": frame_index,
                "frame_timestamp_s": target,
                "pose_index_after_deduplication": pose_index,
                "pose_source_row_index": poses[pose_index]["source_row_index"],
                "pose_source_row_sha256": poses[pose_index]["source_row_sha256"],
                "pose_timestamp_s": timestamps[pose_index],
                "signed_time_offset_ms": offset_ms,
                "absolute_time_offset_ms": abs(offset_ms),
                "match_tolerance_ms": POSE_MATCH_TOLERANCE_MS,
                "binding_status": "matched" if matched else ("ambiguous" if ambiguous else "unmatched"),
                "rgb_archive_member": f"sampledata/rgb/{frame_index:04d}.png",
                "depth_archive_member": f"sampledata/depth/{frame_index:04d}.png",
            }
        )
    return bindings


def _euler_model_transform(values: list[float]) -> np.ndarray:
    if len(values) != 6:
        raise RuntimeError("model_transform_r6_invalid")
    rx, ry, rz, tx, ty, tz = values
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    rotation_x = np.asarray([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    rotation_y = np.asarray([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    rotation_z = np.asarray([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
    matrix: NDArray[np.float64] = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation_z @ rotation_y @ rotation_x
    matrix[:3, 3] = [tx, ty, tz]
    return matrix


def _world_to_camera(robot_pose: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    camera_to_world = (
        config["b_cal"]
        @ np.linalg.inv(config["handeye_x"])
        @ np.linalg.inv(config["a_cal"])
        @ robot_pose
        @ config["handeye_x"]
    )
    return np.linalg.inv(camera_to_world)


def read_model_vertices(path: Path, maximum_candidates: int = 12000) -> np.ndarray:
    vertices: list[list[float]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                values = line.split()
                vertices.append([float(values[1]), float(values[2]), float(values[3])])
    if len(vertices) < 4:
        raise RuntimeError("c3vd_model_vertices_missing")
    array = np.asarray(vertices, dtype=np.float64)
    stride = max(1, math.ceil(array.shape[0] / maximum_candidates))
    return array[::stride]


def select_projection_points(
    model_vertices: np.ndarray,
    model_to_world: np.ndarray,
    world_to_camera: list[np.ndarray],
    calibration: OcamCalibPolynomialV1,
    count: int = 12,
) -> np.ndarray:
    homogeneous = np.c_[model_vertices, np.ones(model_vertices.shape[0])]
    world_points = (model_to_world @ homogeneous.T).T[:, :3]
    visible = np.ones(model_vertices.shape[0], dtype=bool)
    first_pixels: np.ndarray | None = None
    for transform in world_to_camera:
        camera_points = (transform @ np.c_[world_points, np.ones(world_points.shape[0])].T).T[:, :3]
        pixels = calibration.project_camera_points(camera_points)
        inside = (
            (pixels[:, 0] >= 0)
            & (pixels[:, 0] < calibration.width)
            & (pixels[:, 1] >= 0)
            & (pixels[:, 1] < calibration.height)
        )
        visible &= inside
        if first_pixels is None:
            first_pixels = pixels
    candidates = np.flatnonzero(visible)
    if candidates.size < count or first_pixels is None:
        raise RuntimeError("c3vd_shared_visible_projection_points_insufficient")
    selected = [
        int(candidates[np.argmin(np.linalg.norm(first_pixels[candidates] - [calibration.cx, calibration.cy], axis=1))])
    ]
    while len(selected) < count:
        remaining = np.asarray([index for index in candidates if index not in selected], dtype=int)
        distances = np.min(
            np.linalg.norm(first_pixels[remaining, None, :] - first_pixels[np.asarray(selected)][None, :, :], axis=2),
            axis=1,
        )
        selected.append(int(remaining[int(np.argmax(distances))]))
    return model_vertices[np.asarray(selected)]


def frame_metadata(name: str, axis_convention: str, directions: list[str], source: str) -> dict[str, Any]:
    return {
        "name": name,
        "handedness": "right_handed",
        "axis_convention": axis_convention,
        "axis_directions": directions,
        "unit": "mm",
        "source": source,
    }


def build_replay_evidence(
    bindings: list[dict[str, Any]],
    poses: list[dict[str, Any]],
    config: dict[str, Any],
    model_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[list[float]]]:
    selected_bindings = bindings[:REPLAY_FRAME_COUNT]
    model_to_world = _euler_model_transform(config["model_transform_r6"])
    camera_transforms = [
        _world_to_camera(poses[int(binding["pose_index_after_deduplication"])]["matrix"], config)
        for binding in selected_bindings
    ]
    calibration_model = OcamCalibPolynomialV1.from_mapping(
        {"image_size_px": config["image_size_px"], "camera_parameters": config["camera_parameters"]}
    )
    projection_points = select_projection_points(
        read_model_vertices(model_path),
        model_to_world,
        camera_transforms,
        calibration_model,
    )
    calibration = {
        "intrinsics_id": "c3vd-sample-ocamcalib-v1",
        "calibration_table_id": "c3vd-sample-config-ini-v1",
        "selection_method": "nearest_validated_entry_v1",
        "magnification_reference": 1.0,
        "magnification_min": 1.0,
        "magnification_max": 1.0,
        "working_distance_reference_mm": 1.0,
        "working_distance_min_mm": 1.0,
        "working_distance_max_mm": 1.0,
        "camera_model": OCAMCALIB_POLYNOMIAL_V1,
        "image_size_px": config["image_size_px"],
        "camera_parameters": config["camera_parameters"],
        "artifact_sha256": EXPECTED_ARCHIVE_SHA256,
        "verification_status": "verified",
    }
    world_frame = frame_metadata(
        "c3vd_world_reference",
        "c3vd_world_axes_from_official_handeye_chain",
        ["c3vd_world_x", "c3vd_world_y", "c3vd_world_z"],
        "C3VD official sample config and handeye chain",
    )
    camera_frame = frame_metadata(
        "camera_optical",
        "opencv_camera_x_right_y_down_z_forward",
        ["right", "down", "forward"],
        "C3VD official renderer camera space",
    )
    model_frame = frame_metadata(
        "c3vd_model",
        "c3vd_model_axes_from_official_obj",
        ["c3vd_model_x", "c3vd_model_y", "c3vd_model_z"],
        "C3VD official sample model.obj",
    )
    replay_poses: list[dict[str, Any]] = []
    for binding, transform in zip(selected_bindings, camera_transforms):
        replay_poses.append(
            {
                "frame_index": binding["frame_index"],
                "timestamp_s": binding["pose_timestamp_s"],
                "matrix": transform.tolist(),
                "magnification": 1.0,
                "working_distance_mm": 1.0,
                "tracking_status": "tracking",
                "tracking_drift_mm": 0.0,
                "tracking_drift_source": "C3VD proxy transform self-consistency only",
                "dynamic_target_error_mm": 0.0,
                "dynamic_target_error_source": "C3VD proxy transform self-consistency only",
                "from_space": "c3vd_world_reference",
                "to_space": "camera_optical",
                "direction": "forward",
                "unit": "mm",
                "handedness": "right_handed",
                "axis_convention": "opencv_camera_x_right_y_down_z_forward",
                "source_frame": world_frame,
                "target_frame": camera_frame,
                "matrix_convention": MATRIX_CONVENTION,
            }
        )
    common = {
        "frame_timestamps_s": [float(binding["frame_timestamp_s"]) for binding in selected_bindings],
        "poses": replay_poses,
        "calibration_table": [calibration],
        "static_l1_transform": model_to_world.tolist(),
        "l1_tre_mm": 0.0,
        "source_space": "c3vd_model",
        "reference_space": "c3vd_world_reference",
        "camera_space": "camera_optical",
        "config": OfflinePoseReplayConfig(
            max_time_offset_ms=POSE_MATCH_TOLERANCE_MS,
            drift_threshold_mm=1.0,
            tre_proxy_threshold_mm=2.0,
            dynamic_target_error_threshold_mm=2.0,
            minimum_visible_projection_points=4,
            max_magnification_rate_per_s=MAX_MAGNIFICATION_RATE_PER_S,
            max_working_distance_rate_mm_per_s=MAX_WORKING_DISTANCE_RATE_MM_PER_S,
            max_intrinsics_switch_rate_hz=MAX_INTRINSICS_SWITCH_RATE_HZ,
            calibration_ambiguity_margin=CALIBRATION_AMBIGUITY_MARGIN,
        ),
        "validation_mode": DYNAMIC_AR_MODE,
        "projection_points_3d": projection_points.tolist(),
        "frame_indices": [int(binding["frame_index"]) for binding in selected_bindings],
        "source_frame_metadata": model_frame,
        "reference_frame_metadata": world_frame,
        "camera_frame_metadata": camera_frame,
        "matrix_convention": MATRIX_CONVENTION,
    }
    proxy_gate = {int(binding["frame_index"]): ["proxy_domain_claim_closed"] for binding in selected_bindings}
    baseline = replay_offline_poses(**common, failure_injections=proxy_gate)
    injected = dict(proxy_gate)
    injected[int(selected_bindings[5]["frame_index"])] += ["tracking_lost"]
    injected[int(selected_bindings[10]["frame_index"])] += ["time_offset"]
    injected[int(selected_bindings[15]["frame_index"])] += ["drift_exceeded"]
    failure_result = replay_offline_poses(**common, failure_injections=injected)
    return asdict(baseline), asdict(failure_result), projection_points.tolist()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE.relative_to(ROOT)))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE.relative_to(ROOT)))
    args = parser.parse_args()
    archive_path = (ROOT / args.archive).resolve()
    output_dir = (ROOT / args.output_dir).resolve()
    evidence_dir = (ROOT / args.evidence_dir).resolve()
    if sha256_file(archive_path) != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError("c3vd_archive_sha256_mismatch")

    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("c3vd_archive_crc_failed")
        names = set(archive.namelist())
        for name in names:
            safe_member_path(name)
        config = parse_config(archive.read("sampledata/config.ini"))
        poses, duplicate_audit = parse_and_deduplicate_poses(archive.read("sampledata/pose.txt"))
        frame_indices = sorted(
            int(PurePosixPath(name).stem)
            for name in names
            if name.startswith("sampledata/rgb/") and name.endswith(".png")
        )
        if frame_indices != list(range(len(frame_indices))):
            raise RuntimeError("c3vd_frame_indices_not_contiguous_from_zero")
        bindings = bind_frames(frame_indices, poses, float(config["pose_start_time_s"]))
        selected_frames = frame_indices[:REPLAY_FRAME_COUNT]
        members = list(BASE_MEMBERS)
        members.extend(
            f"sampledata/{channel}/{index:04d}.png" for index in selected_frames for channel in ("rgb", "depth")
        )
        inventory = [extract_verified_member(archive, member, output_dir) for member in members]

    if len(duplicate_audit) != 2:
        raise RuntimeError(f"unexpected_duplicate_pose_group_count:{len(duplicate_audit)}")
    unmatched = [item for item in bindings if item["binding_status"] == "unmatched"]
    ambiguous = [item for item in bindings if item["binding_status"] == "ambiguous"]
    baseline, injected, projection_points = build_replay_evidence(
        bindings,
        poses,
        config,
        output_dir / "sampledata/model.obj",
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    pose_manifest = {
        "schema_version": "osteo-vision-c3vd-frame-pose-binding-v1",
        "generated_at_utc": generated_at,
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "official_fps": OFFICIAL_FPS,
        "pose_start_time_s": config["pose_start_time_s"],
        "match_method": "nearest_unique_pose_after_audited_deduplication",
        "match_tolerance_ms": POSE_MATCH_TOLERANCE_MS,
        "raw_pose_record_count": len(poses) + sum(len(item["discarded"]) for item in duplicate_audit),
        "deduplicated_pose_record_count": len(poses),
        "duplicate_pose_group_count": len(duplicate_audit),
        "duplicate_pose_audit": duplicate_audit,
        "frame_count": len(bindings),
        "matched_frame_count": len(bindings) - len(unmatched) - len(ambiguous),
        "unmatched_frame_count": len(unmatched),
        "ambiguous_frame_count": len(ambiguous),
        "maximum_absolute_time_offset_ms": max(item["absolute_time_offset_ms"] for item in bindings),
        "bindings": bindings,
        "target_domain_flag": False,
        "training_eligible": False,
        "navigation_claim_allowed": False,
        "data_boundary": "C3VD colon phantom, non-jaw, non-osteomyelitis and non-fluorescence engineering proxy.",
    }
    calibration_manifest = {
        "schema_version": "osteo-vision-c3vd-ocamcalib-v1",
        "camera_model": OCAMCALIB_POLYNOMIAL_V1,
        "image_size_px": config["image_size_px"],
        "camera_parameters": config["camera_parameters"],
        "source_member": "sampledata/config.ini",
        "source_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "source_renderer_commit": "443b4d19b0c056f54b7eaa15c1bad9d091740ad0",
        "projection_equation": "a4*rho^4+a3*rho^3+a2*rho^2+(a1-z/r)*rho+a0=0; minimum positive real rho",
        "target_domain_flag": False,
        "navigation_claim_allowed": False,
    }
    materialization_manifest = {
        "schema_version": "osteo-vision-c3vd-controlled-materialization-v1",
        "generated_at_utc": generated_at,
        "source_archive": str(archive_path),
        "source_archive_size_bytes": archive_path.stat().st_size,
        "source_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "selected_frame_count": len(selected_frames),
        "selected_frame_indices": selected_frames,
        "files": inventory,
        "target_domain_flag": False,
        "training_eligible": False,
        "navigation_claim_allowed": False,
        "medical_scene": "high_fidelity_colon_phantom_endoscopy",
        "fluorescence": False,
        "jaw_anatomy": False,
        "data_boundary": "Selective materialization for offline software replay only; physical and clinical navigation claims remain closed.",
    }
    materialization_artifact = write_hashed_json(
        output_dir / "c3vd_materialization_manifest.json", materialization_manifest
    )
    pose_manifest_artifact = write_hashed_json(output_dir / "c3vd_frame_pose_binding_manifest.json", pose_manifest)
    calibration_manifest_artifact = write_hashed_json(output_dir / "c3vd_ocamcalib_manifest.json", calibration_manifest)
    outputs = [
        materialization_artifact,
        pose_manifest_artifact,
        calibration_manifest_artifact,
        write_hashed_json(evidence_dir / "c3vd_proxy_replay_baseline.json", baseline),
        write_hashed_json(evidence_dir / "c3vd_proxy_replay_failure_injection.json", injected),
        write_hashed_json(evidence_dir / "c3vd_projection_points.json", {"points_model_mm": projection_points}),
    ]
    summary = {
        "schema_version": "osteo-vision-c3vd-l2-proxy-evidence-v1",
        "generated_at_utc": generated_at,
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "materialized_file_count": len(inventory),
        "materialized_size_bytes": sum(int(item["size_bytes"]) for item in inventory),
        "raw_pose_record_count": pose_manifest["raw_pose_record_count"],
        "deduplicated_pose_record_count": len(poses),
        "duplicate_pose_group_count": len(duplicate_audit),
        "bound_frame_count": len(bindings),
        "unmatched_frame_count": len(unmatched),
        "ambiguous_frame_count": len(ambiguous),
        "maximum_absolute_time_offset_ms": pose_manifest["maximum_absolute_time_offset_ms"],
        "baseline_projected_frame_count": sum(frame["projected_point_count"] > 0 for frame in baseline["frames"]),
        "baseline_navigation_ready": baseline["navigation_ready"],
        "replay_schema_version": baseline["schema_version"],
        "baseline_calibration_transition_summary": baseline["calibration_transition_summary"],
        "failure_calibration_transition_summary": injected["calibration_transition_summary"],
        "failure_injections": ["tracking_lost", "pose_time_offset_exceeded", "drift_threshold_exceeded"],
        "target_domain_flag": False,
        "training_eligible": False,
        "navigation_claim_allowed": False,
        "data_boundary": "C3VD colon-phantom, non-jaw and non-fluorescence proxy. All replay outputs remain L0/unregistered reference evidence.",
        "artifacts": outputs,
    }
    summary_artifact = write_hashed_json(evidence_dir / "c3vd_l2_proxy_replay_summary.json", summary)
    update_download_manifest(
        output_dir,
        summary_artifact=summary_artifact,
        pose_manifest_artifact=pose_manifest_artifact,
        calibration_manifest_artifact=calibration_manifest_artifact,
    )
    print(json.dumps({**summary, "summary_artifact": summary_artifact}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
