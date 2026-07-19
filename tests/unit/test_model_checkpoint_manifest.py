from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from scripts.generate_model_checkpoint_manifest import build_model_checkpoint_manifest, write_manifest_bundle


def test_model_checkpoint_manifest_records_available_and_missing_models(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "convnext_proxy.pt"
    checkpoint_path.write_bytes(b"proxy checkpoint")
    (tmp_path / "convnext_proxy_manifest.json").write_text(
        json.dumps(
            {
                "model_id": "convnext_proxy",
                "model_family": "convnext3d_segmenter",
                "clinical_claim_allowed": False,
                "metrics": {"dice": 0.1, "threshold": 0.2},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "convnext_proxy_model_card.json").write_text(
        json.dumps(
            {
                "model_id": "convnext_proxy",
                "model_family": "convnext3d_segmenter",
                "clinical_claim_allowed": False,
                "limitations": ["proxy only"],
            }
        ),
        encoding="utf-8",
    )
    missing_checkpoint = tmp_path / "medsam_missing.pt"
    config_path = tmp_path / "inference.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "model_version": "test-model-v0",
                    "use_fixture_model": True,
                    "model_selection_policy": "fixture_fallback",
                    "models": [
                        {
                            "model_id": "convnext_proxy",
                            "family": "convnext3d_segmenter",
                            "task_types": ["segmentation"],
                            "input_types": ["npz_roi"],
                            "spatial_dims": [3],
                            "checkpoint_path": str(checkpoint_path),
                            "dependency_group": "torch",
                            "clinical_claim_allowed": False,
                            "extra": {"threshold": 0.2},
                        },
                        {
                            "model_id": "medsam_pending",
                            "family": "medsam_like",
                            "task_types": ["segmentation"],
                            "input_types": ["2d_image"],
                            "checkpoint_path": str(missing_checkpoint),
                            "dependency_group": "sam",
                            "clinical_claim_allowed": False,
                        },
                        {
                            "model_id": "fixture_default",
                            "family": "fixture",
                            "task_types": ["*"],
                            "input_types": ["*"],
                            "clinical_claim_allowed": False,
                        },
                    ],
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_model_checkpoint_manifest(
        config_path,
        generated_at_utc="2026-07-14T00:00:00+00:00",
    )

    assert payload["schema_version"] == "osteo-vision-model-checkpoint-manifest-v2"
    assert payload["config_sha256"]
    assert payload["runtime_profile"] == "development"
    assert payload["strict_startup"] is False
    assert payload["model_count"] == 3
    assert payload["available_model_count"] == 2
    assert payload["summary"]["available_model_ids"] == ["convnext_proxy", "fixture_default"]
    assert payload["summary"]["models_with_missing_checkpoint"] == ["medsam_pending"]
    assert payload["summary"]["models_allowing_clinical_claims"] == []
    convnext_row = next(row for row in payload["models"] if row["model_id"] == "convnext_proxy")
    assert convnext_row["checkpoint"]["exists"] is True
    assert convnext_row["checkpoint"]["sha256"]
    assert convnext_row["artifact_manifest"]["exists"] is True
    assert convnext_row["model_card"]["exists"] is True
    assert convnext_row["manifest_model_id_matches"] is True
    assert convnext_row["runtime_threshold"] == 0.2
    assert convnext_row["sidecar_metric_threshold"] == 0.2
    assert convnext_row["threshold_alignment"]["matches"] is True

    regenerated = build_model_checkpoint_manifest(
        config_path,
        generated_at_utc="2026-07-14T00:00:00+00:00",
    )
    assert regenerated == payload


def test_runtime_promotion_sidecar_is_preferred_for_checkpoint_identity_and_threshold(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "residual_attention.pt"
    checkpoint_path.write_bytes(b"residual attention checkpoint")
    checkpoint_sha256 = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    (tmp_path / "residual_attention_manifest.json").write_text(
        json.dumps(
            {
                "model_id": "residual_attention_mainline",
                "model_family": "residual_attention_unet_keyframe_segmenter",
                "checkpoint_sha256": checkpoint_sha256,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    runtime_sidecar_path = tmp_path / "residual_attention_runtime_promotion.json"
    runtime_sidecar_path.write_text(
        json.dumps(
            {
                "model_id": "residual_attention_checkpoint",
                "model_family": "residual_attention_unet_keyframe_segmenter",
                "checkpoint_sha256": checkpoint_sha256,
                "threshold": 0.4,
                "runtime_allowed": True,
                "clinical_claim_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "inference.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "use_fixture_model": False,
                    "models": [
                        {
                            "model_id": "residual_attention_mainline",
                            "family": "residual_attention_unet_keyframe_segmenter",
                            "task_types": ["segmentation"],
                            "input_types": ["2d_image"],
                            "spatial_dims": [2],
                            "checkpoint_path": str(checkpoint_path),
                            "dependency_group": "torch",
                            "clinical_claim_allowed": False,
                            "extra": {
                                "runtime_allowed": True,
                                "runtime_sidecar_path": str(runtime_sidecar_path),
                                "checkpoint_model_id": "residual_attention_checkpoint",
                                "threshold": 0.4,
                            },
                        }
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_model_checkpoint_manifest(config_path, generated_at_utc="2026-07-15T00:00:00+00:00")
    row = payload["models"][0]

    assert row["runtime_evidence_source"] == "runtime_promotion_sidecar"
    assert row["runtime_promotion_sidecar"]["exists"] is True
    assert row["sidecar_metric_threshold"] == 0.4
    assert row["threshold_alignment"]["matches"] is True
    assert row["manifest_model_id_matches"] is True
    assert row["runtime_evidence_validation"]["passed"] is True
    assert row["runtime_evidence_validation"]["checks"] == {
        "checkpoint_sha256_matches": True,
        "model_id_matches": True,
        "model_family_matches": True,
        "threshold_matches": True,
    }
    assert "non-target-domain" in row["medical_boundary"]
    assert payload["summary"]["models_with_invalid_runtime_promotion_evidence"] == []


def test_runtime_promotion_sidecar_mismatches_are_reported(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "multiscale.pt"
    checkpoint_path.write_bytes(b"multiscale checkpoint")
    runtime_sidecar_path = tmp_path / "multiscale_runtime_promotion.json"
    runtime_sidecar_path.write_text(
        json.dumps(
            {
                "model_id": "wrong_model",
                "model_family": "wrong_family",
                "checkpoint_sha256": "0" * 64,
                "threshold": 0.9,
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "inference.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "use_fixture_model": False,
                    "models": [
                        {
                            "model_id": "multiscale_mainline",
                            "family": "multiscale_depthwise_unet_keyframe_segmenter",
                            "task_types": ["segmentation"],
                            "input_types": ["2d_image"],
                            "checkpoint_path": str(checkpoint_path),
                            "dependency_group": "torch",
                            "extra": {
                                "runtime_sidecar_path": str(runtime_sidecar_path),
                                "threshold": 0.4,
                            },
                        }
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_model_checkpoint_manifest(config_path, generated_at_utc="2026-07-15T00:00:00+00:00")
    row = payload["models"][0]

    assert row["runtime_evidence_validation"]["passed"] is False
    assert row["runtime_evidence_validation"]["errors"] == [
        "checkpoint_sha256_matches",
        "model_id_matches",
        "model_family_matches",
        "threshold_matches",
    ]
    assert "non-target-domain" in row["medical_boundary"]
    assert payload["summary"]["models_with_invalid_runtime_promotion_evidence"] == ["multiscale_mainline"]


def test_write_manifest_bundle_outputs_json_csv_and_reports(tmp_path: Path) -> None:
    payload = {
        "schema_version": "test",
        "generated_at_utc": "2026-07-04T00:00:00+00:00",
        "config_path": "configs/inference/osteo_vision.yml",
        "model_version": "test-model-v0",
        "model_count": 1,
        "available_model_count": 1,
        "runtime_fixture_fallback_enabled": True,
        "model_selection_policy": "fixture_fallback",
        "models": [
            {
                "model_id": "fixture_default",
                "family": "fixture",
                "enabled": True,
                "available": True,
                "status_reasons": [],
                "task_types": ["*"],
                "input_types": ["*"],
                "checkpoint": {"path": None, "exists": False, "sha256": None},
                "artifact_manifest": {"exists": False},
                "model_card": {"exists": False},
                "manifest_model_id_matches": None,
                "runtime_threshold": None,
                "sidecar_metric_threshold": None,
                "threshold_alignment": {"available": False, "reason": "threshold_missing"},
                "clinical_claim_allowed": False,
                "medical_boundary": "Deterministic fixture fallback for tests and demos only.",
            }
        ],
        "summary": {
            "available_model_ids": ["fixture_default"],
            "unavailable_model_ids": [],
            "checkpointed_model_ids": [],
            "models_with_missing_checkpoint": [],
            "models_allowing_clinical_claims": [],
        },
    }

    paths = write_manifest_bundle(payload, output_dir=tmp_path, date_stamp="20260704")

    json_payload = json.loads(Path(paths["json_manifest"]).read_text(encoding="utf-8"))
    assert json_payload["model_count"] == 1
    with Path(paths["csv_manifest"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["model_id"] == "fixture_default"
    assert "模型总数：1" in Path(paths["zh_report"]).read_text(encoding="utf-8")
    assert "Total models: 1" in Path(paths["en_report"]).read_text(encoding="utf-8")
