from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from backend.src.core.artifacts import checksum_for_file
from backend.src.domains.annotations.enums import (
    AnnotationLabel,
    AnnotationSourceType,
    AnnotationStatus,
)
from backend.src.domains.annotations.repository import AnnotationRepository
from backend.src.domains.annotations.schemas import ManualAnnotationRecord
from backend.src.domains.cases.enums import ReviewerRole
from backend.src.domains.cases.schemas import CaseInputAsset, CaseRecord, ReviewActorIdentity

_TRUSTED_PHYSICIAN_AUTH_SOURCES = {
    "institution_sso",
    "signed_session",
    "verified_identity_token",
}
_ACCEPTED_STATUSES = {AnnotationStatus.ACCEPTED, AnnotationStatus.MODIFIED}


def resolve_trusted_reviewed_bone_gate(
    repository: AnnotationRepository | None,
    *,
    case_id: str,
    white_light: CaseInputAsset,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if repository is None:
        return None, _selection("unavailable", ["annotation_repository_unavailable"])
    records = [
        record for record in repository.list_records(case_id=case_id) if record.label == AnnotationLabel.EXPOSED_BONE
    ]
    if not records:
        return None, _selection("missing", ["trusted_reviewed_exposed_bone_annotation_missing"])

    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        evidence, reasons = _validate_gate_record(repository, record, white_light=white_light)
        if evidence is not None:
            valid.append(evidence)
        else:
            rejected.append({"annotation_id": record.annotation_id, "reasons": reasons})
    if len(valid) > 1:
        return None, {
            **_selection("ambiguous", ["multiple_trusted_reviewed_exposed_bone_annotations"]),
            "eligible_annotation_ids": [item["annotation_id"] for item in valid],
            "rejected": rejected,
        }
    if not valid:
        reasons = [reason for item in rejected for reason in item["reasons"]]
        return None, {
            **_selection("failed_closed", list(dict.fromkeys(reasons))),
            "rejected": rejected,
        }
    return valid[0], {
        **_selection("selected", []),
        "annotation_id": valid[0]["annotation_id"],
        "annotation_version": valid[0]["annotation_version"],
        "rejected": rejected,
    }


def target_domain_input_gate(
    case: CaseRecord,
    *,
    white_light: CaseInputAsset,
    fluorescence: CaseInputAsset,
) -> tuple[bool, dict[str, Any]]:
    reasons: list[str] = []
    intake = case.intake_metadata
    if intake is None:
        reasons.append("target_domain_intake_metadata_missing")
    else:
        if intake.authorization_status != "approved":
            reasons.append("target_domain_authorization_not_approved")
        if not intake.deidentification_confirmed:
            reasons.append("target_domain_deidentification_unconfirmed")
        if not intake.mapping_held_by_institution:
            reasons.append("target_domain_case_mapping_governance_missing")
        if not intake.target_condition_confirmed:
            reasons.append("target_condition_unconfirmed")
        if intake.admission_status != "target_registry_ready":
            reasons.append("target_domain_registry_not_ready")

    white_metadata = dict(white_light.metadata or {})
    fluorescence_metadata = dict(fluorescence.metadata or {})
    for name, metadata in (("white_light", white_metadata), ("fluorescence", fluorescence_metadata)):
        if metadata.get("admission_status") != "admitted":
            reasons.append(f"{name}_input_not_admitted")
        if metadata.get("target_domain_flag") is not True:
            reasons.append(f"{name}_target_domain_flag_missing")
        if metadata.get("deidentification_confirmed") is not True:
            reasons.append(f"{name}_deidentification_unconfirmed")
    white_pair = str(white_metadata.get("pair_id") or "").strip()
    fluorescence_pair = str(fluorescence_metadata.get("pair_id") or "").strip()
    if not white_pair or white_pair != fluorescence_pair:
        reasons.append("target_domain_dual_channel_pair_unverified")
    white_batch = str(white_metadata.get("batch_id") or "").strip()
    fluorescence_batch = str(fluorescence_metadata.get("batch_id") or "").strip()
    if not white_batch or white_batch != fluorescence_batch:
        reasons.append("target_domain_batch_binding_unverified")

    reasons = list(dict.fromkeys(reasons))
    return not reasons, {
        "verified": not reasons,
        "reasons": reasons,
        "white_input_id": white_light.input_id,
        "fluorescence_input_id": fluorescence.input_id,
        "pair_id": white_pair or None,
        "batch_id": white_batch or None,
    }


def _validate_gate_record(
    repository: AnnotationRepository,
    record: ManualAnnotationRecord,
    *,
    white_light: CaseInputAsset,
) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    if record.status not in _ACCEPTED_STATUSES:
        reasons.append("exposed_bone_annotation_not_accepted_or_modified")
    for name, actor in (
        ("author", record.latest_author),
        ("submitter", record.submitted_by),
        ("reviewer", record.reviewed_by),
    ):
        if not _trusted_physician(actor):
            reasons.append(f"exposed_bone_{name}_identity_untrusted")
    if record.reviewed_at is None:
        reasons.append("exposed_bone_review_timestamp_missing")
    if record.source.source_type != AnnotationSourceType.CASE_JPEG:
        reasons.append("exposed_bone_source_is_not_case_jpeg")
    if record.source.input_id != white_light.input_id:
        reasons.append("exposed_bone_source_input_mismatch")

    versions = [item for item in repository.versions(record.annotation_id) if item.version == record.current_version]
    if len(versions) != 1:
        reasons.append("exposed_bone_current_version_missing_or_ambiguous")
        current_version = None
    else:
        current_version = versions[0]
        if Path(current_version.mask_path).resolve() != Path(record.mask_path).resolve():
            reasons.append("exposed_bone_current_version_path_mismatch")
        if current_version.mask_checksum != record.mask_checksum:
            reasons.append("exposed_bone_current_version_checksum_mismatch")
        if current_version.positive_pixel_count != record.positive_pixel_count:
            reasons.append("exposed_bone_current_version_area_mismatch")

    try:
        white_path = Path(white_light.path).expanduser().resolve(strict=True)
        white_checksum = checksum_for_file(white_path)
        white_size = _image_size(white_path)
    except (OSError, ValueError, UnidentifiedImageError):
        reasons.append("white_light_source_unreadable_for_bone_gate")
        white_checksum = ""
        white_size = None
    if white_checksum and record.source_checksum != white_checksum:
        reasons.append("exposed_bone_source_checksum_mismatch")
    if record.source.source_checksum != record.source_checksum:
        reasons.append("exposed_bone_descriptor_checksum_mismatch")

    source_snapshot = Path(record.source_snapshot_path).expanduser().resolve()
    if not source_snapshot.is_file():
        reasons.append("exposed_bone_source_snapshot_missing")
    elif checksum_for_file(source_snapshot) != record.source_checksum:
        reasons.append("exposed_bone_source_snapshot_checksum_mismatch")

    mask_path = Path(record.mask_path).expanduser().resolve()
    if not mask_path.is_file():
        reasons.append("exposed_bone_mask_missing")
        positive_pixels = None
    elif checksum_for_file(mask_path) != record.mask_checksum:
        reasons.append("exposed_bone_mask_checksum_mismatch")
        positive_pixels = None
    else:
        try:
            mask_size, positive_pixels, binary = _binary_mask_summary(mask_path)
        except (OSError, ValueError, UnidentifiedImageError):
            reasons.append("exposed_bone_mask_unreadable")
            positive_pixels = None
        else:
            if not binary:
                reasons.append("exposed_bone_mask_not_binary")
            if white_size is not None and mask_size != white_size:
                reasons.append("exposed_bone_mask_dimension_mismatch")
            if (record.original_width, record.original_height) != mask_size:
                reasons.append("exposed_bone_annotation_dimension_mismatch")
            if positive_pixels != record.positive_pixel_count or positive_pixels <= 0:
                reasons.append("exposed_bone_mask_area_mismatch")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return None, reasons
    assert current_version is not None
    assert record.reviewed_at is not None
    assert record.reviewed_by is not None
    return {
        "path": str(mask_path),
        "sha256": record.mask_checksum,
        "physician_reviewed": True,
        "trusted_review": True,
        "review_status": ("physician_accepted" if record.status == AnnotationStatus.ACCEPTED else "physician_modified"),
        "annotation_id": record.annotation_id,
        "annotation_version": record.current_version,
        "training_eligible": record.training_eligible,
        "training_admission_required": False,
        "source_input_id": record.source.input_id,
        "source_checksum": record.source_checksum,
        "positive_pixel_count": positive_pixels,
        "reviewed_at": record.reviewed_at.isoformat(),
        "reviewed_by": record.reviewed_by.model_dump(mode="json"),
        "medical_boundary": record.medical_boundary,
    }, []


def _trusted_physician(actor: ReviewActorIdentity | None) -> bool:
    return bool(
        actor
        and actor.role == ReviewerRole.PHYSICIAN
        and actor.auth_source in _TRUSTED_PHYSICIAN_AUTH_SOURCES
        and actor.actor_id.strip()
        and actor.institution.strip()
    )


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        return image.size


def _binary_mask_summary(path: Path) -> tuple[tuple[int, int], int, bool]:
    with Image.open(path) as image:
        mask = image.convert("L")
        mask.load()
        histogram = mask.histogram()
        return mask.size, int(histogram[255]), sum(histogram[1:255]) == 0


def _selection(status: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "reasons": reasons,
        "physician_reviewed_bone_gate": status == "selected",
    }
