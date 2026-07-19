from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from tools.build_keyframe_candidate_strict_config import build_candidate_strict_config


def test_candidate_strict_config_writes_segmentation_task_and_preserves_production_config(tmp_path: Path) -> None:
    production = tmp_path / "competition_strict.yml"
    production.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "competition_strict",
                    "strict_startup": True,
                    "model_selection_policy": "explicit",
                    "required_model_ids": ["mainline"],
                    "models": [{"model_id": "mainline"}],
                    "tasks": {
                        "segmentation": {"pipeline": "segmentation", "model_id": "mainline"},
                        "classification": {"pipeline": "classification"},
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    production_before = production.read_bytes()
    checkpoint = tmp_path / "candidate.pt"
    checkpoint.write_bytes(b"candidate")
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    sidecar = tmp_path / "candidate_runtime.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": checkpoint_sha,
                "model_id": "candidate_residual",
                "model_family": "residual_attention_unet_keyframe_segmenter",
                "threshold": 0.4,
                "runtime_allowed": True,
                "clinical_claim_allowed": False,
                "data_boundary": "public proxy",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "candidate_strict_runtime.yml"

    summary = build_candidate_strict_config(
        production_config_path=production,
        checkpoint_path=checkpoint,
        runtime_sidecar_path=sidecar,
        output_path=output,
        output_dir=tmp_path / "run",
    )
    generated = yaml.safe_load(output.read_text(encoding="utf-8"))
    runtime = generated["runtime"]

    assert runtime["required_model_ids"] == ["candidate_residual"]
    assert runtime["models"][0]["model_id"] == "candidate_residual"
    assert runtime["models"][0]["family"] == "residual_attention_unet_keyframe_segmenter"
    assert runtime["tasks"]["segmentation"] == {
        "pipeline": "segmentation",
        "model_id": "candidate_residual",
    }
    assert runtime["tasks"]["classification"] == {"pipeline": "classification"}
    assert summary["segmentation_task"]["pipeline"] == "segmentation"
    assert summary["segmentation_task"]["model_id"] == "candidate_residual"
    assert summary["production_config_unchanged"] is True
    assert summary["automatic_replacement_performed"] is False
    assert production.read_bytes() == production_before
