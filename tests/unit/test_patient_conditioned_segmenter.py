from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml
from PIL import Image

from scripts.train_patient_conditioned_segmenter import (
    _symmetric_boundary_hausdorff_mm,
    train_patient_conditioned,
)
from osteo_vision_core.models.patient_conditioned_segmenter import (
    TinyPatientConditionedSegmenter2D,
    apply_patient_conditioning_safety_gate,
    load_patient_conditioned_checkpoint,
)


def _model(*, max_logit_delta: float = 0.4) -> TinyPatientConditionedSegmenter2D:
    torch.manual_seed(7)
    return TinyPatientConditionedSegmenter2D(
        clinical_feature_count=4,
        base_channels=4,
        modulation_basis_count=3,
        clinical_hidden_channels=8,
        max_logit_delta=max_logit_delta,
        min_present_fraction=0.75,
        clinical_mean=[50.0, 0.5, 7.0, 10.0],
        clinical_scale=[20.0, 0.5, 3.0, 20.0],
    )


def _inputs(batch_size: int = 2) -> tuple[torch.Tensor, ...]:
    torch.manual_seed(11)
    white = torch.rand(batch_size, 3, 24, 24)
    fluorescence = torch.rand(batch_size, 1, 24, 24)
    values = torch.tensor([[70.0, 1.0, 12.0, 50.0], [25.0, 0.0, 4.0, 1.0]])[:batch_size]
    present = torch.ones(batch_size, 4, dtype=torch.bool)
    return white, fluorescence, values, present


def test_trusted_context_produces_bounded_spatial_delta_and_all_outputs() -> None:
    model = _model(max_logit_delta=0.4).eval()
    white, fluorescence, values, present = _inputs()
    with torch.no_grad():
        output = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=torch.tensor([True, True]),
            conditioning_authorized=True,
        )

    assert output.image_only_logits.shape == (2, 1, 24, 24)
    assert output.conditioned_logits.shape == (2, 1, 24, 24)
    assert output.delta_map.shape == (2, 1, 24, 24)
    assert output.uncertainty.shape == (2, 1, 24, 24)
    assert torch.all(output.context_eligible)
    assert torch.count_nonzero(output.delta_map).item() > 0
    assert float(output.delta_map.abs().max()) <= 0.4 + 1e-6
    assert torch.allclose(output.conditioned_logits, output.image_only_logits + output.delta_map)
    assert torch.all((output.uncertainty >= 0) & (output.uncertainty <= 1))


@pytest.mark.parametrize("fallback", ["untrusted", "missing", "non_finite"])
def test_unsafe_context_has_exact_zero_spatial_effect(fallback: str) -> None:
    model = _model().eval()
    white, fluorescence, values, present = _inputs()
    trusted = torch.ones(2, dtype=torch.bool)
    if fallback == "untrusted":
        trusted[:] = False
    elif fallback == "missing":
        present[:] = False
    else:
        values[0, 0] = float("nan")
        trusted[1] = False
    with torch.no_grad():
        output = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=trusted,
            conditioning_authorized=True,
        )

    ineligible = ~output.context_eligible
    assert torch.any(ineligible)
    assert torch.count_nonzero(output.delta_map[ineligible]).item() == 0
    assert torch.equal(output.conditioned_logits[ineligible], output.image_only_logits[ineligible])


def test_context_changes_leave_image_only_logits_identical() -> None:
    model = _model().eval()
    white, fluorescence, values, present = _inputs()
    with torch.no_grad():
        first = model(
            white[:1],
            fluorescence[:1],
            values[:1],
            present[:1],
            context_trusted=True,
            conditioning_authorized=True,
        )
        second = model(
            white[:1],
            fluorescence[:1],
            values[1:],
            present[:1],
            context_trusted=True,
            conditioning_authorized=True,
        )

    assert torch.equal(first.image_only_logits, second.image_only_logits)
    assert not torch.equal(first.conditioned_logits, second.conditioned_logits)


def test_trusted_context_still_has_zero_effect_without_promotion_authorization() -> None:
    model = _model().eval()
    white, fluorescence, values, present = _inputs()
    with torch.no_grad():
        output = model(white, fluorescence, values, present, context_trusted=True)

    assert torch.count_nonzero(output.delta_map).item() == 0
    assert torch.equal(output.conditioned_logits, output.image_only_logits)


def test_runtime_gate_restricts_conditioning_to_reviewed_uncertain_bone() -> None:
    model = _model().eval()
    white, fluorescence, values, present = _inputs(batch_size=1)
    reviewed_gate = torch.zeros(1, 1, 24, 24)
    reviewed_gate[:, :, 6:18, 7:19] = 1
    with torch.no_grad():
        raw = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=True,
            conditioning_authorized=True,
        )
        result = apply_patient_conditioning_safety_gate(
            raw,
            reviewed_bone_gate=reviewed_gate,
            physician_reviewed_bone_gate=True,
            clinical_context_verified=True,
            target_domain=True,
            model_promotion_ready=True,
            uncertainty_threshold=0.01,
        )

    outside = reviewed_gate == 0
    assert result["available"] is True
    assert torch.count_nonzero(result["delta_map"][outside]).item() == 0
    assert torch.equal(result["conditioned_logits"][outside], result["image_only_logits"][outside])
    assert torch.count_nonzero(result["difference_mask"][outside]).item() == 0
    assert torch.all(result["spatial_effect_mask"] <= (reviewed_gate > 0))
    assert result["target_domain_promotion_ready"] is True


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"physician_reviewed_bone_gate": False}, "physician_reviewed_bone_gate_missing"),
        ({"clinical_context_verified": False}, "clinical_context_not_verified"),
        ({"target_domain": False}, "non_target_domain_proxy"),
        ({"model_promotion_ready": False}, "model_target_domain_promotion_missing"),
    ],
)
def test_runtime_gate_fails_closed_when_provenance_is_missing(overrides: dict[str, bool], reason: str) -> None:
    model = _model().eval()
    white, fluorescence, values, present = _inputs(batch_size=1)
    with torch.no_grad():
        raw = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=True,
            conditioning_authorized=True,
        )
    arguments = {
        "reviewed_bone_gate": torch.ones(1, 1, 24, 24),
        "physician_reviewed_bone_gate": True,
        "clinical_context_verified": True,
        "target_domain": True,
        "model_promotion_ready": True,
    }
    arguments.update(overrides)
    result = apply_patient_conditioning_safety_gate(raw, **arguments)

    assert result["available"] is False
    assert reason in result["failure_reasons"]
    assert torch.count_nonzero(result["delta_map"]).item() == 0
    assert torch.equal(result["conditioned_logits"], result["image_only_logits"])


def test_unet_backbone_preserves_output_shape_and_bounded_conditioning() -> None:
    torch.manual_seed(13)
    model = TinyPatientConditionedSegmenter2D(
        clinical_feature_count=4,
        base_channels=4,
        image_backbone="unet",
        modulation_basis_count=3,
        clinical_hidden_channels=8,
        max_logit_delta=0.2,
        min_present_fraction=0.75,
        clinical_mean=[50.0, 0.5, 7.0, 10.0],
        clinical_scale=[20.0, 0.5, 3.0, 20.0],
    ).eval()
    white, fluorescence, values, present = _inputs(batch_size=1)

    with torch.no_grad():
        output = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=True,
            conditioning_authorized=True,
        )

    assert output.conditioned_logits.shape == (1, 1, 24, 24)
    assert output.image_only_logits.shape == (1, 1, 24, 24)
    assert float(output.delta_map.abs().max()) <= 0.2 + 1e-6
    assert model.model_config()["image_backbone"] == "unet"


def test_physical_boundary_shift_uses_spacing_and_fails_closed_for_one_empty_mask() -> None:
    first = np.zeros((5, 5), dtype=np.bool_)
    second = np.zeros((5, 5), dtype=np.bool_)
    first[2, 1] = True
    second[2, 2] = True

    distance, status = _symmetric_boundary_hausdorff_mm(
        first,
        second,
        row_spacing_mm=0.5,
        column_spacing_mm=2.0,
    )
    assert distance == pytest.approx(2.0)
    assert status == "available"

    distance, status = _symmetric_boundary_hausdorff_mm(
        np.zeros((5, 5), dtype=np.bool_),
        np.zeros((5, 5), dtype=np.bool_),
        row_spacing_mm=0.5,
        column_spacing_mm=2.0,
    )
    assert distance == 0.0
    assert status == "both_empty_identical"

    distance, status = _symmetric_boundary_hausdorff_mm(
        first,
        np.zeros((5, 5), dtype=np.bool_),
        row_spacing_mm=0.5,
        column_spacing_mm=2.0,
    )
    assert distance is None
    assert status == "one_mask_empty_unavailable"


def test_proxy_training_smoke_writes_non_promotable_checkpoint_manifest(
    tmp_path: Path,
) -> None:
    config = {
        "capability": "patient_conditioned_segmentation",
        "promotion_policy_path": "configs/training/three_priority_promotion.yml",
        "seed": 19,
        "device": "cpu",
        "image_shape": [24, 24],
        "batch_size": 2,
        "max_train_batches": 2,
        "learning_rate": 0.001,
        "threshold": 0.5,
        "model": {
            "base_channels": 4,
            "modulation_basis_count": 3,
            "clinical_hidden_channels": 8,
            "max_logit_delta": 0.5,
            "min_present_fraction": 0.75,
        },
        "clinical_features": {
            "names": ["age_years", "diabetes", "wbc_10e9_l", "crp_mg_l"],
            "mean": [50.0, 0.2, 7.0, 10.0],
            "scale": [20.0, 0.4, 3.0, 20.0],
        },
        "proxy_smoke": {
            "group_counts": {"train": 2, "val": 1, "test": 1},
            "samples_per_group": 1,
        },
        "output": {"directory": str(tmp_path / "unused")},
    }
    config_path = tmp_path / "training.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = train_patient_conditioned(config_path, output_dir=tmp_path / "run")
    checkpoint_path = Path(result["checkpoint_path"])
    manifest_path = Path(result["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["capability"] == "patient_conditioned_segmentation"
    assert manifest["checkpoint_path"] == str(checkpoint_path)
    assert manifest["checkpoint_sha256"] == hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    assert manifest["training_domain"]["target_domain"] is False
    assert manifest["training"]["completed"] is True
    assert manifest["training"]["sample_count"] == 4
    assert manifest["training"]["patient_group_split"]["leakage_detected"] is False
    assert manifest["training"]["data_profile"]["unique_clinical_context_count"] == 4
    assert manifest["training"]["data_profile"]["auxiliary_equals_white_red_sample_rate"] == 0.0
    assert manifest["outputs"] == [
        "image_only_logits",
        "conditioned_logits",
        "delta_map",
        "uncertainty",
    ]
    assert manifest["safety"]["zero_spatial_effect_fallback_passed"] is True
    assert manifest["safety"]["bounded_modulation_passed"] is True
    assert manifest["safety"]["restricted_spatial_effect_passed"] is True
    assert manifest["validation"]["independent_test_set"] is False
    assert "conditioned_global_dice" in manifest["validation"]["proxy_test_metrics"]
    assert "conditioned_minus_image_only_dice" in manifest["validation"]["proxy_test_metrics"]
    assert manifest["validation"]["calibrated"] is False
    assert "dice" in manifest["validation"]["metrics"]
    assert "proxy_test_metrics" in manifest["validation"]
    assert manifest["review"]["physician_reviewed"] is False
    assert manifest["clinical_data"]["paired_image_mask_context"] is False
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    contract = manifest["clinical_data"]["feature_encoder_contract"]
    source_evidence = manifest["clinical_data"]["clinical_feature_source_evidence"]
    assert checkpoint["feature_encoder_contract"] == contract
    assert checkpoint["clinical_data"]["feature_encoder_contract"] == contract
    assert checkpoint["clinical_data"]["clinical_feature_source_evidence"] == source_evidence
    assert contract["feature_names"] == config["clinical_features"]["names"]
    assert source_evidence["feature_names"] == config["clinical_features"]["names"]
    assert all(
        row["source_description"].startswith("synthetic_proxy.generated.") for row in source_evidence["feature_sources"]
    )
    assert manifest["subgroup_audit"]["passed"] is False
    assert manifest["engineering_ready"] is True
    assert manifest["target_domain_promotion_ready"] is False
    assert manifest["promotion"]["engineering_ready"] is True
    assert manifest["promotion"]["target_domain_promotion_ready"] is False
    assert manifest["promotion"]["policy_status"] == "provisional_internal_engineering_gate"
    assert manifest["promotion_policy"]["status"] == "provisional_internal_engineering_gate"
    assert (
        manifest["promotion_policy"]["sha256"]
        == hashlib.sha256(Path(manifest["promotion_policy"]["path"]).read_bytes()).hexdigest()
    )
    assert manifest["promotion_policy"]["normalized_content_sha256"] == manifest["promotion"]["policy_sha256"]
    assert manifest["runtime_allowed"] is False

    loaded, metadata = load_patient_conditioned_checkpoint(checkpoint_path, device=torch.device("cpu"))
    assert isinstance(loaded, TinyPatientConditionedSegmenter2D)
    assert metadata["target_domain_promotion_ready"] is False


def test_training_rejects_feature_that_runtime_vector_contract_cannot_encode(tmp_path: Path) -> None:
    config = {
        "capability": "patient_conditioned_segmentation",
        "promotion_policy_path": "configs/training/three_priority_promotion.yml",
        "clinical_features": {
            "names": ["age_years", "unsupported_clinical_marker"],
            "mean": [50.0, 0.0],
            "scale": [20.0, 1.0],
        },
        "output": {"directory": str(tmp_path / "unused")},
    }
    config_path = tmp_path / "unsupported_feature.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported by the runtime vector contract"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_records_kits_proxy_contract_and_source_evidence(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    result = train_patient_conditioned(config_path, output_dir=tmp_path / "run")
    checkpoint_path = Path(result["checkpoint_path"])
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    source_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    assert manifest["training_domain"] == {
        "target_domain": False,
        "domain": "kits23_abdominal_ct_public_proxy",
        "domain_tier": "kits23_abdominal_ct_public_proxy",
        "data_mode": "manifest",
        "training_eligible_source": True,
        "training_scope": "non_target_proxy_pretraining",
        "channel_semantics": "non_fluorescence_ct_proxy",
    }
    assert manifest["training"]["source_manifest_path"] == str(manifest_path.resolve())
    assert manifest["training"]["source_manifest_sha256"] == source_sha
    assert manifest["training"]["patient_group_split"]["leakage_detected"] is False
    assert manifest["clinical_data"]["paired_image_mask_context"] is True
    assert manifest["clinical_data"]["channel_semantics"] == "non_fluorescence_ct_proxy"
    assert manifest["validation"]["independent_test_set"] is False
    assert manifest["training_domain"]["target_domain"] is False
    assert manifest["target_domain_promotion_ready"] is False
    assert manifest["runtime_replacement_allowed"] is False
    assert manifest["runtime_allowed"] is False
    assert manifest["promotion"]["policy_status"] == "provisional_internal_engineering_gate"
    assert manifest["promotion_policy"]["path"].endswith("three_priority_promotion.yml")

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    assert checkpoint["promotion_policy"]["sha256"] == manifest["promotion_policy"]["sha256"]
    assert checkpoint["training_domain"] == manifest["training_domain"]
    assert checkpoint["training_data"]["source_manifest_sha256"] == source_sha
    assert checkpoint["training_data"]["paired_image_mask_context"] is True
    assert checkpoint["clinical_data"]["paired_image_mask_context"] is True
    contract = manifest["clinical_data"]["feature_encoder_contract"]
    source_evidence = manifest["clinical_data"]["clinical_feature_source_evidence"]
    assert checkpoint["feature_encoder_contract"] == contract
    assert checkpoint["clinical_data"]["feature_encoder_contract"] == contract
    assert checkpoint["clinical_data"]["clinical_feature_source_evidence"] == source_evidence
    assert source_evidence["source_manifest_sha256"] == source_sha
    assert source_evidence["source_fields"] == [
        "clinical_values_json",
        "clinical_present_json",
        "clinical_mapping_json",
    ]
    assert source_evidence["feature_names"] == contract["feature_names"]
    assert source_evidence["evidence_sha256"] == _payload_sha256(
        {key: value for key, value in source_evidence.items() if key != "evidence_sha256"}
    )
    assert all(row["present_sample_count"] == 4 for row in source_evidence["feature_sources"])
    assert all(row["missing_sample_count"] == 0 for row in source_evidence["feature_sources"])
    assert all(row["present_patient_group_count"] == 3 for row in source_evidence["feature_sources"])
    assert all(
        row["source_description_sha256"] == hashlib.sha256(row["source_description"].encode("utf-8")).hexdigest()
        for row in source_evidence["feature_sources"]
    )
    assert checkpoint["loss_config"]["positive_class_weight"] == 1.0
    assert checkpoint["loss_config"]["freeze_image_after_warmup"] is True
    assert checkpoint["validation"]["independent_test_set"] is False
    assert checkpoint["runtime_allowed"] is False
    assert checkpoint["runtime_replacement_allowed"] is False
    assert checkpoint["target_domain_promotion_ready"] is False

    evidence_names = {
        "split_manifest",
        "prediction_manifest",
        "calibration_report",
        "subgroup_report",
        "safety_report",
        "physician_review",
    }
    assert set(manifest["evidence"]) == evidence_names
    evidence_payloads: dict[str, dict] = {}
    for name, record in manifest["evidence"].items():
        path = Path(record["path"])
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        evidence_payloads[name] = json.loads(path.read_text(encoding="utf-8"))
        assert evidence_payloads[name]["checkpoint_sha256"] == manifest["checkpoint_sha256"]

    assert all(record["finite_outputs"] for record in evidence_payloads["prediction_manifest"]["records"])
    assert evidence_payloads["calibration_report"]["proxy_calibration_computed"] is True
    assert evidence_payloads["calibration_report"]["calibrated"] is False
    assert 0.0 <= manifest["validation"]["metrics"]["ece"] <= 1.0
    assert evidence_payloads["subgroup_report"]["proxy_audit_computed"] is True
    assert evidence_payloads["subgroup_report"]["passed"] is False
    assert manifest["validation"]["metrics"]["worst_subgroup_dice_delta"] <= 1.0
    assert evidence_payloads["safety_report"]["output_contract_passed"] is True
    assert evidence_payloads["physician_review"]["trusted_physician_review_available"] is False
    blocker_codes = {item["code"] for item in manifest["promotion"]["promotion_blockers"]}
    assert "promotion_evidence_missing" not in blocker_codes
    assert "promotion_evidence_sha_mismatch" not in blocker_codes
    assert "promotion_evidence_checkpoint_mismatch" not in blocker_codes
    assert "calibration_evidence_failed" in blocker_codes
    assert "subgroup_evidence_failed" in blocker_codes
    assert "promotion_review_not_accepted" in blocker_codes
    assert "promotion_metric_missing_or_non_finite" not in blocker_codes
    mismatch_metrics = {
        item["metric"]
        for item in manifest["promotion"]["promotion_blockers"]
        if item["code"] == "promotion_metric_evidence_mismatch"
    }
    assert mismatch_metrics == set()
    assert manifest["validation"]["metrics"]["max_boundary_shift_mm"] >= 0.0
    assert evidence_payloads["prediction_manifest"]["physical_boundary_shift"]["available_for_all_records"] is True


def test_manifest_training_rejects_target_domain_row(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path, target_domain="true")
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="target_domain=false"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_rejects_missing_clinical_feature_source(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    rows = _read_csv_rows(manifest_path)
    mapping = json.loads(rows[0]["clinical_mapping_json"])
    mapping["renal_disease"] = ""
    rows[0]["clinical_mapping_json"] = json.dumps(mapping)
    _write_csv_rows(manifest_path, rows)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="non-empty source description"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_rejects_file_tampering(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    rows = _read_csv_rows(manifest_path)
    white_path = manifest_path.parent / rows[0]["white_path"]
    payload = bytearray(white_path.read_bytes())
    payload[-1] ^= 1
    white_path.write_bytes(payload)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="white SHA256 mismatch"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_rejects_declared_size_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    rows = _read_csv_rows(manifest_path)
    rows[0]["mask_size_bytes"] = str(int(rows[0]["mask_size_bytes"]) + 1)
    _write_csv_rows(manifest_path, rows)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="mask size mismatch"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_rejects_nonbinary_mask(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    rows = _read_csv_rows(manifest_path)
    mask_path = manifest_path.parent / rows[0]["mask_path"]
    Image.new("L", (16, 16), 127).save(mask_path)
    rows[0]["mask_sha256"] = hashlib.sha256(mask_path.read_bytes()).hexdigest()
    rows[0]["mask_size_bytes"] = str(mask_path.stat().st_size)
    _write_csv_rows(manifest_path, rows)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="mask must be binary"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_rejects_image_dimension_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    rows = _read_csv_rows(manifest_path)
    fluorescence_path = manifest_path.parent / rows[0]["fluorescence_path"]
    Image.new("L", (8, 16), 70).save(fluorescence_path)
    rows[0]["fluorescence_sha256"] = hashlib.sha256(fluorescence_path.read_bytes()).hexdigest()
    rows[0]["fluorescence_size_bytes"] = str(fluorescence_path.stat().st_size)
    _write_csv_rows(manifest_path, rows)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="image dimensions mismatch"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def test_manifest_training_rejects_affine_or_spacing_tampering(tmp_path: Path) -> None:
    manifest_path = _write_manifest_training_fixture(tmp_path)
    rows = _read_csv_rows(manifest_path)
    rows[0]["canonical_axis0_spacing_mm"] = "9.5"
    _write_csv_rows(manifest_path, rows)
    config_path = _write_manifest_training_config(tmp_path, manifest_path)

    with pytest.raises(ValueError, match="does not match canonical affine"):
        train_patient_conditioned(config_path, output_dir=tmp_path / "run")


def _write_manifest_training_config(tmp_path: Path, manifest_path: Path) -> Path:
    config = {
        "capability": "patient_conditioned_segmentation",
        "promotion_policy_path": "configs/training/three_priority_promotion.yml",
        "seed": 23,
        "device": "cpu",
        "image_shape": [16, 16],
        "batch_size": 2,
        "max_train_batches": 1,
        "learning_rate": 0.001,
        "threshold_candidates": [0.4, 0.5],
        "data": {"mode": "manifest", "manifest_path": str(manifest_path)},
        "loss": {
            "conditioning_warmup_batches": 0,
            "freeze_image_after_warmup": True,
        },
        "model": {
            "base_channels": 4,
            "modulation_basis_count": 3,
            "clinical_hidden_channels": 8,
            "max_logit_delta": 0.4,
            "min_present_fraction": 0.8,
        },
        "clinical_features": {
            "names": [
                "age_years",
                "sex_at_birth_female",
                "diabetes",
                "renal_disease",
                "egfr_ml_min_1_73m2",
            ],
            "mean": [60.0, 0.5, 0.2, 0.15, 75.0],
            "scale": [20.0, 0.5, 0.4, 0.35, 30.0],
        },
        "output": {"directory": str(tmp_path / "unused")},
    }
    config_path = tmp_path / "manifest_training.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def _write_manifest_training_fixture(tmp_path: Path, *, target_domain: str = "false") -> Path:
    data_dir = tmp_path / "manifest_data"
    data_dir.mkdir()
    rows: list[dict[str, str]] = []
    clinical_values = {
        "age_years": 63.0,
        "sex_at_birth_female": 1.0,
        "diabetes": 0.0,
        "renal_disease": 0.0,
        "egfr_ml_min_1_73m2": 82.0,
    }
    clinical_present = {name: True for name in clinical_values}
    clinical_mapping = {
        "age_years": "unit_fixture.age_years",
        "sex_at_birth_female": "unit_fixture.sex_at_birth",
        "diabetes": "unit_fixture.comorbidities.diabetes",
        "renal_disease": "unit_fixture.comorbidities.renal_disease",
        "egfr_ml_min_1_73m2": "unit_fixture.labs.egfr",
    }
    source_affine = [
        [0.8, 0.0, 0.0, 0.0],
        [0.0, 1.2, 0.0, 0.0],
        [0.0, 0.0, 2.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    source_affine_json = json.dumps(source_affine, separators=(",", ":"))
    for index, split in enumerate(("train", "train", "val", "test")):
        sample_id = f"kits-proxy-{index:02d}"
        patient_group_id = "patient-train" if split == "train" else f"patient-{split}"
        white_path = data_dir / f"{sample_id}_white.png"
        auxiliary_path = data_dir / f"{sample_id}_auxiliary.png"
        mask_path = data_dir / f"{sample_id}_mask.png"
        Image.new("RGB", (16, 16), (90 + index, 110, 130)).save(white_path)
        Image.new("L", (16, 16), 70 + index).save(auxiliary_path)
        Image.new("L", (16, 16), 255).save(mask_path)
        rows.append(
            {
                "sample_id": sample_id,
                "patient_group_id": patient_group_id,
                "split": split,
                "white_path": white_path.name,
                "white_sha256": hashlib.sha256(white_path.read_bytes()).hexdigest(),
                "white_size_bytes": str(white_path.stat().st_size),
                "fluorescence_path": auxiliary_path.name,
                "fluorescence_sha256": hashlib.sha256(auxiliary_path.read_bytes()).hexdigest(),
                "fluorescence_size_bytes": str(auxiliary_path.stat().st_size),
                "mask_path": mask_path.name,
                "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
                "mask_size_bytes": str(mask_path.stat().st_size),
                "source_ct_affine_json": source_affine_json,
                "source_ct_affine_sha256": hashlib.sha256(source_affine_json.encode("utf-8")).hexdigest(),
                "canonical_ct_affine_json": source_affine_json,
                "canonical_ct_affine_sha256": hashlib.sha256(source_affine_json.encode("utf-8")).hexdigest(),
                "canonical_axis0_spacing_mm": "0.8",
                "canonical_axis1_spacing_mm": "1.2",
                "spacing_unit": "mm",
                "spacing_axis_contract": "array_axis0_rows;array_axis1_columns",
                "clinical_values_json": json.dumps(clinical_values),
                "clinical_present_json": json.dumps(clinical_present),
                "clinical_mapping_json": json.dumps(clinical_mapping),
                "context_trusted": "true",
                "target_domain": target_domain,
                "training_eligible": "true",
                "training_scope": "non_target_proxy_pretraining",
                "runtime_replacement_allowed": "false",
                "domain_tier": "kits23_abdominal_ct_public_proxy",
                "channel_semantics": "non_fluorescence_ct_proxy",
            }
        )
    manifest_path = data_dir / "samples.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest_path


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _payload_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
