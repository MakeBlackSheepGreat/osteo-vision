from __future__ import annotations

import json

import nibabel as nib
import numpy as np

from scripts.convert_d024_to_nnunet import convert_d024_to_nnunet
from osteo_vision_core.datasets.d024 import build_fold_splits, build_nnunet_dataset_json, d024_task_spec, remap_label_array


def test_jaw_roi_label_remap_keeps_only_selected_structures() -> None:
    spec = d024_task_spec("jaw-roi")
    source = np.array([[0, 1, 2, 3], [35, 36, 37, 38]], dtype=np.int16)

    remapped = remap_label_array(source, spec.original_to_target)

    assert remapped.tolist() == [[0, 1, 2, 0], [3, 4, 5, 6]]


def test_full_39_spec_uses_metadata_labels() -> None:
    metadata = {"labels": {"0": "background", "1": "maxilla", "2": "mandible"}}
    spec = d024_task_spec("full-39", metadata)
    payload = build_nnunet_dataset_json(spec, 100, metadata)

    assert payload["labels"] == {"background": 0, "maxilla": 1, "mandible": 2}
    assert payload["channel_names"] == {"0": "CT"}
    assert payload["file_ending"] == ".nii.gz"


def test_build_fold_splits_is_deterministic_and_complete() -> None:
    cases = [f"d024_{index:04d}" for index in range(10)]

    first = build_fold_splits(cases, folds=5)
    second = build_fold_splits(list(reversed(cases)), folds=5)

    assert first == second
    assert len(first) == 5
    assert sorted(first[0]["train"] + first[0]["val"]) == cases
    assert all(len(split["val"]) == 2 for split in first)


def test_convert_d024_to_nnunet_tiny_fixture(tmp_path) -> None:
    raw_dir = tmp_path / "d024" / "raw" / "DentVoxel_Dataset"
    image_dir = raw_dir / "image"
    label_dir = raw_dir / "label"
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    metadata = {
        "name": "DentVoxel",
        "version": "1.0",
        "license": "CC BY",
        "labels": {
            "0": "background",
            "1": "maxilla",
            "2": "mandible",
            "35": "r_mandibular_canal",
            "36": "l_mandibular_canal",
            "37": "r_maxillary_sinus",
            "38": "l_maxillary_sinus",
        },
        "acquisition_protocol": {"spacing_mm": [0.3, 0.3, 0.3]},
    }
    (raw_dir / "dataset_DentVoxel.json").write_text(json.dumps(metadata), encoding="utf-8")
    affine = np.eye(4)
    image = nib.Nifti1Image(np.ones((3, 3, 3), dtype=np.float32), affine)
    label_values = np.array(
        [
            [[0, 1, 35], [36, 37, 38], [2, 3, 0]],
            [[0, 0, 0], [1, 2, 35], [36, 37, 38]],
            [[3, 3, 3], [0, 0, 0], [1, 2, 35]],
        ],
        dtype=np.int16,
    )
    nib.save(image, image_dir / "img0001.nii.gz")
    nib.save(nib.Nifti1Image(label_values, affine), label_dir / "label0001.nii.gz")

    summary = convert_d024_to_nnunet(dataset_dir=tmp_path / "d024", output_root=tmp_path / "nnunet", task="jaw-roi")
    dataset_output = tmp_path / "nnunet" / "nnUNet_raw" / "Dataset124_DentVoxelJawROI"
    converted_label = np.asanyarray(nib.load(str(dataset_output / "labelsTr" / "d024_0001.nii.gz")).dataobj)
    dataset_json = json.loads((dataset_output / "dataset.json").read_text(encoding="utf-8"))

    assert summary["case_count"] == 1
    assert sorted(np.unique(converted_label).astype(int).tolist()) == [0, 1, 2, 3, 4, 5, 6]
    assert dataset_json["numTraining"] == 1
    assert (dataset_output / "splits_final.json").exists()
    assert "nnUNet_raw" in summary["commands"]["environment"]
