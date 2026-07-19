from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from scripts.train_bone_activity_multitask_proxy import _dice_from_counts, train_bone_activity_multitask


def test_bone_activity_proxy_training_writes_fail_closed_manifest(tmp_path: Path) -> None:
    config_path = tmp_path / "bone_activity.yml"
    checkpoint_path = tmp_path / "bone_activity.pt"
    manifest_path = tmp_path / "bone_activity_manifest.json"
    summary_path = tmp_path / "bone_activity_summary.json"
    config_path.write_text(
        yaml.safe_dump(
            {
                "capability": "bone_activity_multitask",
                "model": {"model_id": "smoke", "model_family": "bone_activity", "base_channels": 2},
                "data": {
                    "domain": "synthetic_proxy",
                    "target_domain": False,
                    "sample_count": 10,
                    "patient_group_count": 5,
                    "image_shape": [24, 24],
                },
                "training": {
                    "seed": 7,
                    "device": "cpu",
                    "batch_size": 2,
                    "max_train_batches": 1,
                    "learning_rate": 0.001,
                },
                "outputs": {
                    "checkpoint_path": str(checkpoint_path),
                    "manifest_path": str(manifest_path),
                    "summary_path": str(summary_path),
                },
            }
        ),
        encoding="utf-8",
    )

    result = train_bone_activity_multitask(config_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert checkpoint_path.is_file()
    assert result["engineering_ready"] is True
    assert result["target_domain_promotion_ready"] is False
    assert manifest["capability"] == "bone_activity_multitask"
    assert manifest["training_domain"]["target_domain"] is False
    assert manifest["training"]["completed"] is True
    assert manifest["training"]["patient_group_split"]["leakage_detected"] is False
    assert {
        "bone_gate",
        "activity_score",
        "class_logits",
        "class_probabilities",
        "uncertainty",
        "abstention",
    } == set(manifest["outputs"])
    assert manifest["safety"]["bone_gate_fail_closed_passed"] is True
    assert manifest["safety"]["abstention_passed"] is True
    assert manifest["labels"]["physician_reviewed_bone_gate"] is False
    assert manifest["validation"]["independent_test_set"] is False
    assert manifest["validation"]["calibrated"] is False
    assert manifest["review"]["physician_reviewed"] is False
    assert manifest["inference_thresholds"]["runtime_authorized"] is False


def test_bone_activity_manifest_training_uses_real_image_proxy_contract(tmp_path: Path) -> None:
    data_manifest = _write_manifest_fixture(tmp_path / "data")
    config_path = _write_manifest_config(tmp_path, data_manifest)

    result = train_bone_activity_multitask(config_path)
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

    assert result["engineering_ready"] is True
    assert result["target_domain_promotion_ready"] is False
    assert manifest["training_domain"] == {
        "target_domain": False,
        "domain": "d074_fixture",
        "domain_tier": "clinical_microscope_fluorescence_non_jaw_proxy",
        "data_mode": "manifest",
        "training_scope": "non_target_proxy_pretraining",
        "channel_semantics": "single_ppix_rgb_view_with_red_channel_proxy",
    }
    assert manifest["training"]["patient_group_split"]["leakage_detected"] is False
    assert len(manifest["training"]["source_manifest_sha256"]) == 64
    assert set(manifest["labels"]["class_set"]) == {
        "low_activity",
        "transition",
        "high_activity",
        "ignore",
    }
    assert {
        "macro_dice",
        "low_activity_dice",
        "transition_dice",
        "high_activity_dice",
        "transition_recall",
        "bone_gate_dice",
        "ece",
        "abstention_error_rate",
        "bone_gate_containment_rate",
        "activity_score_mae",
        "selective_error_rate",
        "abstention_coverage_rate",
    }.issubset(manifest["validation"]["metrics"])
    assert manifest["validation"]["promotion_metrics_eligible"] is False
    assert manifest["promotion"]["policy_status"] == "provisional_internal_engineering_gate"
    selection = manifest["validation"]["threshold_selection"]
    assert selection["selection_split"] == "validation"
    assert selection["test_set_used_for_selection"] is False
    assert selection["frozen_test_evaluation"]["thresholds_reused_without_test_tuning"] is True
    assert manifest["validation"]["metrics"]["bone_gate_threshold"] == selection["selected"]["bone_gate_threshold"]
    assert manifest["validation"]["metrics"]["abstention_threshold"] == selection["selected"]["abstention_threshold"]


def test_bone_activity_manifest_training_rejects_derived_file_drift(tmp_path: Path) -> None:
    data_manifest = _write_manifest_fixture(tmp_path / "data")
    rows = list(csv.DictReader(data_manifest.read_text(encoding="utf-8").splitlines()))
    (data_manifest.parent / rows[0]["white_path"]).write_bytes(b"drift")

    with pytest.raises(ValueError, match="white SHA256 mismatch"):
        train_bone_activity_multitask(_write_manifest_config(tmp_path, data_manifest))


def test_bone_activity_manifest_training_rejects_asset_cross_split_overlap(tmp_path: Path) -> None:
    data_manifest = _write_manifest_fixture(tmp_path / "data")
    rows = list(csv.DictReader(data_manifest.read_text(encoding="utf-8").splitlines()))
    rows[1]["white_path"] = rows[0]["white_path"]
    rows[1]["white_sha256"] = rows[0]["white_sha256"]
    _rewrite_rows(data_manifest, rows)

    with pytest.raises(ValueError, match="cross-split leakage detected for white_sha256"):
        train_bone_activity_multitask(_write_manifest_config(tmp_path, data_manifest))


def test_bone_activity_manifest_training_requires_pinned_manifest_hash(tmp_path: Path) -> None:
    data_manifest = _write_manifest_fixture(tmp_path / "data")
    config_path = _write_manifest_config(tmp_path, data_manifest)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["data"].pop("manifest_sha256")
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="data.manifest_sha256 is required"):
        train_bone_activity_multitask(config_path)


def test_empty_class_support_cannot_receive_perfect_dice() -> None:
    assert _dice_from_counts((0.0, 0.0, 0.0)) == 0.0


def _write_manifest_config(root: Path, data_manifest: Path) -> Path:
    config_path = root / "bone_activity_manifest.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "capability": "bone_activity_multitask",
                "promotion_policy_path": str(
                    Path(__file__).resolve().parents[2] / "configs/training/three_priority_promotion.yml"
                ),
                "model": {"model_id": "manifest", "model_family": "bone_activity", "base_channels": 2},
                "data": {
                    "mode": "manifest",
                    "manifest_path": str(data_manifest),
                    "manifest_sha256": hashlib.sha256(data_manifest.read_bytes()).hexdigest(),
                    "domain": "d074_fixture",
                    "target_domain": False,
                    "image_shape": [24, 24],
                    "expected_training_scope": "non_target_proxy_pretraining",
                    "expected_domain_tier": "clinical_microscope_fluorescence_non_jaw_proxy",
                    "expected_channel_semantics": "single_ppix_rgb_view_with_red_channel_proxy",
                },
                "training": {
                    "seed": 7,
                    "device": "cpu",
                    "batch_size": 1,
                    "max_train_batches": 1,
                    "learning_rate": 0.001,
                },
                "safety": {
                    "bone_gate_threshold": 0.5,
                    "abstention_threshold": 0.5,
                    "threshold_selection": {
                        "enabled": True,
                        "bone_gate_candidates": [0.2, 0.5, 0.8],
                        "abstention_candidates": [0.4, 0.6, 0.8],
                        "minimum_coverage_rate": 0.0,
                        "maximum_selective_error_rate": 1.0,
                    },
                },
                "outputs": {
                    "checkpoint_path": str(root / "manifest.pt"),
                    "manifest_path": str(root / "manifest.json"),
                    "summary_path": str(root / "summary.json"),
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_manifest_fixture(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    assignments = (("p1", "train"), ("p2", "val"), ("p3", "test"))
    rows: list[dict[str, str]] = []
    for index, (patient, split) in enumerate(assignments):
        sample_id = f"sample_{patient}"
        y, x = np.mgrid[0:24, 0:24]
        gate = ((x - (11 + index)) ** 2 + (y - 12) ** 2) <= 72 + index * 4
        score = np.clip((x + index * 0.25) / 23.0, 0.0, 1.0) * gate
        classes = np.full((24, 24), 255, dtype=np.uint8)
        classes[gate & (score < 1 / 3)] = 0
        classes[gate & (score >= 1 / 3) & (score < 2 / 3)] = 1
        classes[gate & (score >= 2 / 3)] = 2
        uncertainty = np.where(gate, np.abs(score - 0.5), 1.0)
        rgb = np.stack([np.rint(score * 255), np.full((24, 24), 64 + index), np.full((24, 24), 32)], axis=2).astype(
            np.uint8
        )
        payloads = {
            "white": rgb,
            "fluorescence": np.rint(score * 255).astype(np.uint8),
            "bone_gate": gate.astype(np.uint8) * 255,
            "activity_score": np.rint(score * 255).astype(np.uint8),
            "class_target": classes,
            "uncertainty": np.rint(uncertainty * 255).astype(np.uint8),
        }
        row = {
            "sample_id": sample_id,
            "patient_group_id": patient,
            "case_id": patient,
            "split": split,
            "domain_tier": "clinical_microscope_fluorescence_non_jaw_proxy",
            "training_scope": "non_target_proxy_pretraining",
            "channel_semantics": "single_ppix_rgb_view_with_red_channel_proxy",
            "target_domain": "false",
            "training_eligible": "true",
            "physician_reviewed_bone_gate": "false",
            "runtime_replacement_allowed": "false",
            "source_case_id": patient,
            "source_sequence_id": f"fixture:{patient}",
            "source_frame_id": f"fixture:{sample_id}",
            "source_image_member": f"images/{sample_id}.png",
            "source_mask_member": f"masks/{sample_id}.png",
            "source_asset_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "source_mask_asset_sha256": hashlib.sha256(gate.tobytes()).hexdigest(),
        }
        for role, array in payloads.items():
            path = root / f"{sample_id}_{role}.png"
            Image.fromarray(array).save(path)
            row[f"{role}_path"] = path.name
            row[f"{role}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(row)
    manifest_path = root / "samples.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest_path


def _rewrite_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
