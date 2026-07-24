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

from scripts.train_dual_channel_segmenter import (
    load_resume_checkpoint,
    restore_optimizer_state,
    train_dual_channel,
)
from osteo_vision_core.models.dual_channel_segmenter import DUAL_CHANNEL_MODES, TinyDualChannelSegmenter2D


def test_dual_channel_segmenter_runs_all_ablation_modes() -> None:
    model = TinyDualChannelSegmenter2D(base_channels=4)
    white = torch.rand(2, 3, 32, 40)
    fluorescence = torch.rand(2, 1, 32, 40)
    for mode in DUAL_CHANNEL_MODES:
        output = model(white, fluorescence, mode=mode)
        assert output.shape == (2, 1, 32, 40)


def test_dual_channel_resume_records_manifest_and_legacy_optimizer_gap(tmp_path: Path) -> None:
    manifest = _write_dual_channel_manifest(tmp_path)
    source_model = TinyDualChannelSegmenter2D(base_channels=2)
    source_checkpoint = tmp_path / "legacy_dual.pt"
    torch.save(
        {
            "model_id": "legacy_dual",
            "model_family": "dual_channel_segmenter",
            "model_config": {"base_channels": 2},
            "state_dict": source_model.state_dict(),
            "training": {"completed_train_batches": 5},
        },
        source_checkpoint,
    )
    output_checkpoint = tmp_path / "continued_dual.pt"
    result = train_dual_channel(
        argparse.Namespace(
            manifest=str(manifest),
            output_checkpoint=str(output_checkpoint),
            resume_checkpoint=str(source_checkpoint),
            restore_optimizer_state=True,
            report_dir=str(tmp_path / "reports"),
            report_stamp="resume_test",
            image_shape="16x16",
            max_train_batches=1,
            batch_size=1,
            base_channels=2,
            learning_rate=1e-3,
            threshold=0.5,
            seed=20260710,
            device="cpu",
        )
    )

    sidecar = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    fine_tuning = sidecar["training"]["fine_tuning"]
    assert sidecar["runtime_allowed"] is False
    assert sidecar["training"]["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert fine_tuning["source_checkpoint_sha256"] == hashlib.sha256(source_checkpoint.read_bytes()).hexdigest()
    assert fine_tuning["optimizer_state_status"] == "missing_in_source_checkpoint"
    assert fine_tuning["optimizer_state_restored"] is False
    assert fine_tuning["previous_completed_train_batches"] == 5
    assert fine_tuning["total_completed_train_batches"] == 6
    saved = torch.load(output_checkpoint, map_location="cpu", weights_only=False)
    assert "optimizer_state_dict" in saved
    assert "optimizer_state_dict" not in sidecar

    continued_model = TinyDualChannelSegmenter2D(base_channels=2)
    resume_record = load_resume_checkpoint(
        output_checkpoint,
        model=continued_model,
        expected_model_config={"base_channels": 2},
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


def test_dual_channel_resume_rejects_incompatible_width(tmp_path: Path) -> None:
    source_model = TinyDualChannelSegmenter2D(base_channels=4)
    checkpoint = tmp_path / "wrong_width.pt"
    torch.save(
        {
            "model_family": "dual_channel_segmenter",
            "model_config": {"base_channels": 4},
            "state_dict": source_model.state_dict(),
        },
        checkpoint,
    )

    target_model = TinyDualChannelSegmenter2D(base_channels=2)
    with pytest.raises(ValueError, match="model_config mismatch"):
        load_resume_checkpoint(
            checkpoint,
            model=target_model,
            expected_model_config={"base_channels": 2},
            device=torch.device("cpu"),
        )


def _write_dual_channel_manifest(tmp_path: Path) -> Path:
    rows: list[dict[str, str]] = []
    for split_index, split in enumerate(("train", "val", "test")):
        image_path = tmp_path / f"dual_{split}_image.png"
        mask_path = tmp_path / f"dual_{split}_mask.png"
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[4:12, 4:12, 1] = 220 - split_index * 10
        mask = np.zeros((16, 16), dtype=np.uint8)
        mask[4:12, 4:12] = 255
        Image.fromarray(image).save(image_path)
        Image.fromarray(mask).save(mask_path)
        rows.append(
            {
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "split": split,
                "source_group_id": f"dual-{split}",
            }
        )
    manifest = tmp_path / "dual.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest
