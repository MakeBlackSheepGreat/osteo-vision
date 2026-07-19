from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pytest
import torch
from PIL import Image

from src.core.clinical_context_verification import CLINICAL_CONTEXT_VERIFICATION_VALIDITY_HOURS
from src.core.schemas import AdapterRequest
from src.models.adapters import BaseModelAdapter, build_adapters, select_adapter
from src.models.clinical_feature_vector import (
    DEFAULT_CLINICAL_FEATURE_NAMES,
    build_clinical_feature_encoder_contract,
    build_clinical_feature_vector,
    compute_clinical_context_assessment_checksum,
)
from src.models.patient_conditioned_runtime import PATIENT_CONDITIONING_METADATA_CONTRACT
from src.models.patient_conditioned_segmenter import TinyPatientConditionedSegmenter2D

FEATURE_NAMES = [
    "age_years",
    "sex_at_birth_female",
    "diabetes",
    "renal_disease",
    "egfr_ml_min_1_73m2",
]


def test_proxy_adapter_writes_complete_evidence_and_keeps_image_only_fallback(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    white, fluorescence, gate = _write_inputs(tmp_path)
    adapter = _build_adapter(tmp_path, checkpoint, manifest)

    status = adapter.warmup()
    result = adapter.predict(
        AdapterRequest(
            case_id="case/proxy",
            input_path=str(white),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata=_metadata(fluorescence, gate),
        )
    )

    assert status.available is True
    assert result.prediction["available"] is True
    assert result.prediction["spatial_effect_applied"] is False
    assert result.prediction["safe_fallback_applied"] is True
    assert result.prediction["runtime_replacement_allowed"] is False
    assert result.prediction["proxy_checkpoint"] is True
    assert "non_target_domain_proxy" in result.prediction["failure_reasons"]
    assert "model_target_domain_promotion_missing" in result.prediction["failure_reasons"]
    for key in (
        "image_only_probability_path",
        "conditioned_probability_path",
        "delta_map_path",
        "difference_mask_path",
        "spatial_effect_mask_path",
        "uncertainty_path",
    ):
        assert Path(result.prediction[key]).is_file()
        assert result.lesion_evidence[key] == result.prediction[key]
    image_only = np.load(result.prediction["image_only_probability_array_path"])
    conditioned = np.load(result.prediction["conditioned_probability_array_path"])
    delta = np.load(result.prediction["delta_map_array_path"])
    assert np.array_equal(conditioned, image_only)
    assert np.count_nonzero(delta) == 0
    assert result.segmentation_mask["safe_fallback_applied"] is True
    assert result.quantification["difference_area_px"] == 0
    assert result.prediction["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert result.prediction["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert Path(result.prediction["evidence_manifest_path"]).is_file()
    feature_vector = result.prediction["clinical_feature_vector"]
    assert feature_vector["feature_version"] == "clinical-feature-vector-v1"
    assert feature_vector["checkpoint_consumed_mask"] == [True] * len(FEATURE_NAMES)
    assert feature_vector["spatial_effect_applied_mask"] == [False] * len(FEATURE_NAMES)


def test_runtime_projects_full_assessment_vector_to_kits_checkpoint_features(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    white, fluorescence, gate = _write_inputs(tmp_path)
    metadata = _metadata(fluorescence, gate)
    assessment = metadata["clinical_context_assessment"]
    assessment["clinical_feature_vector"] = build_clinical_feature_vector(
        assessment["clinical_context_snapshot"],
        assessment["normalized_labs"],
        context_checksum=assessment["clinical_context_checksum"],
    )
    assessment["clinical_context_assessment_checksum"] = compute_clinical_context_assessment_checksum(assessment)
    adapter = _build_adapter(tmp_path, checkpoint, manifest)

    result = adapter.predict(
        AdapterRequest(
            case_id="full-vector-checkpoint-projection",
            input_path=str(white),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata=metadata,
        )
    )

    assert assessment["clinical_feature_vector"]["feature_names"] == list(DEFAULT_CLINICAL_FEATURE_NAMES)
    runtime_vector = result.prediction["clinical_feature_vector"]
    assert runtime_vector["feature_names"] == FEATURE_NAMES
    assert runtime_vector["checkpoint_consumed_mask"] == [True] * len(FEATURE_NAMES)
    assert "clinical_feature_vector_checkpoint_features_mismatch" not in result.prediction["failure_reasons"]
    assert result.prediction["spatial_effect_applied"] is False


def test_proxy_adapter_fails_closed_for_untrusted_or_tampered_bone_gate(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    white, fluorescence, gate = _write_inputs(tmp_path)
    metadata = _metadata(fluorescence, gate)
    metadata["reviewed_bone_gate"]["sha256"] = "0" * 64
    adapter = _build_adapter(tmp_path, checkpoint, manifest)

    result = adapter.predict(
        AdapterRequest(
            case_id="tampered-gate",
            input_path=str(white),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata=metadata,
        )
    )

    assert result.prediction["available"] is True
    assert result.prediction["spatial_effect_applied"] is False
    assert "physician_reviewed_bone_gate_sha256_mismatch" in result.prediction["failure_reasons"]
    assert np.array_equal(
        np.load(result.prediction["conditioned_probability_array_path"]),
        np.load(result.prediction["image_only_probability_array_path"]),
    )


def test_adapter_warmup_rejects_checkpoint_or_manifest_tampering(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    adapter = _build_adapter(tmp_path, checkpoint, manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["checkpoint_sha256"] = "f" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    status = adapter.warmup()

    assert status.available is False
    assert any("manifest SHA256 mismatch" in reason for reason in status.reasons)
    assert any(item["code"] == "patient_conditioned_runtime_validation_failed" for item in status.warnings)


def test_adapter_warmup_rejects_checkpoint_sha256_mismatch(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    with checkpoint.open("ab") as handle:
        handle.write(b"tampered")
    spec = _runtime_spec(tmp_path, checkpoint, manifest)
    spec["extra"].pop("checkpoint_manifest_sha256")

    status = build_adapters({"models": [spec]})[0].warmup()

    assert status.available is False
    assert any("checkpoint SHA256 mismatch" in reason for reason in status.reasons)


@pytest.mark.parametrize(
    ("defect", "expected_reason"),
    [
        ("schema", "clinical_feature_encoder_schema_incompatible"),
        ("version", "clinical_feature_encoder_version_incompatible"),
        ("feature_order", "clinical_feature_encoder_feature_names_mismatch"),
        ("bounds", "clinical_feature_encoder_bounds_mismatch"),
        ("mask_semantics", "clinical_feature_encoder_mask_semantics_mismatch"),
        ("checksum", "clinical_feature_encoder_contract_checksum_mismatch"),
    ],
)
def test_adapter_rejects_incompatible_or_tampered_feature_encoder_contract(
    tmp_path: Path,
    defect: str,
    expected_reason: str,
) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)

    def mutate(contract: dict) -> None:
        if defect == "schema":
            contract["schema_version"] = "osteo-vision-clinical-feature-vector-v2"
        elif defect == "version":
            contract["feature_version"] = "clinical-feature-vector-v2"
        elif defect == "feature_order":
            contract["feature_names"] = list(reversed(contract["feature_names"]))
        elif defect == "bounds":
            contract["feature_bounds"]["age_years"] = [0.0, 200.0]
        elif defect == "mask_semantics":
            contract["mask_semantics"]["present"] = "unverified_value"
        else:
            contract["contract_sha256"] = "0" * 64

    _replace_all_encoder_contracts(
        checkpoint,
        manifest,
        mutate,
        rehash=defect != "checksum",
    )
    status = _build_adapter(tmp_path, checkpoint, manifest).warmup()

    assert status.available is False
    assert any(expected_reason in reason for reason in status.reasons)


@pytest.mark.parametrize(
    ("defect", "expected_reason"),
    [
        ("feature_order", "clinical_feature_source_feature_names_mismatch"),
        ("row_order", "clinical_feature_source_row_order_mismatch"),
        ("source_fields", "clinical_feature_source_fields_mismatch"),
        ("description_checksum", "clinical_feature_source_description_sha256_mismatch"),
        ("count_type", "clinical_feature_source_counts_invalid"),
        ("evidence_checksum", "clinical_feature_source_evidence_sha256_mismatch"),
    ],
)
def test_adapter_rejects_invalid_clinical_feature_source_evidence(
    tmp_path: Path,
    defect: str,
    expected_reason: str,
) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)

    def mutate(evidence: dict) -> None:
        if defect == "feature_order":
            evidence["feature_names"] = list(reversed(evidence["feature_names"]))
        elif defect == "row_order":
            evidence["feature_sources"] = list(reversed(evidence["feature_sources"]))
        elif defect == "source_fields":
            evidence["source_fields"] = list(reversed(evidence["source_fields"]))
        elif defect == "description_checksum":
            evidence["feature_sources"][0]["source_description_sha256"] = "0" * 64
        elif defect == "count_type":
            evidence["feature_sources"][0]["present_sample_count"] = "4"
        else:
            evidence["evidence_sha256"] = "0" * 64

    _replace_all_source_evidence(
        checkpoint,
        manifest,
        mutate,
        rehash=defect != "evidence_checksum",
    )
    status = _build_adapter(tmp_path, checkpoint, manifest).warmup()

    assert status.available is False
    assert any(expected_reason in reason for reason in status.reasons)


def test_adapter_rejects_validly_rehashed_manifest_source_evidence_tampering(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)

    def mutate_manifest(checkpoint_payload: dict, manifest_payload: dict) -> None:
        del checkpoint_payload
        evidence = manifest_payload["clinical_data"]["clinical_feature_source_evidence"]
        description = "tampered source description"
        evidence["feature_sources"][0]["source_description"] = description
        evidence["feature_sources"][0]["source_description_sha256"] = hashlib.sha256(
            description.encode("utf-8")
        ).hexdigest()
        evidence["evidence_sha256"] = _canonical_sha256(
            {key: value for key, value in evidence.items() if key != "evidence_sha256"}
        )

    _rewrite_runtime_artifacts(checkpoint, manifest, mutate_manifest)
    status = _build_adapter(tmp_path, checkpoint, manifest).warmup()

    assert status.available is False
    assert any(
        "Checkpoint and manifest clinical feature source evidence disagree" in reason for reason in status.reasons
    )


@pytest.mark.parametrize("missing_component", ["encoder_contract", "source_evidence"])
def test_adapter_rejects_single_artifact_copy_missing(
    tmp_path: Path,
    missing_component: str,
) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)

    def remove_manifest_copy(checkpoint_payload: dict, manifest_payload: dict) -> None:
        del checkpoint_payload
        field = (
            "feature_encoder_contract"
            if missing_component == "encoder_contract"
            else "clinical_feature_source_evidence"
        )
        manifest_payload["clinical_data"].pop(field)

    _rewrite_runtime_artifacts(checkpoint, manifest, remove_manifest_copy)
    status = _build_adapter(tmp_path, checkpoint, manifest).warmup()

    assert status.available is False
    assert any("missing from one" in reason for reason in status.reasons)


def test_legacy_proxy_without_new_contracts_loads_only_with_all_promotion_flags_disabled(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path, include_clinical_contracts=False)

    status = _build_adapter(tmp_path, checkpoint, manifest).warmup()

    assert status.available is True


@pytest.mark.parametrize(
    "unsafe_flags",
    [
        {"target_domain": True},
        {"runtime_allowed": True},
    ],
)
def test_legacy_artifact_without_new_contracts_rejects_target_domain_or_runtime_promotion(
    tmp_path: Path,
    unsafe_flags: dict,
) -> None:
    checkpoint, manifest = _write_proxy_runtime(
        tmp_path,
        include_clinical_contracts=False,
        **unsafe_flags,
    )

    status = _build_adapter(tmp_path, checkpoint, manifest).warmup()

    assert status.available is False
    assert any(
        "feature encoder contract and clinical feature source evidence are required" in reason
        for reason in status.reasons
    )


def test_proxy_adapter_requires_candidate_only_and_explicit_selection(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    invalid = _runtime_spec(tmp_path, checkpoint, manifest)
    invalid["extra"]["candidate_only"] = False
    candidate = _runtime_spec(tmp_path, checkpoint, manifest)
    candidate["model_id"] = "patient_candidate"
    adapters = build_adapters(
        {
            "models": [
                candidate,
                {
                    "model_id": "mainline",
                    "family": "fixture",
                    "task_types": ["segmentation"],
                    "input_types": ["dual_channel_image"],
                },
            ]
        }
    )

    assert build_adapters({"models": [invalid]})[0].warmup().available is False
    automatic, _ = select_adapter(
        adapters,
        task_type="segmentation",
        input_type="dual_channel_image",
        modality="white_light_fluorescence",
    )
    explicit, _ = select_adapter(
        adapters,
        task_type="segmentation",
        input_type="dual_channel_image",
        modality="white_light_fluorescence",
        policy="explicit",
        explicit_model_id="patient_candidate",
    )
    assert automatic is not None and automatic.describe().model_id == "mainline"
    assert explicit is not None and explicit.describe().model_id == "patient_candidate"


def test_metadata_contract_declares_all_safety_inputs() -> None:
    assert PATIENT_CONDITIONING_METADATA_CONTRACT["fluorescence_path"].startswith("required")
    assert PATIENT_CONDITIONING_METADATA_CONTRACT["dual_channel_registration_verified"].startswith("required")
    assert "clinical_context_assessment" in PATIENT_CONDITIONING_METADATA_CONTRACT
    assert "spatial_conditioning_authorized" in PATIENT_CONDITIONING_METADATA_CONTRACT["clinical_context_assessment"]
    assert "clinical_feature_vector" in PATIENT_CONDITIONING_METADATA_CONTRACT["clinical_context_assessment"]
    assert "reviewed_bone_gate" in PATIENT_CONDITIONING_METADATA_CONTRACT
    assert PATIENT_CONDITIONING_METADATA_CONTRACT["target_domain_input_verified"].startswith("required")


def _build_adapter(tmp_path: Path, checkpoint: Path, manifest: Path) -> BaseModelAdapter:
    return build_adapters({"models": [_runtime_spec(tmp_path, checkpoint, manifest)]})[0]


def _runtime_spec(tmp_path: Path, checkpoint: Path, manifest: Path) -> dict:
    return {
        "model_id": "patient_proxy",
        "family": "patient_conditioned_segmenter",
        "task_types": ["segmentation"],
        "input_types": ["dual_channel_image"],
        "checkpoint_path": str(checkpoint),
        "dependency_group": "torch",
        "device_policy": "cpu",
        "clinical_claim_allowed": False,
        "extra": {
            "runtime_allowed": True,
            "candidate_only": True,
            "engineering_candidate_execution_allowed": True,
            "runtime_replacement_allowed": False,
            "checkpoint_manifest_path": str(manifest),
            "checkpoint_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "output_dir": str(tmp_path / "outputs"),
            "threshold": 0.5,
            "uncertainty_threshold": 0.01,
        },
    }


def _write_proxy_runtime(
    tmp_path: Path,
    *,
    include_clinical_contracts: bool = True,
    target_domain: bool = False,
    runtime_allowed: bool = False,
) -> tuple[Path, Path]:
    torch.manual_seed(31)
    model = TinyPatientConditionedSegmenter2D(
        clinical_feature_count=len(FEATURE_NAMES),
        base_channels=2,
        modulation_basis_count=2,
        clinical_hidden_channels=4,
        max_logit_delta=0.2,
        min_present_fraction=0.8,
        image_backbone="unet",
        clinical_mean=[60.0, 0.5, 0.2, 0.15, 75.0],
        clinical_scale=[20.0, 0.5, 0.4, 0.35, 30.0],
    )
    checkpoint = tmp_path / "patient_proxy.pt"
    feature_encoder_contract = build_clinical_feature_encoder_contract(FEATURE_NAMES)
    source_evidence = _clinical_feature_source_evidence()
    clinical_data = {"feature_names": FEATURE_NAMES}
    if include_clinical_contracts:
        clinical_data.update(
            {
                "feature_encoder_contract": feature_encoder_contract,
                "clinical_feature_source_evidence": source_evidence,
            }
        )
    checkpoint_payload = {
        "capability": "patient_conditioned_segmentation",
        "model_id": "patient_proxy",
        "model_family": "patient_conditioned_segmenter",
        "model_config": model.model_config(),
        "clinical_feature_names": FEATURE_NAMES,
        "clinical_data": clinical_data,
        "state_dict": model.state_dict(),
        "threshold": 0.5,
        "training_domain": {"target_domain": target_domain, "domain": "unit_test_proxy"},
        "runtime_allowed": runtime_allowed,
        "runtime_replacement_allowed": False,
        "engineering_ready": True,
        "target_domain_promotion_ready": False,
        "medical_boundary": "Non-target-domain proxy evidence requiring physician review.",
    }
    if include_clinical_contracts:
        checkpoint_payload["feature_encoder_contract"] = feature_encoder_contract
    torch.save(checkpoint_payload, checkpoint)
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = tmp_path / "patient_proxy_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-patient-conditioned-training-v1",
                "capability": "patient_conditioned_segmentation",
                "checkpoint_path": str(checkpoint),
                "checkpoint_sha256": checkpoint_sha,
                "training_domain": {"target_domain": target_domain, "domain": "unit_test_proxy"},
                "clinical_data": clinical_data,
                "engineering_ready": True,
                "target_domain_promotion_ready": False,
                "runtime_allowed": runtime_allowed,
                "runtime_replacement_allowed": False,
                "clinical_claim_allowed": False,
                "medical_boundary": "Non-target-domain proxy evidence requiring physician review.",
                "promotion": {
                    "checkpoint_sha256": checkpoint_sha,
                    "target_domain_promotion_ready": False,
                    "runtime_replacement_allowed": False,
                    "promotion_blockers": [{"code": "non_target_domain_proxy"}],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return checkpoint, manifest


def _clinical_feature_source_evidence() -> dict:
    descriptions = {
        "age_years": "clinical_mapping_json.age_years from source cohort demographics",
        "sex_at_birth_female": "clinical_mapping_json.sex_at_birth_female from source cohort demographics",
        "diabetes": "clinical_mapping_json.diabetes from source cohort comorbidity metadata",
        "renal_disease": "clinical_mapping_json.renal_disease from source cohort comorbidity metadata",
        "egfr_ml_min_1_73m2": "clinical_mapping_json.egfr_ml_min_1_73m2 from source cohort laboratory metadata",
    }
    payload = {
        "schema_version": "osteo-vision-clinical-feature-source-evidence-v1",
        "source_manifest_sha256": "a" * 64,
        "feature_names": FEATURE_NAMES,
        "source_fields": ["clinical_values_json", "clinical_present_json", "clinical_mapping_json"],
        "feature_sources": [
            {
                "feature_name": name,
                "source_description": descriptions[name],
                "source_description_sha256": hashlib.sha256(descriptions[name].encode("utf-8")).hexdigest(),
                "present_sample_count": 4,
                "missing_sample_count": 0,
                "present_patient_group_count": 4,
            }
            for name in FEATURE_NAMES
        ],
    }
    payload["evidence_sha256"] = _canonical_sha256(payload)
    return payload


def _canonical_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _rewrite_runtime_artifacts(
    checkpoint: Path,
    manifest: Path,
    mutate: Callable[[dict, dict], None],
) -> None:
    checkpoint_payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    mutate(checkpoint_payload, manifest_payload)
    torch.save(checkpoint_payload, checkpoint)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest_payload["checkpoint_sha256"] = checkpoint_sha256
    manifest_payload["promotion"]["checkpoint_sha256"] = checkpoint_sha256
    manifest.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _replace_all_encoder_contracts(
    checkpoint: Path,
    manifest: Path,
    mutate: Callable[[dict], None],
    *,
    rehash: bool,
) -> None:
    def replace(checkpoint_payload: dict, manifest_payload: dict) -> None:
        contract = deepcopy(checkpoint_payload["feature_encoder_contract"])
        mutate(contract)
        if rehash:
            contract["contract_sha256"] = _canonical_sha256(
                {key: value for key, value in contract.items() if key != "contract_sha256"}
            )
        checkpoint_payload["feature_encoder_contract"] = deepcopy(contract)
        checkpoint_payload["clinical_data"]["feature_encoder_contract"] = deepcopy(contract)
        manifest_payload["clinical_data"]["feature_encoder_contract"] = deepcopy(contract)

    _rewrite_runtime_artifacts(checkpoint, manifest, replace)


def _replace_all_source_evidence(
    checkpoint: Path,
    manifest: Path,
    mutate: Callable[[dict], None],
    *,
    rehash: bool,
) -> None:
    def replace(checkpoint_payload: dict, manifest_payload: dict) -> None:
        evidence = deepcopy(checkpoint_payload["clinical_data"]["clinical_feature_source_evidence"])
        mutate(evidence)
        if rehash:
            evidence["evidence_sha256"] = _canonical_sha256(
                {key: value for key, value in evidence.items() if key != "evidence_sha256"}
            )
        checkpoint_payload["clinical_data"]["clinical_feature_source_evidence"] = deepcopy(evidence)
        manifest_payload["clinical_data"]["clinical_feature_source_evidence"] = deepcopy(evidence)

    _rewrite_runtime_artifacts(checkpoint, manifest, replace)


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    white = tmp_path / "white.png"
    fluorescence = tmp_path / "fluorescence.png"
    gate = tmp_path / "reviewed_bone_gate.png"
    rgb = np.full((20, 28, 3), 96, dtype=np.uint8)
    rgb[5:15, 7:21, 1] = 180
    signal = np.zeros((20, 28), dtype=np.uint8)
    signal[6:16, 8:22] = 220
    gate_mask = np.zeros((20, 28), dtype=np.uint8)
    gate_mask[4:17, 6:23] = 255
    Image.fromarray(rgb).save(white)
    Image.fromarray(signal).save(fluorescence)
    Image.fromarray(gate_mask).save(gate)
    return white, fluorescence, gate


def _metadata(fluorescence: Path, gate: Path) -> dict:
    snapshot = {
        "age_years": 68,
        "sex_at_birth": "female",
        "comorbidities": ["type_2_diabetes"],
        "medications": [],
        "labs": [
            {
                "name": "eGFR",
                "value": 76.0,
                "unit": "mL/min/1.73m2",
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "abnormal_flag": "normal",
            }
        ],
        "comorbidities_reviewed": True,
        "medications_reviewed": True,
        "deidentified": True,
        "review_status": "verified",
        "verified_by": {
            "actor_id": "doctor-patient-runtime",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "verified_identity_token",
        },
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "clinical_use_boundary": "restricted_spatial_conditioning_with_physician_review",
    }
    checksum = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    normalized_labs = [
        {
            "source_name": "eGFR",
            "canonical_name": "eGFR",
            "canonical_value": 76.0,
            "canonical_unit": "mL/min/1.73m2",
            "eligible_for_rule_summary": True,
        }
    ]
    feature_vector = build_clinical_feature_vector(
        snapshot,
        normalized_labs,
        context_checksum=checksum,
        feature_names=FEATURE_NAMES,
    )
    assessment = {
        "schema_version": "osteo-vision-clinical-context-assessment-v1",
        "clinical_context_snapshot": snapshot,
        "clinical_context_checksum": checksum,
        "clinical_context_quality": {
            "status": "ready_for_rule_summary",
            "review_status": "verified",
            "deidentified": True,
            "issues": [],
        },
        "normalized_labs": normalized_labs,
        "clinical_feature_vector": feature_vector,
        "spatial_conditioning_authorized": True,
    }
    assessment["clinical_context_assessment_checksum"] = compute_clinical_context_assessment_checksum(assessment)
    return {
        "fluorescence_path": str(fluorescence),
        "dual_channel_registration_verified": True,
        "clinical_context_assessment": assessment,
        "reviewed_bone_gate": {
            "path": str(gate),
            "sha256": hashlib.sha256(gate.read_bytes()).hexdigest(),
            "physician_reviewed": True,
            "trusted_review": True,
            "review_status": "physician_accepted",
        },
        "target_domain_input_verified": True,
    }


@pytest.mark.parametrize(
    ("verification_defect", "expected_reason"),
    [
        ("missing_identity", "clinical_context_verified_by_missing"),
        ("missing_timestamp", "clinical_context_verified_at_missing"),
        ("future_timestamp", "clinical_context_verified_at_in_future"),
        ("expired_timestamp", "clinical_context_verification_expired"),
    ],
)
def test_proxy_adapter_rechecks_invalid_verified_snapshot_and_falls_back(
    tmp_path: Path,
    verification_defect: str,
    expected_reason: str,
) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    white, fluorescence, gate = _write_inputs(tmp_path)
    metadata = _metadata(fluorescence, gate)
    snapshot = metadata["clinical_context_assessment"]["clinical_context_snapshot"]
    if verification_defect == "missing_identity":
        snapshot["verified_by"] = None
    elif verification_defect == "missing_timestamp":
        snapshot["verified_at"] = None
    elif verification_defect == "future_timestamp":
        snapshot["verified_at"] = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    else:
        snapshot["verified_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=CLINICAL_CONTEXT_VERIFICATION_VALIDITY_HOURS, seconds=1)
        ).isoformat()
    metadata["clinical_context_assessment"]["clinical_context_checksum"] = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    adapter = _build_adapter(tmp_path, checkpoint, manifest)

    result = adapter.predict(
        AdapterRequest(
            case_id="forged-clinical-verification",
            input_path=str(white),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata=metadata,
        )
    )

    assert expected_reason in result.prediction["failure_reasons"]
    assert "clinical_context_not_verified" in result.prediction["failure_reasons"]
    assert np.array_equal(
        np.load(result.prediction["conditioned_probability_array_path"]),
        np.load(result.prediction["image_only_probability_array_path"]),
    )
    assert np.count_nonzero(np.load(result.prediction["delta_map_array_path"])) == 0


def test_proxy_adapter_rejects_unbound_normalized_lab_and_vector_replacement(tmp_path: Path) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    white, fluorescence, gate = _write_inputs(tmp_path)
    metadata = _metadata(fluorescence, gate)
    assessment = metadata["clinical_context_assessment"]
    assessment["normalized_labs"][0]["canonical_value"] = 11.0
    assessment["clinical_feature_vector"] = build_clinical_feature_vector(
        assessment["clinical_context_snapshot"],
        assessment["normalized_labs"],
        context_checksum=assessment["clinical_context_checksum"],
        feature_names=FEATURE_NAMES,
    )
    adapter = _build_adapter(tmp_path, checkpoint, manifest)

    result = adapter.predict(
        AdapterRequest(
            case_id="unbound-derived-clinical-evidence",
            input_path=str(white),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata=metadata,
        )
    )

    assert "clinical_context_assessment_checksum_mismatch" in result.prediction["failure_reasons"]
    assert result.prediction["clinical_feature_vector"]["checkpoint_consumed_count"] == 0
    assert np.array_equal(
        np.load(result.prediction["conditioned_probability_array_path"]),
        np.load(result.prediction["image_only_probability_array_path"]),
    )


def test_proxy_adapter_rejects_forged_spatial_authorization_when_case_boundary_disallows_it(
    tmp_path: Path,
) -> None:
    checkpoint, manifest = _write_proxy_runtime(tmp_path)
    white, fluorescence, gate = _write_inputs(tmp_path)
    metadata = _metadata(fluorescence, gate)
    assessment = metadata["clinical_context_assessment"]
    snapshot = assessment["clinical_context_snapshot"]
    snapshot["clinical_use_boundary"] = "risk_prior_and_calibration_only_no_spatial_boundary_effect"
    assessment["clinical_context_checksum"] = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assessment["clinical_feature_vector"] = build_clinical_feature_vector(
        snapshot,
        assessment["normalized_labs"],
        context_checksum=assessment["clinical_context_checksum"],
        feature_names=FEATURE_NAMES,
    )
    assessment["clinical_context_assessment_checksum"] = compute_clinical_context_assessment_checksum(assessment)
    adapter = _build_adapter(tmp_path, checkpoint, manifest)

    result = adapter.predict(
        AdapterRequest(
            case_id="clinical-boundary-disallows-spatial-use",
            input_path=str(white),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata=metadata,
        )
    )

    assert "clinical_use_boundary_disallows_spatial_conditioning" in result.prediction["failure_reasons"]
    assert result.prediction["clinical_feature_vector"]["checkpoint_consumed_count"] == 0
