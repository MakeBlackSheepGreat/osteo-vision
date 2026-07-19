from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from scripts.train_video_signal_multimask_v2 import (
    load_resume_checkpoint,
    masked_multimask_loss,
    restore_optimizer_state,
    train_multimask_v2,
)
from src.datasets.group_splits import assign_group_split
from src.models.video_signal_multimask import VideoSignalMultiMask2D


def test_multimask_model_has_independent_heads_and_masked_loss() -> None:
    model = VideoSignalMultiMask2D(base_channels=4)
    image = torch.rand(2, 3, 32, 40)
    logits = model(image)
    target = torch.zeros_like(logits)
    target[0, 0, 8:20, 10:24] = 1
    target[1, 1, 4:28, 6:34] = 1
    valid = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    weights = torch.ones_like(valid)
    loss = masked_multimask_loss(logits, target, valid, weights)
    assert logits.shape == (2, 2, 32, 40)
    assert torch.isfinite(loss)
    loss.backward()


def test_multimask_resume_records_manifest_and_legacy_optimizer_gap(tmp_path: Path) -> None:
    seed = 20260710
    manifest = _write_multimask_manifest(tmp_path, seed=seed)
    source_model = VideoSignalMultiMask2D(base_channels=2)
    source_checkpoint = tmp_path / "legacy_multimask.pt"
    torch.save(
        {
            "model_id": "legacy_multimask",
            "model_family": "convnext2d_video_signal_multimask",
            "model_config": {
                "in_channels": 3,
                "heads": ["fluorescence_signal", "bone_gate"],
                "base_channels": 2,
            },
            "state_dict": source_model.state_dict(),
            "training": {"completed_train_batches": 7},
        },
        source_checkpoint,
    )
    output_checkpoint = tmp_path / "continued_multimask.pt"
    result = train_multimask_v2(
        argparse.Namespace(
            manifest=[str(manifest)],
            heads="fluorescence_signal,bone_gate",
            output_checkpoint=str(output_checkpoint),
            resume_checkpoint=str(source_checkpoint),
            restore_optimizer_state=True,
            report_dir=str(tmp_path / "reports"),
            report_stamp="resume_test",
            image_shape="16x16",
            max_train_batches=1,
            overfit_probe_batches=1,
            batch_size=1,
            base_channels=2,
            learning_rate=1e-3,
            thresholds="0.5",
            val_fraction=0.2,
            test_fraction=0.1,
            seed=seed,
            device="cpu",
        )
    )

    sidecar = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    fine_tuning = sidecar["training"]["fine_tuning"]
    assert sidecar["runtime_allowed"] is False
    assert sidecar["training"]["source_manifest_sha256"] == [
        {"path": str(manifest.resolve()), "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
    ]
    assert fine_tuning["source_checkpoint_sha256"] == hashlib.sha256(source_checkpoint.read_bytes()).hexdigest()
    assert fine_tuning["optimizer_state_status"] == "missing_in_source_checkpoint"
    assert fine_tuning["optimizer_state_restored"] is False
    assert fine_tuning["previous_completed_train_batches"] == 7
    assert fine_tuning["total_completed_train_batches"] == 8
    saved = torch.load(output_checkpoint, map_location="cpu", weights_only=False)
    assert "optimizer_state_dict" in saved
    assert "optimizer_state_dict" not in sidecar

    continued_model = VideoSignalMultiMask2D(base_channels=2)
    resume_record = load_resume_checkpoint(
        output_checkpoint,
        model=continued_model,
        expected_model_config={
            "in_channels": 3,
            "heads": ["fluorescence_signal", "bone_gate"],
            "base_channels": 2,
        },
        device=torch.device("cpu"),
    )
    optimizer = torch.optim.AdamW(continued_model.parameters(), lr=5e-4)
    assert (
        restore_optimizer_state(
            optimizer,
            resume_record=resume_record,
            restore_requested=True,
            learning_rate=5e-4,
        )
        == "restored"
    )


def test_multimask_resume_rejects_incompatible_head_order(tmp_path: Path) -> None:
    model = VideoSignalMultiMask2D(base_channels=2)
    checkpoint = tmp_path / "wrong_heads.pt"
    torch.save(
        {
            "model_family": "convnext2d_video_signal_multimask",
            "model_config": {
                "in_channels": 3,
                "heads": ["bone_gate", "fluorescence_signal"],
                "base_channels": 2,
            },
            "state_dict": model.state_dict(),
        },
        checkpoint,
    )

    with pytest.raises(ValueError, match="model_config mismatch"):
        load_resume_checkpoint(
            checkpoint,
            model=model,
            expected_model_config={
                "in_channels": 3,
                "heads": ["fluorescence_signal", "bone_gate"],
                "base_channels": 2,
            },
            device=torch.device("cpu"),
        )


def _write_multimask_manifest(tmp_path: Path, *, seed: int) -> Path:
    rows: list[dict[str, str]] = []
    for split_index, split in enumerate(("train", "val", "test")):
        group = _group_for_split(split, seed=seed)
        image_path = tmp_path / f"{split}_image.png"
        mask_path = tmp_path / f"{split}_mask.png"
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[4:12, 4:12, 1] = 220 - split_index * 10
        mask = np.zeros((16, 16), dtype=np.uint8)
        mask[4:12, 4:12] = 255
        Image.fromarray(image).save(image_path)
        Image.fromarray(mask).save(mask_path)
        for mask_type in ("fluorescence_hotspot", "exposed_bone"):
            rows.append(
                {
                    "image_path": str(image_path),
                    "mask_path": str(mask_path),
                    "mask_type": mask_type,
                    "source_group_id": group,
                    "review_state": "review_required",
                    "sample_weight": "1.0",
                }
            )
    manifest = tmp_path / "multimask.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def _group_for_split(target: str, *, seed: int) -> str:
    for index in range(10_000):
        group = f"group-{target}-{index}"
        if assign_group_split(group, seed=seed, val_fraction=0.2, test_fraction=0.1) == target:
            return group
    raise AssertionError(f"Unable to construct group for {target}")
