from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw, UnidentifiedImageError

from backend.src.core.artifacts import checksum_for_file
from backend.src.domains.annotations.enums import (
    AnnotationCoordinateSpace,
    AnnotationLabel,
    AnnotationOperationMode,
    AnnotationReviewDecision,
    AnnotationSourceType,
    AnnotationStatus,
    AnnotationTool,
)
from backend.src.domains.annotations.repository import AnnotationNotFoundError, AnnotationRepository
from backend.src.domains.annotations.schemas import (
    AnnotationCreateRequest,
    AnnotationGeometry,
    AnnotationSourceDescriptor,
    AnnotationSourceListResponse,
    AnnotationSourceRequest,
    AnnotationTrainingManifestListResponse,
    AnnotationTrainingManifestResponse,
    AnnotationTrainingManifestSummary,
    AnnotationVersionCreateRequest,
    AnnotationVersionHistoryResponse,
    AnnotationVersionRecord,
    ManualAnnotationRecord,
)
from backend.src.domains.cases.enums import InputChannel, ReviewerRole
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import (
    AnalysisRun,
    CandidateRegion,
    CaseInputAsset,
    CaseRecord,
    ReviewActorIdentity,
)
from src.core.paths import ensure_dir

ANNOTATION_MEDICAL_BOUNDARY = (
    "Manual annotations are research-validation evidence, require physician review, "
    "and do not produce a diagnostic conclusion."
)
TRUSTED_PHYSICIAN_AUTH_SOURCES = {
    "institution_sso",
    "signed_session",
    "verified_identity_token",
}
INDEPENDENT_PHYSICIAN_REVIEW_REQUIRED = "independent_physician_review_required"
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
SUPPORTED_STILL_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
JPEG_SUFFIXES = {".jpg", ".jpeg"}
TRAINING_MANIFEST_FIELDS = [
    "sample_id",
    "record_id",
    "annotation_id",
    "annotation_version",
    "case_id",
    "patient_id",
    "group_id",
    "image_path",
    "local_path",
    "source_snapshot_path",
    "label_path",
    "mask_path",
    "image_checksum",
    "source_checksum",
    "checksum",
    "label_checksum",
    "mask_checksum",
    "label_type",
    "mask_type",
    "review_state",
    "training_eligible",
    "sample_weight",
    "sampling_weight",
    "original_width",
    "original_height",
    "positive_pixel_count",
    "positive_area_fraction",
    "source_type",
    "source_id",
    "source_url",
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
    "input_domain",
    "domain_tier",
    "target_domain_flag",
    "artifact_role",
    "usage_policy",
    "license",
    "medical_scene",
    "split",
    "exclusion_reason",
    "medical_boundary",
]
ERROR_ANALYSIS_FIELDS = [*TRAINING_MANIFEST_FIELDS, "error_analysis_role", "negative_mask_allowed"]
ANNOTATION_AUDIT_FIELDS = [
    "annotation_id",
    "case_id",
    "label",
    "status",
    "current_version",
    "version",
    "is_current_version",
    "mask_path",
    "mask_checksum",
    "source_snapshot_path",
    "source_checksum",
    "positive_pixel_count",
    "positive_area_fraction",
    "author_actor_id",
    "author_role",
    "author_institution",
    "author_auth_source",
    "reviewer_actor_id",
    "reviewer_role",
    "reviewer_institution",
    "reviewer_auth_source",
    "reviewed_at",
    "training_eligible",
    "sample_weight",
    "training_exclusion_reason",
    "file_packaging_status",
    "medical_boundary",
]


class AnnotationValidationError(ValueError):
    pass


class AnnotationPermissionError(PermissionError):
    pass


class ReviewedIgnoreAnnotationSynchronizer(Protocol):
    def validate_reviewed_ignore_annotation(self, annotation: ManualAnnotationRecord) -> None: ...

    def synchronize_reviewed_ignore_annotations(self, case_id: str, candidate_id: str) -> CaseRecord: ...


class ManualAnnotationService:
    def __init__(
        self,
        repository: AnnotationRepository,
        case_repository: CaseRepository,
        artifact_root: str | Path,
        ignore_annotation_synchronizer: ReviewedIgnoreAnnotationSynchronizer | None = None,
    ) -> None:
        self.repository = repository
        self.case_repository = case_repository
        self.artifact_root = ensure_dir(Path(artifact_root) / "manual_annotations")
        self.ignore_annotation_synchronizer = ignore_annotation_synchronizer

    def list_sources(self, case: CaseRecord) -> AnnotationSourceListResponse:
        sources: list[AnnotationSourceDescriptor] = []
        for asset in case.inputs:
            if asset.channel == InputChannel.VIDEO:
                continue
            if Path(asset.path).suffix.lower() not in JPEG_SUFFIXES:
                continue
            try:
                sources.append(self._descriptor_for_case_jpeg(case, asset))
            except AnnotationValidationError:
                continue

        for run in case.analysis_runs:
            sources.extend(self._descriptors_for_run(case, run))

        deduplicated: dict[str, AnnotationSourceDescriptor] = {}
        for source in sources:
            deduplicated.setdefault(source.source_key, source)
        return AnnotationSourceListResponse(case_id=case.case_id, sources=list(deduplicated.values()))

    def list_annotations(self, case_id: str) -> list[ManualAnnotationRecord]:
        return self.repository.list_records(case_id=case_id)

    def get_annotation(self, case_id: str, annotation_id: str) -> ManualAnnotationRecord:
        record = self.repository.get(annotation_id)
        if record is None or record.case_id != case_id:
            raise AnnotationNotFoundError(annotation_id)
        return record

    def create_annotation(
        self,
        case: CaseRecord,
        request: AnnotationCreateRequest,
        actor: ReviewActorIdentity,
    ) -> ManualAnnotationRecord:
        source, source_path = self._resolve_source(case, request.source)
        annotation_id = f"annotation_{uuid4().hex[:12]}"
        annotation_dir = ensure_dir(self.artifact_root / case.case_id / annotation_id)
        snapshot_path = self._copy_source_snapshot(source_path, annotation_dir, source.source_checksum)
        now = datetime.now(timezone.utc)
        mask_result = self._write_mask_version(
            request.geometry,
            width=source.original_width,
            height=source.original_height,
            output_path=annotation_dir / "v0001_mask.png",
        )
        version = AnnotationVersionRecord(
            annotation_id=annotation_id,
            version=1,
            geometry=request.geometry,
            mask_path=str(mask_result["path"]),
            mask_checksum=str(mask_result["checksum"]),
            positive_pixel_count=int(mask_result["positive_pixel_count"]),
            positive_area_fraction=float(mask_result["positive_area_fraction"]),
            author=actor,
            created_at=now,
            notes=request.notes,
        )
        record = ManualAnnotationRecord(
            annotation_id=annotation_id,
            case_id=case.case_id,
            label=request.label,
            current_version=1,
            geometry=request.geometry,
            source=source,
            source_snapshot_path=str(snapshot_path),
            source_checksum=source.source_checksum,
            original_width=source.original_width,
            original_height=source.original_height,
            mask_path=version.mask_path,
            mask_checksum=version.mask_checksum,
            positive_pixel_count=version.positive_pixel_count,
            positive_area_fraction=version.positive_area_fraction,
            created_by=actor,
            latest_author=actor,
            created_at=now,
            updated_at=now,
            notes=request.notes,
            medical_boundary=ANNOTATION_MEDICAL_BOUNDARY,
        )
        return self.repository.create(record, version)

    def save_version(
        self,
        case_id: str,
        annotation_id: str,
        request: AnnotationVersionCreateRequest,
        actor: ReviewActorIdentity,
    ) -> ManualAnnotationRecord:
        record = self.get_annotation(case_id, annotation_id)
        if record.current_version != request.expected_version:
            from backend.src.domains.annotations.repository import AnnotationVersionConflictError

            raise AnnotationVersionConflictError(
                annotation_id,
                expected_version=request.expected_version,
                actual_version=record.current_version,
            )
        if record.status not in {AnnotationStatus.DRAFT, AnnotationStatus.CHANGES_REQUESTED}:
            raise AnnotationValidationError("only draft or changes-requested annotations can be edited")
        if actor.actor_id != record.latest_author.actor_id and actor.role != ReviewerRole.PHYSICIAN:
            raise AnnotationPermissionError("annotation edits require the current author or a trusted physician")

        expected_status = record.status
        next_version = record.current_version + 1
        now = datetime.now(timezone.utc)
        annotation_dir = ensure_dir(self.artifact_root / case_id / annotation_id)
        mask_result = self._write_mask_version(
            request.geometry,
            width=record.original_width,
            height=record.original_height,
            output_path=annotation_dir / f"v{next_version:04d}_mask.png",
        )
        version = AnnotationVersionRecord(
            annotation_id=annotation_id,
            version=next_version,
            geometry=request.geometry,
            mask_path=str(mask_result["path"]),
            mask_checksum=str(mask_result["checksum"]),
            positive_pixel_count=int(mask_result["positive_pixel_count"]),
            positive_area_fraction=float(mask_result["positive_area_fraction"]),
            author=actor,
            created_at=now,
            notes=request.notes,
        )
        updated = record.model_copy(
            update={
                "status": AnnotationStatus.DRAFT,
                "current_version": next_version,
                "geometry": request.geometry,
                "mask_path": version.mask_path,
                "mask_checksum": version.mask_checksum,
                "positive_pixel_count": version.positive_pixel_count,
                "positive_area_fraction": version.positive_area_fraction,
                "latest_author": actor,
                "updated_at": now,
                "notes": request.notes,
                "submitted_by": None,
                "submitted_at": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "review_notes": None,
                "training_eligible": False,
                "sample_weight": 0.0,
                "training_exclusion_reason": None,
            }
        )
        return self.repository.append_version(
            updated,
            version,
            expected_version=request.expected_version,
            expected_status=expected_status,
        )

    def version_history(self, case_id: str, annotation_id: str) -> AnnotationVersionHistoryResponse:
        record = self.get_annotation(case_id, annotation_id)
        versions = self.repository.versions(record.annotation_id)
        return AnnotationVersionHistoryResponse(
            annotation_id=record.annotation_id,
            current_version=record.current_version,
            versions=versions,
            items=versions,
        )

    def submit(
        self,
        case_id: str,
        annotation_id: str,
        *,
        expected_version: int,
        notes: str | None,
        actor: ReviewActorIdentity,
    ) -> ManualAnnotationRecord:
        record = self.get_annotation(case_id, annotation_id)
        self._require_version(record, expected_version)
        if record.status != AnnotationStatus.DRAFT:
            raise AnnotationValidationError("only draft annotations can be submitted")
        if record.positive_pixel_count <= 0:
            raise AnnotationValidationError("an empty annotation mask cannot be submitted")
        if actor.actor_id != record.latest_author.actor_id and actor.role != ReviewerRole.PHYSICIAN:
            raise AnnotationPermissionError("annotation submission requires the current author or a trusted physician")
        now = datetime.now(timezone.utc)
        updated = record.model_copy(
            update={
                "status": AnnotationStatus.SUBMITTED,
                "submitted_by": actor,
                "submitted_at": now,
                "updated_at": now,
                "notes": notes if notes is not None else record.notes,
                "training_eligible": False,
                "sample_weight": 0.0,
                "training_exclusion_reason": None,
            }
        )
        return self.repository.update(
            updated,
            expected_version=expected_version,
            expected_status=AnnotationStatus.DRAFT,
        )

    def review(
        self,
        case_id: str,
        annotation_id: str,
        *,
        expected_version: int,
        decision: AnnotationReviewDecision,
        notes: str | None,
        actor: ReviewActorIdentity,
    ) -> ManualAnnotationRecord:
        record = self.get_annotation(case_id, annotation_id)
        self._require_version(record, expected_version)
        if record.status != AnnotationStatus.SUBMITTED:
            raise AnnotationValidationError("only submitted annotations can receive a review decision")
        if not _is_trusted_physician(actor):
            raise AnnotationPermissionError("annotation review decisions require a trusted physician identity")

        now = datetime.now(timezone.utc)
        status = AnnotationStatus(decision.value)
        independently_reviewed = _has_independent_physician_review(
            latest_author=record.latest_author,
            submitted_by=record.submitted_by,
            reviewer=actor,
        )
        review_ready = (
            decision in {AnnotationReviewDecision.ACCEPTED, AnnotationReviewDecision.MODIFIED}
            and _is_trusted_physician(record.latest_author)
            and record.submitted_by is not None
            and _is_trusted_physician(record.submitted_by)
            and independently_reviewed
            and record.positive_pixel_count > 0
        )
        governance_reasons: list[str] = []
        if review_ready:
            governance_reasons, _ = self._training_governance_evidence(
                self.case_repository.get(case_id),
                source_input_id=record.source.input_id,
                source_checksum_cache=None,
            )
        eligible = review_ready and not governance_reasons
        training_exclusion_reason = None
        if decision in {AnnotationReviewDecision.ACCEPTED, AnnotationReviewDecision.MODIFIED}:
            if not _is_trusted_physician(record.latest_author):
                training_exclusion_reason = "trusted_physician_annotation_required"
            elif record.submitted_by is None or not _is_trusted_physician(record.submitted_by):
                training_exclusion_reason = "trusted_physician_submission_required"
            elif not independently_reviewed:
                training_exclusion_reason = INDEPENDENT_PHYSICIAN_REVIEW_REQUIRED
            elif record.positive_pixel_count <= 0:
                training_exclusion_reason = "empty_annotation_mask"
            elif governance_reasons:
                training_exclusion_reason = governance_reasons[0]
        updated = record.model_copy(
            update={
                "status": status,
                "reviewed_by": actor,
                "reviewed_at": now,
                "updated_at": now,
                "review_notes": notes,
                "training_eligible": eligible,
                "sample_weight": 4.0 if eligible else (0.5 if decision == AnnotationReviewDecision.REJECTED else 0.0),
                "training_exclusion_reason": training_exclusion_reason,
            }
        )
        should_synchronize_ignore = (
            decision in {AnnotationReviewDecision.ACCEPTED, AnnotationReviewDecision.MODIFIED}
            and updated.label == AnnotationLabel.IGNORE
            and updated.source.source_type == AnnotationSourceType.MODEL_CANDIDATE
            and bool(updated.source.candidate_id)
        )
        if should_synchronize_ignore and review_ready:
            if self.ignore_annotation_synchronizer is None:
                raise AnnotationValidationError(
                    "reviewed ignore annotations require the candidate activity synchronizer"
                )
            try:
                self.ignore_annotation_synchronizer.validate_reviewed_ignore_annotation(updated)
            except ValueError as exc:
                raise AnnotationValidationError(str(exc)) from exc

        saved = self.repository.update(
            updated,
            expected_version=expected_version,
            expected_status=AnnotationStatus.SUBMITTED,
        )
        if should_synchronize_ignore and self.ignore_annotation_synchronizer is not None:
            self.ignore_annotation_synchronizer.synchronize_reviewed_ignore_annotations(
                saved.case_id,
                str(saved.source.candidate_id),
            )
        return saved

    def delete_draft(self, case_id: str, annotation_id: str, actor: ReviewActorIdentity) -> None:
        record = self.get_annotation(case_id, annotation_id)
        if record.status != AnnotationStatus.DRAFT:
            raise AnnotationValidationError("only draft annotations can be deleted")
        if record.created_by.actor_id != actor.actor_id:
            raise AnnotationPermissionError("only the draft creator can delete this annotation")
        if not self.repository.delete_draft(annotation_id, actor_id=actor.actor_id):
            raise AnnotationPermissionError("draft deletion was rejected")
        annotation_dir = self.artifact_root / case_id / annotation_id
        if annotation_dir.exists():
            shutil.rmtree(annotation_dir)

    def export_training_manifest(
        self,
        *,
        case_ids: list[str] | None = None,
        include_ineligible: bool = False,
        actor: ReviewActorIdentity,
    ) -> AnnotationTrainingManifestResponse:
        now = datetime.now(timezone.utc)
        records: list[dict[str, Any]] = []
        eligible_count = 0
        excluded_count = 0
        rejected_records: list[dict[str, Any]] = []
        source_checksum_cache: dict[str, str] = {}
        for annotation in self.repository.list_for_cases(case_ids):
            row = self._training_manifest_row(annotation, source_checksum_cache=source_checksum_cache)
            if row["training_eligible"]:
                eligible_count += 1
                records.append(row)
            else:
                excluded_count += 1
                if annotation.status == AnnotationStatus.REJECTED:
                    rejected_records.append(self._rejected_error_analysis_row(annotation, row))
                if include_ineligible:
                    records.append(row)

        manifest_id = now.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
        output_dir = ensure_dir(self.artifact_root / "training_manifests" / manifest_id)
        json_path = output_dir / "manual_annotation_training_manifest.json"
        csv_path = output_dir / "manual_annotation_training_manifest.csv"
        error_json_path = output_dir / "rejected_annotation_error_analysis.json"
        error_csv_path = output_dir / "rejected_annotation_error_analysis.csv"
        payload = {
            "schema_version": "osteo-vision-manual-annotation-training-manifest-v2",
            "created_at": now.isoformat(),
            "eligible_count": eligible_count,
            "excluded_count": excluded_count,
            "records": records,
            "medical_boundary": ANNOTATION_MEDICAL_BOUNDARY,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRAINING_MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows([{key: _csv_value(row.get(key)) for key in TRAINING_MANIFEST_FIELDS} for row in records])
        error_payload = {
            "schema_version": "osteo-vision-rejected-annotation-error-analysis-v1",
            "created_at": now.isoformat(),
            "record_count": len(rejected_records),
            "records": rejected_records,
            "safety_boundary": (
                "Rejected annotation masks are retained for error analysis only. They must not be interpreted "
                "as negative masks or used as disease-absence labels."
            ),
        }
        error_json_path.write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with error_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ERROR_ANALYSIS_FIELDS)
            writer.writeheader()
            writer.writerows(
                [{key: _csv_value(row.get(key)) for key in ERROR_ANALYSIS_FIELDS} for row in rejected_records]
            )
        summary = AnnotationTrainingManifestSummary(
            manifest_id=manifest_id,
            created_at=now,
            created_by=actor,
            case_ids=case_ids or [],
            json_path=str(json_path),
            csv_path=str(csv_path),
            error_analysis_json_path=str(error_json_path),
            error_analysis_csv_path=str(error_csv_path),
            eligible_count=eligible_count,
            excluded_count=excluded_count,
            rejected_count=len(rejected_records),
            manifest_checksum=checksum_for_file(json_path),
            error_analysis_checksum=checksum_for_file(error_json_path),
        )
        self._register_training_manifest(summary)
        return AnnotationTrainingManifestResponse(
            manifest_id=manifest_id,
            schema_version=str(payload["schema_version"]),
            created_at=now,
            json_path=str(json_path),
            manifest_path=str(json_path),
            csv_path=str(csv_path),
            error_analysis_json_path=str(error_json_path),
            error_analysis_csv_path=str(error_csv_path),
            sample_count=len(records),
            eligible_count=eligible_count,
            excluded_count=excluded_count,
            records=records,
            medical_boundary=ANNOTATION_MEDICAL_BOUNDARY,
        )

    def list_training_manifests(self) -> AnnotationTrainingManifestListResponse:
        return AnnotationTrainingManifestListResponse(items=self._read_training_manifest_registry())

    def get_training_manifest(self, manifest_id: str) -> AnnotationTrainingManifestSummary:
        match = next(
            (item for item in self._read_training_manifest_registry() if item.manifest_id == manifest_id), None
        )
        if match is None:
            raise AnnotationValidationError("annotation training manifest was not found")
        return match

    def build_case_annotation_audit(
        self,
        case: CaseRecord,
        *,
        json_path: Path,
        csv_path: Path,
        registry_path: Path,
    ) -> tuple[list[dict[str, Any]], list[tuple[Path, str]]]:
        records = self.repository.list_records(case_id=case.case_id)
        packaging_allowed = self._case_annotation_files_may_be_packaged(case)
        rows: list[dict[str, Any]] = []
        package_files: list[tuple[Path, str]] = []
        source_checksum_cache: dict[str, str] = {}
        for annotation in records:
            manifest_row = self._training_manifest_row(
                annotation,
                source_checksum_cache=source_checksum_cache,
            )
            versions = self.repository.versions(annotation.annotation_id)
            for version in versions:
                row = {
                    "annotation_id": annotation.annotation_id,
                    "case_id": annotation.case_id,
                    "label": annotation.label.value,
                    "status": annotation.status.value,
                    "current_version": annotation.current_version,
                    "version": version.version,
                    "is_current_version": version.version == annotation.current_version,
                    "mask_path": version.mask_path,
                    "mask_checksum": version.mask_checksum,
                    "source_snapshot_path": annotation.source_snapshot_path,
                    "source_checksum": annotation.source_checksum,
                    "positive_pixel_count": version.positive_pixel_count,
                    "positive_area_fraction": version.positive_area_fraction,
                    "author_actor_id": version.author.actor_id,
                    "author_role": version.author.role.value,
                    "author_institution": version.author.institution,
                    "author_auth_source": version.author.auth_source,
                    "reviewer_actor_id": annotation.reviewed_by.actor_id if annotation.reviewed_by else None,
                    "reviewer_role": annotation.reviewed_by.role.value if annotation.reviewed_by else None,
                    "reviewer_institution": annotation.reviewed_by.institution if annotation.reviewed_by else None,
                    "reviewer_auth_source": annotation.reviewed_by.auth_source if annotation.reviewed_by else None,
                    "reviewed_at": annotation.reviewed_at.isoformat() if annotation.reviewed_at else None,
                    "training_eligible": manifest_row["training_eligible"],
                    "sample_weight": manifest_row["sample_weight"],
                    "training_exclusion_reason": manifest_row["exclusion_reason"],
                    "file_packaging_status": (
                        "included_authorized_deidentified"
                        if packaging_allowed
                        else "withheld_authorization_or_deidentification_required"
                    ),
                    "medical_boundary": annotation.medical_boundary,
                }
                rows.append(row)
                if packaging_allowed:
                    mask_path = Path(version.mask_path)
                    if mask_path.is_file() and checksum_for_file(mask_path) == version.mask_checksum:
                        package_files.append(
                            (
                                mask_path,
                                f"annotation_evidence/{annotation.annotation_id}/v{version.version:04d}_mask.png",
                            )
                        )
            source_path = Path(annotation.source_snapshot_path)
            if (
                packaging_allowed
                and source_path.is_file()
                and checksum_for_file(source_path) == annotation.source_checksum
            ):
                package_files.append(
                    (source_path, f"annotation_evidence/{annotation.annotation_id}/{source_path.name}")
                )

        registry_items = [
            item
            for item in self._read_training_manifest_registry()
            if not item.case_ids or case.case_id in item.case_ids
        ]
        payload = {
            "schema_version": "osteo-vision-case-annotation-audit-v1",
            "case_id": case.case_id,
            "annotation_count": len(records),
            "version_count": len(rows),
            "file_packaging_allowed": packaging_allowed,
            "rows": rows,
            "medical_boundary": ANNOTATION_MEDICAL_BOUNDARY,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ANNOTATION_AUDIT_FIELDS)
            writer.writeheader()
            writer.writerows([{key: _csv_value(row.get(key)) for key in ANNOTATION_AUDIT_FIELDS} for row in rows])
        registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "osteo-vision-case-annotation-manifest-registry-v1",
                    "case_id": case.case_id,
                    "items": [item.model_dump(mode="json") for item in registry_items],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return rows, package_files

    @staticmethod
    def _case_annotation_files_may_be_packaged(case: CaseRecord) -> bool:
        intake = case.intake_metadata
        if intake is None:
            return False
        scope = intake.usage_scope.lower()
        return bool(
            intake.authorization_status == "approved"
            and intake.deidentification_confirmed
            and any(marker in scope for marker in ("analysis", "research", "competition", "export", "train"))
        )

    def _register_training_manifest(self, summary: AnnotationTrainingManifestSummary) -> None:
        registry_path = ensure_dir(self.artifact_root / "training_manifests") / "registry.json"
        items = self._read_training_manifest_registry()
        items = [item for item in items if item.manifest_id != summary.manifest_id]
        items.insert(0, summary)
        registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "osteo-vision-annotation-training-manifest-registry-v1",
                    "items": [item.model_dump(mode="json") for item in items],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _read_training_manifest_registry(self) -> list[AnnotationTrainingManifestSummary]:
        registry_path = self.artifact_root / "training_manifests" / "registry.json"
        if not registry_path.is_file():
            return []
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            return [AnnotationTrainingManifestSummary.model_validate(item) for item in payload.get("items", [])]
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AnnotationValidationError("annotation training manifest registry is unreadable") from exc

    @staticmethod
    def _rejected_error_analysis_row(annotation: ManualAnnotationRecord, row: dict[str, Any]) -> dict[str, Any]:
        return {
            **row,
            "training_eligible": False,
            "sample_weight": 0.5,
            "sampling_weight": 0.5,
            "artifact_role": "error_analysis::rejected_manual_annotation",
            "usage_policy": "error_analysis_only_do_not_treat_as_negative_mask",
            "label_type": "rejected_annotation_mask",
            "error_analysis_role": "annotation_rejection_review",
            "negative_mask_allowed": False,
            "exclusion_reason": "rejected_by_trusted_physician",
            "medical_boundary": (
                f"{annotation.medical_boundary} Rejected geometry is not a negative or disease-absence mask."
            ),
        }

    def _resolve_source(
        self,
        case: CaseRecord,
        request: AnnotationSourceRequest,
    ) -> tuple[AnnotationSourceDescriptor, Path]:
        if request.source_type == AnnotationSourceType.CASE_JPEG:
            asset = next((item for item in case.inputs if item.input_id == request.input_id), None)
            if asset is None:
                raise AnnotationValidationError("case JPEG input was not found")
            descriptor = self._descriptor_for_case_jpeg(case, asset)
            return descriptor, _readable_image_path(asset.path)

        if request.source_type == AnnotationSourceType.VIDEO_KEYFRAME:
            run = _find_run(case, request.run_id)
            frame = _find_frame(run, request.frame_index)
            source_path = _frame_image_path(frame)
            descriptor = self._descriptor_for_frame(case, run, frame, source_path)
            if request.input_id and descriptor.input_id != request.input_id:
                raise AnnotationValidationError("video keyframe input_id does not match the analysis run source")
            return descriptor, source_path

        run, candidate = _find_candidate(case, request.candidate_id, run_id=request.run_id)
        candidate_path = _candidate_image_path(candidate)
        if candidate_path is None and candidate.metadata.get("frame_index") is not None:
            frame = _find_frame(run, int(candidate.metadata["frame_index"]))
            candidate_path = _frame_image_path(frame)
        if candidate_path is None:
            raise AnnotationValidationError("model candidate has no readable source image")
        descriptor = self._descriptor_for_candidate(case, run, candidate, candidate_path)
        return descriptor, candidate_path

    def _descriptor_for_case_jpeg(self, case: CaseRecord, asset: CaseInputAsset) -> AnnotationSourceDescriptor:
        path = _readable_image_path(asset.path)
        if path.suffix.lower() not in JPEG_SUFFIXES:
            raise AnnotationValidationError("case image annotation sources must be JPEG files")
        width, height = _image_size(path)
        checksum = checksum_for_file(path)
        preview = self._ensure_source_preview(case.case_id, f"input_{asset.input_id}", path, checksum)
        return AnnotationSourceDescriptor(
            source_key=f"case_jpeg:{asset.input_id}",
            source_id=f"case_jpeg:{asset.input_id}",
            title=f"病例 JPEG {asset.input_id}",
            source_type=AnnotationSourceType.CASE_JPEG,
            input_id=asset.input_id,
            source_path=str(path),
            preview_path=str(preview),
            original_width=width,
            original_height=height,
            source_checksum=checksum,
            metadata={"channel": asset.channel.value, "mime_type": asset.mime_type},
        )

    def _descriptors_for_run(self, case: CaseRecord, run: AnalysisRun) -> list[AnnotationSourceDescriptor]:
        descriptors: list[AnnotationSourceDescriptor] = []
        frames = run.fused_outputs.get("frame_details") or run.fused_outputs.get("keyframes") or []
        if isinstance(frames, list):
            for frame in frames:
                if not isinstance(frame, dict) or frame.get("frame_index") is None:
                    continue
                try:
                    path = _frame_image_path(frame)
                    descriptors.append(self._descriptor_for_frame(case, run, frame, path))
                except AnnotationValidationError:
                    continue
        for candidate in run.candidate_regions:
            try:
                candidate_path = _candidate_image_path(candidate)
                if candidate_path is None and candidate.metadata.get("frame_index") is not None:
                    candidate_path = _frame_image_path(_find_frame(run, int(candidate.metadata["frame_index"])))
                if candidate_path is not None:
                    descriptors.append(self._descriptor_for_candidate(case, run, candidate, candidate_path))
            except AnnotationValidationError:
                continue
        return descriptors

    def _descriptor_for_frame(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        frame: dict[str, Any],
        path: Path,
    ) -> AnnotationSourceDescriptor:
        width, height = _image_size(path)
        checksum = checksum_for_file(path)
        frame_index = int(frame["frame_index"])
        preview = self._ensure_source_preview(case.case_id, f"run_{run.run_id}_frame_{frame_index}", path, checksum)
        video = _run_video_asset(case, run)
        return AnnotationSourceDescriptor(
            source_key=f"video_keyframe:{run.run_id}:{frame_index}",
            source_id=f"video_keyframe:{run.run_id}:{frame_index}",
            title=f"视频关键帧 {frame_index}",
            source_type=AnnotationSourceType.VIDEO_KEYFRAME,
            input_id=video.input_id if video else None,
            run_id=run.run_id,
            frame_index=frame_index,
            timestamp_sec=_optional_float(frame.get("timestamp_sec")),
            source_path=str(path),
            source_video_path=str(run.fused_outputs.get("source_path") or (video.path if video else "")) or None,
            preview_path=str(preview),
            original_width=width,
            original_height=height,
            source_checksum=checksum,
            metadata={"analysis_mode": run.fused_outputs.get("mode")},
        )

    def _descriptor_for_candidate(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        candidate: CandidateRegion,
        path: Path,
    ) -> AnnotationSourceDescriptor:
        width, height = _image_size(path)
        checksum = checksum_for_file(path)
        preview = self._ensure_source_preview(case.case_id, f"candidate_{candidate.candidate_id}", path, checksum)
        video = _run_video_asset(case, run)
        label_hint = _candidate_label_hint(candidate)
        return AnnotationSourceDescriptor(
            source_key=f"model_candidate:{candidate.candidate_id}",
            source_id=f"model_candidate:{candidate.candidate_id}",
            title=f"模型候选区 {candidate.candidate_id}",
            source_type=AnnotationSourceType.MODEL_CANDIDATE,
            input_id=video.input_id if video else None,
            run_id=run.run_id,
            frame_index=_optional_int(candidate.metadata.get("frame_index")),
            timestamp_sec=_optional_float(candidate.metadata.get("timestamp_sec")),
            candidate_id=candidate.candidate_id,
            label_hint=label_hint,
            source_path=str(path),
            source_video_path=str(run.fused_outputs.get("source_path") or (video.path if video else "")) or None,
            preview_path=str(preview),
            original_width=width,
            original_height=height,
            source_checksum=checksum,
            metadata={"risk_type": candidate.risk_type, "score": candidate.score, "confidence": candidate.confidence},
        )

    def _ensure_source_preview(self, case_id: str, key: str, source_path: Path, checksum: str) -> Path:
        suffix = source_path.suffix.lower()
        suffix = suffix if suffix in SUPPORTED_STILL_SUFFIXES else ".png"
        safe_key = _safe_name(key)
        output = ensure_dir(self.artifact_root / "source_previews" / case_id) / (f"{safe_key}_{checksum[:12]}{suffix}")
        if not output.exists():
            shutil.copy2(source_path, output)
        return output

    def _copy_source_snapshot(self, source_path: Path, annotation_dir: Path, checksum: str) -> Path:
        suffix = source_path.suffix.lower()
        suffix = suffix if suffix in SUPPORTED_STILL_SUFFIXES else ".png"
        output = annotation_dir / f"source_{checksum[:12]}{suffix}"
        if not output.exists():
            shutil.copy2(source_path, output)
        return output

    def _write_mask_version(
        self,
        geometry: AnnotationGeometry,
        *,
        width: int,
        height: int,
        output_path: Path,
    ) -> dict[str, Any]:
        mask = _render_annotation_mask(geometry, width=width, height=height)
        ensure_dir(output_path.parent)
        Image.fromarray(mask).save(output_path, format="PNG")
        positive = int(np.count_nonzero(mask))
        return {
            "path": output_path,
            "checksum": checksum_for_file(output_path),
            "positive_pixel_count": positive,
            "positive_area_fraction": round(positive / float(width * height), 8),
        }

    def _training_manifest_row(
        self,
        annotation: ManualAnnotationRecord,
        *,
        source_checksum_cache: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        source_path = Path(annotation.source_snapshot_path)
        mask_path = Path(annotation.mask_path)
        exclusion_reasons: list[str] = []
        latest = annotation.latest_author
        submitter = annotation.submitted_by
        reviewer = annotation.reviewed_by
        if not annotation.training_eligible:
            exclusion_reasons.append("annotation_not_training_eligible")
        if annotation.status not in {AnnotationStatus.ACCEPTED, AnnotationStatus.MODIFIED}:
            exclusion_reasons.append(f"annotation_status_{annotation.status.value}")
        if not _is_trusted_physician(latest):
            exclusion_reasons.append("trusted_physician_annotation_required")
        if submitter is None or not _is_trusted_physician(submitter):
            exclusion_reasons.append("trusted_physician_submission_required")
        if reviewer is None or not _is_trusted_physician(reviewer):
            exclusion_reasons.append("trusted_physician_review_required")
        if annotation.status in {AnnotationStatus.ACCEPTED, AnnotationStatus.MODIFIED} and not (
            reviewer
            and _has_independent_physician_review(
                latest_author=latest,
                submitted_by=submitter,
                reviewer=reviewer,
            )
        ):
            exclusion_reasons.append(INDEPENDENT_PHYSICIAN_REVIEW_REQUIRED)
        if annotation.positive_pixel_count <= 0:
            exclusion_reasons.append("empty_annotation_mask")
        if annotation.training_exclusion_reason and annotation.training_exclusion_reason not in exclusion_reasons:
            exclusion_reasons.append(annotation.training_exclusion_reason)
        if not source_path.is_file():
            exclusion_reasons.append("source_snapshot_missing")
        elif checksum_for_file(source_path) != annotation.source_checksum:
            exclusion_reasons.append("source_checksum_mismatch")
        if not mask_path.is_file():
            exclusion_reasons.append("mask_missing")
        elif checksum_for_file(mask_path) != annotation.mask_checksum:
            exclusion_reasons.append("mask_checksum_mismatch")
        case = self.case_repository.get(annotation.case_id)
        target_domain = bool(case and case.intake_metadata and case.intake_metadata.target_condition_confirmed)
        governance_reasons, governance_evidence = self._training_governance_evidence(
            case,
            source_input_id=annotation.source.input_id,
            source_checksum_cache=source_checksum_cache,
        )
        exclusion_reasons.extend(reason for reason in governance_reasons if reason not in exclusion_reasons)
        intake_training_approved = not governance_reasons
        usage_policy = (
            "institution_authorized_training_use"
            if intake_training_approved
            else "annotation_review_complete_data_use_requires_verification"
        )
        data_license = (
            "authorized institutional research training"
            if intake_training_approved
            else "data use permission pending verification"
        )
        eligible = not exclusion_reasons
        return {
            "sample_id": f"manual_{annotation.annotation_id}_v{annotation.current_version}",
            "record_id": f"manual_{annotation.annotation_id}_v{annotation.current_version}",
            "annotation_id": annotation.annotation_id,
            "annotation_version": annotation.current_version,
            "case_id": annotation.case_id,
            "patient_id": annotation.case_id,
            "group_id": annotation.case_id,
            "image_path": str(source_path),
            "local_path": str(source_path),
            "source_snapshot_path": str(source_path),
            "label_path": str(mask_path),
            "mask_path": str(mask_path),
            "image_checksum": annotation.source_checksum,
            "source_checksum": annotation.source_checksum,
            "checksum": annotation.source_checksum,
            "label_checksum": annotation.mask_checksum,
            "mask_checksum": annotation.mask_checksum,
            "label_type": "physician_mask" if eligible else "manual_annotation_mask",
            "mask_type": annotation.label.value,
            "review_state": annotation.status.value,
            "training_eligible": eligible,
            "sample_weight": 4.0 if eligible else 0.0,
            "sampling_weight": 4.0 if eligible else 0.0,
            "original_width": annotation.original_width,
            "original_height": annotation.original_height,
            "positive_pixel_count": annotation.positive_pixel_count,
            "positive_area_fraction": annotation.positive_area_fraction,
            "source_type": annotation.source.source_type.value,
            "source_id": annotation.source.source_key,
            "source_url": "",
            "source_input_id": annotation.source.input_id,
            "source_run_id": annotation.source.run_id,
            "source_frame_index": annotation.source.frame_index,
            "source_timestamp_sec": annotation.source.timestamp_sec,
            "source_candidate_id": annotation.source.candidate_id,
            "source_video_path": annotation.source.source_video_path,
            **governance_evidence,
            "actor_id": latest.actor_id,
            "actor_role": latest.role.value,
            "institution": latest.institution,
            "auth_source": latest.auth_source,
            "submitted_by_actor_id": submitter.actor_id if submitter else None,
            "submitted_by_role": submitter.role.value if submitter else None,
            "submitted_by_institution": submitter.institution if submitter else None,
            "submitted_by_auth_source": submitter.auth_source if submitter else None,
            "reviewer_actor_id": reviewer.actor_id if reviewer else None,
            "reviewer_role": reviewer.role.value if reviewer else None,
            "reviewer_institution": reviewer.institution if reviewer else None,
            "reviewer_auth_source": reviewer.auth_source if reviewer else None,
            "reviewed_at": annotation.reviewed_at.isoformat() if annotation.reviewed_at else None,
            "input_domain": (
                "target_domain_physician_annotation"
                if target_domain
                else "physician_reviewed_case_annotation_domain_unconfirmed"
            ),
            "domain_tier": "target" if target_domain else "case_annotation_domain_unconfirmed",
            "target_domain_flag": target_domain,
            "artifact_role": "training_keyframe::manual_physician_annotation",
            "usage_policy": usage_policy,
            "license": data_license,
            "medical_scene": "jaw osteomyelitis physician manual annotation" if target_domain else "case annotation",
            "split": "",
            "exclusion_reason": ";".join(exclusion_reasons),
            "medical_boundary": annotation.medical_boundary,
        }

    def _training_governance_evidence(
        self,
        case: CaseRecord | None,
        *,
        source_input_id: str | None,
        source_checksum_cache: dict[str, str] | None,
    ) -> tuple[list[str], dict[str, Any]]:
        reasons: list[str] = []
        evidence: dict[str, Any] = {
            "intake_authorization_status": None,
            "intake_usage_scope": None,
            "intake_deidentification_confirmed": False,
            "intake_mapping_held_by_institution": False,
            "intake_admission_status": None,
            "source_input_admission_status": None,
            "source_input_batch_id": None,
            "source_input_record_id": None,
            "source_input_checksum": None,
            "source_input_checksum_verified": False,
        }
        if case is None:
            return ["case_record_missing"], evidence

        intake = case.intake_metadata
        if intake is None:
            reasons.append("case_intake_metadata_missing")
        else:
            evidence.update(
                {
                    "intake_authorization_status": intake.authorization_status,
                    "intake_usage_scope": intake.usage_scope,
                    "intake_deidentification_confirmed": intake.deidentification_confirmed,
                    "intake_mapping_held_by_institution": intake.mapping_held_by_institution,
                    "intake_admission_status": intake.admission_status,
                }
            )
            if intake.authorization_status != "approved":
                reasons.append("case_training_authorization_not_approved")
            if not intake.deidentification_confirmed:
                reasons.append("case_deidentification_unconfirmed")
            if not intake.mapping_held_by_institution:
                reasons.append("case_mapping_custody_unconfirmed")
            if intake.admission_status not in TRAINING_INTAKE_ADMISSION_STATES:
                reasons.append("case_intake_not_admitted")
            if not _usage_scope_allows_training(intake.usage_scope):
                reasons.append("case_training_usage_not_authorized")

        if not source_input_id:
            reasons.append("source_input_not_bound")
            return reasons, evidence
        source_input = next((item for item in case.inputs if item.input_id == source_input_id), None)
        if source_input is None:
            reasons.append("source_input_missing")
            return reasons, evidence

        metadata = source_input.metadata
        evidence.update(
            {
                "source_input_admission_status": metadata.get("admission_status"),
                "source_input_batch_id": metadata.get("batch_id"),
                "source_input_record_id": metadata.get("intake_record_id"),
                "source_input_checksum": metadata.get("sha256"),
            }
        )
        if metadata.get("source_type") != "institutional_handover":
            reasons.append("source_input_institutional_handover_required")
        if metadata.get("admission_status") != "admitted":
            reasons.append("source_input_not_admitted")
        if metadata.get("authorization_status") != "approved":
            reasons.append("source_input_training_authorization_not_approved")
        if metadata.get("deidentification_confirmed") is not True:
            reasons.append("source_input_deidentification_unconfirmed")
        if not _usage_scope_allows_training(metadata.get("usage_scope")):
            reasons.append("source_input_training_usage_not_authorized")

        batch_id = str(metadata.get("batch_id") or "").strip()
        if not batch_id:
            reasons.append("source_input_batch_id_missing")
        elif intake is None or batch_id not in intake.batch_ids:
            reasons.append("source_input_batch_not_bound_to_case_intake")
        if not str(metadata.get("intake_record_id") or "").strip():
            reasons.append("source_input_intake_record_id_missing")
        if intake is not None:
            if metadata.get("source_organization") != intake.source_organization:
                reasons.append("source_input_organization_mismatch")
            if metadata.get("external_case_id") != intake.external_case_id:
                reasons.append("source_input_external_case_mismatch")

        expected_checksum = str(metadata.get("sha256") or "").strip().lower()
        if not _is_sha256(expected_checksum):
            reasons.append("source_input_checksum_invalid")
            return reasons, evidence
        source_path = Path(source_input.path)
        try:
            resolved_source = source_path.resolve(strict=True)
            resolved_source.relative_to(self.artifact_root.parent.resolve())
        except (OSError, ValueError):
            reasons.append("source_input_outside_controlled_storage_or_missing")
            return reasons, evidence

        cache = source_checksum_cache if source_checksum_cache is not None else {}
        cache_key = str(resolved_source)
        actual_checksum = cache.get(cache_key)
        if actual_checksum is None:
            actual_checksum = checksum_for_file(resolved_source)
            cache[cache_key] = actual_checksum
        verified = actual_checksum == expected_checksum
        evidence["source_input_checksum_verified"] = verified
        if not verified:
            reasons.append("source_input_checksum_mismatch")
        return reasons, evidence

    @staticmethod
    def _require_version(record: ManualAnnotationRecord, expected_version: int) -> None:
        if record.current_version != expected_version:
            from backend.src.domains.annotations.repository import AnnotationVersionConflictError

            raise AnnotationVersionConflictError(
                record.annotation_id,
                expected_version=expected_version,
                actual_version=record.current_version,
            )


def _render_annotation_mask(geometry: AnnotationGeometry, *, width: int, height: int) -> np.ndarray:
    canvas = Image.new("L", (width, height), color=0)
    draw = ImageDraw.Draw(canvas)
    for operation in geometry.operations:
        points = [
            _point_in_pixels(point.x, point.y, geometry.coordinate_space, width=width, height=height)
            for point in operation.points
        ]
        if operation.tool == AnnotationTool.POLYGON:
            fill = 0 if operation.mode == AnnotationOperationMode.ERASE else 255
            draw.polygon(points, fill=fill)
            continue
        fill = 0 if operation.tool == AnnotationTool.ERASER else 255
        radius = max(1, int(round(float(operation.radius or 1.0))))
        line_width = max(1, radius * 2)
        if len(points) > 1:
            draw.line(points, fill=fill, width=line_width, joint="curve")
        for x, y in (points if len(points) == 1 else (points[0], points[-1])):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
    return np.asarray(canvas, dtype=np.uint8)


def _point_in_pixels(
    x: float,
    y: float,
    coordinate_space: AnnotationCoordinateSpace,
    *,
    width: int,
    height: int,
) -> tuple[int, int]:
    if coordinate_space == AnnotationCoordinateSpace.NORMALIZED:
        px = round(max(0.0, min(1.0, x)) * max(0, width - 1))
        py = round(max(0.0, min(1.0, y)) * max(0, height - 1))
    else:
        px = round(max(0.0, min(float(width - 1), x)))
        py = round(max(0.0, min(float(height - 1), y)))
    return int(px), int(py)


def _find_run(case: CaseRecord, run_id: str | None) -> AnalysisRun:
    run = next((item for item in case.analysis_runs if item.run_id == run_id), None)
    if run is None:
        raise AnnotationValidationError("analysis run was not found")
    return run


def _find_frame(run: AnalysisRun, frame_index: int | None) -> dict[str, Any]:
    for key in ("frame_details", "keyframes", "hotspot_outputs"):
        items = run.fused_outputs.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and _optional_int(item.get("frame_index")) == frame_index:
                return item
    raise AnnotationValidationError("video keyframe was not found in the selected analysis run")


def _find_candidate(
    case: CaseRecord,
    candidate_id: str | None,
    *,
    run_id: str | None,
) -> tuple[AnalysisRun, CandidateRegion]:
    for run in case.analysis_runs:
        if run_id and run.run_id != run_id:
            continue
        for candidate in run.candidate_regions:
            if candidate.candidate_id == candidate_id:
                return run, candidate
    raise AnnotationValidationError("model candidate was not found")


def _frame_image_path(frame: dict[str, Any]) -> Path:
    for key in ("evidence_path", "source_path", "preview_path", "path"):
        value = frame.get(key)
        if value:
            try:
                return _readable_image_path(value)
            except AnnotationValidationError:
                continue
    raise AnnotationValidationError("video keyframe has no readable still-image evidence")


def _candidate_image_path(candidate: CandidateRegion) -> Path | None:
    for key in ("source_path", "evidence_path", "preview_path"):
        value = candidate.metadata.get(key)
        if value:
            try:
                return _readable_image_path(value)
            except AnnotationValidationError:
                continue
    return None


def _readable_image_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_STILL_SUFFIXES:
        raise AnnotationValidationError("annotation source image is missing or unsupported")
    _image_size(path)
    return path


def _image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise AnnotationValidationError("annotation source image is unreadable") from exc
    if width < 2 or height < 2:
        raise AnnotationValidationError("annotation source image dimensions are invalid")
    return int(width), int(height)


def _run_video_asset(case: CaseRecord, run: AnalysisRun) -> CaseInputAsset | None:
    source_path = str(run.fused_outputs.get("source_path") or "")
    for asset in case.inputs:
        if asset.channel != InputChannel.VIDEO:
            continue
        if source_path and Path(asset.path).resolve() == Path(source_path).resolve():
            return asset
    return next((asset for asset in case.inputs if asset.channel == InputChannel.VIDEO), None)


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


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _candidate_label_hint(candidate: CandidateRegion) -> AnnotationLabel:
    risk_type = str(candidate.risk_type or "").lower()
    if "bone" in risk_type:
        return AnnotationLabel.EXPOSED_BONE
    if "uncertain" in risk_type:
        return AnnotationLabel.UNCERTAIN
    if "risk" in risk_type or "boundary" in risk_type:
        return AnnotationLabel.BOUNDARY_RISK
    if "fluorescence" in risk_type or "hotspot" in risk_type:
        return AnnotationLabel.FLUORESCENCE_SIGNAL
    return AnnotationLabel.LESION


def _is_trusted_physician(actor: ReviewActorIdentity) -> bool:
    return actor.role == ReviewerRole.PHYSICIAN and actor.auth_source in TRUSTED_PHYSICIAN_AUTH_SOURCES


def _has_independent_physician_review(
    *,
    latest_author: ReviewActorIdentity,
    submitted_by: ReviewActorIdentity | None,
    reviewer: ReviewActorIdentity,
) -> bool:
    if submitted_by is None:
        return False
    return reviewer.actor_id not in {latest_author.actor_id, submitted_by.actor_id}


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "source"


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else value
