from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from osteo_vision_core.models.runtime_promotion import (
    build_keyframe_runtime_promotion,
    write_runtime_promotion_sidecar,
)


def _write_evidence(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    checkpoint = tmp_path / "keyframe.pt"
    checkpoint.write_bytes(b"keyframe checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = tmp_path / "training.csv"
    manifest.write_text("case_id,split\ncase-1,train\n", encoding="utf-8")
    split_report = {
        "row_count": 30,
        "group_count": 15,
        "split_group_counts": {"train": 9, "val": 3, "test": 3},
        "leakage_detected": False,
        "leaking_group_count": 0,
        "leaking_groups": {},
        "missing_group_row_count": 0,
        "missing_group_rows_first20": [],
        "group_keys": ["source_video_path", "case_id"],
        "split_key": "split",
    }
    training_sidecar = tmp_path / "keyframe_manifest.json"
    training_sidecar.write_text(
        json.dumps(
            {
                "checkpoint_path": str(checkpoint),
                "checkpoint_sha256": digest,
                "model_id": "keyframe-v1",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": False,
                "clinical_claim_allowed": False,
                "training": {
                    "manifest_path": str(manifest),
                    "manifest_paths": [str(manifest)],
                    "source_group_split": split_report,
                    "data_boundary": "pseudo-labeled non-target-domain keyframes",
                },
                "warnings": ["proxy evidence"],
            }
        ),
        encoding="utf-8",
    )

    def write_eval(path: Path, split: str, *, threshold: float = 0.45) -> None:
        path.write_text(
            json.dumps(
                {
                    "checkpoint_path": str(checkpoint),
                    "checkpoint_sha256": digest,
                    "checkpoint_metadata": {
                        "model_id": "keyframe-v1",
                        "model_family": "convnext2d_keyframe_segmenter",
                    },
                    "manifest_paths": [str(manifest)],
                    "source_group_split": split_report,
                    "split": split,
                    "recommendation": {
                        "threshold": threshold,
                        "selected_row": {
                            "threshold": threshold,
                            "empty_mask_rate": 0.0,
                            "over_segmentation_rate": 0.01,
                            "foreground_mean_dice": 0.8,
                        },
                    },
                    "medical_boundary": "proxy threshold evaluation",
                }
            ),
            encoding="utf-8",
        )

    val_eval = tmp_path / "val.json"
    test_eval = tmp_path / "test.json"
    write_eval(val_eval, "val")
    write_eval(test_eval, "test")
    return checkpoint, training_sidecar, val_eval, test_eval


def test_runtime_promotion_writes_new_sidecar_without_changing_training_sidecar(tmp_path: Path) -> None:
    checkpoint, training_sidecar, val_eval, test_eval = _write_evidence(tmp_path)
    original_training_sidecar = training_sidecar.read_bytes()

    report = build_keyframe_runtime_promotion(
        checkpoint_path=checkpoint,
        training_sidecar_path=training_sidecar,
        val_eval_path=val_eval,
        test_eval_path=test_eval,
    )
    output = write_runtime_promotion_sidecar(tmp_path / "runtime_promotion.json", report)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert report["passed"] is True
    assert payload["runtime_allowed"] is True
    assert payload["clinical_claim_allowed"] is False
    assert payload["threshold"] == 0.45
    assert payload["metrics"]["validation"]["empty_mask_rate"] == 0.0
    assert payload["metrics"]["test"]["over_segmentation_rate"] == 0.01
    assert payload["data_boundary"] == "pseudo-labeled non-target-domain keyframes"
    assert payload["promotion"]["evidence"]["training_sidecar"]["sha256"]
    assert training_sidecar.read_bytes() == original_training_sidecar


def test_runtime_promotion_rejects_threshold_mismatch_and_gate_failure(tmp_path: Path) -> None:
    checkpoint, training_sidecar, val_eval, test_eval = _write_evidence(tmp_path)
    payload = json.loads(test_eval.read_text(encoding="utf-8"))
    payload["recommendation"]["threshold"] = 0.5
    payload["recommendation"]["selected_row"]["threshold"] = 0.5
    payload["recommendation"]["selected_row"]["empty_mask_rate"] = 0.2
    test_eval.write_text(json.dumps(payload), encoding="utf-8")

    report = build_keyframe_runtime_promotion(
        checkpoint_path=checkpoint,
        training_sidecar_path=training_sidecar,
        val_eval_path=val_eval,
        test_eval_path=test_eval,
        max_empty_mask_rate=0.05,
    )
    codes = {item["code"] for item in report["errors"]}

    assert report["passed"] is False
    assert "val_test_threshold_mismatch" in codes
    assert "empty_mask_rate_exceeds_gate" in codes
    assert "promotion_sidecar" not in report


def test_runtime_promotion_rejects_sha_leakage_and_clinical_claim(tmp_path: Path) -> None:
    checkpoint, training_sidecar, val_eval, test_eval = _write_evidence(tmp_path)
    training_payload = json.loads(training_sidecar.read_text(encoding="utf-8"))
    training_payload["clinical_claim_allowed"] = True
    training_payload["training"]["source_group_split"]["leakage_detected"] = True
    training_payload["training"]["source_group_split"]["leaking_group_count"] = 1
    training_sidecar.write_text(json.dumps(training_payload), encoding="utf-8")
    val_payload = json.loads(val_eval.read_text(encoding="utf-8"))
    val_payload["checkpoint_sha256"] = "0" * 64
    val_eval.write_text(json.dumps(val_payload), encoding="utf-8")

    report = build_keyframe_runtime_promotion(
        checkpoint_path=checkpoint,
        training_sidecar_path=training_sidecar,
        val_eval_path=val_eval,
        test_eval_path=test_eval,
    )
    codes = {item["code"] for item in report["errors"]}

    assert report["passed"] is False
    assert "checkpoint_sha_mismatch" in codes
    assert "source_group_leakage_detected" in codes
    assert "source_group_leaking_group_count_invalid" in codes
    assert "clinical_claim_must_be_false" in codes


def test_runtime_promotion_accepts_exact_registry_admitted_manifest_rows(tmp_path: Path, monkeypatch) -> None:
    checkpoint, training_sidecar, val_eval, test_eval = _write_evidence(tmp_path)
    registry = tmp_path / "layered_registry.csv"
    registry.write_text("record_id\nrow-1\n", encoding="utf-8")
    quality = tmp_path / "quality.json"
    quality.write_text("{}", encoding="utf-8")
    image = tmp_path / "frame.jpg"
    mask = tmp_path / "mask.png"
    image.write_bytes(b"frame")
    mask.write_bytes(b"mask")
    evaluation_manifest = tmp_path / "evaluation.csv"
    evaluation_manifest.write_text(
        "case_id,image_path,mask_path,split,source_group_id\n" f"case-1,{image},{mask},val,video-1\n",
        encoding="utf-8",
    )
    admitted_rows = [
        {
            "case_id": "registry::case-1",
            "image_path": str(image),
            "mask_path": str(mask),
            "split": "val",
            "source_group_id": "video-1",
        }
    ]
    monkeypatch.setattr(
        "osteo_vision_core.models.runtime_promotion.admit_keyframe_training_rows",
        lambda *_args, **_kwargs: SimpleNamespace(rows=admitted_rows),
    )
    training_payload = json.loads(training_sidecar.read_text(encoding="utf-8"))
    training_payload["training"].update(
        {
            "source": "layered_registry_admission",
            "manifest_path": str(registry),
            "manifest_paths": [],
            "registry_path": str(registry),
            "quality_report_path": str(quality),
            "training_admission": {
                "artifact_role": "training_keyframe::fluorescence_hotspot",
                "admission_stage": "proxy_pretrain",
            },
        }
    )
    training_sidecar.write_text(json.dumps(training_payload), encoding="utf-8")
    for evaluation_path in (val_eval, test_eval):
        payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
        payload["manifest_paths"] = [str(evaluation_manifest)]
        evaluation_path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_keyframe_runtime_promotion(
        checkpoint_path=checkpoint,
        training_sidecar_path=training_sidecar,
        val_eval_path=val_eval,
        test_eval_path=test_eval,
    )

    assert report["passed"] is True
    alignment = report["promotion_sidecar"]["promotion"]["manifest_alignment"]
    assert alignment["method"] == "layered_registry_admitted_row_identity"
    assert alignment["matched_row_count"] == 1
