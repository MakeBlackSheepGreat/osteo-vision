from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
from PIL import Image
from pydantic import ValidationError

from src.models.promotion_approval import PromotionTrustStore
from src.models.promotion_approval_gate import validate_promotion_approval_bundle

SCHEMA_VERSION = "osteo-vision-three-priority-model-promotion-v3"
PREDICTION_EVIDENCE_SCHEMA_VERSION = "osteo-vision-three-priority-prediction-evidence-v2"
PROMOTION_EVIDENCE_BUNDLE_SCHEMA_VERSION = "osteo-vision-three-priority-promotion-evidence-bundle-v1"
APPROVED_POLICY_STATUS = "approved_target_domain_runtime_gate"
# T107 remains open. Add a reviewed policy digest here only after formal approval.
TRUSTED_APPROVED_POLICY_SHA256: frozenset[str] = frozenset()
TRUSTED_REVIEW_SOURCES = {
    "verified_identity_token",
    "hospital_sso",
    "project_signed_credential",
}
CAPABILITY_REQUIREMENTS = {
    "patient_conditioned_segmentation": {
        "outputs": {
            "image_only_logits",
            "conditioned_logits",
            "delta_map",
            "uncertainty",
        },
        "safety": {
            "zero_spatial_effect_fallback_passed",
            "bounded_modulation_passed",
            "restricted_spatial_effect_passed",
        },
        "metrics": {
            "dice",
            "iou",
            "recall",
            "precision",
            "ece",
            "empty_mask_rate",
            "over_segmentation_rate",
            "conditioned_minus_image_only_dice",
            "worst_subgroup_dice_delta",
            "context_fallback_success_rate",
            "max_boundary_shift_mm",
        },
    },
    "bone_activity_multitask": {
        "outputs": {
            "bone_gate",
            "activity_score",
            "class_logits",
            "uncertainty",
            "abstention",
        },
        "safety": {"bone_gate_fail_closed_passed", "abstention_passed"},
        "metrics": {
            "macro_dice",
            "low_activity_dice",
            "transition_dice",
            "high_activity_dice",
            "transition_recall",
            "bone_gate_dice",
            "ece",
            "abstention_error_rate",
            "selective_error_rate",
            "abstention_coverage_rate",
            "bone_gate_containment_rate",
            "activity_score_mae",
        },
    },
}
REQUIRED_EVIDENCE = (
    "split_manifest",
    "prediction_manifest",
    "calibration_report",
    "subgroup_report",
    "safety_report",
    "physician_review",
)
PATIENT_PREDICTION_ASSETS = {
    "conditioned_mask",
    "image_only_mask",
    "fallback_mask",
    "conditioned_probability",
}
PATIENT_TRUTH_ASSETS = {"segmentation_mask"}
BONE_ACTIVITY_PREDICTION_ASSETS = {
    "bone_gate_mask",
    "bone_gate_probability",
    "class_prediction",
    "class_probabilities",
    "uncertainty",
    "activity_score",
    "accepted_prediction_mask",
}
BONE_ACTIVITY_TRUTH_ASSETS = {
    "bone_gate_mask",
    "class_target",
    "activity_score",
}


def build_three_priority_promotion_target(
    manifest: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Build the path-independent model/evidence target that both reviewers sign."""

    checkpoint_value = str(manifest.get("checkpoint_path") or "").strip()
    checkpoint = Path(checkpoint_value).expanduser().resolve() if checkpoint_value else None
    checkpoint_sha256 = _safe_sha256(checkpoint) or ""
    resolved_policy = _mapping(policy)
    policy_sha256 = _mapping_sha256(resolved_policy) if resolved_policy else ""
    evidence_hashes: dict[str, str | None] = {}
    evidence = _mapping(manifest.get("evidence"))
    for name in REQUIRED_EVIDENCE:
        record = _mapping(evidence.get(name))
        value = str(record.get("path") or "").strip()
        path = Path(value).expanduser().resolve() if value else None
        evidence_hashes[name] = _safe_sha256(path)
    target_without_bundle = {
        "capability": str(manifest.get("capability") or ""),
        "model_id": str(manifest.get("model_id") or "").strip(),
        "checkpoint_sha256": checkpoint_sha256,
        "policy_sha256": policy_sha256,
    }
    evidence_bundle_sha256 = _mapping_sha256(
        {
            "schema_version": PROMOTION_EVIDENCE_BUNDLE_SCHEMA_VERSION,
            **target_without_bundle,
            "evidence_sha256": evidence_hashes,
        }
    )
    return {**target_without_bundle, "evidence_bundle_sha256": evidence_bundle_sha256}


def evaluate_three_priority_model_promotion(
    manifest: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    metric_gates: Mapping[str, Mapping[str, float]] | None = None,
    approval_bundle: Mapping[str, Any] | None = None,
    approval_trust_store: PromotionTrustStore | Mapping[str, Any] | None = None,
    approval_now: datetime | None = None,
) -> dict[str, Any]:
    capability = str(manifest.get("capability") or "")
    requirements = CAPABILITY_REQUIREMENTS.get(capability)
    errors: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if requirements is None:
        errors.append({"code": "capability_unsupported", "actual": capability})
        return _report(capability, errors=errors, blockers=blockers)

    checkpoint, checkpoint_sha = _checkpoint_evidence(manifest, errors)
    training = _mapping(manifest.get("training"))
    if training.get("completed") is not True:
        errors.append({"code": "training_not_completed"})
    sample_count = _finite_number(training.get("sample_count"))
    if sample_count is None or sample_count <= 0 or not sample_count.is_integer():
        errors.append({"code": "training_sample_count_invalid"})
    if _mapping(training.get("patient_group_split")).get("leakage_detected") is not False:
        errors.append({"code": "patient_group_leakage_unresolved"})
    outputs = {str(item) for item in manifest.get("outputs") or []}
    for output in sorted(requirements["outputs"] - outputs):
        errors.append({"code": "required_output_missing", "output": output})
    safety = _mapping(manifest.get("safety"))
    for gate in sorted(requirements["safety"]):
        if safety.get(gate) is not True:
            errors.append({"code": "engineering_safety_gate_failed", "gate": gate})
    engineering_ready = not errors

    resolved_policy = _mapping(policy)
    if metric_gates is not None and not resolved_policy:
        resolved_policy = {
            "schema_version": "legacy-unapproved-policy",
            "status": "unapproved_legacy_metric_override",
            "clinical_claim_allowed": False,
            "metric_gates": metric_gates,
        }
    policy_status = str(resolved_policy.get("status") or "")
    policy_sha256 = _mapping_sha256(resolved_policy) if resolved_policy else None
    if policy_status != APPROVED_POLICY_STATUS:
        blockers.append({"code": "promotion_policy_not_approved", "actual": policy_status or None})
    elif policy_sha256 not in TRUSTED_APPROVED_POLICY_SHA256:
        blockers.append({"code": "approved_promotion_policy_not_in_trust_store"})
    if resolved_policy.get("clinical_claim_allowed") is not False:
        blockers.append({"code": "promotion_policy_clinical_claim_boundary_invalid"})
    capability_gates = _mapping(_mapping(resolved_policy.get("metric_gates")).get(capability))
    required_metrics = set(requirements["metrics"])
    if _metric_names(capability_gates) != required_metrics:
        blockers.append(
            {
                "code": "promotion_metric_policy_incomplete",
                "required": sorted(required_metrics),
                "actual": sorted(_metric_names(capability_gates)),
            }
        )

    if _mapping(manifest.get("training_domain")).get("target_domain") is not True:
        blockers.append({"code": "target_domain_training_missing"})
    validation = _mapping(manifest.get("validation"))
    metrics = _mapping(validation.get("metrics"))
    if validation.get("promotion_metrics_eligible") is not True:
        blockers.append({"code": "promotion_metrics_not_eligible"})
    for field, code in (
        ("independent_test_set", "independent_target_domain_test_missing"),
        ("calibrated", "probability_calibration_missing"),
        ("patient_leakage_recomputed", "patient_leakage_recomputation_missing"),
        ("independent_institution_split", "institution_independent_validation_missing"),
        ("independent_time_split", "time_independent_validation_missing"),
    ):
        if validation.get(field) is not True:
            blockers.append({"code": code})
    if _mapping(manifest.get("review")).get("physician_reviewed") is not True:
        blockers.append({"code": "physician_review_missing"})
    if capability == "patient_conditioned_segmentation":
        if _mapping(manifest.get("clinical_data")).get("paired_image_mask_context") is not True:
            blockers.append({"code": "paired_image_mask_clinical_context_missing"})
        if _mapping(manifest.get("subgroup_audit")).get("passed") is not True:
            blockers.append({"code": "clinical_subgroup_audit_missing_or_failed"})
    else:
        labels = _mapping(manifest.get("labels"))
        required_classes = {"low_activity", "transition", "high_activity", "ignore"}
        if not required_classes.issubset({str(item) for item in labels.get("class_set") or []}):
            blockers.append({"code": "bone_activity_class_set_incomplete"})
        if labels.get("physician_reviewed_bone_gate") is not True:
            blockers.append({"code": "physician_reviewed_bone_gate_missing"})
        if labels.get("multi_physician_arbitration") is not True:
            blockers.append({"code": "bone_activity_multi_physician_arbitration_missing"})
        _validate_bone_activity_threshold_selection(validation, metrics, blockers)

    payloads, evidence_paths = _verified_evidence(
        _mapping(manifest.get("evidence")),
        checkpoint_sha=checkpoint_sha,
        blockers=blockers,
    )
    if payloads.get("split_manifest") is not None:
        _validate_split_manifest(payloads["split_manifest"], blockers)
    if payloads.get("physician_review") is not None:
        _validate_physician_review(payloads["physician_review"], blockers)
    replay = _validate_capability_evidence(
        capability,
        payloads,
        evidence_paths,
        requirements["safety"],
        metrics,
        required_metrics,
        checkpoint_sha,
        blockers,
    )

    _validate_metric_values(metrics, required_metrics, blockers)
    _apply_metric_gates(metrics, capability_gates, blockers)
    if capability == "patient_conditioned_segmentation":
        gain = _finite_number(metrics.get("conditioned_minus_image_only_dice"))
        fallback = _finite_number(metrics.get("context_fallback_success_rate"))
        if gain is None or gain < 0:
            blockers.append({"code": "patient_conditioning_no_harm_gate_failed"})
        if fallback is None or fallback < 1.0:
            blockers.append({"code": "clinical_context_fallback_not_perfect"})
    else:
        containment = _finite_number(metrics.get("bone_gate_containment_rate"))
        if containment is None or containment < 1.0:
            blockers.append({"code": "bone_activity_prediction_outside_reviewed_gate"})
        for class_name in ("low_activity", "transition", "high_activity"):
            pixel_support = _finite_number(metrics.get(f"{class_name}_support_pixels"))
            sample_support = _finite_number(metrics.get(f"{class_name}_support_samples"))
            if (
                pixel_support is None
                or pixel_support <= 0
                or not pixel_support.is_integer()
                or sample_support is None
                or sample_support <= 0
                or not sample_support.is_integer()
            ):
                blockers.append({"code": "bone_activity_class_support_missing", "class_name": class_name})

    approval_target = build_three_priority_promotion_target(manifest, policy=resolved_policy)
    approval_validation = _validate_promotion_approval_gate(
        approval_target,
        approval_bundle=approval_bundle,
        approval_trust_store=approval_trust_store,
        approval_now=approval_now,
    )
    blockers.extend(approval_validation["blockers"])

    unique_blockers = [_thaw(item) for item in dict.fromkeys(_freeze(item) for item in blockers)]
    return _report(
        capability,
        errors=errors,
        blockers=unique_blockers,
        engineering_ready=engineering_ready,
        policy_status=policy_status,
        policy_sha256=policy_sha256,
        checkpoint_path=str(checkpoint) if checkpoint else None,
        checkpoint_sha256=checkpoint_sha,
        recomputed_metrics=_mapping(replay.get("metrics")),
        prediction_evidence_sha256=str(replay.get("evidence_sha256") or "") or None,
        prediction_evidence_case_count=int(replay.get("case_count") or 0),
        prediction_evidence_patient_count=int(replay.get("patient_count") or 0),
        approval_target=approval_target,
        approval_valid=bool(approval_validation["valid"]),
        approval_bundle_sha256=str(approval_validation.get("bundle_sha256") or "") or None,
        active_approval_count=int(approval_validation.get("active_approval_count") or 0),
    )


def _validate_promotion_approval_gate(
    approval_target: Mapping[str, str],
    *,
    approval_bundle: Mapping[str, Any] | None,
    approval_trust_store: PromotionTrustStore | Mapping[str, Any] | None,
    approval_now: datetime | None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    if not approval_target.get("model_id"):
        blockers.append({"code": "promotion_model_id_missing"})
    if not approval_target.get("checkpoint_sha256"):
        blockers.append({"code": "promotion_approval_checkpoint_target_missing"})
    if not approval_target.get("policy_sha256"):
        blockers.append({"code": "promotion_approval_policy_target_missing"})
    if approval_bundle is None:
        blockers.append({"code": "promotion_approval_bundle_missing"})
    if approval_trust_store is None:
        blockers.append({"code": "promotion_approval_trust_store_missing"})
    if blockers:
        return {
            "valid": False,
            "bundle_sha256": None,
            "active_approval_count": 0,
            "blockers": blockers,
        }
    try:
        trust_store = (
            approval_trust_store
            if isinstance(approval_trust_store, PromotionTrustStore)
            else PromotionTrustStore.model_validate(approval_trust_store)
        )
    except ValidationError:
        return {
            "valid": False,
            "bundle_sha256": None,
            "active_approval_count": 0,
            "blockers": [{"code": "promotion_approval_trust_store_invalid"}],
        }
    return validate_promotion_approval_bundle(
        approval_bundle,
        trust_store=trust_store,
        reference=approval_target,
        now=approval_now,
    )


def _checkpoint_evidence(manifest: Mapping[str, Any], errors: list[dict[str, Any]]) -> tuple[Path | None, str | None]:
    value = str(manifest.get("checkpoint_path") or "").strip()
    checkpoint = Path(value).expanduser().resolve() if value else None
    expected = str(manifest.get("checkpoint_sha256") or "").lower()
    if checkpoint is None or not checkpoint.is_file():
        errors.append(
            {
                "code": "checkpoint_missing",
                "path": str(checkpoint) if checkpoint else None,
            }
        )
        return checkpoint, None
    actual = _sha256(checkpoint)
    if not expected:
        errors.append({"code": "checkpoint_sha256_missing"})
    elif actual != expected:
        errors.append(
            {
                "code": "checkpoint_sha256_mismatch",
                "expected": expected,
                "actual": actual,
            }
        )
    return checkpoint, actual


def _verified_evidence(
    evidence: Mapping[str, Any],
    *,
    checkpoint_sha: str | None,
    blockers: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    payloads: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for name in REQUIRED_EVIDENCE:
        record = _mapping(evidence.get(name))
        value = str(record.get("path") or "").strip()
        path = Path(value).expanduser().resolve() if value else None
        expected = str(record.get("sha256") or "").lower()
        if path is None or not path.is_file():
            blockers.append({"code": "promotion_evidence_missing", "evidence": name})
            continue
        if not expected or _sha256(path) != expected:
            blockers.append({"code": "promotion_evidence_sha_mismatch", "evidence": name})
            continue
        try:
            payload = _read_structured(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            blockers.append(
                {
                    "code": "promotion_evidence_unreadable",
                    "evidence": name,
                    "detail": str(exc),
                }
            )
            continue
        recorded_checkpoint = str(payload.get("checkpoint_sha256") or "").lower()
        if name != "split_manifest" and checkpoint_sha and recorded_checkpoint != checkpoint_sha:
            blockers.append({"code": "promotion_evidence_checkpoint_mismatch", "evidence": name})
        payloads[name] = payload
        paths[name] = path
    return payloads, paths


def _validate_split_manifest(payload: Mapping[str, Any], blockers: list[dict[str, Any]]) -> None:
    rows = payload.get("records")
    if not isinstance(rows, list) or not rows:
        blockers.append({"code": "split_manifest_records_missing"})
        return
    seen: dict[str, dict[str, set[str]]] = {
        field: {}
        for field in (
            "patient_id",
            "case_id",
            "source_asset_sha256",
            "institution_id",
            "acquisition_period",
        )
    }
    test_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            blockers.append({"code": "split_manifest_record_invalid"})
            continue
        split = str(row.get("split") or "").lower()
        if split not in {"train", "calibration", "validation", "test"}:
            blockers.append({"code": "split_manifest_split_invalid", "actual": split})
            continue
        if split == "test":
            test_count += 1
            if row.get("target_domain") is not True or row.get("admitted") is not True:
                blockers.append({"code": "independent_test_record_not_admitted_target_domain"})
            if row.get("physician_reviewed") is not True:
                blockers.append({"code": "independent_test_record_not_physician_reviewed"})
        for field in seen:
            identifier = str(row.get(field) or "").strip()
            if not identifier:
                blockers.append({"code": "split_identity_missing", "field": field})
                continue
            seen[field].setdefault(identifier, set()).add(split)
    if test_count == 0:
        blockers.append({"code": "independent_test_records_missing"})
    for field, identifiers in seen.items():
        if any(len(splits) > 1 for splits in identifiers.values()):
            blockers.append({"code": "split_identity_overlap", "field": field})


def _validate_physician_review(payload: Mapping[str, Any], blockers: list[dict[str, Any]]) -> None:
    if str(payload.get("role") or "") != "physician":
        blockers.append({"code": "promotion_review_role_invalid"})
    if str(payload.get("auth_source") or "") not in TRUSTED_REVIEW_SOURCES:
        blockers.append({"code": "promotion_review_auth_source_untrusted"})
    if not str(payload.get("actor_id") or "").strip() or not str(payload.get("institution") or "").strip():
        blockers.append({"code": "promotion_review_identity_incomplete"})
    if payload.get("decision") != "accepted":
        blockers.append({"code": "promotion_review_not_accepted"})


def _validate_capability_evidence(
    capability: str,
    payloads: Mapping[str, Mapping[str, Any]],
    evidence_paths: Mapping[str, Path],
    safety_gates: set[str],
    reported_metrics: Mapping[str, Any],
    required_metrics: set[str],
    checkpoint_sha256: str | None,
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    calibration = _mapping(payloads.get("calibration_report"))
    if calibration and calibration.get("calibrated") is not True:
        blockers.append({"code": "calibration_evidence_failed"})
    if calibration:
        _require_matching_metric(calibration, reported_metrics, "ece", "calibration_report", blockers)
    subgroup = _mapping(payloads.get("subgroup_report"))
    if subgroup and subgroup.get("passed") is not True:
        blockers.append({"code": "subgroup_evidence_failed"})
    safety = _mapping(payloads.get("safety_report"))
    if safety:
        if safety.get("output_contract_passed") is not True:
            blockers.append({"code": "model_output_contract_evidence_failed"})
        for gate in safety_gates:
            if safety.get(gate) is not True:
                blockers.append({"code": "safety_evidence_gate_failed", "gate": gate})
    predictions = _mapping(payloads.get("prediction_manifest"))
    replay: dict[str, Any] = {}
    if predictions:
        records = predictions.get("records")
        if not isinstance(records, list) or not records:
            blockers.append({"code": "prediction_evidence_records_missing"})
        elif any(not isinstance(row, Mapping) or row.get("finite_outputs") is not True for row in records):
            blockers.append({"code": "prediction_evidence_non_finite_output"})
        if capability == "bone_activity_multitask" and any(
            not isinstance(row, Mapping) or row.get("inside_reviewed_bone_gate") is not True for row in records or []
        ):
            blockers.append({"code": "prediction_evidence_bone_gate_containment_failed"})
        if capability == "bone_activity_multitask":
            inference_thresholds = _mapping(predictions.get("inference_thresholds"))
            for metric_name in ("bone_gate_threshold", "abstention_threshold"):
                _require_matching_metric(
                    inference_thresholds,
                    reported_metrics,
                    metric_name,
                    "prediction_manifest",
                    blockers,
                )
            if isinstance(records, list):
                for row in records:
                    if not isinstance(row, Mapping):
                        continue
                    for metric_name in ("bone_gate_threshold", "abstention_threshold"):
                        if not _numbers_match(row.get(metric_name), reported_metrics.get(metric_name)):
                            blockers.append(
                                {
                                    "code": "prediction_record_threshold_mismatch",
                                    "metric": metric_name,
                                }
                            )
        evidence_metrics = _mapping(predictions.get("metrics"))
        for metric_name in sorted(required_metrics):
            _require_matching_metric(
                evidence_metrics,
                reported_metrics,
                metric_name,
                "prediction_manifest",
                blockers,
            )
        prediction_path = evidence_paths.get("prediction_manifest")
        replay = recompute_three_priority_prediction_evidence(
            capability,
            predictions,
            checkpoint_sha256=checkpoint_sha256,
            evidence_base_dir=prediction_path.parent if prediction_path else Path.cwd(),
            split_manifest=_mapping(payloads.get("split_manifest")),
        )
        blockers.extend(cast(list[dict[str, Any]], replay.get("blockers") or []))
        recomputed_metrics = _mapping(replay.get("metrics"))
        if recomputed_metrics:
            for metric_name in sorted(required_metrics):
                _require_matching_metric(
                    recomputed_metrics,
                    reported_metrics,
                    metric_name,
                    "recomputed_prediction_assets",
                    blockers,
                )
            for metric_name in sorted(required_metrics):
                _require_matching_metric(
                    recomputed_metrics,
                    evidence_metrics,
                    metric_name,
                    "recomputed_prediction_manifest",
                    blockers,
                )
            if capability == "bone_activity_multitask":
                for metric_name in (
                    "low_activity_support_pixels",
                    "low_activity_support_samples",
                    "transition_support_pixels",
                    "transition_support_samples",
                    "high_activity_support_pixels",
                    "high_activity_support_samples",
                ):
                    _require_matching_metric(
                        recomputed_metrics,
                        reported_metrics,
                        metric_name,
                        "recomputed_prediction_assets",
                        blockers,
                    )
    return replay


def recompute_three_priority_prediction_evidence(
    capability: str,
    prediction_manifest: Mapping[str, Any],
    *,
    checkpoint_sha256: str | None,
    evidence_base_dir: Path | None = None,
    split_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay per-case prediction assets and independently recompute promotion metrics."""

    blockers: list[dict[str, Any]] = []
    base_dir = (evidence_base_dir or Path.cwd()).expanduser().resolve()
    if capability not in CAPABILITY_REQUIREMENTS:
        blockers.append({"code": "prediction_evidence_capability_unsupported", "actual": capability})
        return _prediction_replay_report({}, [], blockers, checkpoint_sha256)
    if prediction_manifest.get("schema_version") != PREDICTION_EVIDENCE_SCHEMA_VERSION:
        blockers.append(
            {
                "code": "prediction_evidence_schema_invalid",
                "required": PREDICTION_EVIDENCE_SCHEMA_VERSION,
                "actual": prediction_manifest.get("schema_version"),
            }
        )
        return _prediction_replay_report({}, [], blockers, checkpoint_sha256)
    if str(prediction_manifest.get("capability") or "") != capability:
        blockers.append({"code": "prediction_evidence_capability_mismatch"})
    recorded_checkpoint = str(prediction_manifest.get("checkpoint_sha256") or "").lower()
    if not checkpoint_sha256 or recorded_checkpoint != checkpoint_sha256.lower():
        blockers.append({"code": "prediction_evidence_checkpoint_mismatch"})
    if prediction_manifest.get("split") != "test":
        blockers.append({"code": "prediction_evidence_split_invalid"})
    if prediction_manifest.get("target_domain") is not True:
        blockers.append({"code": "prediction_evidence_target_domain_missing"})
    if prediction_manifest.get("aggregation_unit") != "case":
        blockers.append({"code": "prediction_evidence_aggregation_unit_invalid"})
    if prediction_manifest.get("patient_grouping_key") != "patient_id":
        blockers.append({"code": "prediction_evidence_patient_grouping_invalid"})

    split_index, split_test_cases = _prediction_split_index(_mapping(split_manifest), blockers)
    raw_records = prediction_manifest.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        blockers.append({"code": "prediction_evidence_records_missing"})
        return _prediction_replay_report({}, [], blockers, checkpoint_sha256)

    cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    binding_digests: list[str] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, Mapping):
            blockers.append({"code": "prediction_evidence_record_invalid"})
            continue
        record = dict(raw_record)
        case_id = str(record.get("case_id") or "").strip()
        patient_id = str(record.get("patient_id") or "").strip()
        if not case_id or not patient_id:
            blockers.append({"code": "prediction_record_identity_missing"})
            continue
        if case_id in seen_case_ids:
            blockers.append({"code": "prediction_record_duplicate_case", "case_id": case_id})
            continue
        seen_case_ids.add(case_id)
        if record.get("split") != "test":
            blockers.append({"code": "prediction_record_split_invalid", "case_id": case_id})
        if record.get("target_domain") is not True or record.get("admitted") is not True:
            blockers.append({"code": "prediction_record_not_admitted_target_domain", "case_id": case_id})
        if record.get("physician_reviewed_truth") is not True:
            blockers.append({"code": "prediction_record_truth_not_physician_reviewed", "case_id": case_id})
        if record.get("finite_outputs") is not True:
            blockers.append({"code": "prediction_evidence_non_finite_output", "case_id": case_id})
        if str(record.get("checkpoint_sha256") or "").lower() != recorded_checkpoint:
            blockers.append({"code": "prediction_record_checkpoint_mismatch", "case_id": case_id})
        _validate_record_against_split(case_id, patient_id, split_index, blockers)

        prediction_assets = _mapping(record.get("prediction_assets"))
        truth_assets = _mapping(record.get("ground_truth_assets"))
        expected_prediction_roles, expected_truth_roles = _required_asset_roles(capability)
        if set(prediction_assets) != expected_prediction_roles:
            blockers.append(
                {
                    "code": "prediction_asset_role_set_invalid",
                    "case_id": case_id,
                    "required": sorted(expected_prediction_roles),
                    "actual": sorted(prediction_assets),
                }
            )
        if set(truth_assets) != expected_truth_roles:
            blockers.append(
                {
                    "code": "ground_truth_asset_role_set_invalid",
                    "case_id": case_id,
                    "required": sorted(expected_truth_roles),
                    "actual": sorted(truth_assets),
                }
            )
        arrays: dict[str, dict[str, np.ndarray]] = {"prediction": {}, "truth": {}}
        asset_sha: dict[str, dict[str, str]] = {"prediction": {}, "truth": {}}
        assets_valid = True
        for group_name, assets, required_roles in (
            ("prediction", prediction_assets, expected_prediction_roles),
            ("truth", truth_assets, expected_truth_roles),
        ):
            for role in sorted(required_roles):
                array, digest = _read_verified_array_asset(
                    _mapping(assets.get(role)),
                    base_dir=base_dir,
                    case_id=case_id,
                    group=group_name,
                    role=role,
                    blockers=blockers,
                )
                if array is None or digest is None:
                    assets_valid = False
                    continue
                arrays[group_name][role] = array
                asset_sha[group_name][role] = digest
        expected_binding = _case_evidence_binding_sha256(
            checkpoint_sha256=recorded_checkpoint,
            case_id=case_id,
            patient_id=patient_id,
            prediction_asset_sha256=asset_sha["prediction"],
            ground_truth_asset_sha256=asset_sha["truth"],
        )
        if not assets_valid or str(record.get("evidence_binding_sha256") or "").lower() != expected_binding:
            blockers.append({"code": "prediction_evidence_binding_mismatch", "case_id": case_id})
            continue
        binding_digests.append(expected_binding)
        cases.append(
            {
                "case_id": case_id,
                "patient_id": patient_id,
                "record": record,
                "prediction": arrays["prediction"],
                "truth": arrays["truth"],
            }
        )

    if seen_case_ids != split_test_cases:
        blockers.append(
            {
                "code": "prediction_test_case_coverage_mismatch",
                "missing": sorted(split_test_cases - seen_case_ids),
                "unexpected": sorted(seen_case_ids - split_test_cases),
            }
        )
    patient_ids = {str(item["patient_id"]) for item in cases}
    declared_case_count = _finite_number(prediction_manifest.get("case_count"))
    declared_patient_count = _finite_number(prediction_manifest.get("patient_count"))
    if declared_case_count is None or not declared_case_count.is_integer() or int(declared_case_count) != len(cases):
        blockers.append({"code": "prediction_evidence_case_count_mismatch"})
    if (
        declared_patient_count is None
        or not declared_patient_count.is_integer()
        or int(declared_patient_count) != len(patient_ids)
    ):
        blockers.append({"code": "prediction_evidence_patient_count_mismatch"})

    metrics: dict[str, float] = {}
    if cases and len(cases) == len(raw_records):
        if capability == "patient_conditioned_segmentation":
            metrics = _recompute_patient_conditioned_metrics(
                cases,
                _mapping(prediction_manifest.get("inference_thresholds")),
                blockers,
            )
        else:
            metrics = _recompute_bone_activity_metrics(
                cases,
                _mapping(prediction_manifest.get("inference_thresholds")),
                blockers,
            )
    elif raw_records:
        blockers.append({"code": "prediction_case_metric_recompute_incomplete"})
    evidence_digest = _mapping_sha256(
        {
            "schema_version": PREDICTION_EVIDENCE_SCHEMA_VERSION,
            "capability": capability,
            "checkpoint_sha256": recorded_checkpoint,
            "case_bindings": sorted(binding_digests),
            "metrics": metrics,
        }
    )
    return _prediction_replay_report(
        metrics,
        cases,
        blockers,
        checkpoint_sha256,
        evidence_sha256=evidence_digest,
    )


def _prediction_replay_report(
    metrics: Mapping[str, Any],
    cases: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    checkpoint_sha256: str | None,
    *,
    evidence_sha256: str | None = None,
) -> dict[str, Any]:
    unique = [_thaw(item) for item in dict.fromkeys(_freeze(item) for item in blockers)]
    return {
        "schema_version": PREDICTION_EVIDENCE_SCHEMA_VERSION,
        "checkpoint_sha256": checkpoint_sha256,
        "valid": not unique,
        "metrics": dict(metrics),
        "case_count": len(cases),
        "patient_count": len({str(item["patient_id"]) for item in cases}),
        "evidence_sha256": evidence_sha256,
        "blockers": unique,
    }


def _prediction_split_index(
    split_manifest: Mapping[str, Any], blockers: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    rows = split_manifest.get("records")
    if not isinstance(rows, list) or not rows:
        blockers.append({"code": "prediction_split_manifest_missing"})
        return {}, set()
    index: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping) or str(raw.get("split") or "").lower() != "test":
            continue
        case_id = str(raw.get("case_id") or "").strip()
        patient_id = str(raw.get("patient_id") or "").strip()
        if not case_id or not patient_id:
            blockers.append({"code": "prediction_split_test_identity_missing"})
            continue
        previous = index.get(case_id)
        if previous is not None and str(previous.get("patient_id")) != patient_id:
            blockers.append({"code": "prediction_split_case_patient_conflict", "case_id": case_id})
            continue
        index[case_id] = dict(raw)
    if not index:
        blockers.append({"code": "prediction_split_test_cases_missing"})
    return index, set(index)


def _validate_record_against_split(
    case_id: str,
    patient_id: str,
    split_index: Mapping[str, Mapping[str, Any]],
    blockers: list[dict[str, Any]],
) -> None:
    split_record = _mapping(split_index.get(case_id))
    if not split_record:
        blockers.append({"code": "prediction_record_not_in_split_manifest", "case_id": case_id})
        return
    if str(split_record.get("patient_id") or "") != patient_id:
        blockers.append({"code": "prediction_record_patient_mismatch", "case_id": case_id})
    if split_record.get("target_domain") is not True or split_record.get("admitted") is not True:
        blockers.append({"code": "prediction_split_record_not_admitted_target_domain", "case_id": case_id})
    if split_record.get("physician_reviewed") is not True:
        blockers.append({"code": "prediction_split_record_not_physician_reviewed", "case_id": case_id})


def _required_asset_roles(capability: str) -> tuple[set[str], set[str]]:
    if capability == "patient_conditioned_segmentation":
        return PATIENT_PREDICTION_ASSETS, PATIENT_TRUTH_ASSETS
    return BONE_ACTIVITY_PREDICTION_ASSETS, BONE_ACTIVITY_TRUTH_ASSETS


def _read_verified_array_asset(
    asset: Mapping[str, Any],
    *,
    base_dir: Path,
    case_id: str,
    group: str,
    role: str,
    blockers: list[dict[str, Any]],
) -> tuple[np.ndarray | None, str | None]:
    value = str(asset.get("path") or "").strip()
    path = Path(value).expanduser() if value else None
    if path is not None and not path.is_absolute():
        path = (base_dir / path).resolve()
    elif path is not None:
        path = path.resolve()
    if path is None or not path.is_file():
        blockers.append({"code": "prediction_asset_missing", "case_id": case_id, "group": group, "role": role})
        return None, None
    expected = str(asset.get("sha256") or "").lower()
    actual = _sha256(path)
    if not expected or expected != actual:
        blockers.append({"code": "prediction_asset_sha_mismatch", "case_id": case_id, "group": group, "role": role})
        return None, actual
    try:
        array = _read_array(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        blockers.append(
            {
                "code": "prediction_asset_unreadable",
                "case_id": case_id,
                "group": group,
                "role": role,
                "detail": str(exc),
            }
        )
        return None, actual
    if array.size == 0 or array.size > 100_000_000 or not np.issubdtype(array.dtype, np.number):
        blockers.append({"code": "prediction_asset_array_invalid", "case_id": case_id, "group": group, "role": role})
        return None, actual
    if not np.isfinite(array).all():
        blockers.append({"code": "prediction_asset_non_finite", "case_id": case_id, "group": group, "role": role})
        return None, actual
    declared_shape = asset.get("shape")
    if declared_shape is not None and list(array.shape) != list(declared_shape):
        blockers.append(
            {"code": "prediction_asset_shape_declaration_mismatch", "case_id": case_id, "group": group, "role": role}
        )
        return None, actual
    return np.asarray(array), actual


def _read_array(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return np.asarray(np.load(path, allow_pickle=False))
    if suffix == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            keys = list(archive.files)
            if keys != ["array"]:
                raise ValueError("NPZ evidence must contain exactly one array named 'array'.")
            return np.asarray(archive["array"])
    if suffix == ".json":
        return np.asarray(json.loads(path.read_text(encoding="utf-8")))
    if suffix in {".png", ".tif", ".tiff"}:
        with Image.open(path) as image:
            return np.asarray(image)
    raise ValueError(f"Unsupported prediction evidence array format: {suffix}")


def _case_evidence_binding_sha256(
    *,
    checkpoint_sha256: str,
    case_id: str,
    patient_id: str,
    prediction_asset_sha256: Mapping[str, str],
    ground_truth_asset_sha256: Mapping[str, str],
) -> str:
    return _mapping_sha256(
        {
            "schema_version": PREDICTION_EVIDENCE_SCHEMA_VERSION,
            "checkpoint_sha256": checkpoint_sha256,
            "case_id": case_id,
            "patient_id": patient_id,
            "prediction_assets": dict(sorted(prediction_asset_sha256.items())),
            "ground_truth_assets": dict(sorted(ground_truth_asset_sha256.items())),
        }
    )


def _recompute_patient_conditioned_metrics(
    cases: list[dict[str, Any]],
    inference_thresholds: Mapping[str, Any],
    blockers: list[dict[str, Any]],
) -> dict[str, float]:
    segmentation_threshold = _finite_number(inference_thresholds.get("segmentation_threshold"))
    if segmentation_threshold is None or not 0.0 < segmentation_threshold < 1.0:
        blockers.append({"code": "prediction_inference_thresholds_invalid"})
        return {}
    case_rows: list[dict[str, Any]] = []
    probabilities: list[np.ndarray] = []
    truths: list[np.ndarray] = []
    for item in cases:
        case_id = str(item["case_id"])
        prediction = cast(dict[str, np.ndarray], item["prediction"])
        truth_assets = cast(dict[str, np.ndarray], item["truth"])
        truth = _strict_binary_array(truth_assets["segmentation_mask"], case_id, "segmentation_mask", blockers)
        conditioned = _strict_binary_array(prediction["conditioned_mask"], case_id, "conditioned_mask", blockers)
        image_only = _strict_binary_array(prediction["image_only_mask"], case_id, "image_only_mask", blockers)
        fallback = _strict_binary_array(prediction["fallback_mask"], case_id, "fallback_mask", blockers)
        probability = _strict_probability_array(
            prediction["conditioned_probability"], case_id, "conditioned_probability", blockers
        )
        arrays = (truth, conditioned, image_only, fallback, probability)
        if any(value is None for value in arrays):
            continue
        truth = cast(np.ndarray, truth)
        conditioned = cast(np.ndarray, conditioned)
        image_only = cast(np.ndarray, image_only)
        fallback = cast(np.ndarray, fallback)
        probability = cast(np.ndarray, probability)
        if any(value.shape != truth.shape for value in (conditioned, image_only, fallback, probability)):
            blockers.append({"code": "prediction_asset_shape_mismatch", "case_id": case_id})
            continue
        if not _numbers_match(_mapping(item["record"]).get("segmentation_threshold"), segmentation_threshold):
            blockers.append({"code": "prediction_record_threshold_mismatch", "case_id": case_id})
            continue
        if not np.array_equal(conditioned, probability >= segmentation_threshold):
            blockers.append({"code": "prediction_mask_probability_mismatch", "case_id": case_id})
            continue
        conditioned_counts = _binary_counts_array(conditioned, truth)
        image_counts = _binary_counts_array(image_only, truth)
        conditioned_dice = _dice_from_counts(conditioned_counts)
        image_dice = _dice_from_counts(image_counts)
        predicted_fraction = float(np.mean(conditioned))
        truth_fraction = float(np.mean(truth))
        spacing = _pixel_spacing(_mapping(item["record"]).get("pixel_spacing_mm"), case_id, blockers)
        boundary_shift: float | None = None
        if spacing is not None:
            boundary_shift = _symmetric_boundary_hausdorff_mm(conditioned, image_only, spacing=spacing)
            if boundary_shift is None:
                blockers.append({"code": "patient_boundary_metric_unavailable", "case_id": case_id})
        subgroup_labels = _mapping(_mapping(item["record"]).get("subgroup_labels"))
        if not subgroup_labels:
            blockers.append({"code": "prediction_record_subgroup_labels_missing", "case_id": case_id})
        case_rows.append(
            {
                "case_id": case_id,
                "patient_id": str(item["patient_id"]),
                "dice": conditioned_dice,
                "iou": _iou_from_counts(conditioned_counts),
                "recall": _safe_ratio(conditioned_counts[0], conditioned_counts[0] + conditioned_counts[2]),
                "precision": _safe_ratio(conditioned_counts[0], conditioned_counts[0] + conditioned_counts[1]),
                "image_only_dice": image_dice,
                "dice_delta": conditioned_dice - image_dice,
                "empty_mask": float(not np.any(conditioned)),
                "over_segmentation": float(predicted_fraction > max(0.05, truth_fraction * 2.0)),
                "fallback_success": float(np.array_equal(fallback, image_only)),
                "boundary_shift_mm": boundary_shift,
                "subgroup_labels": subgroup_labels,
            }
        )
        probabilities.append(probability.astype(np.float64, copy=False).reshape(-1))
        truths.append(truth.astype(np.float64, copy=False).reshape(-1))
    if len(case_rows) != len(cases):
        blockers.append({"code": "prediction_case_metric_recompute_incomplete"})
        return {}

    deltas_by_patient: dict[str, list[float]] = {}
    deltas_by_subgroup: dict[str, list[float]] = {}
    for row in case_rows:
        deltas_by_patient.setdefault(str(row["patient_id"]), []).append(float(row["dice_delta"]))
        for name, value in _mapping(row["subgroup_labels"]).items():
            deltas_by_subgroup.setdefault(f"{name}:{value}", []).append(float(row["dice_delta"]))
    if not deltas_by_subgroup:
        blockers.append({"code": "prediction_subgroup_recompute_unavailable"})
    patient_deltas = [float(np.mean(values)) for values in deltas_by_patient.values()]
    subgroup_deltas = [float(np.mean(values)) for values in deltas_by_subgroup.values()]
    boundary_values = [float(row["boundary_shift_mm"]) for row in case_rows if row["boundary_shift_mm"] is not None]
    metrics = {
        "dice": _mean_case_metric(case_rows, "dice"),
        "iou": _mean_case_metric(case_rows, "iou"),
        "recall": _mean_case_metric(case_rows, "recall"),
        "precision": _mean_case_metric(case_rows, "precision"),
        "ece": _expected_calibration_error_binary(np.concatenate(probabilities), np.concatenate(truths), bins=15),
        "empty_mask_rate": _mean_case_metric(case_rows, "empty_mask"),
        "over_segmentation_rate": _mean_case_metric(case_rows, "over_segmentation"),
        "conditioned_minus_image_only_dice": _mean_case_metric(case_rows, "dice_delta"),
        "worst_subgroup_dice_delta": min(subgroup_deltas, default=-1.0),
        "context_fallback_success_rate": _mean_case_metric(case_rows, "fallback_success"),
        "max_boundary_shift_mm": max(boundary_values, default=0.0),
        "worst_patient_dice_delta": min(patient_deltas, default=-1.0),
        "case_count": float(len(case_rows)),
        "patient_count": float(len(deltas_by_patient)),
    }
    if metrics["conditioned_minus_image_only_dice"] < 0.0:
        blockers.append({"code": "patient_conditioning_recomputed_no_harm_failed"})
    if metrics["context_fallback_success_rate"] < 1.0:
        blockers.append({"code": "patient_conditioning_recomputed_fallback_failed"})
    return metrics


def _recompute_bone_activity_metrics(
    cases: list[dict[str, Any]],
    inference_thresholds: Mapping[str, Any],
    blockers: list[dict[str, Any]],
) -> dict[str, float]:
    gate_threshold = _finite_number(inference_thresholds.get("bone_gate_threshold"))
    abstention_threshold = _finite_number(inference_thresholds.get("abstention_threshold"))
    if (
        gate_threshold is None
        or abstention_threshold is None
        or not 0.0 < gate_threshold < 1.0
        or not 0.0 < abstention_threshold < 1.0
    ):
        blockers.append({"code": "prediction_inference_thresholds_invalid"})
        return {}
    class_counts = {index: [0.0, 0.0, 0.0] for index in range(3)}
    class_support_samples = {index: 0.0 for index in range(3)}
    gate_dice_values: list[float] = []
    activity_mae_values: list[float] = []
    confidence_values: list[np.ndarray] = []
    correctness_values: list[np.ndarray] = []
    non_abstained_errors = 0.0
    non_abstained_count = 0.0
    valid_count = 0.0
    contained_count = 0.0
    accepted_count = 0.0
    valid_case_count = 0
    for item in cases:
        case_id = str(item["case_id"])
        record = _mapping(item["record"])
        if not _numbers_match(record.get("bone_gate_threshold"), gate_threshold) or not _numbers_match(
            record.get("abstention_threshold"), abstention_threshold
        ):
            blockers.append({"code": "prediction_record_threshold_mismatch", "case_id": case_id})
        prediction = cast(dict[str, np.ndarray], item["prediction"])
        truth_assets = cast(dict[str, np.ndarray], item["truth"])
        predicted_gate = _strict_binary_array(prediction["bone_gate_mask"], case_id, "bone_gate_mask", blockers)
        gate_probability = _strict_probability_array(
            prediction["bone_gate_probability"], case_id, "bone_gate_probability", blockers
        )
        truth_gate = _strict_binary_array(truth_assets["bone_gate_mask"], case_id, "truth_bone_gate_mask", blockers)
        accepted = _strict_binary_array(
            prediction["accepted_prediction_mask"], case_id, "accepted_prediction_mask", blockers
        )
        class_prediction = _strict_class_array(
            prediction["class_prediction"], case_id, "class_prediction", blockers, allow_ignore=False
        )
        class_target = _strict_class_array(
            truth_assets["class_target"], case_id, "class_target", blockers, allow_ignore=True
        )
        class_probabilities = _strict_class_probabilities(prediction["class_probabilities"], case_id, blockers)
        uncertainty = _strict_probability_array(prediction["uncertainty"], case_id, "uncertainty", blockers)
        activity_score = _strict_probability_array(prediction["activity_score"], case_id, "activity_score", blockers)
        activity_target = _strict_probability_array(
            truth_assets["activity_score"], case_id, "truth_activity_score", blockers
        )
        arrays = (
            predicted_gate,
            gate_probability,
            truth_gate,
            accepted,
            class_prediction,
            class_target,
            class_probabilities,
            uncertainty,
            activity_score,
            activity_target,
        )
        if any(value is None for value in arrays):
            continue
        predicted_gate = cast(np.ndarray, predicted_gate)
        gate_probability = cast(np.ndarray, gate_probability)
        truth_gate = cast(np.ndarray, truth_gate)
        accepted = cast(np.ndarray, accepted)
        class_prediction = cast(np.ndarray, class_prediction)
        class_target = cast(np.ndarray, class_target)
        class_probabilities = cast(np.ndarray, class_probabilities)
        uncertainty = cast(np.ndarray, uncertainty)
        activity_score = cast(np.ndarray, activity_score)
        activity_target = cast(np.ndarray, activity_target)
        shape = truth_gate.shape
        two_dimensional = (
            predicted_gate,
            accepted,
            class_prediction,
            class_target,
            uncertainty,
            activity_score,
            activity_target,
            gate_probability,
        )
        if any(value.shape != shape for value in two_dimensional) or class_probabilities.shape != (*shape, 3):
            blockers.append({"code": "prediction_asset_shape_mismatch", "case_id": case_id})
            continue
        if not np.array_equal(predicted_gate, gate_probability >= gate_threshold):
            blockers.append({"code": "prediction_bone_gate_probability_mismatch", "case_id": case_id})
            continue
        argmax_prediction = np.argmax(class_probabilities, axis=-1)
        if not np.array_equal(argmax_prediction, class_prediction):
            blockers.append({"code": "prediction_class_argmax_mismatch", "case_id": case_id})
            continue
        valid = class_target != 255
        abstention = uncertainty >= abstention_threshold
        expected_accepted = (~abstention) & truth_gate & valid
        if not np.array_equal(accepted, expected_accepted):
            blockers.append({"code": "prediction_accepted_mask_contract_mismatch", "case_id": case_id})
            continue
        gate_dice_values.append(_dice_from_counts(_binary_counts_array(predicted_gate, truth_gate)))
        if not np.any(truth_gate):
            blockers.append({"code": "bone_activity_score_support_missing", "case_id": case_id})
            continue
        activity_mae_values.append(float(np.mean(np.abs(activity_score[truth_gate] - activity_target[truth_gate]))))
        correct = class_prediction[valid] == class_target[valid]
        confidence = np.max(class_probabilities, axis=-1)[valid]
        confidence_values.append(confidence.astype(np.float64, copy=False))
        correctness_values.append(correct.astype(np.float64, copy=False))
        for class_index in range(3):
            prediction_mask = class_prediction == class_index
            truth_mask = class_target == class_index
            class_counts[class_index][0] += float(np.count_nonzero(prediction_mask & truth_mask))
            class_counts[class_index][1] += float(np.count_nonzero(prediction_mask & valid & ~truth_mask))
            class_counts[class_index][2] += float(np.count_nonzero(~prediction_mask & truth_mask))
            class_support_samples[class_index] += float(bool(np.any(truth_mask)))
        errors = (~abstention) & valid & (class_prediction != class_target)
        non_abstained_errors += float(np.count_nonzero(errors))
        non_abstained_count += float(np.count_nonzero((~abstention) & valid))
        valid_count += float(np.count_nonzero(valid))
        contained_count += float(np.count_nonzero(accepted & truth_gate))
        accepted_count += float(np.count_nonzero(accepted))
        valid_case_count += 1
    if valid_case_count != len(cases):
        blockers.append({"code": "prediction_case_metric_recompute_incomplete"})
        return {}
    if valid_count <= 0.0 or not confidence_values or not correctness_values:
        blockers.append({"code": "bone_activity_valid_class_support_missing"})
        return {}

    class_names = ("low_activity", "transition", "high_activity")
    per_class_dice = {
        class_names[index]: _dice_from_counts(
            (
                class_counts[index][0],
                class_counts[index][1],
                class_counts[index][2],
            )
        )
        for index in range(3)
    }
    metrics = {
        "bone_gate_threshold": gate_threshold,
        "abstention_threshold": abstention_threshold,
        "bone_gate_dice": float(np.mean(gate_dice_values)),
        "activity_score_mae": float(np.mean(activity_mae_values)),
        "macro_dice": float(np.mean(list(per_class_dice.values()))),
        "low_activity_dice": per_class_dice["low_activity"],
        "transition_dice": per_class_dice["transition"],
        "high_activity_dice": per_class_dice["high_activity"],
        "transition_recall": _safe_ratio(class_counts[1][0], class_counts[1][0] + class_counts[1][2]),
        "ece": _expected_calibration_error_confidence(
            np.concatenate(confidence_values), np.concatenate(correctness_values), bins=10
        ),
        "abstention_error_rate": _safe_ratio(non_abstained_errors, valid_count),
        "selective_error_rate": _safe_ratio(non_abstained_errors, non_abstained_count),
        "abstention_coverage_rate": _safe_ratio(non_abstained_count, valid_count),
        "bone_gate_containment_rate": _safe_ratio(contained_count, accepted_count),
        "non_abstained_pixel_count": non_abstained_count,
        "valid_pixel_count": valid_count,
        "case_count": float(len(cases)),
        "patient_count": float(len({str(item["patient_id"]) for item in cases})),
    }
    for index, class_name in enumerate(class_names):
        metrics[f"{class_name}_support_pixels"] = class_counts[index][0] + class_counts[index][2]
        metrics[f"{class_name}_support_samples"] = class_support_samples[index]
        if metrics[f"{class_name}_support_pixels"] <= 0 or metrics[f"{class_name}_support_samples"] <= 0:
            blockers.append({"code": "bone_activity_class_support_missing", "class_name": class_name})
    if non_abstained_count <= 0:
        blockers.append({"code": "bone_activity_all_abstained"})
    return metrics


def _strict_binary_array(
    value: np.ndarray,
    case_id: str,
    role: str,
    blockers: list[dict[str, Any]],
) -> np.ndarray | None:
    array = np.asarray(value)
    if array.ndim != 2 or not np.isin(array, (0, 1, False, True)).all():
        blockers.append({"code": "prediction_binary_asset_invalid", "case_id": case_id, "role": role})
        return None
    return array.astype(np.bool_, copy=False)


def _strict_probability_array(
    value: np.ndarray,
    case_id: str,
    role: str,
    blockers: list[dict[str, Any]],
) -> np.ndarray | None:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or not np.isfinite(array).all() or np.any(array < 0.0) or np.any(array > 1.0):
        blockers.append({"code": "prediction_probability_asset_invalid", "case_id": case_id, "role": role})
        return None
    return array


def _strict_class_array(
    value: np.ndarray,
    case_id: str,
    role: str,
    blockers: list[dict[str, Any]],
    *,
    allow_ignore: bool,
) -> np.ndarray | None:
    array = np.asarray(value)
    allowed = (0, 1, 2, 255) if allow_ignore else (0, 1, 2)
    if array.ndim != 2 or not np.equal(array, np.floor(array)).all() or not np.isin(array, allowed).all():
        blockers.append({"code": "prediction_class_asset_invalid", "case_id": case_id, "role": role})
        return None
    return array.astype(np.int64, copy=False)


def _strict_class_probabilities(
    value: np.ndarray,
    case_id: str,
    blockers: list[dict[str, Any]],
) -> np.ndarray | None:
    array = np.asarray(value, dtype=np.float64)
    valid = (
        array.ndim == 3
        and array.shape[-1] == 3
        and np.isfinite(array).all()
        and bool(np.all(array >= 0.0))
        and bool(np.all(array <= 1.0))
        and bool(np.allclose(np.sum(array, axis=-1), 1.0, rtol=1e-6, atol=1e-6))
    )
    if not valid:
        blockers.append({"code": "prediction_class_probability_asset_invalid", "case_id": case_id})
        return None
    return array


def _pixel_spacing(
    value: Any,
    case_id: str,
    blockers: list[dict[str, Any]],
) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        blockers.append({"code": "prediction_pixel_spacing_missing", "case_id": case_id})
        return None
    row = _finite_number(value[0])
    column = _finite_number(value[1])
    if row is None or column is None or row <= 0.0 or column <= 0.0:
        blockers.append({"code": "prediction_pixel_spacing_invalid", "case_id": case_id})
        return None
    return row, column


def _binary_counts_array(prediction: np.ndarray, truth: np.ndarray) -> tuple[float, float, float]:
    return (
        float(np.count_nonzero(prediction & truth)),
        float(np.count_nonzero(prediction & ~truth)),
        float(np.count_nonzero(~prediction & truth)),
    )


def _dice_from_counts(counts: tuple[float, float, float]) -> float:
    true_positive, false_positive, false_negative = counts
    return _safe_ratio(2.0 * true_positive, 2.0 * true_positive + false_positive + false_negative)


def _iou_from_counts(counts: tuple[float, float, float]) -> float:
    true_positive, false_positive, false_negative = counts
    return _safe_ratio(true_positive, true_positive + false_positive + false_negative)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / max(1.0, denominator))


def _mean_case_metric(rows: list[dict[str, Any]], name: str) -> float:
    return float(np.mean([float(row[name]) for row in rows]))


def _expected_calibration_error_binary(
    probabilities: np.ndarray,
    truth: np.ndarray,
    *,
    bins: int,
) -> float:
    return _expected_calibration_error_confidence(probabilities, truth, bins=bins)


def _expected_calibration_error_confidence(
    confidence: np.ndarray,
    correct: np.ndarray,
    *,
    bins: int,
) -> float:
    confidence = np.asarray(confidence, dtype=np.float64).reshape(-1)
    correct = np.asarray(correct, dtype=np.float64).reshape(-1)
    if confidence.size == 0 or confidence.shape != correct.shape:
        raise ValueError("Calibration replay requires paired non-empty arrays.")
    edges = np.linspace(0.0, 1.0, bins + 1, dtype=np.float64)
    ece = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        selected = (confidence >= lower) & (confidence < upper if index < bins - 1 else confidence <= upper)
        if not np.any(selected):
            continue
        ece += float(np.mean(selected)) * abs(float(np.mean(confidence[selected])) - float(np.mean(correct[selected])))
    return float(ece)


def _symmetric_boundary_hausdorff_mm(
    first: np.ndarray,
    second: np.ndarray,
    *,
    spacing: tuple[float, float],
) -> float | None:
    first_positive = bool(np.any(first))
    second_positive = bool(np.any(second))
    if not first_positive and not second_positive:
        return 0.0
    if first_positive != second_positive:
        return None
    first_points = np.argwhere(_binary_boundary(first)).astype(np.float64)
    second_points = np.argwhere(_binary_boundary(second)).astype(np.float64)
    if first_points.size == 0 or second_points.size == 0:
        return None
    scale = np.asarray(spacing, dtype=np.float64)
    first_points *= scale
    second_points *= scale
    return max(
        _directed_boundary_distance(first_points, second_points),
        _directed_boundary_distance(second_points, first_points),
    )


def _binary_boundary(mask: np.ndarray) -> np.ndarray:
    value = np.asarray(mask, dtype=np.bool_)
    padded = np.pad(value, 1, mode="constant", constant_values=False)
    height, width = value.shape
    neighborhoods = [
        padded[1 + row_offset : 1 + row_offset + height, 1 + column_offset : 1 + column_offset + width]
        for row_offset in (-1, 0, 1)
        for column_offset in (-1, 0, 1)
    ]
    eroded = np.logical_and.reduce(neighborhoods)
    return value & ~eroded


def _directed_boundary_distance(source: np.ndarray, target: np.ndarray) -> float:
    maximum = 0.0
    for start in range(0, len(source), 128):
        difference = source[start : start + 128, None, :] - target[None, :, :]
        nearest_squared = np.min(np.sum(np.square(difference), axis=2), axis=1)
        maximum = max(maximum, float(np.max(nearest_squared)))
    return math.sqrt(maximum)


def _validate_metric_values(metrics: Mapping[str, Any], required: set[str], blockers: list[dict[str, Any]]) -> None:
    for name in sorted(required):
        value = _finite_number(metrics.get(name))
        if value is None:
            blockers.append({"code": "promotion_metric_missing_or_non_finite", "metric": name})
        elif not _metric_value_in_range(name, value):
            blockers.append(
                {
                    "code": "promotion_metric_out_of_range",
                    "metric": name,
                    "actual": value,
                }
            )


def _apply_metric_gates(metrics: Mapping[str, Any], gates: Mapping[str, Any], blockers: list[dict[str, Any]]) -> None:
    for key, threshold_value in gates.items():
        threshold = _finite_number(threshold_value)
        metric_name = key.removeprefix("max_").removeprefix("min_")
        if threshold is None or not _metric_value_in_range(metric_name, threshold):
            blockers.append({"code": "promotion_policy_threshold_invalid", "metric": key})
            continue
        maximum = key.startswith("max_")
        actual = _finite_number(metrics.get(metric_name))
        if actual is None:
            continue
        if maximum and actual > threshold:
            blockers.append({"code": "promotion_metric_above_maximum", "metric": metric_name})
        if not maximum and actual < threshold:
            blockers.append({"code": "promotion_metric_below_minimum", "metric": metric_name})


def _metric_names(gates: Mapping[str, Any]) -> set[str]:
    return {str(key).removeprefix("max_").removeprefix("min_") for key in gates}


def _validate_bone_activity_threshold_selection(
    validation: Mapping[str, Any],
    test_metrics: Mapping[str, Any],
    blockers: list[dict[str, Any]],
) -> None:
    selection = _mapping(validation.get("threshold_selection"))
    selected = _mapping(selection.get("selected"))
    defaults = _mapping(selection.get("defaults"))
    constraints = _mapping(selection.get("selection_constraints"))
    frozen_test = _mapping(selection.get("frozen_test_evaluation"))
    validation_metrics = _mapping(validation.get("proxy_validation_metrics"))
    gate_threshold = _finite_number(selected.get("bone_gate_threshold"))
    abstention_threshold = _finite_number(selected.get("abstention_threshold"))
    default_gate = _finite_number(defaults.get("bone_gate_threshold"))
    minimum_coverage = _finite_number(constraints.get("minimum_coverage_rate"))
    maximum_error = _finite_number(constraints.get("maximum_selective_error_rate"))
    if selection.get("validation_constraints_passed") is not True:
        blockers.append({"code": "bone_activity_validation_threshold_constraints_failed"})
    if frozen_test.get("constraints_passed") is not True:
        blockers.append({"code": "bone_activity_frozen_test_selective_safety_failed"})
    if (
        selection.get("enabled") is not True
        or selection.get("selection_split") != "validation"
        or selection.get("test_set_used_for_selection") is not False
        or frozen_test.get("thresholds_reused_without_test_tuning") is not True
        or gate_threshold is None
        or abstention_threshold is None
        or default_gate is None
        or minimum_coverage is None
        or maximum_error is None
        or not all(0.0 < value < 1.0 for value in (gate_threshold, abstention_threshold, default_gate))
        or not 0.0 <= minimum_coverage <= 1.0
        or not 0.0 <= maximum_error <= 1.0
    ):
        blockers.append({"code": "bone_activity_threshold_selection_evidence_invalid"})
        return
    for metric_name, selected_value in (
        ("bone_gate_threshold", gate_threshold),
        ("abstention_threshold", abstention_threshold),
    ):
        if not _numbers_match(test_metrics.get(metric_name), selected_value) or not _numbers_match(
            validation_metrics.get(metric_name), selected_value
        ):
            blockers.append({"code": "bone_activity_frozen_threshold_metric_mismatch", "metric": metric_name})

    gate_scan = _parse_threshold_scan(
        selection.get("bone_gate_scan"),
        metric_names=("bone_gate_dice", "bone_gate_precision"),
    )
    abstention_scan = _parse_threshold_scan(
        selection.get("abstention_scan"),
        metric_names=("coverage_rate", "selective_error_rate"),
    )
    if gate_scan is None or abstention_scan is None:
        blockers.append({"code": "bone_activity_threshold_scan_invalid"})
        return
    expected_gate = max(
        gate_scan,
        key=lambda item: (
            item["bone_gate_dice"],
            item["bone_gate_precision"],
            -abs(item["threshold"] - default_gate),
        ),
    )["threshold"]
    if not math.isclose(gate_threshold, expected_gate, rel_tol=0.0, abs_tol=1e-12):
        blockers.append({"code": "bone_activity_gate_threshold_selection_rule_mismatch"})

    eligible = [
        item
        for item in abstention_scan
        if item["coverage_rate"] >= minimum_coverage and item["selective_error_rate"] <= maximum_error
    ]
    expected_validation_passed = bool(eligible)
    expected_abstention = (
        min(
            eligible,
            key=lambda item: (
                item["selective_error_rate"],
                -item["coverage_rate"],
                item["threshold"],
            ),
        )["threshold"]
        if eligible
        else min(item["threshold"] for item in abstention_scan)
    )
    if selection.get("validation_constraints_passed") is not expected_validation_passed:
        blockers.append({"code": "bone_activity_validation_constraint_evidence_mismatch"})
    if not expected_validation_passed:
        blockers.append({"code": "bone_activity_validation_threshold_constraints_failed"})
    if not math.isclose(abstention_threshold, expected_abstention, rel_tol=0.0, abs_tol=1e-12):
        blockers.append({"code": "bone_activity_abstention_threshold_selection_rule_mismatch"})

    test_coverage = _finite_number(test_metrics.get("abstention_coverage_rate"))
    test_error = _finite_number(test_metrics.get("selective_error_rate"))
    if test_coverage is None or test_error is None:
        blockers.append({"code": "bone_activity_frozen_test_selective_metrics_missing"})
        return
    coverage_passed = test_coverage >= minimum_coverage
    error_passed = test_error <= maximum_error
    constraints_passed = coverage_passed and error_passed
    if (
        frozen_test.get("minimum_coverage_rate_passed") is not coverage_passed
        or frozen_test.get("maximum_selective_error_rate_passed") is not error_passed
        or frozen_test.get("constraints_passed") is not constraints_passed
    ):
        blockers.append({"code": "bone_activity_frozen_test_constraint_evidence_mismatch"})
    if not constraints_passed:
        blockers.append({"code": "bone_activity_frozen_test_selective_safety_failed"})


def _parse_threshold_scan(
    value: Any,
    *,
    metric_names: tuple[str, ...],
) -> list[dict[str, float]] | None:
    if not isinstance(value, list) or not value:
        return None
    parsed: list[dict[str, float]] = []
    seen_thresholds: set[float] = set()
    for raw in value:
        row = _mapping(raw)
        threshold = _finite_number(row.get("threshold"))
        metrics = {name: _finite_number(row.get(name)) for name in metric_names}
        if (
            threshold is None
            or not 0.0 < threshold < 1.0
            or threshold in seen_thresholds
            or any(item is None or not 0.0 <= item <= 1.0 for item in metrics.values())
        ):
            return None
        seen_thresholds.add(threshold)
        parsed.append(
            {
                "threshold": threshold,
                **{name: float(cast(float, item)) for name, item in metrics.items()},
            }
        )
    return parsed


def _metric_value_in_range(name: str, value: float) -> bool:
    if name in {"conditioned_minus_image_only_dice", "worst_subgroup_dice_delta"}:
        return -1.0 <= value <= 1.0
    if name == "max_boundary_shift_mm":
        return value >= 0.0
    return 0.0 <= value <= 1.0


def _require_matching_metric(
    evidence_metrics: Mapping[str, Any],
    reported_metrics: Mapping[str, Any],
    metric_name: str,
    evidence_name: str,
    blockers: list[dict[str, Any]],
) -> None:
    evidence_value = _finite_number(evidence_metrics.get(metric_name))
    reported_value = _finite_number(reported_metrics.get(metric_name))
    if evidence_value is None or reported_value is None or not _numbers_match(evidence_value, reported_value):
        blockers.append(
            {
                "code": "promotion_metric_evidence_mismatch",
                "evidence": evidence_name,
                "metric": metric_name,
            }
        )


def _numbers_match(left: Any, right: Any) -> bool:
    left_value = _finite_number(left)
    right_value = _finite_number(right)
    return bool(
        left_value is not None
        and right_value is not None
        and math.isclose(left_value, right_value, rel_tol=1e-9, abs_tol=1e-12)
    )


def _read_structured(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {"records": list(csv.DictReader(handle))}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Evidence must contain a JSON object.")
    return payload


def _report(
    capability: str,
    *,
    errors: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    engineering_ready: bool = False,
    policy_status: str = "",
    policy_sha256: str | None = None,
    checkpoint_path: str | None = None,
    checkpoint_sha256: str | None = None,
    recomputed_metrics: Mapping[str, Any] | None = None,
    prediction_evidence_sha256: str | None = None,
    prediction_evidence_case_count: int = 0,
    prediction_evidence_patient_count: int = 0,
    approval_target: Mapping[str, Any] | None = None,
    approval_valid: bool = False,
    approval_bundle_sha256: str | None = None,
    active_approval_count: int = 0,
) -> dict[str, Any]:
    target_ready = engineering_ready and not blockers and policy_status == APPROVED_POLICY_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "capability": capability,
        "engineering_ready": engineering_ready,
        "target_domain_promotion_ready": target_ready,
        "runtime_replacement_allowed": target_ready,
        "clinical_claim_allowed": False,
        "policy_status": policy_status or None,
        "policy_sha256": policy_sha256,
        "checkpoint_path": checkpoint_path,
        "checkpoint_sha256": checkpoint_sha256,
        "recomputed_metrics": dict(recomputed_metrics or {}),
        "prediction_evidence_sha256": prediction_evidence_sha256,
        "prediction_evidence_case_count": prediction_evidence_case_count,
        "prediction_evidence_patient_count": prediction_evidence_patient_count,
        "promotion_approval_target": dict(approval_target or {}),
        "promotion_approval_valid": approval_valid,
        "promotion_approval_bundle_sha256": approval_bundle_sha256,
        "promotion_active_approval_count": active_approval_count,
        "errors": errors,
        "promotion_blockers": blockers,
        "medical_boundary": (
            "Target-domain promotion requires paired jaw-osteomyelitis evidence, recomputed patient/institution/time "
            "separation, calibration, capability-specific safety metrics, and trusted physician review."
        ),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mapping_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        return _sha256(path)
    except OSError:
        return None


def _freeze(value: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((str(key), json.dumps(item, ensure_ascii=False, sort_keys=True)) for key, item in value.items())
    )


def _thaw(value: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    return {key: json.loads(item) for key, item in value}
