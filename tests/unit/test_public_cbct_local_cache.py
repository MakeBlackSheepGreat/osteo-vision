from __future__ import annotations

import numpy as np

from scripts.build_public_cbct_local_training_cache import (
    CACHE_MANIFEST_FIELDS,
    inspect_npz_cache,
    normalize_image,
    parse_target_shape,
    resize_volume,
    write_cache_manifest,
    write_npz_cache,
)
from src.datasets.manifests import read_manifest


def test_parse_target_shape_accepts_common_formats() -> None:
    assert parse_target_shape("64x64x32") == (64, 64, 32)
    assert parse_target_shape("32,32,16") == (32, 32, 16)


def test_normalize_image_is_bounded() -> None:
    image = np.arange(27, dtype=np.float32).reshape(3, 3, 3)
    normalized = normalize_image(image)
    assert normalized.shape == image.shape
    assert float(normalized.min()) >= -1.0
    assert float(normalized.max()) <= 1.0


def test_write_npz_cache_keeps_expected_fields(tmp_path) -> None:
    image = np.arange(27, dtype=np.float32).reshape(3, 3, 3)
    label = np.zeros((3, 3, 3), dtype=np.int16)
    label[1:] = 2
    cache_path = tmp_path / "case_64x64x64.npz"

    meta = write_npz_cache(image, label, cache_path, (2, 2, 2), spacing=(0.3, 0.3, 0.3))
    inspected = inspect_npz_cache(cache_path)

    assert cache_path.exists()
    assert meta["target_shape"] == "2x2x2"
    assert inspected["target_shape"] == "2x2x2"
    with np.load(cache_path) as payload:
        assert set(["image", "label", "original_shape", "target_shape", "original_spacing", "label_values"]).issubset(
            payload.files
        )
        assert payload["image"].shape == (2, 2, 2)
        assert payload["image"].dtype == np.float16
        assert payload["label"].dtype == np.int16


def test_resize_volume_uses_requested_shape() -> None:
    volume = np.ones((2, 3, 4), dtype=np.float32)
    resized = resize_volume(volume, (4, 6, 8), order=1)
    assert resized.shape == (4, 6, 8)


def test_cache_manifest_is_framework_readable(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    cache_path = tmp_path / "case.npz"
    rows = [
        {
            "case_id": "case_001",
            "input_path": str(cache_path),
            "label": "available",
            "task_type": "segmentation",
            "input_type": "npz_roi",
            "modality": "cbct",
            "mask_path": str(cache_path),
            "split": "train",
            "fold": 1,
            "label_source": "unit-test",
            "dataset_id": "D000",
            "cache_path": str(cache_path),
            "target_shape": "2x2x2",
        }
    ]

    info = write_cache_manifest(rows, manifest_path)
    read_rows, read_info = read_manifest(manifest_path)

    assert info["row_count"] == 1
    assert read_info["manifest_version"] == "v2"
    assert read_rows[0]["input_type"] == "npz_roi"
    assert read_rows[0]["input_path"] == str(cache_path)
    assert read_rows[0]["mask_path"] == str(cache_path)
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        header = handle.readline().strip().split(",")
    assert header == CACHE_MANIFEST_FIELDS
