from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import osteo_vision_core.models.three_priority_promotion as promotion_module
from backend.osteo_vision_api.domains.cases.enums import ReviewerRole
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from backend.osteo_vision_api.services.promotion_approval_service import (
    PromotionApprovalRepository,
    PromotionApprovalService,
)
from osteo_vision_core.models.promotion_approval import (
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    TrustedPromotionKey,
    public_key_pem,
    sign_approval_payload,
)
from osteo_vision_core.models.three_priority_promotion import (
    CAPABILITY_REQUIREMENTS,
    PREDICTION_EVIDENCE_SCHEMA_VERSION,
    _case_evidence_binding_sha256,
    _mapping_sha256,
    _validate_bone_activity_threshold_selection,
    build_three_priority_promotion_target,
    evaluate_three_priority_model_promotion,
    recompute_three_priority_prediction_evidence,
)

APPROVAL_NOW = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)


def _base_manifest(tmp_path: Path, capability: str) -> dict:
    checkpoint = tmp_path / f"{capability}.pt"
    checkpoint.write_bytes(b"checkpoint")
    return {
        "capability": capability,
        "model_id": f"{capability}-engineering-v1",
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "training_domain": {"target_domain": False},
        "training": {
            "completed": True,
            "sample_count": 8,
            "patient_group_split": {"leakage_detected": False},
        },
        "validation": {
            "independent_test_set": False,
            "calibrated": False,
            "metrics": {},
        },
        "review": {"physician_reviewed": False},
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_array(path: Path, value: np.ndarray) -> dict[str, Any]:
    np.save(path, value, allow_pickle=False)
    return {"path": str(path), "sha256": _sha256(path), "shape": list(value.shape)}


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, str]:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path), "sha256": _sha256(path)}


def _policy(capability: str) -> dict[str, Any]:
    maxima = {
        "ece",
        "empty_mask_rate",
        "over_segmentation_rate",
        "max_boundary_shift_mm",
        "abstention_error_rate",
        "selective_error_rate",
        "activity_score_mae",
    }
    gates: dict[str, float] = {}
    for metric in CAPABILITY_REQUIREMENTS[capability]["metrics"]:
        if metric in maxima:
            gates[f"max_{metric}"] = 100.0 if metric == "max_boundary_shift_mm" else 1.0
        elif metric in {"conditioned_minus_image_only_dice", "worst_subgroup_dice_delta"}:
            gates[f"min_{metric}"] = -1.0
        else:
            gates[f"min_{metric}"] = 0.0
    return {
        "schema_version": "target-domain-test-policy-v1",
        "status": "approved_target_domain_runtime_gate",
        "clinical_claim_allowed": False,
        "metric_gates": {capability: gates},
    }


def _split_payload(checkpoint_sha256: str, cases: list[tuple[str, str]]) -> dict[str, Any]:
    records = [
        {
            "patient_id": "training-patient",
            "case_id": "training-case",
            "source_asset_sha256": "1" * 64,
            "institution_id": "training-institution",
            "acquisition_period": "2026-Q1",
            "split": "train",
            "target_domain": True,
            "admitted": True,
            "physician_reviewed": True,
        }
    ]
    for index, (case_id, patient_id) in enumerate(cases):
        records.append(
            {
                "patient_id": patient_id,
                "case_id": case_id,
                "source_asset_sha256": f"{index + 2:064x}",
                "institution_id": f"test-institution-{index}",
                "acquisition_period": f"2026-Q{index + 2}",
                "split": "test",
                "target_domain": True,
                "admitted": True,
                "physician_reviewed": True,
            }
        )
    return {
        "schema_version": "target-domain-split-v1",
        "checkpoint_sha256": checkpoint_sha256,
        "records": records,
    }


def _case_record(
    *,
    checkpoint_sha256: str,
    case_id: str,
    patient_id: str,
    prediction_assets: dict[str, dict[str, Any]],
    ground_truth_assets: dict[str, dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "case_id": case_id,
        "patient_id": patient_id,
        "split": "test",
        "target_domain": True,
        "admitted": True,
        "physician_reviewed_truth": True,
        "finite_outputs": True,
        "checkpoint_sha256": checkpoint_sha256,
        "prediction_assets": prediction_assets,
        "ground_truth_assets": ground_truth_assets,
        "evidence_binding_sha256": _case_evidence_binding_sha256(
            checkpoint_sha256=checkpoint_sha256,
            case_id=case_id,
            patient_id=patient_id,
            prediction_asset_sha256={name: str(asset["sha256"]) for name, asset in prediction_assets.items()},
            ground_truth_asset_sha256={name: str(asset["sha256"]) for name, asset in ground_truth_assets.items()},
        ),
    }
    record.update(extra or {})
    return record


def _build_patient_prediction_payload(
    tmp_path: Path,
    checkpoint_sha256: str,
    split_payload: dict[str, Any],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for index in range(2):
        case_id = f"patient-case-{index}"
        patient_id = f"patient-{index}"
        truth = np.zeros((2, 2), dtype=np.uint8)
        truth[0, index] = 1
        probability = np.where(truth > 0, 0.9, 0.1).astype(np.float32)
        prediction_assets = {
            "conditioned_mask": _write_array(tmp_path / f"{case_id}-conditioned.npy", truth),
            "image_only_mask": _write_array(tmp_path / f"{case_id}-image.npy", truth),
            "fallback_mask": _write_array(tmp_path / f"{case_id}-fallback.npy", truth),
            "conditioned_probability": _write_array(tmp_path / f"{case_id}-probability.npy", probability),
        }
        truth_assets = {
            "segmentation_mask": _write_array(tmp_path / f"{case_id}-truth.npy", truth),
        }
        records.append(
            _case_record(
                checkpoint_sha256=checkpoint_sha256,
                case_id=case_id,
                patient_id=patient_id,
                prediction_assets=prediction_assets,
                ground_truth_assets=truth_assets,
                extra={
                    "pixel_spacing_mm": [0.5, 0.5],
                    "segmentation_threshold": 0.5,
                    "subgroup_labels": {"age_group": "adult", "sex": "female" if index else "male"},
                },
            )
        )
    payload: dict[str, Any] = {
        "schema_version": PREDICTION_EVIDENCE_SCHEMA_VERSION,
        "capability": "patient_conditioned_segmentation",
        "checkpoint_sha256": checkpoint_sha256,
        "split": "test",
        "target_domain": True,
        "aggregation_unit": "case",
        "patient_grouping_key": "patient_id",
        "case_count": 2,
        "patient_count": 2,
        "inference_thresholds": {"segmentation_threshold": 0.5},
        "records": records,
    }
    replay = recompute_three_priority_prediction_evidence(
        "patient_conditioned_segmentation",
        payload,
        checkpoint_sha256=checkpoint_sha256,
        evidence_base_dir=tmp_path,
        split_manifest=split_payload,
    )
    assert replay["blockers"] == []
    payload["metrics"] = replay["metrics"]
    return payload


def _build_bone_prediction_payload(
    tmp_path: Path,
    checkpoint_sha256: str,
    split_payload: dict[str, Any],
    *,
    all_abstained: bool = False,
    zero_high_support: bool = False,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    class_indexes = (0, 1, 1 if zero_high_support else 2)
    for index, class_index in enumerate(class_indexes):
        case_id = f"bone-case-{index}"
        patient_id = f"bone-patient-{index}"
        truth_gate = np.asarray([[1, 0], [0, 0]], dtype=np.uint8)
        gate_probability = np.where(truth_gate > 0, 0.9, 0.1).astype(np.float32)
        target = np.full((2, 2), 255, dtype=np.uint8)
        target[0, 0] = class_index
        class_prediction = np.full((2, 2), class_index, dtype=np.uint8)
        probabilities = np.full((2, 2, 3), 0.05, dtype=np.float32)
        probabilities[..., class_index] = 0.9
        uncertainty = np.full((2, 2), 0.9 if all_abstained else 0.1, dtype=np.float32)
        accepted = ((uncertainty < 0.5) & (truth_gate > 0) & (target != 255)).astype(np.uint8)
        activity = np.full((2, 2), 0.5, dtype=np.float32)
        prediction_assets = {
            "bone_gate_mask": _write_array(tmp_path / f"{case_id}-gate-pred.npy", truth_gate),
            "bone_gate_probability": _write_array(tmp_path / f"{case_id}-gate-probability.npy", gate_probability),
            "class_prediction": _write_array(tmp_path / f"{case_id}-class-pred.npy", class_prediction),
            "class_probabilities": _write_array(tmp_path / f"{case_id}-class-prob.npy", probabilities),
            "uncertainty": _write_array(tmp_path / f"{case_id}-uncertainty.npy", uncertainty),
            "activity_score": _write_array(tmp_path / f"{case_id}-activity-pred.npy", activity),
            "accepted_prediction_mask": _write_array(tmp_path / f"{case_id}-accepted.npy", accepted),
        }
        truth_assets = {
            "bone_gate_mask": _write_array(tmp_path / f"{case_id}-gate-truth.npy", truth_gate),
            "class_target": _write_array(tmp_path / f"{case_id}-class-truth.npy", target),
            "activity_score": _write_array(tmp_path / f"{case_id}-activity-truth.npy", activity),
        }
        records.append(
            _case_record(
                checkpoint_sha256=checkpoint_sha256,
                case_id=case_id,
                patient_id=patient_id,
                prediction_assets=prediction_assets,
                ground_truth_assets=truth_assets,
                extra={
                    "bone_gate_threshold": 0.5,
                    "abstention_threshold": 0.5,
                    "inside_reviewed_bone_gate": True,
                },
            )
        )
    payload: dict[str, Any] = {
        "schema_version": PREDICTION_EVIDENCE_SCHEMA_VERSION,
        "capability": "bone_activity_multitask",
        "checkpoint_sha256": checkpoint_sha256,
        "split": "test",
        "target_domain": True,
        "aggregation_unit": "case",
        "patient_grouping_key": "patient_id",
        "case_count": 3,
        "patient_count": 3,
        "inference_thresholds": {"bone_gate_threshold": 0.5, "abstention_threshold": 0.5},
        "records": records,
    }
    replay = recompute_three_priority_prediction_evidence(
        "bone_activity_multitask",
        payload,
        checkpoint_sha256=checkpoint_sha256,
        evidence_base_dir=tmp_path,
        split_manifest=split_payload,
    )
    payload["metrics"] = replay["metrics"]
    return payload


def _target_domain_bundle(
    tmp_path: Path,
    capability: str,
    *,
    all_abstained: bool = False,
    zero_high_support: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], Path, dict[str, Any]]:
    checkpoint = tmp_path / f"{capability}.pt"
    checkpoint.write_bytes(b"target-domain-checkpoint")
    checkpoint_sha256 = _sha256(checkpoint)
    cases = (
        [(f"patient-case-{index}", f"patient-{index}") for index in range(2)]
        if capability == "patient_conditioned_segmentation"
        else [(f"bone-case-{index}", f"bone-patient-{index}") for index in range(3)]
    )
    split_payload = _split_payload(checkpoint_sha256, cases)
    prediction_payload = (
        _build_patient_prediction_payload(tmp_path, checkpoint_sha256, split_payload)
        if capability == "patient_conditioned_segmentation"
        else _build_bone_prediction_payload(
            tmp_path,
            checkpoint_sha256,
            split_payload,
            all_abstained=all_abstained,
            zero_high_support=zero_high_support,
        )
    )
    prediction_path = tmp_path / "prediction_manifest.json"
    evidence = {
        "split_manifest": _write_json(tmp_path / "split_manifest.json", split_payload),
        "prediction_manifest": _write_json(prediction_path, prediction_payload),
    }
    metrics = dict(prediction_payload["metrics"])
    evidence["calibration_report"] = _write_json(
        tmp_path / "calibration_report.json",
        {
            "checkpoint_sha256": checkpoint_sha256,
            "calibrated": True,
            "ece": metrics["ece"],
        },
    )
    evidence["subgroup_report"] = _write_json(
        tmp_path / "subgroup_report.json",
        {"checkpoint_sha256": checkpoint_sha256, "passed": True},
    )
    safety_gates = CAPABILITY_REQUIREMENTS[capability]["safety"]
    evidence["safety_report"] = _write_json(
        tmp_path / "safety_report.json",
        {
            "checkpoint_sha256": checkpoint_sha256,
            "output_contract_passed": True,
            **{gate: True for gate in safety_gates},
        },
    )
    evidence["physician_review"] = _write_json(
        tmp_path / "physician_review.json",
        {
            "checkpoint_sha256": checkpoint_sha256,
            "role": "physician",
            "auth_source": "hospital_sso",
            "actor_id": "physician-1",
            "institution": "target-hospital",
            "decision": "accepted",
        },
    )
    manifest: dict[str, Any] = {
        "capability": capability,
        "model_id": f"{capability}-target-v1",
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "training_domain": {"target_domain": True},
        "training": {
            "completed": True,
            "sample_count": 8,
            "patient_group_split": {"leakage_detected": False},
        },
        "validation": {
            "promotion_metrics_eligible": True,
            "independent_test_set": True,
            "calibrated": True,
            "patient_leakage_recomputed": True,
            "independent_institution_split": True,
            "independent_time_split": True,
            "metrics": metrics,
        },
        "review": {"physician_reviewed": True},
        "evidence": evidence,
    }
    if capability == "patient_conditioned_segmentation":
        manifest.update(
            {
                "outputs": ["image_only_logits", "conditioned_logits", "delta_map", "uncertainty"],
                "safety": {
                    "zero_spatial_effect_fallback_passed": True,
                    "bounded_modulation_passed": True,
                    "restricted_spatial_effect_passed": True,
                },
                "clinical_data": {"paired_image_mask_context": True},
                "subgroup_audit": {"passed": True},
            }
        )
    else:
        coverage = float(metrics["abstention_coverage_rate"])
        error = float(metrics["selective_error_rate"])
        manifest.update(
            {
                "outputs": ["bone_gate", "activity_score", "class_logits", "uncertainty", "abstention"],
                "safety": {"bone_gate_fail_closed_passed": True, "abstention_passed": True},
                "labels": {
                    "class_set": ["low_activity", "transition", "high_activity", "ignore"],
                    "physician_reviewed_bone_gate": True,
                    "multi_physician_arbitration": True,
                },
            }
        )
        manifest["validation"].update(
            {
                "proxy_validation_metrics": {
                    "bone_gate_threshold": 0.5,
                    "abstention_threshold": 0.5,
                },
                "threshold_selection": {
                    "enabled": True,
                    "selection_split": "validation",
                    "test_set_used_for_selection": False,
                    "defaults": {"bone_gate_threshold": 0.5, "abstention_threshold": 0.5},
                    "selection_constraints": {
                        "minimum_coverage_rate": 0.0,
                        "maximum_selective_error_rate": 1.0,
                    },
                    "selected": {"bone_gate_threshold": 0.5, "abstention_threshold": 0.5},
                    "validation_constraints_passed": True,
                    "bone_gate_scan": [{"threshold": 0.5, "bone_gate_dice": 1.0, "bone_gate_precision": 1.0}],
                    "abstention_scan": [{"threshold": 0.5, "coverage_rate": coverage, "selective_error_rate": error}],
                    "frozen_test_evaluation": {
                        "thresholds_reused_without_test_tuning": True,
                        "minimum_coverage_rate_passed": True,
                        "maximum_selective_error_rate_passed": True,
                        "constraints_passed": True,
                    },
                },
            }
        )
    return manifest, _policy(capability), prediction_path, split_payload


def _trust_policy(monkeypatch: pytest.MonkeyPatch, policy: dict[str, Any]) -> None:
    monkeypatch.setattr(
        promotion_module,
        "TRUSTED_APPROVED_POLICY_SHA256",
        frozenset({_mapping_sha256(policy)}),
    )


def _signed_approval_bundle(
    tmp_path: Path,
    manifest: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], PromotionTrustStore]:
    target = build_three_priority_promotion_target(manifest, policy=policy)
    actors = (
        ReviewActorIdentity(
            actor_id="physician-approval-1",
            role=ReviewerRole.PHYSICIAN,
            institution="target-hospital",
            auth_source="verified_identity_token",
        ),
        ReviewActorIdentity(
            actor_id="project-safety-approval-1",
            role=ReviewerRole.PROJECT_REVIEWER,
            institution="osteo-vision-project",
            auth_source="verified_identity_token",
        ),
    )
    private_keys = (Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate())
    key_ids = ("target-physician-key-1", "target-project-key-1")
    trust_store = PromotionTrustStore(
        keys=[
            TrustedPromotionKey(
                key_id=key_id,
                public_key_pem=public_key_pem(private_key.public_key()),
                actor_id=actor.actor_id,
                role=actor.role.value,
                institution=actor.institution,
                valid_from_utc=APPROVAL_NOW - timedelta(days=1),
                valid_until_utc=APPROVAL_NOW + timedelta(days=30),
                allowed_capabilities=[target["capability"]],
            )
            for actor, private_key, key_id in zip(actors, private_keys, key_ids, strict=True)
        ]
    )
    service = PromotionApprovalService(
        PromotionApprovalRepository(tmp_path / "promotion-approvals.sqlite"),
        trust_store,
        now_factory=lambda: APPROVAL_NOW,
    )
    reference: PromotionApprovalPayload | None = None
    for index, (actor, private_key, key_id) in enumerate(
        zip(actors, private_keys, key_ids, strict=True),
        start=1,
    ):
        payload = PromotionApprovalPayload(
            approval_id=f"target-approval-{index:02d}",
            **target,
            decision="approve",
            signer_actor_id=actor.actor_id,
            signer_role=actor.role.value,
            signer_institution=actor.institution,
            signed_at_utc=APPROVAL_NOW,
            nonce=f"target-approval-nonce-{index:024d}",
        )
        submission = SignedPromotionApproval(
            payload=payload,
            key_id=key_id,
            signature_b64=sign_approval_payload(payload, private_key),
        )
        service.submit(submission, actor)
        reference = reference or payload
    assert reference is not None
    return service.readiness(reference), trust_store


def test_patient_conditioned_proxy_can_pass_engineering_gate_without_runtime_promotion(
    tmp_path: Path,
) -> None:
    manifest = _base_manifest(tmp_path, "patient_conditioned_segmentation")
    manifest.update(
        {
            "outputs": [
                "image_only_logits",
                "conditioned_logits",
                "delta_map",
                "uncertainty",
            ],
            "safety": {
                "zero_spatial_effect_fallback_passed": True,
                "bounded_modulation_passed": True,
                "restricted_spatial_effect_passed": True,
            },
            "clinical_data": {"paired_image_mask_context": False},
            "subgroup_audit": {"passed": False},
        }
    )

    report = evaluate_three_priority_model_promotion(manifest)

    assert report["engineering_ready"] is True
    assert report["target_domain_promotion_ready"] is False
    assert report["runtime_replacement_allowed"] is False
    assert "target_domain_training_missing" in {item["code"] for item in report["promotion_blockers"]}


def test_bone_activity_requires_fail_closed_outputs_for_engineering_gate(
    tmp_path: Path,
) -> None:
    manifest = _base_manifest(tmp_path, "bone_activity_multitask")
    manifest.update(
        {
            "outputs": ["bone_gate", "activity_score", "class_logits"],
            "safety": {
                "bone_gate_fail_closed_passed": False,
                "abstention_passed": True,
            },
            "labels": {
                "class_set": ["low_activity", "transition"],
                "physician_reviewed_bone_gate": False,
            },
        }
    )

    report = evaluate_three_priority_model_promotion(manifest)

    assert report["engineering_ready"] is False
    assert {item["code"] for item in report["errors"]} == {
        "required_output_missing",
        "engineering_safety_gate_failed",
    }


def test_target_domain_self_declarations_cannot_cross_unapproved_gate(
    tmp_path: Path,
) -> None:
    manifest = _base_manifest(tmp_path, "patient_conditioned_segmentation")
    manifest.update(
        {
            "training_domain": {"target_domain": True},
            "outputs": [
                "image_only_logits",
                "conditioned_logits",
                "delta_map",
                "uncertainty",
            ],
            "safety": {
                "zero_spatial_effect_fallback_passed": True,
                "bounded_modulation_passed": True,
                "restricted_spatial_effect_passed": True,
            },
            "validation": {
                "independent_test_set": True,
                "calibrated": True,
                "patient_leakage_recomputed": True,
                "independent_institution_split": True,
                "independent_time_split": True,
                "metrics": {
                    "dice": 0.8,
                    "iou": 0.7,
                    "recall": 0.85,
                    "precision": 0.8,
                    "ece": 0.03,
                    "empty_mask_rate": 0.0,
                    "over_segmentation_rate": 0.01,
                    "conditioned_minus_image_only_dice": 0.02,
                    "worst_subgroup_dice_delta": -0.01,
                    "context_fallback_success_rate": 1.0,
                    "max_boundary_shift_mm": 0.5,
                },
            },
            "review": {"physician_reviewed": True},
            "clinical_data": {"paired_image_mask_context": True},
            "subgroup_audit": {"passed": True},
        }
    )

    report = evaluate_three_priority_model_promotion(manifest, metric_gates={})

    assert report["target_domain_promotion_ready"] is False
    codes = {item["code"] for item in report["promotion_blockers"]}
    assert "promotion_policy_not_approved" in codes
    assert "promotion_evidence_missing" in codes


def test_non_finite_or_boolean_sample_counts_fail_engineering_gate(
    tmp_path: Path,
) -> None:
    for value in (float("nan"), float("inf"), True):
        manifest = _base_manifest(tmp_path, "patient_conditioned_segmentation")
        manifest["training"]["sample_count"] = value
        manifest["outputs"] = [
            "image_only_logits",
            "conditioned_logits",
            "delta_map",
            "uncertainty",
        ]
        manifest["safety"] = {
            "zero_spatial_effect_fallback_passed": True,
            "bounded_modulation_passed": True,
            "restricted_spatial_effect_passed": True,
        }
        report = evaluate_three_priority_model_promotion(manifest)
        assert report["engineering_ready"] is False
        assert "training_sample_count_invalid" in {item["code"] for item in report["errors"]}


def test_bone_activity_all_abstention_cannot_pass_target_domain_metric_gate(
    tmp_path: Path,
) -> None:
    manifest = _base_manifest(tmp_path, "bone_activity_multitask")
    manifest.update(
        {
            "training_domain": {"target_domain": True},
            "outputs": ["bone_gate", "activity_score", "class_logits", "uncertainty", "abstention"],
            "safety": {
                "bone_gate_fail_closed_passed": True,
                "abstention_passed": True,
            },
            "labels": {
                "class_set": ["low_activity", "transition", "high_activity", "ignore"],
                "physician_reviewed_bone_gate": True,
                "multi_physician_arbitration": True,
            },
            "validation": {
                "independent_test_set": True,
                "calibrated": True,
                "patient_leakage_recomputed": True,
                "independent_institution_split": True,
                "independent_time_split": True,
                "metrics": {
                    "macro_dice": 0.8,
                    "low_activity_dice": 0.8,
                    "transition_dice": 0.8,
                    "high_activity_dice": 0.8,
                    "transition_recall": 0.8,
                    "bone_gate_dice": 0.9,
                    "ece": 0.04,
                    "abstention_error_rate": 0.0,
                    "selective_error_rate": 0.0,
                    "abstention_coverage_rate": 0.0,
                    "bone_gate_containment_rate": 1.0,
                    "activity_score_mae": 0.1,
                },
                "threshold_selection": {
                    "selection_split": "validation",
                    "test_set_used_for_selection": False,
                    "validation_constraints_passed": False,
                    "frozen_test_evaluation": {
                        "thresholds_reused_without_test_tuning": True,
                        "constraints_passed": False,
                    },
                },
            },
            "review": {"physician_reviewed": True},
        }
    )
    policy = {
        "schema_version": "test-policy",
        "status": "approved_target_domain_runtime_gate",
        "clinical_claim_allowed": False,
        "metric_gates": {
            "bone_activity_multitask": {
                "min_macro_dice": 0.7,
                "min_low_activity_dice": 0.7,
                "min_transition_dice": 0.65,
                "min_high_activity_dice": 0.7,
                "min_transition_recall": 0.75,
                "min_bone_gate_dice": 0.8,
                "max_ece": 0.08,
                "max_abstention_error_rate": 0.05,
                "max_selective_error_rate": 0.15,
                "min_abstention_coverage_rate": 0.1,
                "min_bone_gate_containment_rate": 1.0,
                "max_activity_score_mae": 0.15,
            }
        },
    }

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    blockers = {(item["code"], item.get("metric")) for item in report["promotion_blockers"]}
    assert ("promotion_metric_below_minimum", "abstention_coverage_rate") in blockers
    assert ("bone_activity_frozen_test_selective_safety_failed", None) in blockers
    assert ("bone_activity_validation_threshold_constraints_failed", None) in blockers
    assert ("promotion_metrics_not_eligible", None) in blockers
    assert ("approved_promotion_policy_not_in_trust_store", None) in blockers


def test_negative_safety_metrics_are_rejected_by_semantic_range(tmp_path: Path) -> None:
    manifest = _base_manifest(tmp_path, "bone_activity_multitask")
    manifest.update(
        {
            "outputs": ["bone_gate", "activity_score", "class_logits", "uncertainty", "abstention"],
            "safety": {
                "bone_gate_fail_closed_passed": True,
                "abstention_passed": True,
            },
            "labels": {
                "class_set": ["low_activity", "transition", "high_activity", "ignore"],
                "physician_reviewed_bone_gate": False,
                "multi_physician_arbitration": False,
            },
        }
    )
    manifest["validation"]["metrics"] = {
        "macro_dice": 0.8,
        "low_activity_dice": 0.8,
        "transition_dice": 0.8,
        "high_activity_dice": 0.8,
        "transition_recall": 0.8,
        "bone_gate_dice": 0.9,
        "ece": -0.01,
        "abstention_error_rate": -0.01,
        "selective_error_rate": -0.01,
        "abstention_coverage_rate": 0.5,
        "bone_gate_containment_rate": 1.0,
        "activity_score_mae": -0.01,
    }

    report = evaluate_three_priority_model_promotion(manifest)

    out_of_range = {
        item["metric"] for item in report["promotion_blockers"] if item["code"] == "promotion_metric_out_of_range"
    }
    assert {"ece", "abstention_error_rate", "selective_error_rate", "activity_score_mae"}.issubset(out_of_range)


def test_bone_activity_threshold_selection_is_recomputed_from_validation_scan() -> None:
    test_metrics = {
        "bone_gate_threshold": 0.5,
        "abstention_threshold": 0.4,
        "abstention_coverage_rate": 0.2,
        "selective_error_rate": 0.1,
    }
    validation: dict[str, Any] = {
        "proxy_validation_metrics": {
            "bone_gate_threshold": 0.5,
            "abstention_threshold": 0.4,
        },
        "threshold_selection": {
            "enabled": True,
            "selection_split": "validation",
            "test_set_used_for_selection": False,
            "defaults": {"bone_gate_threshold": 0.5, "abstention_threshold": 0.5},
            "selection_constraints": {
                "minimum_coverage_rate": 0.1,
                "maximum_selective_error_rate": 0.15,
            },
            "selected": {"bone_gate_threshold": 0.5, "abstention_threshold": 0.4},
            "validation_constraints_passed": True,
            "bone_gate_scan": [
                {"threshold": 0.4, "bone_gate_dice": 0.7, "bone_gate_precision": 0.8},
                {"threshold": 0.5, "bone_gate_dice": 0.8, "bone_gate_precision": 0.7},
            ],
            "abstention_scan": [
                {"threshold": 0.4, "coverage_rate": 0.2, "selective_error_rate": 0.1},
                {"threshold": 0.6, "coverage_rate": 0.5, "selective_error_rate": 0.2},
            ],
            "frozen_test_evaluation": {
                "test_set_used_for_selection": False,
                "thresholds_reused_without_test_tuning": True,
                "minimum_coverage_rate_passed": True,
                "maximum_selective_error_rate_passed": True,
                "constraints_passed": True,
            },
        },
    }
    blockers: list[dict] = []

    _validate_bone_activity_threshold_selection(validation, test_metrics, blockers)

    assert blockers == []
    validation["threshold_selection"]["selected"]["bone_gate_threshold"] = 0.4
    tampered_blockers: list[dict] = []
    _validate_bone_activity_threshold_selection(validation, test_metrics, tampered_blockers)
    assert "bone_activity_gate_threshold_selection_rule_mismatch" in {item["code"] for item in tampered_blockers}


def test_patient_prediction_evidence_v2_replays_to_target_domain_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, policy, _, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    _trust_policy(monkeypatch, policy)
    approval_bundle, trust_store = _signed_approval_bundle(tmp_path, manifest, policy)

    report = evaluate_three_priority_model_promotion(
        manifest,
        policy=policy,
        approval_bundle=approval_bundle,
        approval_trust_store=trust_store,
        approval_now=APPROVAL_NOW,
    )

    assert report["target_domain_promotion_ready"] is True
    assert report["runtime_replacement_allowed"] is True
    assert report["prediction_evidence_case_count"] == 2
    assert report["prediction_evidence_patient_count"] == 2
    assert report["recomputed_metrics"]["dice"] == pytest.approx(1.0)
    assert report["recomputed_metrics"]["context_fallback_success_rate"] == pytest.approx(1.0)
    assert report["prediction_evidence_sha256"]
    assert report["promotion_approval_valid"] is True
    assert report["promotion_active_approval_count"] == 2
    assert report["promotion_approval_bundle_sha256"] == approval_bundle["bundle_sha256"]


def test_valid_target_domain_evidence_cannot_promote_without_two_signed_approvals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, policy, _, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    _trust_policy(monkeypatch, policy)

    report = evaluate_three_priority_model_promotion(
        manifest,
        policy=policy,
        approval_trust_store=PromotionTrustStore(keys=[]),
        approval_now=APPROVAL_NOW,
    )

    assert report["target_domain_promotion_ready"] is False
    assert report["runtime_replacement_allowed"] is False
    assert report["promotion_approval_valid"] is False
    assert "promotion_approval_bundle_missing" in {item["code"] for item in report["promotion_blockers"]}


def test_bone_activity_prediction_evidence_v2_replays_all_required_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, policy, _, _ = _target_domain_bundle(tmp_path, "bone_activity_multitask")
    _trust_policy(monkeypatch, policy)
    approval_bundle, trust_store = _signed_approval_bundle(tmp_path, manifest, policy)

    report = evaluate_three_priority_model_promotion(
        manifest,
        policy=policy,
        approval_bundle=approval_bundle,
        approval_trust_store=trust_store,
        approval_now=APPROVAL_NOW,
    )

    assert report["target_domain_promotion_ready"] is True
    metrics = report["recomputed_metrics"]
    assert metrics["macro_dice"] == pytest.approx(1.0)
    assert metrics["abstention_coverage_rate"] == pytest.approx(1.0)
    assert metrics["bone_gate_containment_rate"] == pytest.approx(1.0)
    assert metrics["low_activity_support_pixels"] == pytest.approx(1.0)
    assert metrics["transition_support_pixels"] == pytest.approx(1.0)
    assert metrics["high_activity_support_pixels"] == pytest.approx(1.0)
    assert report["promotion_approval_valid"] is True


def test_prediction_asset_tampering_fails_closed(tmp_path: Path) -> None:
    manifest, policy, prediction_path, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    tampered_path = Path(prediction["records"][0]["prediction_assets"]["conditioned_mask"]["path"])
    np.save(tampered_path, np.zeros((2, 2), dtype=np.uint8), allow_pickle=False)

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    codes = {item["code"] for item in report["promotion_blockers"]}
    assert "prediction_asset_sha_mismatch" in codes
    assert "prediction_evidence_binding_mismatch" in codes
    assert report["runtime_replacement_allowed"] is False


def test_missing_ground_truth_asset_fails_closed(tmp_path: Path) -> None:
    manifest, policy, prediction_path, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    truth_path = Path(prediction["records"][0]["ground_truth_assets"]["segmentation_mask"]["path"])
    truth_path.unlink()

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    codes = {item["code"] for item in report["promotion_blockers"]}
    assert "prediction_asset_missing" in codes
    assert report["recomputed_metrics"] == {}


def test_declared_aggregate_metric_cannot_override_asset_replay(tmp_path: Path) -> None:
    manifest, policy, prediction_path, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["metrics"]["dice"] = 0.5
    manifest["evidence"]["prediction_manifest"] = _write_json(prediction_path, prediction)

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    mismatches = {(item["code"], item.get("evidence"), item.get("metric")) for item in report["promotion_blockers"]}
    assert (
        "promotion_metric_evidence_mismatch",
        "recomputed_prediction_manifest",
        "dice",
    ) in mismatches
    assert report["recomputed_metrics"]["dice"] == pytest.approx(1.0)


def test_all_abstention_is_blocked_after_independent_replay(tmp_path: Path) -> None:
    manifest, policy, _, _ = _target_domain_bundle(
        tmp_path,
        "bone_activity_multitask",
        all_abstained=True,
    )

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    codes = {item["code"] for item in report["promotion_blockers"]}
    assert "bone_activity_all_abstained" in codes
    assert report["recomputed_metrics"]["abstention_coverage_rate"] == pytest.approx(0.0)
    assert report["runtime_replacement_allowed"] is False


def test_zero_class_support_is_derived_from_truth_assets(tmp_path: Path) -> None:
    manifest, policy, _, _ = _target_domain_bundle(
        tmp_path,
        "bone_activity_multitask",
        zero_high_support=True,
    )

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    support_blockers = [
        item for item in report["promotion_blockers"] if item["code"] == "bone_activity_class_support_missing"
    ]
    assert any(item.get("class_name") == "high_activity" for item in support_blockers)
    assert report["recomputed_metrics"]["high_activity_support_pixels"] == pytest.approx(0.0)


def test_prediction_replay_is_deterministic(tmp_path: Path) -> None:
    manifest, _, prediction_path, split_payload = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    kwargs = {
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "evidence_base_dir": tmp_path,
        "split_manifest": split_payload,
    }

    first = recompute_three_priority_prediction_evidence("patient_conditioned_segmentation", prediction, **kwargs)
    second = recompute_three_priority_prediction_evidence("patient_conditioned_segmentation", prediction, **kwargs)

    assert first == second
    assert first["valid"] is True
    assert first["evidence_sha256"] == second["evidence_sha256"]


def test_patient_no_harm_and_physical_boundary_are_recomputed_from_assets(tmp_path: Path) -> None:
    manifest, _, prediction_path, split_payload = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    record = prediction["records"][0]
    shifted = np.asarray([[0, 1], [0, 0]], dtype=np.uint8)
    shifted_probability = np.where(shifted > 0, 0.9, 0.1).astype(np.float32)
    conditioned_path = Path(record["prediction_assets"]["conditioned_mask"]["path"])
    probability_path = Path(record["prediction_assets"]["conditioned_probability"]["path"])
    record["prediction_assets"]["conditioned_mask"] = _write_array(conditioned_path, shifted)
    record["prediction_assets"]["conditioned_probability"] = _write_array(probability_path, shifted_probability)
    record["evidence_binding_sha256"] = _case_evidence_binding_sha256(
        checkpoint_sha256=manifest["checkpoint_sha256"],
        case_id=record["case_id"],
        patient_id=record["patient_id"],
        prediction_asset_sha256={name: asset["sha256"] for name, asset in record["prediction_assets"].items()},
        ground_truth_asset_sha256={name: asset["sha256"] for name, asset in record["ground_truth_assets"].items()},
    )

    replay = recompute_three_priority_prediction_evidence(
        "patient_conditioned_segmentation",
        prediction,
        checkpoint_sha256=manifest["checkpoint_sha256"],
        evidence_base_dir=tmp_path,
        split_manifest=split_payload,
    )

    assert "patient_conditioning_recomputed_no_harm_failed" in {item["code"] for item in replay["blockers"]}
    assert replay["metrics"]["conditioned_minus_image_only_dice"] == pytest.approx(-0.5)
    assert replay["metrics"]["max_boundary_shift_mm"] == pytest.approx(0.5)


def test_case_binding_and_target_domain_flags_are_fail_closed(tmp_path: Path) -> None:
    manifest, policy, prediction_path, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["records"][0]["target_domain"] = False
    prediction["records"][0]["evidence_binding_sha256"] = "0" * 64
    manifest["evidence"]["prediction_manifest"] = _write_json(prediction_path, prediction)

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    codes = {item["code"] for item in report["promotion_blockers"]}
    assert "prediction_record_not_admitted_target_domain" in codes
    assert "prediction_evidence_binding_mismatch" in codes


def test_prediction_patient_identity_must_match_grouped_split(tmp_path: Path) -> None:
    manifest, policy, prediction_path, _ = _target_domain_bundle(tmp_path, "patient_conditioned_segmentation")
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["records"][0]["patient_id"] = "unmatched-patient"
    manifest["evidence"]["prediction_manifest"] = _write_json(prediction_path, prediction)

    report = evaluate_three_priority_model_promotion(manifest, policy=policy)

    codes = {item["code"] for item in report["promotion_blockers"]}
    assert "prediction_record_patient_mismatch" in codes
    assert "prediction_evidence_binding_mismatch" in codes
