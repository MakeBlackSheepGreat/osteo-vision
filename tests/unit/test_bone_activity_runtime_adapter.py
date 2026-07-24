from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from osteo_vision_core.core.schemas import AdapterRequest
from osteo_vision_core.models.adapters import build_adapter, model_spec_from_mapping
from osteo_vision_core.models.bone_activity_multitask import BONE_ACTIVITY_CLASSES, BoneActivityMultiTask2D


def test_bone_activity_proxy_adapter_executes_checkpoint_and_keeps_spatial_outputs_closed(
    tmp_path: Path,
) -> None:
    checkpoint_path, manifest_path, manifest_sha256 = _write_proxy_runtime_bundle(tmp_path)
    white_path, fluorescence_path, gate_path = _write_input_pair(tmp_path)
    adapter = build_adapter(
        model_spec_from_mapping(_adapter_spec(checkpoint_path, manifest_path, manifest_sha256, tmp_path / "outputs"))
    )

    status = adapter.warmup()
    result = adapter.predict(
        AdapterRequest(
            case_id="case-bone-activity",
            input_path=str(white_path),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="microscope_dual_channel",
            metadata={
                "fluorescence_path": str(fluorescence_path),
                "dual_channel_registration_verified": True,
                "target_domain_input_verified": False,
                "reviewed_bone_gate": {
                    "path": str(gate_path),
                    "sha256": _sha256_file(gate_path),
                    "physician_reviewed": True,
                    "trusted_review": True,
                    "review_status": "physician_accepted",
                },
            },
        )
    )

    assert status.available is True
    assert result.model_family == "bone_activity_multitask"
    assert result.prediction["engineering_inference_executed"] is True
    assert result.prediction["spatial_candidates_available"] is False
    assert result.prediction["safe_fallback_applied"] is True
    assert result.prediction["runtime_replacement_allowed"] is False
    assert "non_target_domain_proxy" in result.prediction["failure_reasons"]
    assert "engineering_utility_gate_failed" in result.prediction["failure_reasons"]
    assert result.segmentation_mask == {
        "available": False,
        "path": None,
        "format": None,
        "physician_review_required": True,
        "safe_fallback_applied": True,
    }
    spectrum = result.prediction["bone_activity_spectrum"]
    assert spectrum["activity_score"]["available"] is False
    assert spectrum["activity_class_map_path"] is None
    assert all(
        spectrum[key]["available"] is False
        for key in (
            "low_activity_candidate",
            "transition_candidate",
            "high_activity_candidate",
            "ignore_region",
        )
    )
    raw_path = Path(result.prediction["raw_engineering_outputs"]["path"])
    assert raw_path.is_file()
    assert result.prediction["raw_engineering_outputs"]["sha256"] == _sha256_file(raw_path)
    with np.load(raw_path) as raw:
        assert raw["bone_gate_probability"].shape == (24, 32)
        assert raw["activity_score"].shape == (24, 32)
        assert raw["class_probabilities"].shape == (3, 24, 32)
        assert raw["uncertainty"].shape == (24, 32)
        assert np.isfinite(raw["class_probabilities"]).all()
    evidence_path = Path(result.prediction["evidence_manifest_path"])
    assert evidence_path.is_file()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["checkpoint_sha256"] == _sha256_file(checkpoint_path)
    assert evidence["manifest_sha256"] == manifest_sha256
    assert evidence["source_inputs"]["white_light_sha256"] == _sha256_file(white_path)
    assert evidence["source_inputs"]["fluorescence_sha256"] == _sha256_file(fluorescence_path)
    warning_codes = {row["code"] for row in result.warnings}
    assert "bone_activity_proxy_engineering_only" in warning_codes
    assert "bone_activity_engineering_utility_gate_failed" in warning_codes
    assert "bone_activity_spatial_fallback" in warning_codes


def test_bone_activity_adapter_rejects_manifest_drift(tmp_path: Path) -> None:
    checkpoint_path, manifest_path, manifest_sha256 = _write_proxy_runtime_bundle(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["medical_boundary"] = "drifted"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    adapter = build_adapter(
        model_spec_from_mapping(_adapter_spec(checkpoint_path, manifest_path, manifest_sha256, tmp_path / "outputs"))
    )

    status = adapter.warmup()

    assert status.available is False
    assert any("manifest SHA256 mismatch" in reason for reason in status.reasons)


def test_bone_activity_adapter_rejects_proxy_runtime_flag_escalation(tmp_path: Path) -> None:
    checkpoint_path, manifest_path, _ = _write_proxy_runtime_bundle(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_allowed"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_sha256 = _sha256_file(manifest_path)
    adapter = build_adapter(
        model_spec_from_mapping(_adapter_spec(checkpoint_path, manifest_path, manifest_sha256, tmp_path / "outputs"))
    )

    status = adapter.warmup()

    assert status.available is False
    assert any("runtime_allowed flags disagree" in reason for reason in status.reasons)


def test_bone_activity_adapter_fails_closed_on_channel_dimension_mismatch(tmp_path: Path) -> None:
    checkpoint_path, manifest_path, manifest_sha256 = _write_proxy_runtime_bundle(tmp_path)
    white_path, fluorescence_path, _ = _write_input_pair(tmp_path)
    Image.fromarray(np.full((19, 21), 90, dtype=np.uint8)).save(fluorescence_path)
    adapter = build_adapter(
        model_spec_from_mapping(_adapter_spec(checkpoint_path, manifest_path, manifest_sha256, tmp_path / "outputs"))
    )

    result = adapter.predict(
        AdapterRequest(
            case_id="dimension-mismatch",
            input_path=str(white_path),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="microscope_dual_channel",
            metadata={"fluorescence_path": str(fluorescence_path)},
        )
    )

    assert result.prediction["engineering_inference_executed"] is False
    assert result.prediction["spatial_candidates_available"] is False
    assert result.prediction["failure_reasons"] == ["bone_activity_inference_failed"]
    assert result.segmentation_mask == {}
    assert any(row["code"] == "bone_activity_inference_failed" for row in result.warnings)


def test_target_domain_runtime_requires_checksum_bound_physician_identity(tmp_path: Path) -> None:
    checkpoint_path, manifest_path, manifest_sha256 = _write_runtime_bundle(tmp_path, target_domain=True)
    white_path, fluorescence_path, gate_path = _write_input_pair(tmp_path)
    spec = _adapter_spec(checkpoint_path, manifest_path, manifest_sha256, tmp_path / "outputs")
    spec["extra"]["strict_promotion_authorized"] = True
    spec["extra"]["runtime_replacement_allowed"] = True
    adapter = build_adapter(model_spec_from_mapping(spec))
    base_metadata = {
        "fluorescence_path": str(fluorescence_path),
        "dual_channel_registration_verified": True,
        "target_domain_input_verified": True,
    }
    forged = adapter.predict(
        AdapterRequest(
            case_id="target-gate-binding",
            input_path=str(white_path),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="microscope_dual_channel",
            metadata={
                **base_metadata,
                "reviewed_bone_gate": {
                    "path": str(gate_path),
                    "sha256": _sha256_file(gate_path),
                    "physician_reviewed": True,
                    "trusted_review": True,
                    "review_status": "physician_accepted",
                },
            },
        )
    )
    gate_pixels = int((np.asarray(Image.open(gate_path).convert("L")) > 127).sum())
    trusted = adapter.predict(
        AdapterRequest(
            case_id="target-gate-binding",
            input_path=str(white_path),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="microscope_dual_channel",
            metadata={
                **base_metadata,
                "reviewed_bone_gate": {
                    "path": str(gate_path),
                    "sha256": _sha256_file(gate_path),
                    "physician_reviewed": True,
                    "trusted_review": True,
                    "review_status": "physician_accepted",
                    "annotation_id": "ann-target-gate",
                    "annotation_version": 3,
                    "source_input_id": "white-input-1",
                    "source_checksum": _sha256_file(white_path),
                    "positive_pixel_count": gate_pixels,
                    "reviewed_at": "2026-07-19T12:00:00+08:00",
                    "reviewed_by": {
                        "actor_id": "physician-1",
                        "role": "physician",
                        "institution": "Test Hospital",
                        "auth_source": "institution_sso",
                    },
                },
            },
        )
    )

    assert forged.prediction["spatial_candidates_available"] is False
    assert "physician_reviewed_bone_gate_reviewer_identity_untrusted" in forged.prediction["failure_reasons"]
    assert "physician_reviewed_bone_gate_annotation_binding_missing" in forged.prediction["failure_reasons"]
    assert trusted.prediction["runtime_replacement_allowed"] is True
    assert trusted.prediction["spatial_candidates_available"] is True
    assert trusted.prediction["failure_reasons"] == []
    assert trusted.segmentation_mask["available"] is True
    assert Path(trusted.segmentation_mask["path"]).is_file()
    spectrum = trusted.prediction["bone_activity_spectrum"]
    assert spectrum["available"] is True
    assert spectrum["activity_score"]["available"] is True
    assert Path(spectrum["activity_class_map_path"]).is_file()


def _adapter_spec(
    checkpoint_path: Path,
    manifest_path: Path,
    manifest_sha256: str,
    output_dir: Path,
) -> dict[str, object]:
    return {
        "model_id": "bone_activity_test",
        "family": "bone_activity_multitask",
        "task_types": ["segmentation"],
        "input_types": ["dual_channel_image"],
        "checkpoint_path": str(checkpoint_path),
        "dependency_group": "torch",
        "device_policy": "cpu",
        "clinical_claim_allowed": False,
        "extra": {
            "runtime_allowed": True,
            "candidate_only": True,
            "engineering_candidate_execution_allowed": True,
            "runtime_replacement_allowed": False,
            "mainline_replacement_allowed": False,
            "strict_promotion_authorized": False,
            "checkpoint_manifest_path": str(manifest_path),
            "checkpoint_manifest_sha256": manifest_sha256,
            "input_shape": [24, 32],
            "output_dir": str(output_dir),
        },
    }


def _write_proxy_runtime_bundle(root: Path) -> tuple[Path, Path, str]:
    return _write_runtime_bundle(root, target_domain=False)


def _write_runtime_bundle(root: Path, *, target_domain: bool) -> tuple[Path, Path, str]:
    checkpoint_path = root / "bone_activity.pt"
    manifest_path = root / "bone_activity_manifest.json"
    model = BoneActivityMultiTask2D(base_channels=2)
    outputs = [
        "bone_gate",
        "activity_score",
        "class_logits",
        "class_probabilities",
        "uncertainty",
        "abstention",
    ]
    training_domain = {
        "target_domain": target_domain,
        "domain": "unit_test_target" if target_domain else "unit_test_proxy",
        "domain_tier": "target_domain" if target_domain else "non_target_proxy",
        "data_mode": "manifest",
        "training_scope": "target_domain_training" if target_domain else "non_target_proxy_pretraining",
        "channel_semantics": "registered_test_pair",
    }
    inference_thresholds = {
        "bone_gate_threshold": 0.4,
        "abstention_threshold": 0.6,
        "selection_source": "validation_split",
        "runtime_authorized": target_domain,
    }
    metadata = {
        "model_id": "bone_activity_test",
        "model_family": "dual_channel_bone_activity_multitask",
        "model_config": {"base_channels": 2},
        "training_domain": training_domain,
        "outputs": outputs,
        "inference_thresholds": inference_thresholds,
        "engineering_utility": {"ready": target_domain, "runtime_authorized": target_domain},
        "safety": {"bone_gate_fail_closed_passed": True, "abstention_passed": True},
        "labels": {
            "class_set": [*BONE_ACTIVITY_CLASSES, "ignore"],
            "physician_reviewed_bone_gate": False,
        },
        "validation": {"independent_test_set": False, "calibrated": False},
        "review": {"physician_reviewed": False},
        "runtime_allowed": target_domain,
        "clinical_claim_allowed": False,
        "medical_boundary": "Unit-test non-target-domain engineering evidence.",
    }
    torch.save({**metadata, "state_dict": model.state_dict()}, checkpoint_path)
    checkpoint_sha256 = _sha256_file(checkpoint_path)
    manifest = {
        "schema_version": "osteo-vision-bone-activity-multitask-checkpoint-v1",
        "capability": "bone_activity_multitask",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256,
        **metadata,
        "engineering_ready": True,
        "target_domain_promotion_ready": target_domain,
        "runtime_replacement_allowed": target_domain,
        "promotion": {
            "checkpoint_sha256": checkpoint_sha256,
            "target_domain_promotion_ready": target_domain,
            "runtime_replacement_allowed": target_domain,
            "promotion_blockers": [] if target_domain else [{"code": "non_target_domain_proxy"}],
            "errors": [],
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return checkpoint_path, manifest_path, _sha256_file(manifest_path)


def _write_input_pair(root: Path) -> tuple[Path, Path, Path]:
    white_path = root / "white.jpg"
    fluorescence_path = root / "fluorescence.jpg"
    gate_path = root / "gate.png"
    y, x = np.mgrid[0:30, 0:44]
    white = np.stack(
        [
            np.clip(40 + x * 3, 0, 255),
            np.clip(50 + y * 4, 0, 255),
            np.full((30, 44), 90),
        ],
        axis=2,
    ).astype(np.uint8)
    fluorescence = np.clip((x + y) * 3, 0, 255).astype(np.uint8)
    gate = (((x - 22) ** 2) / 18**2 + ((y - 15) ** 2) / 11**2 <= 1).astype(np.uint8) * 255
    Image.fromarray(white).save(white_path)
    Image.fromarray(fluorescence).save(fluorescence_path)
    Image.fromarray(gate).save(gate_path)
    return white_path, fluorescence_path, gate_path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
