from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from scripts.convert_d036_to_nnunet import convert_d036_to_nnunet


def test_convert_d036_to_nnunet_writes_mandible_binary_dataset(tmp_path: Path) -> None:
    manifest = _write_d036_fixture(tmp_path)
    output_root = tmp_path / "derived" / "nnunet"

    summary = convert_d036_to_nnunet(
        project_root=tmp_path,
        manifest_path=manifest,
        output_root=output_root,
        dataset_id=136,
        dataset_name="D036Mandible",
        label_mode="mandible_binary",
        max_cases=None,
        overwrite=True,
        dry_run=False,
    )

    dataset_dir = output_root / "nnUNet_raw" / "Dataset136_D036Mandible"
    dataset_json = json.loads((dataset_dir / "dataset.json").read_text(encoding="utf-8"))
    assert summary["selected_cases"] == 2
    assert summary["converted_cases"] == 2
    assert dataset_json["labels"] == {"background": 0, "mandible_or_lower_jawbone": 1}
    assert (dataset_dir / "imagesTr" / "ToothFairy2F_001_0000.nii.gz").exists()
    label_path = dataset_dir / "labelsTr" / "ToothFairy2F_001.nii.gz"
    assert label_path.exists()
    label_data = _read_sitk_array(label_path)
    assert set(np.unique(label_data).tolist()) == {0, 1}
    assert int(np.count_nonzero(label_data == 1)) == 8
    assert "run_training" in summary["commands"]["train_fold0"]

    with open(summary["conversion_manifest_path"], encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["status"] for row in rows] == ["converted", "converted"]


def test_convert_d036_to_nnunet_writes_upper_lower_jaw2_dataset(tmp_path: Path) -> None:
    manifest = _write_d036_fixture(tmp_path)
    output_root = tmp_path / "derived" / "nnunet"

    summary = convert_d036_to_nnunet(
        project_root=tmp_path,
        manifest_path=manifest,
        output_root=output_root,
        dataset_id=136,
        dataset_name="D036Jawbones",
        label_mode="jaw2",
        max_cases=1,
        overwrite=True,
        dry_run=False,
    )

    dataset_dir = output_root / "nnUNet_raw" / "Dataset136_D036Jawbones"
    dataset_json = json.loads((dataset_dir / "dataset.json").read_text(encoding="utf-8"))
    assert dataset_json["labels"] == {
        "background": 0,
        "maxilla_or_upper_jawbone": 1,
        "mandible_or_lower_jawbone": 2,
    }
    label_data = _read_sitk_array(dataset_dir / "labelsTr" / "ToothFairy2F_001.nii.gz")
    assert set(np.unique(label_data).tolist()) == {0, 1, 2}
    assert int(np.count_nonzero(label_data == 1)) == 8
    assert int(np.count_nonzero(label_data == 2)) == 8
    assert "upper/lower jawbone" in summary["data_boundary"]


def test_convert_d036_to_nnunet_dry_run_reports_available_cases(tmp_path: Path) -> None:
    manifest = _write_d036_fixture(tmp_path)

    summary = convert_d036_to_nnunet(
        project_root=tmp_path,
        manifest_path=manifest,
        output_root=tmp_path / "nnunet",
        dataset_id=136,
        dataset_name="D036Mandible",
        label_mode="mandible_binary",
        max_cases=1,
        dry_run=True,
    )

    assert summary["dry_run"] is True
    assert summary["available_local_pairs"] == 2
    assert summary["selected_cases"] == 1
    assert summary["converted_cases"] == 0


def _write_d036_fixture(tmp_path: Path) -> Path:
    raw_root = (
        tmp_path / "research" / "datasets" / "public-candidates" / "d036_toothfairy2" / "raw" / "Dataset112_ToothFairy2"
    )
    images_dir = raw_root / "imagesTr"
    labels_dir = raw_root / "labelsTr"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    rows: list[dict[str, str]] = []
    for index in range(1, 3):
        case_id = f"ToothFairy2F_{index:03d}"
        image_path = images_dir / f"{case_id}_0000.mha"
        label_path = labels_dir / f"{case_id}.mha"
        _write_sitk_volume(image_path, np.zeros((6, 6, 6), dtype=np.float32))
        label = np.zeros((6, 6, 6), dtype=np.uint8)
        label[1:3, 1:3, 1:3] = 1
        label[4:6, 4:6, 4:6] = 2
        _write_sitk_volume(label_path, label)
        rows.append(
            {
                "case_id": case_id,
                "input_path": str(image_path.relative_to(tmp_path)),
                "mask_path": str(label_path.relative_to(tmp_path)),
                "label_source": "fixture",
            }
        )
    manifest = (
        tmp_path
        / "research"
        / "datasets"
        / "public-candidates"
        / "d036_toothfairy2"
        / "derived"
        / "manifests"
        / "d036_toothfairy2_manifest.csv"
    )
    manifest.parent.mkdir(parents=True)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "input_path", "mask_path", "label_source"])
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def _write_sitk_volume(path: Path, data: np.ndarray) -> None:
    import SimpleITK as sitk

    image = sitk.GetImageFromArray(data)
    image.SetSpacing((0.3, 0.3, 0.3))
    sitk.WriteImage(image, str(path))


def _read_sitk_array(path: Path) -> np.ndarray:
    import SimpleITK as sitk

    return sitk.GetArrayFromImage(sitk.ReadImage(str(path)))
