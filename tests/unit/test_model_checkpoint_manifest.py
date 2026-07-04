from __future__ import annotations

import csv
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
                "metrics": {"dice": 0.1},
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

    payload = build_model_checkpoint_manifest(config_path)

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
