from __future__ import annotations

import json
import struct

import numpy as np
import pytest

from scripts.export_brp_geometry_manifest import export_brp_geometry_manifest
from scripts.export_cbct_mandible_surface import write_binary_stl


def test_export_brp_geometry_manifest_measures_plane_intersections_and_nearest_point(tmp_path) -> None:
    stl_path = tmp_path / "cube.stl"
    scene_path = tmp_path / "scene.json"
    candidates_path = tmp_path / "candidates.json"
    output_path = tmp_path / "geometry.json"
    vertices, faces = cube_mesh()
    write_binary_stl(stl_path, vertices=vertices, faces=faces)
    scene_path.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-three-d-scene-v1",
                "source_project": "unit-test BRP geometry scene",
                "coordinate_space": "synthetic_mm",
                "review_planes": [
                    {
                        "id": "plane_x_0",
                        "label": "Cube mid plane",
                        "origin_mm": [0.0, 0.0, 0.0],
                        "normal": [1.0, 0.0, 0.0],
                    },
                    {
                        "id": "plane_x_05",
                        "label": "Cube offset plane",
                        "origin_mm": [0.5, 0.0, 0.0],
                        "normal": [1.0, 0.0, 0.0],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps([{"id": "cand_center", "point_mm": [0.2, 0.1, 0.0]}]),
        encoding="utf-8",
    )

    result = export_brp_geometry_manifest(
        stl_path=stl_path,
        scene_manifest_path=scene_path,
        output_path=output_path,
        candidate_points_path=candidates_path,
    )

    assert result["plane_count"] == 2
    assert result["ready_plane_count"] == 2
    assert result["candidate_count"] == 1
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "osteo-vision-brp-geometry-manifest-v1"
    assert manifest["mesh_summary"]["triangle_count"] == 12
    assert manifest["plane_intersections"][0]["segment_count"] > 0
    assert manifest["plane_intersections"][0]["centroid_mm"] == [0.0, 0.0, 0.0]
    assert manifest["segment_measurements"][0]["length_mm"] == pytest.approx(0.5, abs=0.05)
    assert manifest["candidate_surface_points"][0]["candidate_id"] == "cand_center"
    assert manifest["candidate_surface_points"][0]["status"] == "unregistered_reference_only"
    assert manifest["geometry_status"]["navigation_ready"] is False
    assert "not a clinical resection guide" in manifest["data_boundary"]

    with stl_path.open("rb") as handle:
        handle.seek(80)
        triangle_count = struct.unpack("<I", handle.read(4))[0]
    assert triangle_count == 12


def cube_mesh() -> tuple[np.ndarray, np.ndarray]:
    vertices = np.asarray(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [1, 1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
            [1, -1, 1],
            [1, 1, 1],
            [-1, 1, 1],
        ],
        dtype=np.float32,
    )
    faces = np.asarray(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ],
        dtype=np.int64,
    )
    return vertices, faces
