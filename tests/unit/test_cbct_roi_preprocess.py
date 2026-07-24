from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from osteo_vision_core.preprocess.cbct_roi import build_cbct_anatomy_roi


def _write_npz(path: Path, *, include_label: bool = True, image_nonzero: bool = True) -> None:
    image = np.zeros((10, 12, 14), dtype=np.float32)
    if image_nonzero:
        image[2:8, 3:9, 4:10] = 120.0
    if include_label:
        label = np.zeros_like(image, dtype=np.int16)
        label[3:6, 4:7, 5:8] = 2
        np.savez_compressed(path, image=image, label=label)
    else:
        np.savez_compressed(path, image=image)


def test_build_cbct_anatomy_roi_uses_external_anatomy_mask_and_writes_manifest(tmp_path: Path) -> None:
    input_path = tmp_path / "case_a.npz"
    mask_path = tmp_path / "case_a_anatomy.npy"
    _write_npz(input_path)
    anatomy = np.zeros((10, 12, 14), dtype=np.int16)
    anatomy[1:4, 2:5, 3:6] = 1
    np.save(mask_path, anatomy)

    result = build_cbct_anatomy_roi(
        input_path,
        tmp_path / "roi",
        case_id="case_a",
        anatomy_mask_path=mask_path,
        foreground_labels=[1],
        margin_voxels=(1, 2, 3),
    )

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "osteo-vision-cbct-anatomy-roi-v1"
    assert manifest["case_id"] == "case_a"
    assert manifest["roi_source"] == "external_anatomy_mask"
    assert manifest["bbox_zyx"] == [0, 0, 0, 5, 7, 9]
    assert manifest["crop_shape_zyx"] == [5, 7, 9]
    assert manifest["label_values"] == [0, 2]
    assert manifest["anatomy_label_values"] == [0, 1]
    assert "non-target-domain" in manifest["dataset_boundary"]
    assert "not intraoperative ICG" in manifest["medical_boundary"]

    with np.load(result.roi_npz_path) as payload:
        assert payload["image"].shape == (5, 7, 9)
        assert payload["label"].shape == (5, 7, 9)
        assert payload["anatomy_mask"].shape == (5, 7, 9)
        assert payload["roi_bbox_zyx"].tolist() == [0, 0, 0, 5, 7, 9]


def test_build_cbct_anatomy_roi_falls_back_to_input_label(tmp_path: Path) -> None:
    input_path = tmp_path / "case_b.npz"
    _write_npz(input_path)

    result = build_cbct_anatomy_roi(input_path, tmp_path / "roi", margin_voxels=1)

    manifest = result.manifest
    assert manifest["roi_source"] == "input_label"
    assert manifest["bbox_zyx"] == [2, 3, 4, 7, 8, 9]
    assert manifest["foreground_voxel_count"] == 27
    assert manifest["warnings"] == []


def test_build_cbct_anatomy_roi_uses_image_nonzero_fallback_without_label(tmp_path: Path) -> None:
    input_path = tmp_path / "case_c.npz"
    _write_npz(input_path, include_label=False)

    result = build_cbct_anatomy_roi(input_path, tmp_path / "roi", margin_voxels=0)

    manifest = result.manifest
    assert manifest["roi_source"] == "image_nonzero_fallback"
    assert manifest["bbox_zyx"] == [2, 3, 4, 8, 9, 10]
    assert [warning["code"] for warning in manifest["warnings"]] == ["cbct_roi_image_nonzero_fallback"]
    with np.load(result.roi_npz_path) as payload:
        assert "label" not in payload.files


def test_build_cbct_anatomy_roi_uses_center_crop_when_no_foreground(tmp_path: Path) -> None:
    input_path = tmp_path / "case_d.npz"
    _write_npz(input_path, include_label=False, image_nonzero=False)

    result = build_cbct_anatomy_roi(
        input_path,
        tmp_path / "roi",
        fallback_crop_shape=(4, 6, 8),
    )

    manifest = result.manifest
    assert manifest["roi_source"] == "center_crop_fallback"
    assert manifest["bbox_zyx"] == [3, 3, 3, 7, 9, 11]
    assert [warning["code"] for warning in manifest["warnings"]] == [
        "cbct_roi_image_nonzero_fallback",
        "cbct_roi_center_crop_fallback",
    ]


def test_build_cbct_anatomy_roi_rejects_shape_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "case_e.npz"
    _write_npz(input_path)
    np.save(tmp_path / "bad_mask.npy", np.ones((3, 3, 3), dtype=np.int16))

    with pytest.raises(ValueError, match="does not match image shape"):
        build_cbct_anatomy_roi(
            input_path,
            tmp_path / "roi",
            anatomy_mask_path=tmp_path / "bad_mask.npy",
        )
