from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

from src.datasets.registry import sha256_file

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
KEYFRAME_ROLE = "training_keyframe::fluorescence_hotspot"
MANUAL_ANNOTATION_ROLE = "training_keyframe::manual_physician_annotation"
MANUAL_ANNOTATION_SCHEMA = "osteo-vision-manual-annotation-training-manifest-v2"
TRUSTED_PHYSICIAN_AUTH_SOURCES = {
    "institution_sso",
    "signed_session",
    "verified_identity_token",
}
TRAINING_INTAKE_ADMISSION_STATES = {"engineering_analysis_ready", "target_registry_ready"}
TRAINING_SCOPE_TOKENS = {"train", "training"}
TRAINING_SCOPE_DENY_MARKERS = {
    "analysis only",
    "competition only",
    "exclude training",
    "no training",
    "not for training",
    "training denied",
    "training prohibited",
    "validation only",
    "without training",
}
TRAINING_SCOPE_DENY_TOKENS = {
    "deny",
    "denied",
    "disallow",
    "disallowed",
    "exclude",
    "excluded",
    "false",
    "no",
    "non",
    "not",
    "prohibit",
    "prohibited",
    "without",
}
MANUAL_ANNOTATION_MASK_TYPES = {
    "lesion",
    "exposed_bone",
    "fluorescence_signal",
    "boundary_risk",
    "uncertain",
    "low_activity",
    "transition",
    "high_activity",
    "ignore",
}
DEFAULT_TASK_BY_MANUAL_MASK_TYPE = {
    "lesion": "lesion_segmentation",
    "exposed_bone": "bone_gate_segmentation",
    "fluorescence_signal": "video_signal_segmentation",
    "boundary_risk": "boundary_risk_segmentation",
    "uncertain": "uncertainty_segmentation",
    "low_activity": "bone_activity_segmentation",
    "transition": "bone_activity_segmentation",
    "high_activity": "bone_activity_segmentation",
    "ignore": "bone_activity_segmentation",
}
MANUAL_ANNOTATION_TRAINING_FIELDS = [
    "case_id",
    "record_id",
    "sample_id",
    "image_path",
    "mask_path",
    "split",
    "group_id",
    "source_group_id",
    "source_type",
    "source_id",
    "source_url",
    "source_record_id",
    "source_input_id",
    "source_run_id",
    "source_frame_index",
    "source_timestamp_sec",
    "source_candidate_id",
    "source_video_path",
    "intake_authorization_status",
    "intake_usage_scope",
    "intake_deidentification_confirmed",
    "intake_mapping_held_by_institution",
    "intake_admission_status",
    "source_input_admission_status",
    "source_input_batch_id",
    "source_input_record_id",
    "source_input_checksum",
    "source_input_checksum_verified",
    "label_source",
    "label_type",
    "mask_type",
    "target_mask_type",
    "target_task",
    "input_domain",
    "domain_tier",
    "target_domain_flag",
    "license",
    "usage_policy",
    "sampling_weight",
    "sample_weight",
    "checksum",
    "image_checksum",
    "source_checksum",
    "label_checksum",
    "mask_checksum",
    "review_manifest_path",
    "review_manifest_checksum",
    "review_state",
    "annotation_id",
    "annotation_version",
    "source_snapshot_path",
    "actor_id",
    "actor_role",
    "institution",
    "auth_source",
    "submitted_by_actor_id",
    "submitted_by_role",
    "submitted_by_institution",
    "submitted_by_auth_source",
    "reviewer_actor_id",
    "reviewer_role",
    "reviewer_institution",
    "reviewer_auth_source",
    "reviewed_at",
    "original_width",
    "original_height",
    "positive_pixel_count",
    "positive_area_fraction",
    "training_eligible",
    "artifact_role",
    "medical_scene",
    "medical_boundary",
]
ALLOWED_LABEL_TYPES = {
    "proxy_mask",
    "prompt_assisted_mask",
    "human_reviewed_mask",
    "physician_mask",
    "segmentation_mask",
}
ALLOWED_REVIEW_STATES = {"review_required", "accepted", "modified"}
ADMISSION_STAGES = {
    "proxy_pretrain",
    "reviewed_finetune",
    "independent_evaluation",
}
BLOCKED_USAGE_POLICY_MARKERS = ("reference_only", "no_derivatives", "no_derivative", "display_only", "no_training")
OPEN_LICENSE_MARKERS = (
    "cc0",
    "cc by",
    "cc-by",
    "public domain",
    "mit",
    "apache",
    "bsd",
    "permission granted",
    "authorized",
    "approved for training",
)
BLOCKED_LICENSE_MARKERS = (
    "cc by-nc-nd",
    "cc-by-nc-nd",
    "no derivatives",
    "no-derivatives",
    "all rights reserved",
    "training prohibited",
)


class TrainingAdmissionError(ValueError):
    """Raised when registry-level evidence cannot support a training run."""


@dataclass(frozen=True)
class TrainingAdmissionResult:
    rows: list[dict[str, str]]
    summary: dict[str, Any]


def admit_keyframe_training_rows(
    registry_path: str | Path,
    quality_report_path: str | Path,
    *,
    artifact_role: str = KEYFRAME_ROLE,
    verify_checksums: bool = True,
    validation_fraction: float = 0.2,
    split_seed: int = 20260711,
    admission_stage: str = "proxy_pretrain",
) -> TrainingAdmissionResult:
    registry = Path(registry_path).resolve()
    quality_path = Path(quality_report_path).resolve()
    raw_rows = _read_csv(registry)
    quality = _load_quality_report(quality_path)
    registry_sha256 = sha256_file(registry)
    quality_sha256 = sha256_file(quality_path)
    stage = _normalized_token(admission_stage)
    if stage not in ADMISSION_STAGES:
        raise TrainingAdmissionError(f"admission_stage must be one of: {', '.join(sorted(ADMISSION_STAGES))}")
    _validate_quality_gate(
        quality,
        registry_path=registry,
        registry_sha256=registry_sha256,
        record_count=len(raw_rows),
    )

    source_by_key: dict[str, dict[str, str]] = {}
    for row in raw_rows:
        if str(row.get("artifact_role") or "") not in {"source_video", "source_article_figure"}:
            continue
        for value in (row.get("local_path"), row.get("group_id"), row.get("source_id"), row.get("record_id")):
            key = _normalized_path(value)
            if key:
                source_by_key[key] = row
    admitted: list[dict[str, str]] = []
    quarantine: list[dict[str, Any]] = []
    candidate_count = 0
    for row in raw_rows:
        if str(row.get("artifact_role") or "") != artifact_role:
            continue
        candidate_count += 1
        source_record = next(
            (
                source_by_key[key]
                for key in (_normalized_path(row.get("source_id")), _normalized_path(row.get("group_id")))
                if key in source_by_key
            ),
            None,
        )
        reasons = _admission_reasons(
            row,
            source_record=source_record,
            verify_checksums=verify_checksums,
            admission_stage=stage,
        )
        if reasons:
            quarantine.append(
                {
                    "record_id": str(row.get("record_id") or ""),
                    "codes": [code for code, _message in reasons],
                    "messages": [message for _code, message in reasons],
                }
            )
            continue
        admitted.append(_training_row(row, source_record=source_record))

    if not admitted:
        reason_counts = Counter(code for item in quarantine for code in item["codes"])
        raise TrainingAdmissionError(
            f"No keyframe rows passed training admission for role={artifact_role}; reasons={dict(reason_counts)}"
        )

    if stage == "independent_evaluation":
        split_summary = _validate_independent_evaluation_split(admitted)
    else:
        split_summary = _ensure_grouped_train_val_split(
            admitted,
            validation_fraction=validation_fraction,
            split_seed=split_seed,
        )
    _assert_group_split_integrity(admitted)
    isolation_reason_counts = Counter(code for item in quarantine for code in item["codes"])
    summary: dict[str, Any] = {
        "schema_version": "osteo-vision-training-admission-v1",
        "registry_path": str(registry),
        "registry_sha256": registry_sha256,
        "quality_report_path": str(quality_path),
        "quality_report_sha256": quality_sha256,
        "quality_gate_passed": True,
        "quality_schema_version": str(quality.get("schema_version") or ""),
        "registry_record_count": len(raw_rows),
        "candidate_count": candidate_count,
        "admitted_count": len(admitted),
        "isolated_count": len(quarantine),
        "isolation_reason_counts": dict(sorted(isolation_reason_counts.items())),
        "isolation_records": quarantine,
        "artifact_role": artifact_role,
        "admission_stage": stage,
        "split_policy": split_summary,
        "split_counts": dict(sorted(Counter(row["split"] for row in admitted).items())),
        "source_group_count": len({row["source_group_id"] for row in admitted}),
        "domain_tier_counts": dict(sorted(Counter(row["domain_tier"] for row in admitted).items())),
        "review_state_counts": dict(sorted(Counter(row["review_state"] for row in admitted).items())),
        "usage_policy_counts": dict(sorted(Counter(row["usage_policy"] for row in admitted).items())),
        "data_boundary": (
            "Admitted rows retain registry provenance and non-target-domain boundaries; admission does not create "
            "clinical ground truth."
        ),
    }
    return TrainingAdmissionResult(rows=admitted, summary=summary)


def admit_manual_annotation_training_rows(
    manifest_path: str | Path,
    *,
    verify_checksums: bool = True,
    validation_fraction: float = 0.2,
    split_seed: int = 20260715,
    target_mask_type: str = "lesion",
    target_task: str | None = None,
) -> TrainingAdmissionResult:
    """Admit trusted physician masks from a manual-annotation export for fine-tuning."""
    manifest = Path(manifest_path).resolve()
    payload = _load_manual_annotation_manifest(manifest)
    records = payload.get("records")
    if not isinstance(records, list):
        raise TrainingAdmissionError("Manual annotation manifest records must be a JSON array")

    declared_eligible = payload.get("eligible_count")
    explicit_eligible = sum(
        1 for row in records if isinstance(row, dict) and _explicit_true(row.get("training_eligible"))
    )
    if declared_eligible is not None and int(declared_eligible) != explicit_eligible:
        raise TrainingAdmissionError(
            "Manual annotation manifest eligible_count does not match its records: "
            f"declared={declared_eligible}, records={explicit_eligible}"
        )

    admitted: list[dict[str, str]] = []
    quarantine: list[dict[str, Any]] = []
    seen_samples: set[str] = set()
    manifest_checksum = sha256_file(manifest)
    selected_mask_type = _normalized_token(target_mask_type)
    if selected_mask_type not in MANUAL_ANNOTATION_MASK_TYPES:
        raise TrainingAdmissionError(
            "target_mask_type must be one of: " f"{', '.join(sorted(MANUAL_ANNOTATION_MASK_TYPES))}"
        )
    selected_task = _manual_target_task(selected_mask_type, target_task)
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            quarantine.append(
                {
                    "record_id": f"row-{index}",
                    "codes": ["invalid_record"],
                    "messages": ["manual annotation record must be a JSON object"],
                    "record": raw_record,
                }
            )
            continue
        record = {str(key): value for key, value in raw_record.items()}
        record_id = str(record.get("record_id") or record.get("annotation_id") or f"row-{index}")
        reasons = _manual_annotation_admission_reasons(
            record,
            manifest_dir=manifest.parent,
            verify_checksums=verify_checksums,
            target_mask_type=selected_mask_type,
        )
        sample_id = _manual_sample_id(record)
        if sample_id in seen_samples:
            reasons.append(("duplicate_annotation_version", sample_id))
        if reasons:
            quarantine.append(
                {
                    "record_id": record_id,
                    "annotation_id": str(record.get("annotation_id") or ""),
                    "annotation_version": str(record.get("annotation_version") or ""),
                    "codes": [code for code, _message in reasons],
                    "messages": [message for _code, message in reasons],
                    "record": record,
                }
            )
            continue
        seen_samples.add(sample_id)
        admitted.append(
            _manual_annotation_training_row(
                record,
                manifest_path=manifest,
                manifest_checksum=manifest_checksum,
                target_mask_type=selected_mask_type,
                target_task=selected_task,
            )
        )

    if not admitted:
        reason_counts = Counter(code for item in quarantine for code in item["codes"])
        raise TrainingAdmissionError(
            "No manual annotation rows passed reviewed fine-tuning admission; " f"reasons={dict(reason_counts)}"
        )

    group_count = len({row["source_group_id"] for row in admitted})
    if group_count == 1:
        for row in admitted:
            row["split"] = "train"
        split_summary: dict[str, Any] = {
            "name": "single_group_train_only",
            "seed": None,
            "validation_fraction": None,
            "reassigned_group_count": 0,
            "warning": "A separate source group is required for validation.",
        }
    else:
        split_summary = _ensure_grouped_train_val_split(
            admitted,
            validation_fraction=validation_fraction,
            split_seed=split_seed,
        )
    _assert_group_split_integrity(admitted)

    reason_counts = Counter(code for item in quarantine for code in item["codes"])
    summary: dict[str, Any] = {
        "schema_version": "osteo-vision-manual-annotation-admission-v1",
        "source_schema_version": str(payload.get("schema_version") or ""),
        "source_manifest_path": str(manifest),
        "source_manifest_sha256": manifest_checksum,
        "source_record_count": len(records),
        "admission_stage": "reviewed_finetune",
        "admitted_count": len(admitted),
        "isolated_count": len(quarantine),
        "isolation_reason_counts": dict(sorted(reason_counts.items())),
        "isolation_records": quarantine,
        "artifact_role": MANUAL_ANNOTATION_ROLE,
        "split_policy": split_summary,
        "split_counts": dict(sorted(Counter(row["split"] for row in admitted).items())),
        "source_group_count": group_count,
        "review_state_counts": dict(sorted(Counter(row["review_state"] for row in admitted).items())),
        "target_mask_type": selected_mask_type,
        "target_task": selected_task,
        "mask_type_counts": dict(sorted(Counter(row["mask_type"] for row in admitted).items())),
        "actor_role_counts": dict(sorted(Counter(row["actor_role"] for row in admitted).items())),
        "reviewer_role_counts": dict(sorted(Counter(row["reviewer_role"] for row in admitted).items())),
        "fields": MANUAL_ANNOTATION_TRAINING_FIELDS,
        "data_boundary": (
            "Admitted rows retain physician identity, review, version, checksum, rights, and source provenance. "
            "They remain research-validation labels subject to physician review and data-use authorization."
        ),
    }
    return TrainingAdmissionResult(rows=admitted, summary=summary)


def _load_manual_annotation_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrainingAdmissionError(f"Invalid manual annotation manifest JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise TrainingAdmissionError("Manual annotation manifest must be a JSON object")
    schema = str(payload.get("schema_version") or "")
    if schema != MANUAL_ANNOTATION_SCHEMA:
        raise TrainingAdmissionError(f"Unsupported manual annotation manifest schema: {schema or 'missing'}")
    return payload


def _manual_annotation_admission_reasons(
    row: dict[str, Any],
    *,
    manifest_dir: Path,
    verify_checksums: bool,
    target_mask_type: str,
) -> list[tuple[str, str]]:
    reasons: list[tuple[str, str]] = []
    if not _explicit_true(row.get("training_eligible")):
        reasons.append(("training_ineligible", "training_eligible must be explicitly true"))

    review_state = _normalized_token(row.get("review_state"))
    if review_state == "rejected":
        reasons.append(("rejected_review", "review_state=rejected"))
    elif review_state not in {"accepted", "modified"}:
        reasons.append(("review_not_accepted", f"review_state={review_state or 'missing'}"))
    if _normalized_token(row.get("label_type")) != "physician_mask":
        reasons.append(("invalid_label_type", str(row.get("label_type") or "missing")))
    mask_type = _normalized_token(row.get("mask_type"))
    if mask_type != target_mask_type:
        reasons.append(
            (
                "mask_type_not_selected",
                f"mask_type={mask_type or 'missing'}; target={target_mask_type}",
            )
        )
    if str(row.get("artifact_role") or "") != MANUAL_ANNOTATION_ROLE:
        reasons.append(("invalid_artifact_role", str(row.get("artifact_role") or "missing")))

    if _normalized_token(row.get("intake_authorization_status")) != "approved":
        reasons.append(("case_training_authorization_not_approved", "intake authorization must be approved"))
    if not _explicit_true(row.get("intake_deidentification_confirmed")):
        reasons.append(("case_deidentification_unconfirmed", "case deidentification must be confirmed"))
    if not _explicit_true(row.get("intake_mapping_held_by_institution")):
        reasons.append(("case_mapping_custody_unconfirmed", "institutional mapping custody must be confirmed"))
    if _normalized_token(row.get("intake_admission_status")) not in TRAINING_INTAKE_ADMISSION_STATES:
        reasons.append(("case_intake_not_admitted", str(row.get("intake_admission_status") or "missing")))
    if not _usage_scope_allows_training(row.get("intake_usage_scope")):
        reasons.append(("case_training_usage_not_authorized", str(row.get("intake_usage_scope") or "missing")))
    if _normalized_token(row.get("source_input_admission_status")) != "admitted":
        reasons.append(("source_input_not_admitted", str(row.get("source_input_admission_status") or "missing")))
    if not str(row.get("source_input_batch_id") or "").strip():
        reasons.append(("source_input_batch_id_missing", "source input batch id is required"))
    if not str(row.get("source_input_record_id") or "").strip():
        reasons.append(("source_input_intake_record_id_missing", "source intake record id is required"))
    source_input_checksum = str(row.get("source_input_checksum") or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(source_input_checksum):
        reasons.append(("source_input_checksum_invalid", source_input_checksum or "missing"))
    if not _explicit_true(row.get("source_input_checksum_verified")):
        reasons.append(("source_input_checksum_unverified", "source input checksum verification is required"))

    actor_role = _normalized_token(row.get("actor_role"))
    auth_source = _normalized_token(row.get("auth_source"))
    if actor_role != "physician":
        reasons.append(("untrusted_annotation_actor", f"actor_role={actor_role or 'missing'}"))
    if auth_source not in TRUSTED_PHYSICIAN_AUTH_SOURCES:
        reasons.append(("untrusted_annotation_auth_source", f"auth_source={auth_source or 'missing'}"))
    if not str(row.get("actor_id") or "").strip():
        reasons.append(("missing_annotation_actor", "actor_id is required"))

    submitted_by_actor_id = str(row.get("submitted_by_actor_id") or "").strip()
    submitted_by_role = _normalized_token(row.get("submitted_by_role"))
    submitted_by_auth_source = _normalized_token(row.get("submitted_by_auth_source"))
    if submitted_by_role != "physician":
        reasons.append(("untrusted_submitter_role", f"submitted_by_role={submitted_by_role or 'missing'}"))
    if submitted_by_auth_source not in TRUSTED_PHYSICIAN_AUTH_SOURCES:
        reasons.append(
            (
                "untrusted_submitter_auth_source",
                f"submitted_by_auth_source={submitted_by_auth_source or 'missing'}",
            )
        )

    reviewer_role = _normalized_token(row.get("reviewer_role"))
    reviewer_auth_source = _normalized_token(row.get("reviewer_auth_source"))
    reviewer_actor_id = str(row.get("reviewer_actor_id") or "").strip()
    if not reviewer_actor_id:
        reasons.append(("missing_reviewer", "reviewer_actor_id is required"))
    if reviewer_role != "physician":
        reasons.append(("untrusted_reviewer_role", f"reviewer_role={reviewer_role or 'missing'}"))
    if reviewer_auth_source not in TRUSTED_PHYSICIAN_AUTH_SOURCES:
        reasons.append(
            (
                "untrusted_reviewer_auth_source",
                f"reviewer_auth_source={reviewer_auth_source or 'missing'}",
            )
        )
    if not str(row.get("reviewed_at") or "").strip():
        reasons.append(("missing_review_timestamp", "reviewed_at is required"))
    latest_author_actor_id = str(row.get("actor_id") or "").strip()
    if (
        not submitted_by_actor_id
        or not reviewer_actor_id
        or reviewer_actor_id in {latest_author_actor_id, submitted_by_actor_id}
    ):
        reasons.append(
            (
                "independent_physician_review_required",
                "reviewer_actor_id must differ from actor_id and submitted_by_actor_id",
            )
        )

    annotation_id = str(row.get("annotation_id") or "").strip()
    if not annotation_id:
        reasons.append(("missing_annotation_id", "annotation_id is required"))
    try:
        version = int(row.get("annotation_version") or 0)
    except (TypeError, ValueError):
        version = 0
    if version < 1:
        reasons.append(("invalid_annotation_version", str(row.get("annotation_version") or "missing")))

    reasons.extend(
        _path_alias_reasons(
            row,
            manifest_dir=manifest_dir,
            keys=("source_snapshot_path", "image_path", "local_path"),
            code="source_path_alias_mismatch",
        )
    )
    reasons.extend(
        _path_alias_reasons(
            row,
            manifest_dir=manifest_dir,
            keys=("mask_path", "label_path"),
            code="mask_path_alias_mismatch",
        )
    )
    reasons.extend(
        _checksum_alias_reasons(
            row,
            keys=("source_checksum", "image_checksum", "checksum"),
            code="source_checksum_alias_mismatch",
        )
    )
    reasons.extend(
        _checksum_alias_reasons(
            row,
            keys=("mask_checksum", "label_checksum"),
            code="mask_checksum_alias_mismatch",
        )
    )
    image_path = _manual_record_path(
        row,
        manifest_dir=manifest_dir,
        keys=("source_snapshot_path", "image_path", "local_path"),
    )
    mask_path = _manual_record_path(
        row,
        manifest_dir=manifest_dir,
        keys=("mask_path", "label_path"),
    )
    if image_path is None or not image_path.is_file():
        reasons.append(("missing_source_snapshot", str(image_path or "missing")))
    if mask_path is None or not mask_path.is_file():
        reasons.append(("missing_mask", str(mask_path or "missing")))

    source_checksum = _manual_record_checksum(
        row,
        keys=("source_checksum", "image_checksum", "checksum"),
    )
    mask_checksum = _manual_record_checksum(
        row,
        keys=("mask_checksum", "label_checksum"),
    )
    if not SHA256_PATTERN.fullmatch(source_checksum):
        reasons.append(("invalid_source_checksum", source_checksum or "missing"))
    elif verify_checksums and image_path is not None and image_path.is_file():
        if sha256_file(image_path) != source_checksum:
            reasons.append(("source_checksum_mismatch", str(image_path)))
    if not SHA256_PATTERN.fullmatch(mask_checksum):
        reasons.append(("invalid_mask_checksum", mask_checksum or "missing"))
    elif verify_checksums and mask_path is not None and mask_path.is_file():
        if sha256_file(mask_path) != mask_checksum:
            reasons.append(("mask_checksum_mismatch", str(mask_path)))

    if image_path is not None and image_path.is_file() and mask_path is not None and mask_path.is_file():
        reasons.extend(_mask_quality_reasons(image_path, mask_path, require_size_match=True))
        reasons.extend(_reported_dimension_reasons(row, image_path=image_path))

    if _positive_float(row.get("sample_weight")) is None:
        reasons.append(("invalid_sample_weight", str(row.get("sample_weight") or "missing")))
    if _positive_float(row.get("sampling_weight") or row.get("sample_weight")) is None:
        reasons.append(("invalid_sampling_weight", str(row.get("sampling_weight") or "missing")))
    if not str(row.get("case_id") or row.get("group_id") or "").strip():
        reasons.append(("missing_source_group", "case_id or group_id is required"))
    if not str(row.get("source_id") or "").strip():
        reasons.append(("missing_source_id", "source_id is required"))
    if not str(row.get("source_type") or "").strip():
        reasons.append(("missing_source_type", "source_type is required"))
    if not str(row.get("medical_boundary") or "").strip():
        reasons.append(("missing_medical_boundary", "medical_boundary is required"))
    if not _license_allows_training(row, source_record=None):
        reasons.append(("training_rights_not_verified", _effective_license(row, source_record=None)))
    return reasons


def _manual_annotation_training_row(
    row: dict[str, Any],
    *,
    manifest_path: Path,
    manifest_checksum: str,
    target_mask_type: str,
    target_task: str,
) -> dict[str, str]:
    image_path = _manual_record_path(
        row,
        manifest_dir=manifest_path.parent,
        keys=("source_snapshot_path", "image_path", "local_path"),
    )
    mask_path = _manual_record_path(
        row,
        manifest_dir=manifest_path.parent,
        keys=("mask_path", "label_path"),
    )
    if image_path is None or mask_path is None:
        raise TrainingAdmissionError("Admitted manual annotation row lost its source or mask path")
    source_checksum = _manual_record_checksum(
        row,
        keys=("source_checksum", "image_checksum", "checksum"),
    )
    mask_checksum = _manual_record_checksum(row, keys=("mask_checksum", "label_checksum"))
    group_id = str(row.get("group_id") or row.get("case_id") or "").strip()
    sample_weight = str(float(row.get("sample_weight") or 0.0))
    sampling_weight = str(float(row.get("sampling_weight") or row.get("sample_weight") or 0.0))
    sample_id = _manual_sample_id(row)
    return {
        "case_id": str(row.get("case_id") or ""),
        "record_id": str(row.get("record_id") or sample_id),
        "sample_id": sample_id,
        "image_path": str(image_path),
        "mask_path": str(mask_path),
        "split": "train",
        "group_id": group_id,
        "source_group_id": group_id,
        "source_type": str(row.get("source_type") or "manual_annotation"),
        "source_id": str(row.get("source_id") or ""),
        "source_url": str(row.get("source_url") or ""),
        "source_record_id": str(row.get("source_id") or row.get("record_id") or ""),
        "source_input_id": str(row.get("source_input_id") or ""),
        "source_run_id": str(row.get("source_run_id") or ""),
        "source_frame_index": str(row.get("source_frame_index") if row.get("source_frame_index") is not None else ""),
        "source_timestamp_sec": str(
            row.get("source_timestamp_sec") if row.get("source_timestamp_sec") is not None else ""
        ),
        "source_candidate_id": str(row.get("source_candidate_id") or ""),
        "source_video_path": str(row.get("source_video_path") or ""),
        "intake_authorization_status": str(row.get("intake_authorization_status") or ""),
        "intake_usage_scope": str(row.get("intake_usage_scope") or ""),
        "intake_deidentification_confirmed": (
            "true" if _explicit_true(row.get("intake_deidentification_confirmed")) else "false"
        ),
        "intake_mapping_held_by_institution": (
            "true" if _explicit_true(row.get("intake_mapping_held_by_institution")) else "false"
        ),
        "intake_admission_status": str(row.get("intake_admission_status") or ""),
        "source_input_admission_status": str(row.get("source_input_admission_status") or ""),
        "source_input_batch_id": str(row.get("source_input_batch_id") or ""),
        "source_input_record_id": str(row.get("source_input_record_id") or ""),
        "source_input_checksum": str(row.get("source_input_checksum") or ""),
        "source_input_checksum_verified": (
            "true" if _explicit_true(row.get("source_input_checksum_verified")) else "false"
        ),
        "label_source": "physician_manual_annotation",
        "label_type": "physician_mask",
        "mask_type": str(row.get("mask_type") or "lesion"),
        "target_mask_type": target_mask_type,
        "target_task": target_task,
        "input_domain": str(row.get("input_domain") or "physician_reviewed_case_annotation"),
        "domain_tier": _manual_domain_tier(row),
        "target_domain_flag": "true" if _explicit_true(row.get("target_domain_flag")) else "false",
        "license": str(row.get("license") or ""),
        "usage_policy": _normalized_token(row.get("usage_policy")),
        "sampling_weight": sampling_weight,
        "sample_weight": sample_weight,
        "checksum": source_checksum,
        "image_checksum": source_checksum,
        "source_checksum": source_checksum,
        "label_checksum": mask_checksum,
        "mask_checksum": mask_checksum,
        "review_manifest_path": str(manifest_path),
        "review_manifest_checksum": manifest_checksum,
        "review_state": "accepted",
        "annotation_id": str(row.get("annotation_id") or ""),
        "annotation_version": str(row.get("annotation_version") or ""),
        "source_snapshot_path": str(image_path),
        "actor_id": str(row.get("actor_id") or ""),
        "actor_role": _normalized_token(row.get("actor_role")),
        "institution": str(row.get("institution") or ""),
        "auth_source": _normalized_token(row.get("auth_source")),
        "submitted_by_actor_id": str(row.get("submitted_by_actor_id") or ""),
        "submitted_by_role": _normalized_token(row.get("submitted_by_role")),
        "submitted_by_institution": str(row.get("submitted_by_institution") or ""),
        "submitted_by_auth_source": _normalized_token(row.get("submitted_by_auth_source")),
        "reviewer_actor_id": str(row.get("reviewer_actor_id") or ""),
        "reviewer_role": _normalized_token(row.get("reviewer_role")),
        "reviewer_institution": str(row.get("reviewer_institution") or ""),
        "reviewer_auth_source": _normalized_token(row.get("reviewer_auth_source")),
        "reviewed_at": str(row.get("reviewed_at") or ""),
        "original_width": str(row.get("original_width") or ""),
        "original_height": str(row.get("original_height") or ""),
        "positive_pixel_count": str(row.get("positive_pixel_count") or ""),
        "positive_area_fraction": str(row.get("positive_area_fraction") or ""),
        "training_eligible": "true",
        "artifact_role": MANUAL_ANNOTATION_ROLE,
        "medical_scene": str(row.get("medical_scene") or ""),
        "medical_boundary": str(row.get("medical_boundary") or ""),
    }


def _manual_record_path(
    row: dict[str, Any],
    *,
    manifest_dir: Path,
    keys: tuple[str, ...],
) -> Path | None:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = manifest_dir / path
        return path.resolve()
    return None


def _manual_record_checksum(row: dict[str, Any], *, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _path_alias_reasons(
    row: dict[str, Any],
    *,
    manifest_dir: Path,
    keys: tuple[str, ...],
    code: str,
) -> list[tuple[str, str]]:
    values: dict[str, str] = {}
    for key in keys:
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = manifest_dir / path
        values[key] = str(path.resolve()).replace("\\", "/").casefold()
    if len(set(values.values())) > 1:
        return [(code, json.dumps(values, ensure_ascii=False, sort_keys=True))]
    return []


def _checksum_alias_reasons(
    row: dict[str, Any],
    *,
    keys: tuple[str, ...],
    code: str,
) -> list[tuple[str, str]]:
    values = {key: str(row.get(key) or "").strip().lower() for key in keys if str(row.get(key) or "").strip()}
    if len(set(values.values())) > 1:
        return [(code, json.dumps(values, ensure_ascii=False, sort_keys=True))]
    return []


def _manual_sample_id(row: dict[str, Any]) -> str:
    annotation_id = str(row.get("annotation_id") or row.get("record_id") or "annotation").strip()
    version = str(row.get("annotation_version") or "0").strip()
    return f"manual_{annotation_id}_v{version}"


def _manual_domain_tier(row: dict[str, Any]) -> str:
    value = _normalized_token(row.get("domain_tier"))
    if _explicit_true(row.get("target_domain_flag")) and value in {"target", "target_domain"}:
        return "target_domain"
    if value in {"near_domain", "fluorescence_proxy", "derived_proxy"}:
        return value
    return "derived_proxy"


def _manual_target_task(mask_type: str, requested_task: str | None) -> str:
    task = _normalized_token(requested_task)
    if task:
        return task
    return DEFAULT_TASK_BY_MANUAL_MASK_TYPE[mask_type]


def _reported_dimension_reasons(
    row: dict[str, Any],
    *,
    image_path: Path,
) -> list[tuple[str, str]]:
    try:
        expected_width = int(row.get("original_width") or 0)
        expected_height = int(row.get("original_height") or 0)
    except (TypeError, ValueError):
        return [("invalid_reported_dimensions", "original_width/original_height must be integers")]
    if expected_width < 1 or expected_height < 1:
        return [("invalid_reported_dimensions", f"reported={expected_width}x{expected_height}")]
    try:
        with Image.open(image_path) as image:
            actual = (int(image.width), int(image.height))
    except OSError as exc:
        return [("source_dimension_read_failure", str(exc))]
    expected = (expected_width, expected_height)
    if actual != expected:
        return [("reported_dimension_mismatch", f"reported={expected}, actual={actual}")]
    return []


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]


def _load_quality_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrainingAdmissionError(f"Invalid dataset quality report JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise TrainingAdmissionError(f"Dataset quality report must be a JSON object: {path}")
    return payload


def _validate_quality_gate(
    quality: dict[str, Any],
    *,
    registry_path: Path,
    registry_sha256: str,
    record_count: int,
) -> None:
    if quality.get("passed") is not True or int(quality.get("error_count") or 0) != 0:
        raise TrainingAdmissionError(
            f"Dataset quality gate did not pass: passed={quality.get('passed')}, "
            f"error_count={quality.get('error_count')}"
        )
    expected_count = quality.get("record_count")
    if expected_count is None or int(expected_count) != record_count:
        raise TrainingAdmissionError(
            f"Quality report record_count does not match registry: report={expected_count}, registry={record_count}"
        )
    reported_path = str(quality.get("registry_path") or "").strip()
    if reported_path and Path(reported_path).resolve() != registry_path:
        raise TrainingAdmissionError(
            f"Quality report references another registry: report={reported_path}, requested={registry_path}"
        )
    reported_sha = str(quality.get("registry_sha256") or "").strip().lower()
    if reported_sha and reported_sha != registry_sha256:
        raise TrainingAdmissionError(
            f"Quality report registry SHA256 mismatch: report={reported_sha}, actual={registry_sha256}"
        )


def _admission_reasons(
    row: dict[str, str],
    *,
    source_record: dict[str, str] | None,
    verify_checksums: bool,
    admission_stage: str,
) -> list[tuple[str, str]]:
    reasons: list[tuple[str, str]] = []
    if not _explicit_true(row.get("training_eligible")):
        reasons.append(("training_ineligible", "training_eligible must be explicitly true"))
    usage_policy = _normalized_token(row.get("usage_policy"))
    if _usage_policy_blocked(usage_policy):
        reasons.append(("blocked_usage_policy", f"usage_policy={usage_policy}"))
    review_state = _normalized_token(row.get("review_state"))
    if review_state == "rejected":
        reasons.append(("rejected_review", "review_state=rejected"))
    elif review_state not in ALLOWED_REVIEW_STATES:
        reasons.append(("invalid_review_state", f"review_state={review_state or 'missing'}"))
    label_type = _normalized_token(row.get("label_type"))
    if label_type not in ALLOWED_LABEL_TYPES:
        reasons.append(("invalid_label_type", f"label_type={label_type or 'missing'}"))

    image_path = Path(str(row.get("local_path") or ""))
    label_path = Path(str(row.get("label_path") or ""))
    if not image_path.is_file():
        reasons.append(("missing_image", str(image_path)))
    if not label_path.is_file():
        reasons.append(("missing_label", str(label_path)))
    elif not _valid_image_file(label_path):
        reasons.append(("invalid_label_file", str(label_path)))
    elif image_path.is_file():
        reasons.extend(
            _mask_quality_reasons(
                image_path,
                label_path,
                require_size_match=label_type != "proxy_mask",
            )
        )

    checksum = str(row.get("checksum") or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(checksum):
        reasons.append(("invalid_checksum", checksum or "missing"))
    elif verify_checksums and image_path.is_file() and sha256_file(image_path) != checksum:
        reasons.append(("checksum_mismatch", str(image_path)))
    label_checksum = str(row.get("label_checksum") or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(label_checksum):
        reasons.append(("invalid_label_checksum", label_checksum or "missing"))
    elif verify_checksums and label_path.is_file() and sha256_file(label_path) != label_checksum:
        reasons.append(("label_checksum_mismatch", str(label_path)))

    sample_weight = _positive_float(row.get("sample_weight"))
    if sample_weight is None:
        reasons.append(("invalid_sample_weight", str(row.get("sample_weight") or "missing")))
    sampling_weight = _positive_float(row.get("sampling_weight") or row.get("sample_weight"))
    if sampling_weight is None:
        reasons.append(("invalid_sampling_weight", str(row.get("sampling_weight") or "missing")))
    if not str(row.get("group_id") or "").strip():
        reasons.append(("missing_source_group", "group_id is required"))
    if not str(row.get("medical_boundary") or "").strip():
        reasons.append(("missing_medical_boundary", "medical_boundary is required"))
    if not _license_allows_training(row, source_record=source_record):
        reasons.append(("license_not_training_approved", _effective_license(row, source_record=source_record)))
    reasons.extend(_admission_stage_reasons(row, admission_stage=admission_stage))
    return reasons


def _admission_stage_reasons(row: dict[str, str], *, admission_stage: str) -> list[tuple[str, str]]:
    if admission_stage == "proxy_pretrain":
        return []
    reasons: list[tuple[str, str]] = []
    review_state = _normalized_token(row.get("review_state"))
    label_type = _normalized_token(row.get("label_type"))
    if review_state not in {"accepted", "modified"}:
        reasons.append(
            (
                "stage_requires_reviewed_label",
                f"stage={admission_stage}; review_state={review_state or 'missing'}",
            )
        )
    if label_type not in {
        "prompt_assisted_mask",
        "human_reviewed_mask",
        "physician_mask",
        "segmentation_mask",
    }:
        reasons.append(
            (
                "stage_rejects_proxy_label",
                f"stage={admission_stage}; label_type={label_type or 'missing'}",
            )
        )
    if admission_stage == "independent_evaluation":
        usage_policy = _normalized_token(row.get("usage_policy"))
        if "independent_evaluation" not in usage_policy:
            reasons.append(
                (
                    "evaluation_policy_missing",
                    f"usage_policy={usage_policy or 'missing'}",
                )
            )
        if _normalized_token(row.get("split")) != "test":
            reasons.append(("evaluation_split_not_frozen", "independent evaluation requires split=test"))
    return reasons


def _training_row(row: dict[str, str], *, source_record: dict[str, str] | None) -> dict[str, str]:
    source_group_id = str(row.get("group_id") or "").strip()
    sample_weight = str(row.get("sample_weight") or "1.0")
    sampling_weight = str(row.get("sampling_weight") or sample_weight)
    return {
        "case_id": str(row.get("record_id") or ""),
        "record_id": str(row.get("record_id") or ""),
        "image_path": str(Path(str(row.get("local_path") or "")).resolve()),
        "mask_path": str(Path(str(row.get("label_path") or "")).resolve()),
        "split": _normalized_token(row.get("split")) or "train",
        "registry_split": _normalized_token(row.get("split")) or "unspecified",
        "group_id": source_group_id,
        "source_group_id": source_group_id,
        "source_id": str(row.get("source_id") or ""),
        "source_url": str(row.get("source_url") or ""),
        "domain_tier": str(row.get("domain_tier") or ""),
        "sample_weight": sample_weight,
        "sampling_weight": sampling_weight,
        "review_state": _normalized_token(row.get("review_state")),
        "label_source": str(row.get("label_type") or ""),
        "label_type": str(row.get("label_type") or ""),
        "artifact_role": str(row.get("artifact_role") or ""),
        "usage_policy": _normalized_token(row.get("usage_policy")) or "training_allowed_by_license",
        "training_eligible": "true",
        "license": _effective_license(row, source_record=source_record),
        "checksum": str(row.get("checksum") or "").lower(),
        "label_checksum": str(row.get("label_checksum") or "").lower(),
        "target_domain_flag": str(row.get("target_domain_flag") or "false").lower(),
        "medical_scene": str(row.get("medical_scene") or ""),
        "medical_boundary": str(row.get("medical_boundary") or ""),
    }


def _ensure_grouped_train_val_split(
    rows: list[dict[str, str]],
    *,
    validation_fraction: float,
    split_seed: int,
) -> dict[str, Any]:
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_splits[row["source_group_id"]].add(row["split"])
    existing = {split for splits in group_splits.values() for split in splits}
    if "train" in existing and "val" in existing:
        return {
            "name": "registry_group_split",
            "seed": None,
            "validation_fraction": None,
            "reassigned_group_count": 0,
        }
    groups = sorted(group_splits, key=lambda value: _split_digest(value, split_seed))
    if len(groups) < 2:
        raise TrainingAdmissionError("Training admission requires at least two source groups for train/val separation")
    safe_fraction = min(0.5, max(0.05, float(validation_fraction)))
    val_count = min(len(groups) - 1, max(1, round(len(groups) * safe_fraction)))
    val_groups = set(groups[:val_count])
    original = {group: next(iter(splits)) if len(splits) == 1 else "mixed" for group, splits in group_splits.items()}
    for row in rows:
        row["split"] = "val" if row["source_group_id"] in val_groups else "train"
    reassigned = sum(original[group] != ("val" if group in val_groups else "train") for group in groups)
    return {
        "name": "deterministic_group_fallback",
        "seed": int(split_seed),
        "validation_fraction": safe_fraction,
        "reassigned_group_count": reassigned,
        "validation_group_count": len(val_groups),
    }


def _assert_group_split_integrity(rows: Iterable[dict[str, str]]) -> None:
    splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        splits[row["source_group_id"]].add(row["split"])
    leaking = {group: values for group, values in splits.items() if len(values) > 1}
    if leaking:
        raise TrainingAdmissionError(f"Admitted source groups cross train/val splits: {leaking}")


def _validate_independent_evaluation_split(
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    if any(row.get("split") != "test" for row in rows):
        raise TrainingAdmissionError("Independent evaluation admission requires every admitted row to keep split=test")
    return {
        "name": "frozen_independent_test",
        "seed": None,
        "validation_fraction": None,
        "reassigned_group_count": 0,
    }


def _license_allows_training(row: dict[str, str], *, source_record: dict[str, str] | None) -> bool:
    usage_policy = _normalized_token(row.get("usage_policy"))
    if _usage_policy_blocked(usage_policy):
        return False
    text = _effective_license(row, source_record=source_record).lower()
    if any(marker in text for marker in BLOCKED_LICENSE_MARKERS):
        return False
    return any(marker in text for marker in OPEN_LICENSE_MARKERS)


def _effective_license(row: dict[str, str], *, source_record: dict[str, str] | None) -> str:
    values = [str(row.get("license") or "").strip()]
    if source_record is not None:
        values.append(str(source_record.get("license") or "").strip())
    return " | upstream: ".join(value for value in values if value)


def _usage_policy_blocked(value: str) -> bool:
    return any(marker in value for marker in BLOCKED_USAGE_POLICY_MARKERS)


def _valid_image_file(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def _mask_quality_reasons(
    image_path: Path,
    mask_path: Path,
    *,
    require_size_match: bool,
) -> list[tuple[str, str]]:
    try:
        with Image.open(image_path) as image, Image.open(mask_path) as mask_image:
            image_size = image.size
            mask = np.asarray(mask_image.convert("L"), dtype=np.uint8)
    except OSError as exc:
        return [("mask_quality_read_failure", str(exc))]
    reasons: list[tuple[str, str]] = []
    if require_size_match and (mask.shape[1], mask.shape[0]) != image_size:
        reasons.append(("mask_size_mismatch", f"image={image_size}, mask={(mask.shape[1], mask.shape[0])}"))
        return reasons
    positive_fraction = float(np.mean(mask > 0)) if mask.size else 0.0
    if positive_fraction <= 0.0:
        reasons.append(("empty_mask", str(mask_path)))
    if positive_fraction >= 0.98:
        reasons.append(("near_full_mask", f"positive_fraction={positive_fraction:.6f}"))
    values = set(int(value) for value in np.unique(mask))
    if not values <= {0, 1, 255}:
        reasons.append(("non_binary_mask", f"values={sorted(values)[:12]}"))
    return reasons


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _explicit_false(value: Any) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no"}


def _explicit_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _normalized_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _usage_scope_allows_training(value: Any) -> bool:
    normalized = " ".join(
        "".join(character if character.isalnum() else " " for character in str(value or "").lower()).split()
    )
    if any(marker in normalized for marker in TRAINING_SCOPE_DENY_MARKERS):
        return False
    tokens = {token for token in normalized.split() if token}
    if tokens & TRAINING_SCOPE_TOKENS and tokens & TRAINING_SCOPE_DENY_TOKENS:
        return False
    return bool(tokens & TRAINING_SCOPE_TOKENS)


def _normalized_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()


def _split_digest(group_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{_normalized_path(group_id)}".encode("utf-8")).hexdigest()
