from __future__ import annotations

import json
from pathlib import Path

from tools.build_keyframe_model_selection_summary import build_summary


def test_selection_requires_three_seeds_and_chooses_checkpoint_by_validation(tmp_path: Path) -> None:
    baseline_id = "baseline"
    _write_eval(
        tmp_path / "baseline_test",
        model_id=baseline_id,
        family="baseline_family",
        seed=1,
        split="test",
        dice=0.8,
        iou=0.7,
    )
    for seed, val_dice, test_dice in ((1, 0.82, 0.83), (2, 0.86, 0.84), (3, 0.84, 0.85)):
        model_id = f"candidate_{seed}"
        _write_eval(
            tmp_path / f"candidate_{seed}_val",
            model_id=model_id,
            family="candidate_family",
            seed=seed,
            split="val",
            dice=val_dice,
            iou=val_dice - 0.1,
        )
        _write_eval(
            tmp_path / f"candidate_{seed}_test",
            model_id=model_id,
            family="candidate_family",
            seed=seed,
            split="test",
            dice=test_dice,
            iou=test_dice - 0.1,
        )

    summary = build_summary(tmp_path, baseline_model_id=baseline_id, minimum_seeds=3)

    assert summary["recommendation"]["selected_family"] == "candidate_family"
    assert summary["recommendation"]["selected_model_id"] == "candidate_2"
    assert summary["recommendation"]["runtime_replacement_allowed"] is False
    assert summary["candidate_families"][0]["gates"]["eligible_for_4k_runtime_gate"] is True


def _write_eval(
    directory: Path,
    *,
    model_id: str,
    family: str,
    seed: int,
    split: str,
    dice: float,
    iou: float,
) -> None:
    directory.mkdir(parents=True)
    row = {
        "foreground_mean_dice": dice,
        "foreground_mean_iou": iou,
        "foreground_precision_mean": dice,
        "foreground_recall_mean": dice,
        "boundary_f1_mean": dice,
        "ece": 0.01,
        "brier_score": 0.02,
        "empty_mask_rate": 0.0,
        "over_segmentation_rate": 0.0,
        "video_group_bootstrap": {},
    }
    payload = {
        "split": split,
        "checkpoint_path": str(directory / "model.pt"),
        "checkpoint_sha256": "abc",
        "checkpoint_metadata": {"model_id": model_id, "model_family": family, "training": {"seed": seed}},
        "sample_count": 4,
        "source_group_split": {"leakage_detected": False},
        "recommendation": {"threshold": 0.5, "selected_row": row},
        "inference_benchmark": {
            "mean_latency_ms": 2.0,
            "p95_latency_ms": 3.0,
            "peak_gpu_memory_mb": 10.0,
            "parameter_count": 100,
        },
    }
    (directory / "keyframe_threshold_eval.json").write_text(json.dumps(payload), encoding="utf-8")
