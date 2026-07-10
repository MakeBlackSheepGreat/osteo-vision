from __future__ import annotations

import json
import struct

import nibabel as nib
import numpy as np

from scripts.export_cbct_mandible_surface import export_mandible_surface


def test_export_cbct_mandible_surface_writes_stl_and_manifest(tmp_path) -> None:
    data = np.zeros((12, 12, 12), dtype=np.uint8)
    data[3:9, 3:9, 3:9] = 2
    data[5:7, 5:7, 5:7] = 1
    input_path = tmp_path / "synthetic_label.nii.gz"
    output_path = tmp_path / "mandible.stl"
    image = nib.Nifti1Image(data, affine=np.diag([0.3, 0.3, 0.3, 1.0]))
    image.header.set_zooms((0.3, 0.3, 0.3))
    nib.save(image, input_path)

    result = export_mandible_surface(
        input_path=input_path,
        output_path=output_path,
        label_value=2,
        dataset_id="D024",
        case_id="synthetic",
    )

    assert output_path.exists()
    assert result["face_count"] > 0
    assert result["vertex_count"] > 0
    with output_path.open("rb") as handle:
        header = handle.read(80)
        triangle_count = struct.unpack("<I", handle.read(4))[0]
    assert b"Osteo Vision D024 public CBCT mandible surface" in header
    assert triangle_count == result["face_count"]

    manifest_path = output_path.with_suffix(".three_d_evidence.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest["three_d_evidence"]
    scene_manifest = evidence["scene_manifest"]
    scene_manifest_v2 = evidence["scene_manifest_v2"]
    assert manifest["source"]["label_value"] == 2
    assert manifest["source"]["target_domain"] is False
    assert evidence["model_path"] == str(output_path)
    assert evidence["registration_status"] == "unregistered"
    assert evidence["navigation_ready"] is False
    assert "non-target-domain" in evidence["data_boundary"]
    assert "not surgical navigation" in evidence["boundary_note"]
    assert scene_manifest["schema_version"] == "osteo-vision-three-d-scene-v1"
    assert scene_manifest["mandibular_curve"]["label"] == "D024 mandibular reference curve"
    assert len(scene_manifest["mandibular_curve"]["points_mm"]) == 7
    assert len(scene_manifest["review_planes"]) == 3
    assert scene_manifest["review_planes"][0]["status"] == "illustrative_unregistered"
    assert scene_manifest["fibula_reference"]["segment_lengths_mm"] == [29.49, 28.95]
    assert "not physician markups" in scene_manifest["mandibular_curve"]["source"]
    assert scene_manifest_v2["schema_version"] == "osteo-vision-three-d-scene-v2"
    assert scene_manifest_v2["scene"]["navigation_ready"] is False
    assert scene_manifest_v2["nodes"][0]["type"] == "volume"
    assert scene_manifest_v2["nodes"][1]["type"] == "segmentation"
    assert scene_manifest_v2["nodes"][2]["type"] == "model"
    assert scene_manifest_v2["transforms"][1]["status"] == "missing"


def test_export_cbct_mandible_surface_applies_nifti_affine(tmp_path) -> None:
    data = np.zeros((8, 9, 10), dtype=np.uint8)
    data[2:5, 3:7, 4:9] = 2
    input_path = tmp_path / "oriented_label.nii.gz"
    output_path = tmp_path / "oriented_mandible.stl"
    affine = np.array(
        [
            [0.5, 0.0, 0.0, 10.0],
            [0.0, 1.0, 0.0, 20.0],
            [0.0, 0.0, 2.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    image = nib.Nifti1Image(data, affine=affine)
    image.header.set_zooms((0.5, 1.0, 2.0))
    nib.save(image, input_path)

    export_mandible_surface(
        input_path=input_path,
        output_path=output_path,
        label_value=2,
        dataset_id="D024",
        case_id="synthetic_oriented",
    )

    vertices = _read_binary_stl_vertices(output_path)
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    assert 10.7 <= mins[0] <= 10.8
    assert 22.4 <= mins[1] <= 22.6
    assert 37.0 <= mins[2] <= 37.1
    assert 12.2 <= maxs[0] <= 12.3
    assert 26.5 <= maxs[1] <= 26.6
    assert 46.9 <= maxs[2] <= 47.1


def _read_binary_stl_vertices(path) -> np.ndarray:
    vertices: list[tuple[float, float, float]] = []
    with path.open("rb") as handle:
        handle.seek(80)
        triangle_count = struct.unpack("<I", handle.read(4))[0]
        for _ in range(triangle_count):
            handle.read(12)
            for _vertex_index in range(3):
                vertices.append(struct.unpack("<3f", handle.read(12)))
            handle.read(2)
    return np.asarray(vertices, dtype=np.float32)
