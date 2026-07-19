from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import torch

from scripts.train_keyframe_segmentation_proxy import train_keyframe_proxy


def test_keyframe_checkpoint_resume_and_pretrained_modes(tmp_path: Path) -> None:
    fresh = train_keyframe_proxy(_args(tmp_path, "fresh"))
    fresh_checkpoint = torch.load(fresh["checkpoint_path"], map_location="cpu", weights_only=False)
    assert "optimizer_state_dict" not in fresh_checkpoint
    assert Path(fresh["optimizer_state_path"]).is_file()
    assert fresh_checkpoint["optimizer_state"]["path"] == fresh["optimizer_state_path"]

    resume_args = _args(tmp_path, "resumed")
    resume_args.resume_checkpoint = fresh["checkpoint_path"]
    resume_args.restore_optimizer = True
    resume_args.freeze_encoder = True
    resume_args.learning_rate = 2e-4
    resumed = train_keyframe_proxy(resume_args)
    resumed_checkpoint = torch.load(resumed["checkpoint_path"], map_location="cpu", weights_only=False)
    resumed_training = resumed_checkpoint["training"]
    resumed_fine_tuning = resumed_training["fine_tuning"]
    assert resumed_training["previous_completed_train_batches"] == 1
    assert resumed_training["total_completed_train_batches"] == 2
    assert resumed_fine_tuning["mode"] == "resume"
    assert resumed_fine_tuning["optimizer_restored"] is True
    assert resumed_fine_tuning["encoder_frozen"] is True
    assert resumed_fine_tuning["frozen_parameter_count"] > 0
    assert resumed_training["learning_rate"] == 2e-4
    assert torch.equal(
        fresh_checkpoint["state_dict"]["enc0.stage.0.weight"],
        resumed_checkpoint["state_dict"]["enc0.stage.0.weight"],
    )

    pretrained_args = _args(tmp_path, "pretrained")
    pretrained_args.pretrained_checkpoint = fresh["checkpoint_path"]
    pretrained = train_keyframe_proxy(pretrained_args)
    pretrained_checkpoint = torch.load(pretrained["checkpoint_path"], map_location="cpu", weights_only=False)
    pretrained_training = pretrained_checkpoint["training"]
    assert pretrained_training["previous_completed_train_batches"] == 0
    assert pretrained_training["total_completed_train_batches"] == 1
    assert pretrained_training["fine_tuning"]["mode"] == "pretrained"
    assert pretrained_training["fine_tuning"]["optimizer_restored"] is False

    sidecar = json.loads(Path(pretrained["manifest_path"]).read_text(encoding="utf-8"))
    assert sidecar["runtime_allowed"] is False
    assert sidecar["fine_tuning"]["source_checkpoint"] == fresh["checkpoint_path"]


def _args(tmp_path: Path, name: str) -> Namespace:
    return Namespace(
        seed=17,
        device="cpu",
        image_shape="16x16",
        manifest=[],
        registry="",
        quality_report="",
        synthetic_train_size=2,
        synthetic_val_size=1,
        base_channels=2,
        learning_rate=1e-3,
        batch_size=1,
        max_train_batches=1,
        threshold=0.5,
        output_checkpoint=str(tmp_path / f"{name}.pt"),
        model_id=f"keyframe_{name}",
        report_dir=str(tmp_path / "reports"),
        report_stamp=name,
        domain_aware=False,
        domain_adaptation_config="",
        resume_checkpoint="",
        pretrained_checkpoint="",
        restore_optimizer=False,
        freeze_encoder=False,
    )
