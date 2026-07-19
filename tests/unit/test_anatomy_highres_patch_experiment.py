from __future__ import annotations

from pathlib import Path

import numpy as np

from scripts.anatomy_highres_patch_experiment import (
    ANATOMY_LABELS,
    PATCH_MANIFEST_FIELDS,
    SourceCase,
    build_patch_cache,
    choose_center,
    crop_patch,
    patch_cache_dir,
    patch_data_info,
    read_patch_manifest,
    remap_label,
    sampling_mode_for_index,
)


def test_d036_label_mapping_merges_to_common_anatomy_roi() -> None:
    label = np.asarray([0, 1, 2, 3, 4, 5, 6, 7, 11], dtype=np.int16)

    mapped = remap_label("D036", label)

    assert mapped.tolist() == [0, 2, 1, 4, 3, 6, 5, 0, 0]
    assert set(np.unique(mapped).tolist()) <= set(ANATOMY_LABELS)


def test_coarse3_label_mapping_merges_laterality_and_jaw_parts() -> None:
    label = np.asarray([0, 1, 2, 3, 4, 5, 6, 7, 11], dtype=np.int16)

    mapped_d024 = remap_label("D024", label, label_mode="coarse3")
    mapped_d036 = remap_label("D036", label, label_mode="coarse3")

    assert mapped_d024.tolist() == [0, 1, 1, 2, 2, 3, 3, 0, 0]
    assert mapped_d036.tolist() == [0, 1, 1, 2, 2, 3, 3, 0, 0]


def test_anatomy4_label_mapping_merges_laterality_but_keeps_jaw_parts() -> None:
    label = np.asarray([0, 1, 2, 3, 4, 5, 6, 7, 11], dtype=np.int16)

    mapped_d024 = remap_label("D024", label, label_mode="anatomy4")
    mapped_d036 = remap_label("D036", label, label_mode="anatomy4")

    assert mapped_d024.tolist() == [0, 1, 2, 3, 3, 4, 4, 0, 0]
    assert mapped_d036.tolist() == [0, 2, 1, 3, 3, 4, 4, 0, 0]


def test_d024_label_mapping_keeps_jaw_roi_labels_only() -> None:
    label = np.asarray([0, 1, 2, 3, 4, 5, 6, 7, 35], dtype=np.int16)

    mapped = remap_label("D024", label)

    assert mapped.tolist() == [0, 1, 2, 3, 4, 5, 6, 0, 0]


def test_sampling_schedule_matches_fixed_foreground_small_random_ratio() -> None:
    modes = [sampling_mode_for_index(index) for index in range(8)]

    assert modes == ["foreground", "foreground", "small", "random", "foreground", "foreground", "small", "random"]
    assert [sampling_mode_for_index(index, "small50") for index in range(4)] == [
        "small",
        "foreground",
        "small",
        "random",
    ]
    assert [sampling_mode_for_index(index, "small75") for index in range(4)] == [
        "small",
        "foreground",
        "small",
        "small",
    ]
    assert [sampling_mode_for_index(index, "class_cycle", label_mode="coarse3") for index in range(4)] == [
        "foreground",
        "label_1",
        "label_2",
        "label_3",
    ]
    assert [sampling_mode_for_index(index, "class_cycle", label_mode="anatomy4") for index in range(5)] == [
        "foreground",
        "label_1",
        "label_2",
        "label_3",
        "label_4",
    ]
    assert [sampling_mode_for_index(index, "small_cycle", label_mode="anatomy4") for index in range(5)] == [
        "label_3",
        "label_4",
        "small",
        "foreground",
        "random",
    ]
    assert [sampling_mode_for_index(index, "small_cycle", label_mode="anatomy6") for index in range(7)] == [
        "label_3",
        "label_4",
        "label_5",
        "label_6",
        "small",
        "foreground",
        "random",
    ]
    assert [sampling_mode_for_index(index, "canal_focus", label_mode="anatomy6") for index in range(8)] == [
        "label_3",
        "label_4",
        "label_3",
        "label_4",
        "label_5",
        "label_6",
        "foreground",
        "random",
    ]


def test_patch_cache_dir_isolated_by_sampling_strategy(tmp_path) -> None:
    default_dir = patch_cache_dir(tmp_path, "D024", (8, 8, 8), "anatomy6", "default")
    focused_dir = patch_cache_dir(tmp_path, "D024", (8, 8, 8), "anatomy6", "small_cycle")

    assert default_dir != focused_dir
    assert default_dir.name == "anatomy_roi_8x8x8"
    assert focused_dir.name == "anatomy_roi_8x8x8_small_cycle"


def test_choose_center_prioritizes_requested_small_structure() -> None:
    label = np.zeros((8, 8, 8), dtype=np.int16)
    label[6, 5, 4] = 3

    center = choose_center(label, (4, 4, 4), "small", np.random.default_rng(1))

    assert center == (6, 5, 4)


def test_choose_center_supports_specific_label_sampling() -> None:
    label = np.zeros((8, 8, 8), dtype=np.int16)
    label[1, 2, 3] = 1
    label[6, 5, 4] = 3

    center = choose_center(label, (4, 4, 4), "label_3", np.random.default_rng(1))

    assert center == (6, 5, 4)


def test_crop_patch_pads_at_volume_boundary() -> None:
    volume = np.ones((3, 3, 3), dtype=np.float32)

    patch, origin = crop_patch(volume, (0, 0, 0), (4, 4, 4), fill_value=0)

    assert patch.shape == (4, 4, 4)
    assert origin == (-2, -2, -2)
    assert float(patch.sum()) == 8.0


def _write_pair(image_path: Path, label_path: Path) -> None:
    import nibabel as nib

    image = np.zeros((12, 12, 12), dtype=np.float32)
    label = np.zeros((12, 12, 12), dtype=np.int16)
    image[4:9, 4:9, 4:9] = 10.0
    label[4:9, 4:9, 4:9] = 1
    label[6, 6, 6] = 3
    nib.save(nib.Nifti1Image(image, affine=np.eye(4)), str(image_path))
    nib.save(nib.Nifti1Image(label, affine=np.eye(4)), str(label_path))


def test_build_patch_cache_writes_manifest_and_required_npz_fields(tmp_path) -> None:
    image_path = tmp_path / "case_0000.nii.gz"
    label_path = tmp_path / "case.nii.gz"
    _write_pair(image_path, label_path)
    project_root = tmp_path / "project" / "research" / "datasets" / "public-candidates"
    case = SourceCase(
        case_id="case",
        dataset_id="D024",
        image_path=image_path,
        label_path=label_path,
        label_source="unit",
        source_kind="unit",
    )

    summary = build_patch_cache(
        "D024",
        [case],
        project_root,
        patch_shape=(8, 8, 8),
        patches_per_case=4,
        seed=1,
        force=True,
        max_cases=None,
        label_mode="anatomy6",
    )
    rows = read_patch_manifest(Path(summary["manifest_path"]))

    assert len(rows) == 4
    assert set(PATCH_MANIFEST_FIELDS) <= set(rows[0])
    with np.load(rows[0]["cache_path"]) as payload:
        assert {"image", "label", "case_id", "source_shape", "spacing", "patch_origin", "label_values"} <= set(
            payload.files
        )
        assert payload["image"].shape == (8, 8, 8)
        assert payload["label"].shape == (8, 8, 8)
    info = patch_data_info(rows)
    assert info["n_classes"] == 7
    assert info["foreground_voxel_fraction"] > 0
