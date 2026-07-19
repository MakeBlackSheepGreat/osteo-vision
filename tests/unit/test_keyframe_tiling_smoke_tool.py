from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from tools.run_keyframe_tiling_smoke import _model_mapping_for_args


def test_candidate_checkpoint_override_uses_manifest_identity_without_editing_config(tmp_path: Path) -> None:
    checkpoint = tmp_path / "candidate.pt"
    checkpoint.write_bytes(b"candidate checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    sidecar = tmp_path / "candidate_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": digest,
                "model_id": "candidate_residual",
                "model_family": "residual_attention_unet_keyframe_segmenter",
                "runtime_allowed": False,
                "clinical_claim_allowed": False,
                "training": {"data_boundary": "public non-target-domain proxy"},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "inference.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "models": [
                        {
                            "model_id": "template",
                            "family": "convnext2d_keyframe_segmenter",
                            "task_types": ["segmentation"],
                            "input_types": ["2d_image"],
                            "checkpoint_path": "template.pt",
                            "extra": {"runtime_allowed": True},
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        config=str(config),
        model_id="",
        template_model_id="template",
        checkpoint=str(checkpoint),
        checkpoint_sidecar=str(sidecar),
    )

    mapping, evidence = _model_mapping_for_args(args)

    assert mapping["model_id"] == "candidate_residual"
    assert mapping["family"] == "residual_attention_unet_keyframe_segmenter"
    assert mapping["checkpoint_path"] == str(checkpoint.resolve())
    assert mapping["extra"]["runtime_allowed"] is True
    assert mapping["extra"]["target_domain"] is False
    assert evidence["consistent"] is True
    assert evidence["training_runtime_allowed"] is False
    assert evidence["ephemeral_runtime_enablement"] is True
    assert evidence["persistent_config_unchanged"] is True
