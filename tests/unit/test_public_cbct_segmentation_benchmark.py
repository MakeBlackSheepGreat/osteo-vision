from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from scripts.benchmark_public_cbct_segmentation_models import (
    DEFAULT_TOP_MODELS,
    DatasetSpec,
    ModelCandidate,
    binary_dice_iou,
    build_segmentation_loss,
    combined_model_catalog,
    foreground_sampling_weights,
    lesion_metrics_from_accumulator,
    load_manifest_rows,
    parse_model_ids,
    selected_dataset_specs,
    train_and_evaluate_on_dataset,
    write_summary_reports,
)


def test_combined_catalog_tracks_expected_21_candidates() -> None:
    catalog = combined_model_catalog()

    assert len(catalog) == 21
    assert "nnunet_v2_plainconv_external" in catalog
    assert "monai_segresnetds" in catalog
    assert "segmamba_multiscale_proxy" in catalog
    assert catalog["nnunet_v2_plainconv_external"].family == "external_nnunet"


def test_default_and_all_model_selection() -> None:
    assert parse_model_ids("") == DEFAULT_TOP_MODELS
    assert len(parse_model_ids("all")) == 21


def test_selected_dataset_specs_cover_three_local_tasks() -> None:
    specs = selected_dataset_specs("all")

    assert [spec.dataset_key for spec in specs] == ["d024_jaw_roi", "d036_anatomy_roi", "d025_lesion_roi"]
    assert {spec.task_group for spec in selected_dataset_specs("anatomy_roi")} == {"anatomy_roi"}
    assert [spec.dataset_key for spec in selected_dataset_specs("lesion_roi")] == ["d025_lesion_roi"]


def test_local_manifests_exist_and_npz_fields_are_readable() -> None:
    expected_counts = {"D024": 100, "D025": 262, "D036": 480}

    for spec in selected_dataset_specs("all"):
        assert spec.manifest_path.exists(), spec.manifest_path
        rows = load_manifest_rows(spec)
        assert len(rows) == expected_counts[spec.dataset_id]
        cache_path = Path(rows[0]["cache_path"])
        assert cache_path.exists(), cache_path
        with np.load(cache_path) as payload:
            assert {"image", "label"} <= set(payload.files)
            assert payload["image"].shape == (64, 64, 64)
            assert payload["label"].shape == (64, 64, 64)


def test_binary_dice_iou_handles_empty_and_overlap_cases() -> None:
    empty = np.zeros((2, 2), dtype=bool)
    assert binary_dice_iou(empty, empty)["dice"] is None

    pred = np.array([[1, 1], [0, 0]], dtype=bool)
    target = np.array([[1, 0], [1, 0]], dtype=bool)
    score = binary_dice_iou(pred, target)

    assert score["dice"] == 0.5
    assert score["iou"] == 1 / 3
    assert score["target_present"] is True
    assert score["prediction_present"] is True


def test_lesion_metrics_from_accumulator_reports_detection_fields() -> None:
    metrics = lesion_metrics_from_accumulator(
        {
            "tp": 8.0,
            "fp": 2.0,
            "fn": 4.0,
            "target_positive_cases": 3,
            "prediction_positive_cases": 4,
            "detected_positive_cases": 2,
            "target_negative_cases": 5,
            "false_positive_cases": 1,
        }
    )

    assert metrics["lesion_sensitivity"] == 8 / 12
    assert metrics["lesion_precision"] == 0.8
    assert metrics["case_detection_sensitivity"] == 2 / 3
    assert metrics["false_positive_case_rate"] == 0.2
    assert metrics["lesion_false_positive_voxels"] == 2.0
    assert metrics["lesion_false_negative_voxels"] == 4.0


class TinySegModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = torch.nn.Conv3d(1, 2, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


def _write_tiny_npz(path: Path, *, foreground: int) -> None:
    image = np.zeros((4, 4, 4), dtype=np.float32)
    label = np.zeros((4, 4, 4), dtype=np.int16)
    if foreground > 0:
        label.reshape(-1)[:foreground] = 1
        image.reshape(-1)[:foreground] = 1.0
    np.savez_compressed(path, image=image, label=label)


def test_train_loop_runs_across_epochs_and_reports_schema(tmp_path) -> None:
    paths = [tmp_path / "case_1.npz", tmp_path / "case_2.npz"]
    _write_tiny_npz(paths[0], foreground=8)
    _write_tiny_npz(paths[1], foreground=4)
    rows = [
        {"case_id": f"case_{index}", "cache_path": str(path), "split": "train"}
        for index, path in enumerate(paths, start=1)
    ]
    spec = DatasetSpec(
        dataset_key="unit_lesion",
        dataset_id="UNIT",
        task_group="lesion_roi",
        task_name="tiny",
        display_name="Tiny Lesion",
        manifest_path=tmp_path / "manifest.csv",
        metric_profile="lesion",
        medical_boundary="unit",
    )
    candidate = ModelCandidate(
        model_id="tiny",
        display_name="Tiny",
        family="unit",
        rationale="unit",
        source_url="unit",
        constructor=lambda shape, n: TinySegModel(),
    )
    data_info = {
        "target_shape": [4, 4, 4],
        "n_classes": 2,
        "foreground_labels": [1],
        "foreground_voxel_fraction": 12 / 128,
        "label_voxel_counts": [116, 12],
    }

    result = train_and_evaluate_on_dataset(
        candidate,
        spec,
        rows,
        rows,
        data_info,
        device=torch.device("cpu"),
        max_train_batches=5,
        max_val_cases=2,
        batch_size=1,
        learning_rate=1e-2,
        seed=1,
        loss_name="dice_ce",
        max_epochs=10,
        foreground_oversample_ratio=0.0,
        class_weighting="none",
        target_labels="foreground",
        overfit_cases=0,
    )

    assert result["status"] == "completed"
    assert result["train_batches"] == 5
    assert result["epochs_seen"] >= 3
    assert result["samples_seen"] == 5
    assert result["loss_name"] == "dice_ce"
    assert result["foreground_voxel_fraction"] == 12 / 128
    assert "prediction_positive_fraction" in result
    assert "target_positive_fraction" in result


def test_segmentation_losses_are_finite_for_sparse_foreground() -> None:
    logits = torch.randn(1, 2, 4, 4, 4)
    target = torch.zeros((1, 4, 4, 4), dtype=torch.long)
    target.reshape(-1)[0] = 1
    data_info = {"n_classes": 2, "foreground_labels": [1], "label_voxel_counts": [63, 1]}

    for loss_name in ["ce", "dice_ce", "dice_focal", "tversky_focal"]:
        loss_fn = build_segmentation_loss(
            loss_name=loss_name,
            data_info=data_info,
            target_labels="foreground",
            class_weighting="sqrt_inverse",
            device=torch.device("cpu"),
        )
        loss = loss_fn(logits, target)
        assert torch.isfinite(loss), loss_name


def test_foreground_sampling_weights_prioritize_richer_foreground_cases() -> None:
    rows = [
        {"foreground_voxel_fraction": 0.001, "label_counts": {0: 999, 1: 1}},
        {"foreground_voxel_fraction": 0.1, "label_counts": {0: 900, 1: 100}},
    ]

    weights = foreground_sampling_weights(rows, foreground_oversample_ratio=1.0)

    assert weights[1] > weights[0]


def test_report_path_convention(tmp_path) -> None:
    payload = {
        "run_id": "unit",
        "data": {
            "d024_jaw_roi": {
                "display_name": "D024 DentVoxel jaw ROI",
                "case_count": 100,
                "train_count": 80,
                "val_count": 20,
                "n_classes": 7,
            }
        },
        "config": {
            "catalog_model_count": 21,
            "models": ["monai_segresnetds"],
            "max_train_batches": 1,
            "max_val_cases": 1,
            "batch_size": 1,
            "loss": "dice_ce",
            "class_weighting": "sqrt_inverse",
            "foreground_oversample_ratio": 0.0,
            "overfit_cases": 0,
        },
        "environment": {"device": "cpu", "cuda_device_name": None, "torch_version": torch.__version__},
        "results": [
            {
                "dataset_key": "d024_jaw_roi",
                "display_name": "MONAI SegResNetDS",
                "status": "completed",
                "foreground_mean_dice": 0.1,
                "foreground_mean_iou": 0.05,
                "lesion_sensitivity": None,
                "lesion_precision": None,
                "parameter_count": 10,
                "train_loss": 1.0,
                "elapsed_seconds": 2.0,
                "peak_memory_mb": None,
            }
        ],
        "rankings": {
            "anatomy_aggregate": [{"model_id": "monai_segresnetds", "mean_anatomy_dice": 0.1}],
            "lesion": [],
        },
        "paths": {"summary_json": "summary.json", "results_csv": "results.csv"},
    }

    paths = write_summary_reports(payload, tmp_path)

    assert paths["zh_report"].endswith("public_cbct_3dataset_segmentation_benchmark_zh.md")
    assert paths["en_report"].endswith("public_cbct_3dataset_segmentation_benchmark_en.md")
    assert "公开 CBCT 三数据集" in Path(paths["zh_report"]).read_text(encoding="utf-8")
    assert "Public CBCT Three-Dataset" in Path(paths["en_report"]).read_text(encoding="utf-8")
