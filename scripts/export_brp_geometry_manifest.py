from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA_VERSION = "osteo-vision-brp-geometry-manifest-v1"
DATA_BOUNDARY = (
    "BRP-style geometry manifest derived from a surface mesh and scene manifest for research validation only. "
    "It is not a registered surgical navigation plan, not a clinical resection guide, and requires physician review."
)
D024_RUNTIME_REFERENCE_DIRECTORY = Path("artifacts/platform/three_d_runtime/references/d024")
DEFAULT_STL = D024_RUNTIME_REFERENCE_DIRECTORY / "mandible_d024_0001.stl"
DEFAULT_SCENE_MANIFEST = D024_RUNTIME_REFERENCE_DIRECTORY / "mandible_d024_0001.three_d_evidence.json"
DEFAULT_OUTPUT = D024_RUNTIME_REFERENCE_DIRECTORY / "mandible_d024_0001.brp_geometry_manifest.json"


def main() -> None:
    args = parse_args()
    result = export_brp_geometry_manifest(
        stl_path=args.stl,
        scene_manifest_path=args.scene_manifest,
        output_path=args.output,
        candidate_points_path=args.candidate_points,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export BRP-style geometric evidence from STL and scene manifest.")
    parser.add_argument("--stl", type=Path, default=DEFAULT_STL, help="Input binary STL surface path.")
    parser.add_argument(
        "--scene-manifest",
        type=Path,
        default=DEFAULT_SCENE_MANIFEST,
        help="Input three_d_evidence or scene manifest JSON path.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output geometry manifest path.")
    parser.add_argument(
        "--candidate-points",
        type=Path,
        default=None,
        help="Optional JSON list of candidate points with id and point_mm fields.",
    )
    return parser.parse_args()


def export_brp_geometry_manifest(
    *,
    stl_path: Path,
    scene_manifest_path: Path,
    output_path: Path,
    candidate_points_path: Path | None = None,
) -> dict[str, Any]:
    if not stl_path.exists():
        raise FileNotFoundError(f"STL file does not exist: {stl_path}")
    if not scene_manifest_path.exists():
        raise FileNotFoundError(f"Scene manifest does not exist: {scene_manifest_path}")

    triangles = read_binary_stl_triangles(stl_path)
    if triangles.size == 0:
        raise ValueError(f"STL did not contain triangles: {stl_path}")
    vertices = triangles.reshape((-1, 3))
    scene_manifest = read_scene_manifest(scene_manifest_path)
    planes = scene_manifest.get("review_planes")
    if not isinstance(planes, list) or not planes:
        raise ValueError("Scene manifest does not contain review_planes")

    plane_results = [
        plane_intersection_result(index=index, plane=plane, triangles=triangles) for index, plane in enumerate(planes)
    ]
    segment_results = segment_lengths_from_planes(plane_results)
    candidate_results = nearest_surface_points(vertices, read_candidate_points(candidate_points_path))

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "stl_path": str(stl_path),
            "scene_manifest_path": str(scene_manifest_path),
            "stl_sha256": sha256_for_file(stl_path),
            "scene_manifest_sha256": sha256_for_file(scene_manifest_path),
            "source_project": scene_manifest.get("source_project"),
            "coordinate_space": scene_manifest.get("coordinate_space") or "unrecorded",
        },
        "mesh_summary": {
            "triangle_count": int(len(triangles)),
            "point_sample_count": int(len(vertices)),
            "bounds_mm": bounds_summary(vertices),
        },
        "plane_intersections": plane_results,
        "segment_measurements": segment_results,
        "candidate_surface_points": candidate_results,
        "geometry_status": {
            "plane_intersection_ready": all(item["segment_count"] > 0 for item in plane_results),
            "candidate_projection_ready": bool(candidate_results),
            "navigation_ready": False,
            "doctor_review_status": "not_reviewed",
        },
        "data_boundary": DATA_BOUNDARY,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "geometry_manifest_path": str(output_path),
        "plane_count": len(plane_results),
        "ready_plane_count": sum(1 for item in plane_results if item["segment_count"] > 0),
        "candidate_count": len(candidate_results),
        "sha256": sha256_for_file(output_path),
    }


def read_binary_stl_triangles(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"STL is too small: {path}")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if len(data) < expected_size:
        raise ValueError(f"Binary STL is truncated: {path}")
    triangles = np.zeros((triangle_count, 3, 3), dtype=np.float64)
    offset = 84
    for index in range(triangle_count):
        offset += 12
        values = struct.unpack_from("<9f", data, offset)
        triangles[index] = np.asarray(values, dtype=np.float64).reshape((3, 3))
        offset += 38
    return triangles


def read_scene_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Scene manifest JSON must be an object")
    evidence = payload.get("three_d_evidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("scene_manifest"), dict):
        return dict(evidence["scene_manifest"])
    if isinstance(payload.get("scene_manifest"), dict):
        return dict(payload["scene_manifest"])
    return payload


def plane_intersection_result(*, index: int, plane: Any, triangles: np.ndarray) -> dict[str, Any]:
    if not isinstance(plane, dict):
        raise ValueError(f"Plane {index} is not an object")
    origin = point_array(plane.get("origin_mm"))
    normal = point_array(plane.get("normal"))
    if origin is None or normal is None:
        return {
            "id": str(plane.get("id") or f"plane_{index + 1}"),
            "label": str(plane.get("label") or f"Plane {index + 1}"),
            "status": "missing_origin_or_normal",
            "segment_count": 0,
            "centroid_mm": None,
            "polyline_length_mm": 0.0,
            "sample_points_mm": [],
        }
    normal = normalize(normal)
    segments: list[tuple[np.ndarray, np.ndarray]] = []
    for triangle in triangles:
        segment = intersect_triangle_with_plane(triangle, origin, normal)
        if segment is not None:
            segments.append(segment)
    points = np.asarray([point for segment in segments for point in segment], dtype=np.float64)
    centroid = points.mean(axis=0) if len(points) else None
    return {
        "id": str(plane.get("id") or f"plane_{index + 1}"),
        "label": str(plane.get("label") or f"Plane {index + 1}"),
        "status": "ready" if segments else "no_intersection",
        "origin_mm": float_list(origin),
        "normal": float_list(normal),
        "segment_count": len(segments),
        "centroid_mm": float_list(centroid) if centroid is not None else None,
        "polyline_length_mm": round(sum(float(np.linalg.norm(a - b)) for a, b in segments), 4),
        "sample_points_mm": [float_list(point) for point in points[:24]],
    }


def intersect_triangle_with_plane(
    triangle: np.ndarray,
    origin: np.ndarray,
    normal: np.ndarray,
    *,
    eps: float = 1e-7,
) -> tuple[np.ndarray, np.ndarray] | None:
    distances = np.dot(triangle - origin, normal)
    if np.all(distances > eps) or np.all(distances < -eps):
        return None
    points: list[np.ndarray] = []
    for start, end in ((0, 1), (1, 2), (2, 0)):
        d0 = float(distances[start])
        d1 = float(distances[end])
        p0 = triangle[start]
        p1 = triangle[end]
        if abs(d0) <= eps:
            points.append(p0)
        if d0 * d1 < -eps:
            t = d0 / (d0 - d1)
            points.append(p0 + t * (p1 - p0))
        elif abs(d1) <= eps:
            points.append(p1)
    unique = unique_points(points)
    if len(unique) < 2:
        return None
    return unique[0], unique[1]


def segment_lengths_from_planes(plane_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index in range(len(plane_results) - 1):
        a = point_array(plane_results[index].get("centroid_mm"))
        b = point_array(plane_results[index + 1].get("centroid_mm"))
        if a is None or b is None:
            length = None
            status = "missing_intersection_centroid"
        else:
            length = round(float(np.linalg.norm(b - a)), 4)
            status = "ready"
        results.append(
            {
                "id": f"S{index}",
                "from_plane_id": plane_results[index]["id"],
                "to_plane_id": plane_results[index + 1]["id"],
                "length_mm": length,
                "measurement_mode": "intersection_centroid_to_centroid",
                "status": status,
            }
        )
    return results


def nearest_surface_points(vertices: np.ndarray, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        point = point_array(candidate.get("point_mm"))
        if point is None:
            continue
        distances = np.linalg.norm(vertices - point, axis=1)
        nearest_index = int(np.argmin(distances))
        nearest = vertices[nearest_index]
        results.append(
            {
                "candidate_id": str(candidate.get("id") or candidate.get("candidate_id") or f"candidate_{index + 1}"),
                "input_point_mm": float_list(point),
                "nearest_surface_point_mm": float_list(nearest),
                "distance_mm": round(float(distances[nearest_index]), 4),
                "status": "unregistered_reference_only",
            }
        )
    return results


def read_candidate_points(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        return [dict(item) for item in payload["candidates"] if isinstance(item, dict)]
    raise ValueError("Candidate points JSON must be a list or an object with a candidates list")


def point_array(value: Any) -> np.ndarray | None:
    if isinstance(value, list | tuple) and len(value) >= 3:
        numbers = [float(value[0]), float(value[1]), float(value[2])]
        if all(math.isfinite(item) for item in numbers):
            return np.asarray(numbers, dtype=np.float64)
    if isinstance(value, dict):
        try:
            numbers = [float(value["x"]), float(value["y"]), float(value["z"])]
        except (KeyError, TypeError, ValueError):
            return None
        if all(math.isfinite(item) for item in numbers):
            return np.asarray(numbers, dtype=np.float64)
    return None


def normalize(value: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(value))
    if norm <= 0:
        raise ValueError("Plane normal must be non-zero")
    return value / norm


def unique_points(points: list[np.ndarray], *, precision: int = 6) -> list[np.ndarray]:
    unique: dict[tuple[float, float, float], np.ndarray] = {}
    for point in points:
        key = tuple(round(float(axis), precision) for axis in point)
        unique.setdefault(key, point)
    return list(unique.values())


def bounds_summary(vertices: np.ndarray) -> dict[str, list[float]]:
    return {
        "min": float_list(vertices.min(axis=0)),
        "max": float_list(vertices.max(axis=0)),
        "center": float_list((vertices.min(axis=0) + vertices.max(axis=0)) / 2.0),
        "size": float_list(vertices.max(axis=0) - vertices.min(axis=0)),
    }


def float_list(value: np.ndarray) -> list[float]:
    return [round(float(item), 4) for item in value.tolist()]


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
