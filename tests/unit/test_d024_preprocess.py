from __future__ import annotations

import csv
import json
import zipfile

from scripts.preprocess_d024_dentvoxel import (
    DEFAULT_REPORT_DIR,
    MANIFEST_FIELDS,
    is_macos_resource_entry,
    pair_image_label_entries,
    write_manifest,
    write_reports,
)
from osteo_vision_core.datasets.manifests import read_manifest


def test_filters_macos_resource_entries() -> None:
    assert is_macos_resource_entry("DentVoxel_Dataset/image/._img0001.nii.gz")
    assert is_macos_resource_entry("__MACOSX/DentVoxel_Dataset/image/img0001.nii.gz")
    assert not is_macos_resource_entry("DentVoxel_Dataset/image/img0001.nii.gz")


def test_pairs_image_and_label_entries() -> None:
    entries = [
        "DentVoxel_Dataset/image/img0001.nii.gz",
        "DentVoxel_Dataset/label/label0001.nii.gz",
        "DentVoxel_Dataset/image/img0002.nii.gz",
        "DentVoxel_Dataset/label/._label0002.nii.gz",
        "DentVoxel_Dataset/label/label0003.nii.gz",
    ]

    images, labels, missing_labels, missing_images = pair_image_label_entries(entries)

    assert sorted(images) == ["0001", "0002"]
    assert sorted(labels) == ["0001", "0003"]
    assert missing_labels == ["0002"]
    assert missing_images == ["0003"]


def test_manifest_fields_are_framework_readable(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    cases = [
        {
            "case_id": "d024_0001",
            "image_path": tmp_path / "img0001.nii.gz",
            "label_path": tmp_path / "label0001.nii.gz",
        }
    ]

    write_manifest(cases, manifest_path)
    rows, info = read_manifest(manifest_path)

    assert rows[0]["case_id"] == "d024_0001"
    assert rows[0]["task_type"] == "segmentation"
    assert rows[0]["input_type"] == "nifti_volume"
    assert rows[0]["mask_path"].endswith("label0001.nii.gz")
    assert info["row_count"] == 1
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == MANIFEST_FIELDS


def test_report_paths_follow_preprocessing_convention(tmp_path) -> None:
    summary = {
        "dataset_name": "DentVoxel",
        "source_zip": "dataset.zip",
        "license": "CC BY",
        "run_timestamp_utc": "2026-06-15T00:00:00+00:00",
        "raw_dataset_dir": "raw/DentVoxel_Dataset",
        "derived_dir": "derived",
        "report_dir": str(DEFAULT_REPORT_DIR),
        "metadata": {"label_count": 39},
        "pairing": {
            "image_count": 100,
            "label_count": 100,
            "paired_count": 100,
            "missing_labels_for_images": [],
            "missing_images_for_labels": [],
        },
        "quality": {
            "error_count": 0,
            "shape_distribution": {"440x440x344": 100},
            "spacing_distribution": {"0.3x0.3x0.3": 100},
        },
        "manifest": {"path": "manifest.csv", "row_count": 100},
        "label_inventory_path": "labels.csv",
        "quality_csv_path": "quality.csv",
        "summary_json_path": "summary.json",
        "preview_count_generated": 5,
    }

    paths = write_reports(summary, tmp_path)

    assert paths["zh_report"].endswith("d024_dentvoxel_preprocessing_zh.md")
    assert paths["en_report"].endswith("d024_dentvoxel_preprocessing_en.md")
    assert (tmp_path / "d024_dentvoxel_preprocessing_zh.md").exists()
    assert (tmp_path / "d024_dentvoxel_preprocessing_en.md").exists()


def test_tiny_zip_fixture_can_skip_resource_files(tmp_path) -> None:
    zip_path = tmp_path / "tiny.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("DentVoxel_Dataset/image/img0001.nii.gz", b"image")
        zf.writestr("DentVoxel_Dataset/image/._img0001.nii.gz", b"resource")
        zf.writestr("DentVoxel_Dataset/dataset_DentVoxel.json", json.dumps({"name": "DentVoxel"}))

    with zipfile.ZipFile(zip_path) as zf:
        names = [info.filename for info in zf.infolist() if not is_macos_resource_entry(info.filename)]

    assert "DentVoxel_Dataset/image/img0001.nii.gz" in names
    assert "DentVoxel_Dataset/image/._img0001.nii.gz" not in names
