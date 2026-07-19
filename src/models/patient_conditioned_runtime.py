from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from PIL import Image

from src.core.clinical_context_verification import clinical_context_verification_issues
from src.core.paths import ensure_dir
from src.models.clinical_feature_vector import (
    DEFAULT_CLINICAL_FEATURE_NAMES,
    attach_runtime_consumption,
    build_clinical_feature_vector,
    compute_clinical_context_assessment_checksum,
    unsupported_clinical_feature_names,
    validate_clinical_feature_encoder_contract,
    validate_clinical_feature_vector,
)
from src.models.patient_conditioned_segmenter import (
    TinyPatientConditionedSegmenter2D,
    apply_patient_conditioning_safety_gate,
    load_patient_conditioned_checkpoint,
)

PATIENT_CONDITIONING_METADATA_CONTRACT: dict[str, Any] = {
    "fluorescence_path": "required_registered_grayscale_or_rgb_image_path",
    "dual_channel_registration_verified": "required_true_for_spatial_effect",
    "clinical_context_assessment": {
        "schema_version": "osteo-vision-clinical-context-assessment-v1",
        "clinical_context_snapshot": "required_deidentified_snapshot",
        "clinical_context_checksum": "required_sha256_of_snapshot",
        "clinical_context_assessment_checksum": "required_sha256_of_bound_assessment_evidence",
        "clinical_context_quality": "required_verified_quality_mapping",
        "model_features": "legacy_input_ignored_runtime_rebuilds_from_verified_snapshot",
        "model_feature_present": "legacy_input_ignored_runtime_rebuilds_masks_from_verified_snapshot",
        "clinical_feature_vector": {
            "schema_version": "osteo-vision-clinical-feature-vector-v1",
            "feature_version": "clinical-feature-vector-v1",
            "masks": ["present_mask", "missing_mask", "ood_mask"],
            "checksum": "required_for_verified_runtime_consumption",
        },
        "spatial_conditioning_authorized": "required_true_for_spatial_effect",
    },
    "reviewed_bone_gate": {
        "path": "required_for_spatial_effect",
        "sha256": "required_for_spatial_effect",
        "physician_reviewed": True,
        "trusted_review": True,
        "review_status": ["physician_accepted", "physician_modified", "reviewed_bone_gate"],
    },
    "target_domain_input_verified": "required_true_for_spatial_effect",
}

_ASSESSMENT_SCHEMA = "osteo-vision-clinical-context-assessment-v1"
_MANIFEST_SCHEMA = "osteo-vision-patient-conditioned-training-v1"
_CAPABILITY = "patient_conditioned_segmentation"
_REVIEWED_GATE_STATES = {"physician_accepted", "physician_modified", "reviewed_bone_gate"}
_RESTRICTED_SPATIAL_USE_BOUNDARY = "restricted_spatial_conditioning_with_physician_review"
_CLINICAL_FEATURE_SOURCE_EVIDENCE_SCHEMA = "osteo-vision-clinical-feature-source-evidence-v1"
_CLINICAL_FEATURE_SOURCE_FIELDS = [
    "clinical_values_json",
    "clinical_present_json",
    "clinical_mapping_json",
]
_CLINICAL_FEATURE_SOURCE_ROW_FIELDS = {
    "feature_name",
    "source_description",
    "source_description_sha256",
    "present_sample_count",
    "missing_sample_count",
    "present_patient_group_count",
}


@dataclass(frozen=True)
class PatientConditionedRuntimeEvidence:
    checkpoint_path: Path
    checkpoint_sha256: str
    manifest_path: Path
    manifest_sha256: str
    feature_names: tuple[str, ...]
    engineering_ready: bool
    proxy_checkpoint: bool
    target_domain_promotion_ready: bool
    runtime_replacement_allowed: bool
    medical_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_path": str(self.checkpoint_path),
            "checkpoint_sha256": self.checkpoint_sha256,
            "manifest_path": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
            "feature_names": list(self.feature_names),
            "engineering_ready": self.engineering_ready,
            "proxy_checkpoint": self.proxy_checkpoint,
            "target_domain_promotion_ready": self.target_domain_promotion_ready,
            "runtime_replacement_allowed": self.runtime_replacement_allowed,
            "medical_boundary": self.medical_boundary,
        }


def load_validated_patient_conditioned_runtime(
    checkpoint_path: str | Path,
    manifest_path: str | Path,
    *,
    device: torch.device,
    expected_manifest_sha256: str | None = None,
    strict_promotion_authorized: bool = False,
) -> tuple[TinyPatientConditionedSegmenter2D, dict[str, Any], PatientConditionedRuntimeEvidence]:
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    manifest_file = Path(manifest_path).expanduser().resolve()
    if not checkpoint.is_file():
        raise ValueError(f"Patient-conditioned checkpoint is missing: {checkpoint}")
    if not manifest_file.is_file():
        raise ValueError(f"Patient-conditioned manifest is missing: {manifest_file}")

    checkpoint_sha256 = _sha256_file(checkpoint)
    manifest_sha256 = _sha256_file(manifest_file)
    if expected_manifest_sha256 and manifest_sha256 != _normalized_sha256(expected_manifest_sha256):
        raise ValueError("Patient-conditioned manifest SHA256 mismatch")
    try:
        manifest_value = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Patient-conditioned manifest is unreadable: {exc}") from exc
    if not isinstance(manifest_value, dict):
        raise ValueError("Patient-conditioned manifest root must be a mapping")
    manifest = dict(manifest_value)
    if manifest.get("schema_version") != _MANIFEST_SCHEMA:
        raise ValueError("Patient-conditioned manifest schema_version is unsupported")
    if manifest.get("capability") != _CAPABILITY:
        raise ValueError("Patient-conditioned manifest capability mismatch")
    if _normalized_sha256(manifest.get("checkpoint_sha256")) != checkpoint_sha256:
        raise ValueError("Patient-conditioned checkpoint SHA256 mismatch")

    model, checkpoint_metadata = load_patient_conditioned_checkpoint(checkpoint, device=device)
    _validate_checkpoint_metadata(checkpoint_metadata, manifest, checkpoint_sha256, model)
    feature_names = _feature_names(manifest, checkpoint_metadata, model.clinical_feature_count)
    _validate_clinical_artifact_contracts(checkpoint_metadata, manifest, feature_names)
    training_domain = _mapping(manifest.get("training_domain"))
    target_domain_training = training_domain.get("target_domain") is True
    proxy_checkpoint = not target_domain_training
    engineering_ready = manifest.get("engineering_ready") is True
    manifest_target_ready = manifest.get("target_domain_promotion_ready") is True
    manifest_runtime_allowed = manifest.get("runtime_allowed") is True
    manifest_replacement_allowed = manifest.get("runtime_replacement_allowed") is True
    promotion = _mapping(manifest.get("promotion"))
    promotion_ready = (
        promotion.get("target_domain_promotion_ready") is True
        and promotion.get("runtime_replacement_allowed") is True
        and _normalized_sha256(promotion.get("checkpoint_sha256")) == checkpoint_sha256
        and not list(promotion.get("promotion_blockers") or [])
    )
    if proxy_checkpoint and (manifest_target_ready or manifest_runtime_allowed or manifest_replacement_allowed):
        raise ValueError("Non-target-domain patient-conditioned checkpoint contains forbidden runtime flags")
    target_domain_promotion_ready = bool(
        target_domain_training and manifest_target_ready and manifest_runtime_allowed and promotion_ready
    )
    runtime_replacement_allowed = bool(
        target_domain_promotion_ready and manifest_replacement_allowed and strict_promotion_authorized
    )
    medical_boundary = str(
        manifest.get("medical_boundary")
        or "Patient-conditioned output remains research validation evidence requiring physician review."
    )
    return (
        model,
        checkpoint_metadata,
        PatientConditionedRuntimeEvidence(
            checkpoint_path=checkpoint,
            checkpoint_sha256=checkpoint_sha256,
            manifest_path=manifest_file,
            manifest_sha256=manifest_sha256,
            feature_names=feature_names,
            engineering_ready=engineering_ready,
            proxy_checkpoint=proxy_checkpoint,
            target_domain_promotion_ready=target_domain_promotion_ready,
            runtime_replacement_allowed=runtime_replacement_allowed,
            medical_boundary=medical_boundary,
        ),
    )


def predict_patient_conditioned_image(
    model: TinyPatientConditionedSegmenter2D,
    runtime: PatientConditionedRuntimeEvidence,
    *,
    white_path: str | Path,
    fluorescence_path: str | Path,
    metadata: Mapping[str, Any],
    device: torch.device,
    output_dir: str | Path,
    case_id: str,
    segmentation_threshold: float,
    uncertainty_threshold: float,
) -> dict[str, Any]:
    white, fluorescence, rgb = _load_registered_images(white_path, fluorescence_path, device=device)
    registration_verified = metadata.get("dual_channel_registration_verified") is True
    assessment = _mapping(metadata.get("clinical_context_assessment"))
    (
        clinical_values,
        clinical_present,
        context_verified,
        context_reasons,
        context_checksum,
        clinical_feature_vector,
    ) = _clinical_tensors(assessment, runtime.feature_names, device=device)
    reviewed_gate, physician_reviewed, gate_reasons, gate_evidence = _reviewed_gate(
        metadata.get("reviewed_bone_gate"),
        width=rgb.shape[1],
        height=rgb.shape[0],
        device=device,
    )
    target_domain_input_verified = metadata.get("target_domain_input_verified") is True
    if not registration_verified:
        context_reasons.append("dual_channel_registration_not_verified")
    trusted_context = context_verified and registration_verified

    model.eval()
    with torch.no_grad():
        raw = model(
            white,
            fluorescence,
            clinical_values,
            clinical_present,
            context_trusted=trusted_context,
            conditioning_authorized=runtime.engineering_ready,
        )
        safe = apply_patient_conditioning_safety_gate(
            raw,
            reviewed_bone_gate=reviewed_gate,
            physician_reviewed_bone_gate=physician_reviewed,
            clinical_context_verified=trusted_context,
            target_domain=target_domain_input_verified and not runtime.proxy_checkpoint,
            model_promotion_ready=runtime.runtime_replacement_allowed,
            uncertainty_threshold=uncertainty_threshold,
            segmentation_threshold=segmentation_threshold,
        )

    failure_reasons = list(
        dict.fromkeys(
            [
                *context_reasons,
                *gate_reasons,
                *list(safe["failure_reasons"]),
                *([] if target_domain_input_verified else ["target_domain_input_not_verified"]),
            ]
        )
    )
    image_only_probability = _single_array(safe["image_only_probability"])
    conditioned_probability = _single_array(safe["conditioned_probability"])
    delta_map = _single_array(safe["delta_map"])
    uncertainty = _single_array(safe["uncertainty"])
    difference_mask: np.ndarray = _single_array(safe["difference_mask"]).astype(np.bool_)
    spatial_effect_mask: np.ndarray = _single_array(safe["spatial_effect_mask"]).astype(np.bool_)
    if runtime.proxy_checkpoint:
        conditioned_probability = image_only_probability.copy()
        delta_map = np.zeros_like(delta_map)
        difference_mask = np.zeros_like(difference_mask)
        spatial_effect_mask = np.zeros_like(spatial_effect_mask)
        if "non_target_domain_proxy" not in failure_reasons:
            failure_reasons.append("non_target_domain_proxy")

    assets = _write_prediction_assets(
        output_dir=output_dir,
        case_id=case_id,
        image_only_probability=image_only_probability,
        conditioned_probability=conditioned_probability,
        delta_map=delta_map,
        uncertainty=uncertainty,
        difference_mask=difference_mask,
        spatial_effect_mask=spatial_effect_mask,
        threshold=segmentation_threshold,
    )
    image_only_mask = image_only_probability >= segmentation_threshold
    conditioned_mask = conditioned_probability >= segmentation_threshold
    positive_area_px = int(conditioned_mask.sum())
    spatial_effect_applied = bool(np.any(np.abs(delta_map) > 0.0))
    context_eligible = bool(raw.context_eligible.detach().cpu().reshape(-1)[0].item())
    runtime_feature_vector = attach_runtime_consumption(
        clinical_feature_vector,
        checkpoint_sha256=runtime.checkpoint_sha256,
        context_eligible=context_eligible,
        spatial_effect_applied=spatial_effect_applied,
    )
    available = bool(np.isfinite(image_only_probability).all())
    payload = {
        "schema_version": "osteo-vision-patient-conditioned-runtime-v1",
        "available": available,
        "adapter_mode": "patient_conditioned_segmentation",
        "spatial_effect_applied": spatial_effect_applied,
        "safe_fallback_applied": not spatial_effect_applied,
        "failure_reasons": failure_reasons,
        "runtime_replacement_allowed": runtime.runtime_replacement_allowed,
        "target_domain_promotion_ready": runtime.target_domain_promotion_ready,
        "proxy_checkpoint": runtime.proxy_checkpoint,
        "image_only_probability_path": assets["image_only_probability_path"],
        "conditioned_probability_path": assets["conditioned_probability_path"],
        "delta_map_path": assets["delta_map_path"],
        "difference_mask_path": assets["difference_mask_path"],
        "spatial_effect_mask_path": assets["spatial_effect_mask_path"],
        "uncertainty_path": assets["uncertainty_path"],
        "image_only_mask_path": assets["image_only_mask_path"],
        "conditioned_mask_path": assets["conditioned_mask_path"],
        "image_only_probability_array_path": assets["image_only_probability_array_path"],
        "conditioned_probability_array_path": assets["conditioned_probability_array_path"],
        "delta_map_array_path": assets["delta_map_array_path"],
        "uncertainty_array_path": assets["uncertainty_array_path"],
        "checkpoint_sha256": runtime.checkpoint_sha256,
        "manifest_sha256": runtime.manifest_sha256,
        "clinical_context_checksum": context_checksum,
        "clinical_context_assessment_checksum": assessment.get("clinical_context_assessment_checksum"),
        "clinical_feature_names": list(runtime.feature_names),
        "clinical_present_fraction": float(clinical_present.float().mean().item()),
        "clinical_feature_vector": runtime_feature_vector,
        "dual_channel_registration_verified": registration_verified,
        "source_inputs": {
            "white_light_path": str(Path(white_path).expanduser().resolve()),
            "white_light_sha256": _sha256_file(Path(white_path).expanduser().resolve()),
            "fluorescence_path": str(Path(fluorescence_path).expanduser().resolve()),
            "fluorescence_sha256": _sha256_file(Path(fluorescence_path).expanduser().resolve()),
            "width": int(rgb.shape[1]),
            "height": int(rgb.shape[0]),
        },
        "reviewed_bone_gate": gate_evidence,
        "threshold": float(segmentation_threshold),
        "uncertainty_threshold": float(uncertainty_threshold),
        "quantification": {
            "positive_area_px": positive_area_px,
            "positive_area_fraction": float(conditioned_mask.mean()),
            "image_only_positive_area_px": int(image_only_mask.sum()),
            "image_only_positive_area_fraction": float(image_only_mask.mean()),
            "difference_area_px": int(difference_mask.sum()),
            "spatial_effect_area_px": int(spatial_effect_mask.sum()),
            "delta_abs_mean": float(np.abs(delta_map).mean()),
            "delta_abs_max": float(np.abs(delta_map).max()),
            "uncertainty_mean": float(uncertainty.mean()),
            "uncertainty_max": float(uncertainty.max()),
            "conditioned_probability_mean": float(conditioned_probability.mean()),
            "conditioned_probability_max": float(conditioned_probability.max()),
        },
        "asset_sha256": assets["asset_sha256"],
        "medical_boundary": runtime.medical_boundary,
    }
    evidence_path = Path(output_dir).expanduser().resolve() / f"{_safe_name(case_id)}_patient_conditioned_evidence.json"
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["evidence_manifest_path"] = str(evidence_path)
    payload["evidence_manifest_sha256"] = _sha256_file(evidence_path)
    return payload


def _validate_checkpoint_metadata(
    metadata: Mapping[str, Any],
    manifest: Mapping[str, Any],
    checkpoint_sha256: str,
    model: TinyPatientConditionedSegmenter2D,
) -> None:
    if metadata.get("capability") != _CAPABILITY:
        raise ValueError("Patient-conditioned checkpoint capability mismatch")
    if metadata.get("model_family") != "patient_conditioned_segmenter":
        raise ValueError("Patient-conditioned checkpoint model_family mismatch")
    for field in (
        "engineering_ready",
        "target_domain_promotion_ready",
        "runtime_allowed",
        "runtime_replacement_allowed",
    ):
        if metadata.get(field) is not manifest.get(field):
            raise ValueError(f"Checkpoint and manifest {field} flags disagree")
    checkpoint_training_domain = _mapping(metadata.get("training_domain"))
    manifest_training_domain = _mapping(manifest.get("training_domain"))
    if checkpoint_training_domain.get("target_domain") is not manifest_training_domain.get("target_domain"):
        raise ValueError("Checkpoint and manifest target-domain flags disagree")
    checkpoint_config = _mapping(metadata.get("model_config"))
    if int(checkpoint_config.get("clinical_feature_count") or 0) != model.clinical_feature_count:
        raise ValueError("Patient-conditioned checkpoint clinical feature count mismatch")
    promotion = _mapping(manifest.get("promotion"))
    promotion_sha = promotion.get("checkpoint_sha256")
    if promotion_sha and _normalized_sha256(promotion_sha) != checkpoint_sha256:
        raise ValueError("Patient-conditioned promotion checkpoint SHA256 mismatch")


def _feature_names(
    manifest: Mapping[str, Any],
    checkpoint_metadata: Mapping[str, Any],
    expected_count: int,
) -> tuple[str, ...]:
    clinical_data = _mapping(manifest.get("clinical_data"))
    source = clinical_data.get("feature_names") or checkpoint_metadata.get("clinical_feature_names")
    if not isinstance(source, list):
        raise ValueError("Patient-conditioned clinical feature names are missing")
    names = tuple(str(value).strip() for value in source)
    checkpoint_names = tuple(str(value).strip() for value in checkpoint_metadata.get("clinical_feature_names") or [])
    if len(names) != expected_count or len(set(names)) != len(names) or any(not value for value in names):
        raise ValueError("Patient-conditioned clinical feature names are invalid")
    unsupported = unsupported_clinical_feature_names(names)
    if unsupported:
        raise ValueError(
            "Patient-conditioned checkpoint declares unsupported clinical features: " + ", ".join(unsupported)
        )
    if checkpoint_names and checkpoint_names != names:
        raise ValueError("Checkpoint and manifest clinical feature names disagree")
    return names


def _validate_clinical_artifact_contracts(
    checkpoint_metadata: Mapping[str, Any],
    manifest: Mapping[str, Any],
    feature_names: Sequence[str],
) -> None:
    checkpoint_clinical_data = _mapping(checkpoint_metadata.get("clinical_data"))
    manifest_clinical_data = _mapping(manifest.get("clinical_data"))
    encoder_contracts = (
        checkpoint_metadata.get("feature_encoder_contract"),
        checkpoint_clinical_data.get("feature_encoder_contract"),
        manifest_clinical_data.get("feature_encoder_contract"),
    )
    source_evidence = (
        checkpoint_clinical_data.get("clinical_feature_source_evidence"),
        manifest_clinical_data.get("clinical_feature_source_evidence"),
    )
    all_encoder_contracts_missing = all(value is None for value in encoder_contracts)
    all_source_evidence_missing = all(value is None for value in source_evidence)
    if all_encoder_contracts_missing and all_source_evidence_missing:
        if not _legacy_proxy_metadata_allowed(checkpoint_metadata, manifest):
            raise ValueError(
                "Patient-conditioned feature encoder contract and clinical feature source evidence are required"
            )
        return
    if any(value is None for value in encoder_contracts):
        raise ValueError("Patient-conditioned feature encoder contract is missing from one or more artifact copies")
    if any(value is None for value in source_evidence):
        raise ValueError("Patient-conditioned clinical feature source evidence is missing from one artifact copy")

    checkpoint_top_contract = _mapping(encoder_contracts[0])
    checkpoint_clinical_contract = _mapping(encoder_contracts[1])
    manifest_contract = _mapping(encoder_contracts[2])
    for location, contract in (
        ("checkpoint top-level", checkpoint_top_contract),
        ("checkpoint clinical_data", checkpoint_clinical_contract),
        ("manifest clinical_data", manifest_contract),
    ):
        issues = validate_clinical_feature_encoder_contract(
            contract,
            expected_feature_names=feature_names,
        )
        if issues:
            raise ValueError(f"Patient-conditioned {location} feature encoder contract invalid: {', '.join(issues)}")
    if checkpoint_top_contract != checkpoint_clinical_contract:
        raise ValueError("Patient-conditioned checkpoint feature encoder contract copies disagree")
    if checkpoint_clinical_contract != manifest_contract:
        raise ValueError("Checkpoint and manifest feature encoder contracts disagree")

    checkpoint_source_evidence = _mapping(source_evidence[0])
    manifest_source_evidence = _mapping(source_evidence[1])
    for location, evidence in (
        ("checkpoint", checkpoint_source_evidence),
        ("manifest", manifest_source_evidence),
    ):
        issues = _clinical_feature_source_evidence_issues(evidence, feature_names)
        if issues:
            raise ValueError(
                f"Patient-conditioned {location} clinical feature source evidence invalid: {', '.join(issues)}"
            )
    if checkpoint_source_evidence != manifest_source_evidence:
        raise ValueError("Checkpoint and manifest clinical feature source evidence disagree")


def _clinical_feature_source_evidence_issues(
    value: Mapping[str, Any],
    feature_names: Sequence[str],
) -> list[str]:
    issues: list[str] = []
    expected_names = list(feature_names)
    if value.get("schema_version") != _CLINICAL_FEATURE_SOURCE_EVIDENCE_SCHEMA:
        issues.append("clinical_feature_source_evidence_schema_incompatible")
    if not _normalized_sha256(value.get("source_manifest_sha256")):
        issues.append("clinical_feature_source_manifest_sha256_invalid")
    if value.get("feature_names") != expected_names:
        issues.append("clinical_feature_source_feature_names_mismatch")
    if value.get("source_fields") != _CLINICAL_FEATURE_SOURCE_FIELDS:
        issues.append("clinical_feature_source_fields_mismatch")

    rows = value.get("feature_sources")
    if not isinstance(rows, list) or len(rows) != len(expected_names):
        issues.append("clinical_feature_source_rows_invalid")
    else:
        for expected_name, row_value in zip(expected_names, rows):
            if not isinstance(row_value, Mapping):
                issues.append("clinical_feature_source_row_invalid")
                continue
            row = dict(row_value)
            if set(row) != _CLINICAL_FEATURE_SOURCE_ROW_FIELDS:
                issues.append("clinical_feature_source_row_fields_invalid")
            if row.get("feature_name") != expected_name:
                issues.append("clinical_feature_source_row_order_mismatch")
            description = str(row.get("source_description") or "").strip()
            if not description:
                issues.append("clinical_feature_source_description_missing")
            elif _normalized_sha256(row.get("source_description_sha256")) != _sha256_text(description):
                issues.append("clinical_feature_source_description_sha256_mismatch")
            present_count = _nonnegative_int(row.get("present_sample_count"))
            missing_count = _nonnegative_int(row.get("missing_sample_count"))
            present_group_count = _nonnegative_int(row.get("present_patient_group_count"))
            if present_count is None or missing_count is None or present_group_count is None:
                issues.append("clinical_feature_source_counts_invalid")
            elif present_count + missing_count == 0:
                issues.append("clinical_feature_source_sample_count_empty")
            elif present_group_count > present_count:
                issues.append("clinical_feature_source_patient_group_count_invalid")

    declared_checksum = _normalized_sha256(value.get("evidence_sha256"))
    checksum_payload = {key: item for key, item in value.items() if key != "evidence_sha256"}
    if not declared_checksum or declared_checksum != _canonical_mapping_sha256(checksum_payload):
        issues.append("clinical_feature_source_evidence_sha256_mismatch")
    return list(dict.fromkeys(issues))


def _legacy_proxy_metadata_allowed(
    checkpoint_metadata: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> bool:
    checkpoint_domain = _mapping(checkpoint_metadata.get("training_domain"))
    manifest_domain = _mapping(manifest.get("training_domain"))
    if checkpoint_domain.get("target_domain") is not False or manifest_domain.get("target_domain") is not False:
        return False
    restricted_flags = (
        "clinical_claim_allowed",
        "target_domain_promotion_ready",
        "runtime_allowed",
        "runtime_replacement_allowed",
    )
    if any(source.get(field) is True for source in (checkpoint_metadata, manifest) for field in restricted_flags):
        return False
    promotion = _mapping(manifest.get("promotion"))
    return not any(
        promotion.get(field) is True for field in ("target_domain_promotion_ready", "runtime_replacement_allowed")
    )


def _load_registered_images(
    white_path: str | Path,
    fluorescence_path: str | Path,
    *,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, np.ndarray]:
    with Image.open(white_path) as white_image:
        rgb = np.asarray(white_image.convert("RGB"), dtype=np.uint8).copy()
    with Image.open(fluorescence_path) as fluorescence_image:
        fluorescence = np.asarray(fluorescence_image.convert("L"), dtype=np.uint8).copy()
    if rgb.shape[:2] != fluorescence.shape:
        raise ValueError("White-light and fluorescence image dimensions must match")
    white_tensor = torch.from_numpy(rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0).to(device)
    fluorescence_tensor = torch.from_numpy(fluorescence[None, None].astype(np.float32) / 255.0).to(device)
    return white_tensor, fluorescence_tensor, rgb


def _clinical_tensors(
    assessment: Mapping[str, Any],
    feature_names: Sequence[str],
    *,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, bool, list[str], str | None, dict[str, Any]]:
    reasons: list[str] = []
    snapshot = _mapping(assessment.get("clinical_context_snapshot"))
    checksum = str(assessment.get("clinical_context_checksum") or "").lower() or None
    expected_checksum = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    quality = _mapping(assessment.get("clinical_context_quality"))
    stored_assessment_checksum = str(assessment.get("clinical_context_assessment_checksum") or "").lower()
    expected_assessment_checksum = compute_clinical_context_assessment_checksum(assessment)
    assessment_integrity_issues: list[str] = []
    if not stored_assessment_checksum:
        assessment_integrity_issues.append("clinical_context_assessment_checksum_missing")
    elif stored_assessment_checksum != expected_assessment_checksum:
        assessment_integrity_issues.append("clinical_context_assessment_checksum_mismatch")
    normalized_labs = [dict(row) for row in assessment.get("normalized_labs") or [] if isinstance(row, Mapping)]
    stored_feature_vector = assessment.get("clinical_feature_vector")
    stored_vector = _mapping(stored_feature_vector)
    stored_feature_names = stored_vector.get("feature_names")
    if isinstance(stored_feature_names, list):
        assessment_feature_names = [str(value).strip() for value in stored_feature_names]
    else:
        assessment_feature_names = list(DEFAULT_CLINICAL_FEATURE_NAMES)
    feature_vector_issues: list[str] = []
    try:
        unsupported_assessment_features = unsupported_clinical_feature_names(assessment_feature_names)
    except ValueError:
        feature_vector_issues.append("clinical_feature_vector_feature_names_invalid")
        assessment_feature_names = list(DEFAULT_CLINICAL_FEATURE_NAMES)
        unsupported_assessment_features = []
    if unsupported_assessment_features:
        feature_vector_issues.append("clinical_feature_vector_features_unsupported")
    rebuilt_assessment_vector = build_clinical_feature_vector(
        snapshot,
        normalized_labs,
        context_checksum=checksum or expected_checksum,
        feature_names=assessment_feature_names,
    )
    feature_vector_issues.extend(
        validate_clinical_feature_vector(
            stored_feature_vector,
            expected_context_checksum=checksum or expected_checksum,
            expected_feature_names=assessment_feature_names,
        )
    )
    if stored_vector.get("vector_checksum") and stored_vector.get("vector_checksum") != rebuilt_assessment_vector.get(
        "vector_checksum"
    ):
        feature_vector_issues.append("clinical_feature_vector_rebuild_mismatch")
    rebuilt_feature_vector = build_clinical_feature_vector(
        snapshot,
        normalized_labs,
        context_checksum=checksum or expected_checksum,
        feature_names=feature_names,
    )
    snapshot_review_verified = snapshot.get("review_status") == "verified"
    verification_issues = (
        clinical_context_verification_issues(snapshot)
        if snapshot_review_verified
        else ["clinical_context_not_verified"]
    )
    verified_quality = bool(
        assessment.get("schema_version") == _ASSESSMENT_SCHEMA
        and checksum == expected_checksum
        and snapshot_review_verified
        and not verification_issues
        and quality.get("review_status") == "verified"
        and quality.get("deidentified") is True
        and quality.get("status") == "ready_for_rule_summary"
        and not list(quality.get("issues") or [])
        and not assessment_integrity_issues
        and not feature_vector_issues
    )
    spatial_conditioning_authorized = assessment.get("spatial_conditioning_authorized") is True
    spatial_use_declared = snapshot.get("clinical_use_boundary") == _RESTRICTED_SPATIAL_USE_BOUNDARY
    context_verified = verified_quality and spatial_conditioning_authorized and spatial_use_declared
    if assessment.get("schema_version") != _ASSESSMENT_SCHEMA:
        reasons.append("clinical_context_schema_invalid")
    if checksum != expected_checksum:
        reasons.append("clinical_context_checksum_mismatch")
    reasons.extend(verification_issues)
    reasons.extend(assessment_integrity_issues)
    reasons.extend(feature_vector_issues)
    if not verified_quality and "clinical_context_not_verified" not in reasons:
        reasons.append("clinical_context_not_verified")
    if not spatial_conditioning_authorized:
        reasons.append("clinical_spatial_conditioning_not_authorized")
    if not spatial_use_declared:
        reasons.append("clinical_use_boundary_disallows_spatial_conditioning")

    values = [float(value) for value in rebuilt_feature_vector["model_input_values"]]
    present = [bool(value) for value in rebuilt_feature_vector["present_mask"]]
    return (
        torch.tensor([values], dtype=torch.float32, device=device),
        torch.tensor([present], dtype=torch.bool, device=device),
        context_verified,
        reasons,
        checksum,
        rebuilt_feature_vector,
    )


def _reviewed_gate(
    value: Any,
    *,
    width: int,
    height: int,
    device: torch.device,
) -> tuple[torch.Tensor | None, bool, list[str], dict[str, Any]]:
    record = _mapping(value)
    path_value = str(record.get("path") or "").strip()
    expected_sha = _normalized_sha256(record.get("sha256"))
    evidence = {
        "path": path_value or None,
        "sha256": expected_sha or None,
        "physician_reviewed": record.get("physician_reviewed") is True,
        "trusted_review": record.get("trusted_review") is True,
        "review_status": record.get("review_status"),
    }
    reasons: list[str] = []
    trusted = bool(
        record.get("physician_reviewed") is True
        and record.get("trusted_review") is True
        and str(record.get("review_status") or "") in _REVIEWED_GATE_STATES
    )
    if not trusted:
        reasons.append("physician_reviewed_bone_gate_untrusted")
    if not path_value or not expected_sha:
        reasons.append("physician_reviewed_bone_gate_evidence_missing")
        return None, False, reasons, evidence
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        reasons.append("physician_reviewed_bone_gate_file_missing")
        return None, False, reasons, evidence
    actual_sha = _sha256_file(path)
    evidence["actual_sha256"] = actual_sha
    if actual_sha != expected_sha:
        reasons.append("physician_reviewed_bone_gate_sha256_mismatch")
        return None, False, reasons, evidence
    try:
        with Image.open(path) as image:
            gate = np.asarray(image.convert("L"), dtype=np.uint8).copy()
    except (OSError, ValueError) as exc:
        reasons.append("physician_reviewed_bone_gate_unreadable")
        evidence["read_error"] = str(exc)
        return None, False, reasons, evidence
    if gate.shape != (height, width):
        reasons.append("physician_reviewed_bone_gate_dimension_mismatch")
        return None, False, reasons, evidence
    tensor = torch.from_numpy((gate > 127)[None, None]).to(device=device)
    return tensor, trusted, reasons, evidence


def _write_prediction_assets(
    *,
    output_dir: str | Path,
    case_id: str,
    image_only_probability: np.ndarray,
    conditioned_probability: np.ndarray,
    delta_map: np.ndarray,
    uncertainty: np.ndarray,
    difference_mask: np.ndarray,
    spatial_effect_mask: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    out_dir = ensure_dir(Path(output_dir).expanduser().resolve())
    prefix = out_dir / f"{_safe_name(case_id)}_patient_conditioned"
    paths = {
        "image_only_probability_path": Path(f"{prefix}_image_only_probability.png"),
        "conditioned_probability_path": Path(f"{prefix}_conditioned_probability.png"),
        "delta_map_path": Path(f"{prefix}_delta_map.png"),
        "difference_mask_path": Path(f"{prefix}_difference_mask.png"),
        "spatial_effect_mask_path": Path(f"{prefix}_spatial_effect_mask.png"),
        "uncertainty_path": Path(f"{prefix}_uncertainty.png"),
        "image_only_mask_path": Path(f"{prefix}_image_only_mask.png"),
        "conditioned_mask_path": Path(f"{prefix}_conditioned_mask.png"),
        "image_only_probability_array_path": Path(f"{prefix}_image_only_probability.npy"),
        "conditioned_probability_array_path": Path(f"{prefix}_conditioned_probability.npy"),
        "delta_map_array_path": Path(f"{prefix}_delta_map.npy"),
        "uncertainty_array_path": Path(f"{prefix}_uncertainty.npy"),
    }
    Image.fromarray(_unit_preview(image_only_probability)).save(paths["image_only_probability_path"])
    Image.fromarray(_unit_preview(conditioned_probability)).save(paths["conditioned_probability_path"])
    max_abs_delta = max(float(np.abs(delta_map).max()), 1e-8)
    delta_preview = np.clip((delta_map / (2.0 * max_abs_delta) + 0.5) * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(delta_preview).save(paths["delta_map_path"])
    Image.fromarray(difference_mask.astype(np.uint8) * 255).save(paths["difference_mask_path"])
    Image.fromarray(spatial_effect_mask.astype(np.uint8) * 255).save(paths["spatial_effect_mask_path"])
    Image.fromarray(_unit_preview(uncertainty)).save(paths["uncertainty_path"])
    Image.fromarray((image_only_probability >= threshold).astype(np.uint8) * 255).save(paths["image_only_mask_path"])
    Image.fromarray((conditioned_probability >= threshold).astype(np.uint8) * 255).save(paths["conditioned_mask_path"])
    np.save(paths["image_only_probability_array_path"], image_only_probability.astype(np.float32))
    np.save(paths["conditioned_probability_array_path"], conditioned_probability.astype(np.float32))
    np.save(paths["delta_map_array_path"], delta_map.astype(np.float32))
    np.save(paths["uncertainty_array_path"], uncertainty.astype(np.float32))
    serialized_paths: dict[str, Any] = {name: str(path) for name, path in paths.items()}
    serialized_paths["asset_sha256"] = {name: _sha256_file(path) for name, path in paths.items()}
    return serialized_paths


def _single_array(value: torch.Tensor) -> np.ndarray:
    return value.detach().to(device="cpu", dtype=torch.float32).numpy()[0, 0].copy()


def _unit_preview(value: np.ndarray) -> np.ndarray:
    return np.clip(value * 255.0, 0.0, 255.0).astype(np.uint8)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalized_sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if len(text) == 64 and all(character in "0123456789abcdef" for character in text) else ""


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_mapping_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    result = "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
    return result or "case"
