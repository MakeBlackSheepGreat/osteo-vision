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
