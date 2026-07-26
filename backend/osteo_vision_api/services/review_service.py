from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, NoReturn
from uuid import uuid4

import numpy as np
from PIL import Image

from backend.osteo_vision_api.core.artifacts import checksum_for_file
from backend.osteo_vision_api.domains.annotations.enums import AnnotationLabel, AnnotationSourceType, AnnotationStatus
from backend.osteo_vision_api.domains.annotations.repository import AnnotationRepository
from backend.osteo_vision_api.domains.annotations.schemas import ManualAnnotationRecord
from backend.osteo_vision_api.domains.cases.enums import (
    ArtifactKind,
    CaseStatus,
    RegionSource,
    ReviewerRole,
    ReviewState,
)
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    BoneGateMaskCreateRequest,
    BoneGateMaskEditRequest,
    CandidateRegion,
    CaseRecord,
    EvidenceArtifact,
    RegionOfInterest,
    RegionUpdateRequest,
    ReviewActorIdentity,
    ReviewEvent,
    ReviewEventCreateRequest,
)
from backend.osteo_vision_api.services.review_geometry import (
    bbox_xyxy_from_geometry,
    candidate_geometry,
    normalized_rect_geometry,
)
from osteo_vision_core.core.config import load_yaml
from osteo_vision_core.core.paths import ensure_dir, resolve_path
from osteo_vision_core.core.schemas import AdapterRequest
from osteo_vision_core.models.adapters import build_adapter, model_spec_from_mapping
from osteo_vision_core.models.video_signal_masks import save_bone_activity_candidate_maps

BONE_GATE_BOUNDARY = (
    "Bone gate mask is generated from reviewer ROI or prompt-assisted review using the MedSAM-like prompt "
    "fallback contract. It is not real MedSAM2 checkpoint inference and is not a clinical diagnosis."
)
EDITED_BONE_GATE_BOUNDARY = (
    "Bone gate mask was modified through platform review tooling. It is training feedback for the platform "
    "workflow and is not a standalone clinical diagnosis."
)
TRUSTED_PHYSICIAN_AUTH_SOURCES = {
    "institution_sso",
    "signed_session",
    "verified_identity_token",
}


class PromptFallbackSafetyError(ValueError):
    def __init__(self, *, code: str, runtime_profile: str, config_path: Path) -> None:
        self.code = code
        self.runtime_profile = runtime_profile
        self.config_path = config_path
        super().__init__(f"{code}: prompt-assisted fallback is disabled for runtime profile {runtime_profile}")

    def detail(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
            "runtime_profile": self.runtime_profile,
            "inference_config": str(self.config_path),
        }


class ActivityIgnoreMaskError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ReviewService:
    def __init__(
        self,
        repo: CaseRepository,
        inference_config_path: str | Path = "configs/inference/osteo_vision.yml",
        *,
        annotation_repository: AnnotationRepository | None = None,
        artifact_root: str | Path | None = None,
    ) -> None:
        self.repo = repo
        self.inference_config_path = resolve_path(inference_config_path).resolve()
        self.annotation_repository = annotation_repository
        root = Path(artifact_root) if artifact_root is not None else resolve_path("artifacts")
        self.activity_spectrum_root = ensure_dir(root / "visual_evidence" / "osteo_vision" / "bone_activity_spectrum")

    def update_region(
        self,
        case: CaseRecord,
        region_id: str,
        request: RegionUpdateRequest,
        actor: ReviewActorIdentity,
    ) -> CaseRecord:
        rois: list[RegionOfInterest] = []
        found = False
        before_state: str | None = None
        for roi in case.rois:
            if roi.roi_id != region_id:
                rois.append(roi)
                continue
            found = True
            before_state = roi.review_state.value
            rois.append(
                roi.model_copy(
                    update={
                        "review_state": request.review_state,
                        "geometry": request.geometry if request.geometry is not None else roi.geometry,
                        "label": request.label if request.label is not None else roi.label,
                    }
                )
            )
        if not found:
            rois.append(
                RegionOfInterest(
                    roi_id=region_id,
                    case_id=case.case_id,
                    source=RegionSource.MANUAL,
                    geometry=request.geometry or {},
                    label=request.label,
                    review_state=request.review_state,
                )
            )
        event = _review_event(
            case_id=case.case_id,
            actor=actor,
            action="region_state_update",
            target_id=region_id,
            before_state=before_state,
            after_state=request.review_state.value,
            notes=request.reviewer_notes,
        )
        updated = case.model_copy(
            update={"rois": rois, "review_events": [*case.review_events, event], "status": CaseStatus.REVIEWING}
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def add_review_event(
        self,
        case: CaseRecord,
        request: ReviewEventCreateRequest,
        actor: ReviewActorIdentity,
    ) -> CaseRecord:
        event = _review_event(
            case_id=case.case_id,
            actor=actor,
            action=request.action,
            target_id=request.target_id,
            before_state=request.before_state,
            after_state=request.after_state,
            notes=request.notes,
        )
        updated = case.model_copy(
            update={"review_events": [*case.review_events, event], "status": CaseStatus.REVIEWING}
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def validate_reviewed_ignore_annotation(self, annotation: ManualAnnotationRecord) -> None:
        """Validate an independently reviewed physician ignore annotation against its candidate source."""

        if not _is_qualifying_ignore_annotation(annotation):
            return
        case = self.repo.get(annotation.case_id)
        if case is None:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_case_missing",
                f"Ignore annotation case is missing: {annotation.case_id}",
            )
        run, candidate = _find_candidate_with_run(case, str(annotation.source.candidate_id or ""))
        if run is None or candidate is None:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_candidate_missing",
                f"Ignore annotation candidate is missing: {annotation.source.candidate_id}",
            )
        _validate_ignore_annotation_link(
            annotation,
            case=case,
            run=run,
            candidate=candidate,
            annotation_repository=self.annotation_repository,
        )

    def synchronize_reviewed_ignore_annotations(self, case_id: str, candidate_id: str) -> CaseRecord:
        """Union independently reviewed physician ignore masks and re-materialize the activity spectrum."""

        if self.annotation_repository is None:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_repository_unavailable",
                "Reviewed ignore synchronization requires the annotation repository",
            )
        case = self.repo.get(case_id)
        if case is None:
            raise ActivityIgnoreMaskError("ignore_annotation_case_missing", f"Case is missing: {case_id}")
        run, candidate = _find_candidate_with_run(case, candidate_id)
        if run is None or candidate is None:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_candidate_missing",
                f"Candidate is missing: {candidate_id}",
            )

        metadata = dict(candidate.metadata)
        previous_signal_masks = _candidate_signal_masks(metadata)
        stale_paths = _activity_evidence_paths(previous_signal_masks)
        annotations = [
            annotation
            for annotation in self.annotation_repository.list_records(case_id=case_id)
            if _annotation_targets_candidate(annotation, candidate_id) and _is_qualifying_ignore_annotation(annotation)
        ]
        if not annotations:
            return case
        review_context = max(
            annotations,
            key=lambda item: item.reviewed_at or item.updated_at,
        )

        try:
            combined_mask, provenance = _union_reviewed_ignore_annotations(
                annotations,
                case=case,
                run=run,
                candidate=candidate,
                annotation_repository=self.annotation_repository,
            )
            union_record = self._write_physician_ignore_union(
                case_id=case_id,
                candidate_id=candidate_id,
                mask=combined_mask,
                provenance=provenance,
            )
            signal_masks = dict(previous_signal_masks)
            signal_masks["schema_version"] = "osteo-vision-video-signal-masks-v2"
            signal_masks["physician_ignore_mask"] = union_record
            signal_masks = _derive_reviewed_activity_spectrum(
                signal_masks=signal_masks,
                actor=review_context.reviewed_by or review_context.latest_author,
                review_state=review_context.status.value,
                case_id=case_id,
                candidate_id=candidate_id,
                output_root=self.activity_spectrum_root,
            )
            spectrum = signal_masks.get("bone_activity_spectrum")
            if not isinstance(spectrum, dict) or spectrum.get("available") is not True:
                status = str(spectrum.get("status") if isinstance(spectrum, dict) else "activity_spectrum_unavailable")
                raise ActivityIgnoreMaskError(status, f"Reviewed ignore spectrum derivation failed: {status}")
            partition = spectrum.get("partition_check")
            if not isinstance(partition, dict) or partition.get("valid") is not True:
                raise ActivityIgnoreMaskError(
                    "activity_partition_invalid",
                    "Reviewed bone activity classes and ignore region do not form a valid partition",
                )
            _validate_activity_spectrum_evidence(
                spectrum, expected_size=(combined_mask.shape[1], combined_mask.shape[0])
            )
            _validate_video_segmentation_manifest_target(
                run.fused_outputs,
                frame_order=metadata.get("frame_order"),
                frame_index=metadata.get("frame_index"),
            )
        except ActivityIgnoreMaskError as exc:
            return self._fail_closed_reviewed_ignore_sync(
                case=case,
                run=run,
                candidate=candidate,
                signal_masks=previous_signal_masks,
                stale_paths=stale_paths,
                code=exc.code,
                reason=str(exc),
                attempted_annotations=annotations,
            )
        except (OSError, ValueError) as exc:
            return self._fail_closed_reviewed_ignore_sync(
                case=case,
                run=run,
                candidate=candidate,
                signal_masks=previous_signal_masks,
                stale_paths=stale_paths,
                code="reviewed_ignore_derivation_failed",
                reason=str(exc),
                attempted_annotations=annotations,
            )

        updated_metadata = {
            **metadata,
            "video_signal_segmentation": signal_masks,
            "signal_masks": signal_masks,
            "physician_ignore_annotation_count": len(provenance),
            "physician_ignore_annotation_ids": [item["annotation_id"] for item in provenance],
            "physician_ignore_sync_status": "applied",
            "physician_ignore_synced_at": datetime.now(timezone.utc).isoformat(),
        }
        updated_candidate = candidate.model_copy(update={"metadata": updated_metadata})
        bone_gate_entry = dict(signal_masks.get("bone_gate_mask") or {})
        runs = [
            _run_with_candidate_and_bone_gate(item, candidate_id, updated_candidate, signal_masks, bone_gate_entry)
            for item in case.analysis_runs
        ]
        target_run = next(item for item in runs if item.run_id == run.run_id)
        try:
            _patch_video_segmentation_manifest_file(
                target_run.fused_outputs,
                frame_order=metadata.get("frame_order"),
                frame_index=metadata.get("frame_index"),
                signal_masks=signal_masks,
                strict=True,
            )
        except ActivityIgnoreMaskError as exc:
            return self._fail_closed_reviewed_ignore_sync(
                case=case,
                run=run,
                candidate=candidate,
                signal_masks=previous_signal_masks,
                stale_paths=stale_paths,
                code=exc.code,
                reason=str(exc),
                attempted_annotations=annotations,
            )
        evidence = [
            *_physician_ignore_annotation_artifacts(case_id, run.run_id, union_record, provenance),
            *_activity_spectrum_artifacts(case_id, run.run_id, signal_masks),
        ]
        event = _review_event(
            case_id=case_id,
            actor=review_context.reviewed_by or review_context.latest_author,
            action="physician_ignore_annotations_synchronized",
            target_id=candidate_id,
            before_state=str(metadata.get("physician_ignore_sync_status") or "not_applied"),
            after_state="applied",
            notes=f"{len(provenance)} trusted physician ignore annotation(s) unioned",
        )
        updated = case.model_copy(
            update={
                "analysis_runs": runs,
                "artifacts": _replace_activity_evidence(case.artifacts, stale_paths=stale_paths, additions=evidence),
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        return self.repo.save(updated)

    def _write_physician_ignore_union(
        self,
        *,
        case_id: str,
        candidate_id: str,
        mask: np.ndarray,
        provenance: list[dict[str, Any]],
    ) -> dict[str, Any]:
        digest_source = "|".join(f"{item['annotation_id']}:{item['version']}:{item['sha256']}" for item in provenance)
        digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
        output_dir = ensure_dir(self.activity_spectrum_root / case_id / "physician_ignore_annotations")
        output_path = output_dir / f"{_safe_name(candidate_id)}_{digest}_union.png"
        Image.fromarray(mask.astype(np.uint8) * 255).save(output_path, format="PNG")
        return {
            "mask_type": "ignore",
            "available": True,
            "status": "trusted_physician_reviewed_union",
            "path": str(output_path),
            "sha256": checksum_for_file(output_path),
            "format": "png_binary_mask",
            "label_source": "trusted_physician_manual_annotation",
            "review_state": "accepted_or_modified",
            "annotation_count": len(provenance),
            "annotations": provenance,
            "medical_boundary": (
                "Physician-reviewed ignore regions mark pixels that must remain outside low, transition, and high "
                "activity spatial candidates."
            ),
        }

    def _fail_closed_reviewed_ignore_sync(
        self,
        *,
        case: CaseRecord,
        run: Any,
        candidate: CandidateRegion,
        signal_masks: dict[str, Any],
        stale_paths: set[str],
        code: str,
        reason: str,
        attempted_annotations: list[ManualAnnotationRecord],
    ) -> CaseRecord:
        failed_masks = dict(signal_masks)
        failed_masks["schema_version"] = "osteo-vision-video-signal-masks-v2"
        failed_masks["physician_ignore_mask"] = {
            "available": False,
            "status": code,
            "path": None,
            "sha256": None,
            "annotations": [],
            "attempted_annotations": [
                {
                    "annotation_id": item.annotation_id,
                    "version": item.current_version,
                    "path": item.mask_path,
                    "declared_sha256": item.mask_checksum,
                    "review_state": item.status.value,
                    "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
                    "reviewer": _review_identity_snapshot(item.reviewed_by) if item.reviewed_by else None,
                }
                for item in attempted_annotations
            ],
            "failure_reason": reason,
        }
        failed_masks["bone_activity_spectrum"] = _unavailable_activity_spectrum(
            failed_masks.get("bone_activity_spectrum"),
            status=code,
            failure_reason=reason,
        )
        metadata = dict(candidate.metadata)
        failed_metadata = {
            **metadata,
            "video_signal_segmentation": failed_masks,
            "signal_masks": failed_masks,
            "physician_ignore_sync_status": "failed_closed",
            "physician_ignore_sync_failure_code": code,
            "physician_ignore_sync_failure_reason": reason,
            "physician_ignore_synced_at": datetime.now(timezone.utc).isoformat(),
        }
        failed_candidate = candidate.model_copy(update={"metadata": failed_metadata})
        bone_gate_entry = dict(failed_masks.get("bone_gate_mask") or {})
        runs = [
            _run_with_candidate_and_bone_gate(
                item, candidate.candidate_id, failed_candidate, failed_masks, bone_gate_entry
            )
            for item in case.analysis_runs
        ]
        event_actor = ReviewActorIdentity(
            actor_id="system-safety-gate",
            role=ReviewerRole.ENGINEERING_REVIEWER,
            institution="Osteo Vision Platform",
            auth_source="signed_session",
        )
        event = _review_event(
            case_id=case.case_id,
            actor=event_actor,
            action="physician_ignore_annotations_failed_closed",
            target_id=candidate.candidate_id,
            before_state=str(metadata.get("physician_ignore_sync_status") or "not_applied"),
            after_state="failed_closed",
            notes=f"{code}: {reason}",
        )
        updated = case.model_copy(
            update={
                "analysis_runs": runs,
                "artifacts": _replace_activity_evidence(case.artifacts, stale_paths=stale_paths, additions=[]),
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        return self.repo.save(updated)

    def candidate_to_roi(self, case: CaseRecord, candidate: CandidateRegion) -> RegionOfInterest:
        geometry = candidate_geometry(candidate)
        return RegionOfInterest(
            roi_id=f"roi_{candidate.candidate_id}",
            case_id=case.case_id,
            source=RegionSource.AI,
            geometry=geometry,
            label=candidate.risk_type,
            metrics={
                "score": candidate.score,
                "confidence": candidate.confidence,
                "frame_index": candidate.metadata.get("frame_index"),
                "timestamp_sec": candidate.metadata.get("timestamp_sec"),
                "positive_area_fraction": candidate.metadata.get("positive_area_fraction"),
                "mask_type": candidate.metadata.get("mask_type"),
                "mask_path": candidate.metadata.get("mask_path"),
                "label_source": candidate.metadata.get("label_source"),
                "prompt_source": candidate.metadata.get("prompt_source"),
                "sample_weight": _sample_weight_for_review_state(candidate.status.value),
                "risk_mask_path": candidate.metadata.get("risk_mask_path"),
                "uncertain_mask_path": candidate.metadata.get("uncertain_mask_path"),
                "bone_gate_status": candidate.metadata.get("bone_gate_status"),
                "bone_gate_mask_path": candidate.metadata.get("bone_gate_mask_path"),
                "bone_gate_overlay_path": candidate.metadata.get("bone_gate_overlay_path"),
            },
            review_state=candidate.status,
            candidate_id=candidate.candidate_id,
        )

    def add_candidate_roi(
        self,
        case: CaseRecord,
        candidate_id: str,
        actor: ReviewActorIdentity,
    ) -> CaseRecord:
        candidate = _find_candidate(case, candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate not found: {candidate_id}")
        roi = self.candidate_to_roi(case, candidate)
        rois = [existing for existing in case.rois if existing.roi_id != roi.roi_id]
        event = _review_event(
            case_id=case.case_id,
            actor=actor,
            action="candidate_promoted_to_roi",
            target_id=candidate_id,
            before_state=candidate.status.value,
            after_state=roi.review_state.value,
        )
        updated = case.model_copy(
            update={
                "rois": [*rois, roi],
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def generate_candidate_bone_gate_mask(
        self,
        case: CaseRecord,
        candidate_id: str,
        request: BoneGateMaskCreateRequest,
        actor: ReviewActorIdentity,
    ) -> CaseRecord:
        run, candidate = _find_candidate_with_run(case, candidate_id)
        if candidate is None or run is None:
            raise ValueError(f"Candidate not found: {candidate_id}")
        metadata = dict(candidate.metadata)
        source_path = _candidate_source_path(metadata)
        if source_path is None:
            raise ValueError(f"Candidate has no readable keyframe source path: {candidate_id}")
        geometry = _prompt_geometry(request.geometry, metadata)
        if geometry is None:
            raise ValueError(f"Candidate has no bbox/ROI geometry for bone gate prompt: {candidate_id}")

        payload, warnings = _run_bone_gate_prompt_fallback(
            source_path=source_path,
            case_id=case.case_id,
            candidate_id=candidate_id,
            geometry=geometry,
            prompt_source=request.prompt_source,
            config_path=self.inference_config_path,
        )
        segmentation_mask = payload["segmentation_mask"]
        lesion_evidence = payload["lesion_evidence"]
        mask_path = str(segmentation_mask["path"])
        overlay_path = str(lesion_evidence["overlay_path"])
        bone_gate_entry = _bone_gate_entry(
            mask_path=mask_path,
            overlay_path=overlay_path,
            geometry=geometry,
            prompt_source=request.prompt_source,
            review_state=request.review_state.value,
        )
        signal_masks = _updated_signal_masks(metadata, bone_gate_entry)
        signal_masks = _derive_reviewed_activity_spectrum(
            signal_masks=signal_masks,
            actor=actor,
            review_state=request.review_state.value,
            case_id=case.case_id,
            candidate_id=candidate_id,
            output_root=self.activity_spectrum_root,
        )
        previous_mask_path = metadata.get("mask_path")
        updated_metadata = {
            **metadata,
            "signal_mask_path": previous_mask_path,
            "fluorescence_signal_mask_path": _fluorescence_signal_path(metadata),
            "mask_path": mask_path,
            "mask_type": "exposed_bone",
            "bone_gate_mask_path": mask_path,
            "bone_gate_overlay_path": overlay_path,
            "bone_gate_status": "prompt_assisted_review",
            "label_source": "prompt_assisted_review",
            "prompt_source": request.prompt_source,
            "prompt_geometry": geometry,
            "prompt_contract_fallback": True,
            "sample_weight": _sample_weight_for_review_state(request.review_state.value),
            "review_label": request.label or "exposed_bone",
            "reviewer_notes": request.reviewer_notes or metadata.get("reviewer_notes"),
            "reviewer_identity": _review_identity_snapshot(actor),
            "video_signal_segmentation": signal_masks,
            "signal_masks": signal_masks,
            "medical_boundary": BONE_GATE_BOUNDARY,
            "bone_gate_generated_at": datetime.now(timezone.utc).isoformat(),
            "bone_gate_warnings": warnings,
        }
        updated_candidate = candidate.model_copy(update={"status": request.review_state, "metadata": updated_metadata})
        runs = [
            _run_with_candidate_and_bone_gate(run_item, candidate_id, updated_candidate, signal_masks, bone_gate_entry)
            for run_item in case.analysis_runs
        ]
        event = _review_event(
            case_id=case.case_id,
            actor=actor,
            action="bone_gate_mask_generated",
            target_id=candidate_id,
            before_state=candidate.status.value,
            after_state=request.review_state.value,
            notes=request.reviewer_notes or BONE_GATE_BOUNDARY,
        )
        artifacts = [
            *case.artifacts,
            *_bone_gate_artifacts(case.case_id, run.run_id, mask_path=mask_path, overlay_path=overlay_path),
            *_activity_spectrum_artifacts(case.case_id, run.run_id, signal_masks),
        ]
        updated = case.model_copy(
            update={
                "analysis_runs": runs,
                "artifacts": artifacts,
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
                "warnings": [*case.warnings, *warnings],
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def save_candidate_bone_gate_mask_edit(
        self,
        case: CaseRecord,
        candidate_id: str,
        request: BoneGateMaskEditRequest,
        actor: ReviewActorIdentity,
    ) -> CaseRecord:
        run, candidate = _find_candidate_with_run(case, candidate_id)
        if candidate is None or run is None:
            raise ValueError(f"Candidate not found: {candidate_id}")
        metadata = dict(candidate.metadata)
        source_path = _candidate_source_path(metadata)
        if source_path is None:
            raise ValueError(f"Candidate has no readable keyframe source path: {candidate_id}")
        geometry = _prompt_geometry(metadata.get("prompt_geometry"), metadata) or _prompt_geometry(None, metadata) or {}
        mask_path, overlay_path, mask_size = _save_edited_bone_gate_mask(
            source_path=source_path,
            mask_png_base64=request.mask_png_base64,
            case_id=case.case_id,
            candidate_id=candidate_id,
        )
        provenance = _modified_mask_provenance(actor)
        bone_gate_entry = _bone_gate_entry(
            mask_path=mask_path,
            overlay_path=overlay_path,
            geometry=geometry,
            prompt_source="frontend_mask_editor",
            review_state=request.review_state.value,
            status=provenance,
            label_source=provenance,
            fallback_mode=False,
            medical_boundary=EDITED_BONE_GATE_BOUNDARY,
        )
        signal_masks = _updated_signal_masks(metadata, bone_gate_entry)
        signal_masks = _derive_reviewed_activity_spectrum(
            signal_masks=signal_masks,
            actor=actor,
            review_state=request.review_state.value,
            case_id=case.case_id,
            candidate_id=candidate_id,
            output_root=self.activity_spectrum_root,
        )
        updated_metadata = {
            **metadata,
            "signal_mask_path": metadata.get("signal_mask_path") or metadata.get("fluorescence_signal_mask_path"),
            "fluorescence_signal_mask_path": _fluorescence_signal_path(metadata),
            "mask_path": mask_path,
            "mask_type": "exposed_bone",
            "bone_gate_mask_path": mask_path,
            "bone_gate_overlay_path": overlay_path,
            "bone_gate_status": provenance,
            "label_source": provenance,
            "prompt_source": "frontend_mask_editor",
            "prompt_geometry": geometry,
            "prompt_contract_fallback": False,
            "sample_weight": _sample_weight_for_review_state(request.review_state.value),
            "review_label": request.label or "exposed_bone",
            "reviewer_notes": request.reviewer_notes or metadata.get("reviewer_notes"),
            "reviewer_identity": _review_identity_snapshot(actor),
            "edited_mask_size": mask_size,
            "video_signal_segmentation": signal_masks,
            "signal_masks": signal_masks,
            "medical_boundary": EDITED_BONE_GATE_BOUNDARY,
            "bone_gate_edited_at": datetime.now(timezone.utc).isoformat(),
        }
        updated_candidate = candidate.model_copy(update={"status": request.review_state, "metadata": updated_metadata})
        runs = [
            _run_with_candidate_and_bone_gate(run_item, candidate_id, updated_candidate, signal_masks, bone_gate_entry)
            for run_item in case.analysis_runs
        ]
        event = _review_event(
            case_id=case.case_id,
            actor=actor,
            action="bone_gate_mask_edited",
            target_id=candidate_id,
            before_state=candidate.status.value,
            after_state=request.review_state.value,
            notes=request.reviewer_notes or EDITED_BONE_GATE_BOUNDARY,
        )
        artifacts = [
            *case.artifacts,
            *_bone_gate_artifacts(case.case_id, run.run_id, mask_path=mask_path, overlay_path=overlay_path),
            *_activity_spectrum_artifacts(case.case_id, run.run_id, signal_masks),
        ]
        updated = case.model_copy(
            update={
                "analysis_runs": runs,
                "artifacts": artifacts,
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def update_candidate_region(
        self,
        case: CaseRecord,
        candidate_id: str,
        request: RegionUpdateRequest,
        actor: ReviewActorIdentity,
    ) -> CaseRecord:
        runs = []
        found = False
        before_state: str | None = None
        for run in case.analysis_runs:
            candidates = []
            for candidate in run.candidate_regions:
                if candidate.candidate_id != candidate_id:
                    candidates.append(candidate)
                    continue
                found = True
                before_state = candidate.status.value
                metadata = dict(candidate.metadata)
                if request.reviewer_notes:
                    metadata["reviewer_notes"] = request.reviewer_notes
                if request.label is not None:
                    metadata["review_label"] = request.label
                metadata["reviewer_identity"] = _review_identity_snapshot(actor)
                metadata["sample_weight"] = _sample_weight_for_review_state(request.review_state.value)
                if request.geometry is not None:
                    geometry = normalized_rect_geometry(request.geometry)
                    metadata["bbox_normalized"] = geometry
                    metadata["review_geometry"] = geometry
                    metadata["geometry_reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    metadata["geometry_review_source"] = actor.role.value
                    bbox_xyxy = bbox_xyxy_from_geometry(
                        geometry,
                        image_width=metadata.get("image_width"),
                        image_height=metadata.get("image_height"),
                    )
                    if bbox_xyxy is not None:
                        metadata["bbox_xyxy"] = bbox_xyxy
                candidates.append(candidate.model_copy(update={"status": request.review_state, "metadata": metadata}))
            runs.append(run.model_copy(update={"candidate_regions": candidates}))
        if not found:
            raise ValueError(f"Candidate not found: {candidate_id}")
        event = _review_event(
            case_id=case.case_id,
            actor=actor,
            action="candidate_region_state_update",
            target_id=candidate_id,
            before_state=before_state,
            after_state=request.review_state.value,
            notes=request.reviewer_notes,
        )
        updated = case.model_copy(
            update={
                "analysis_runs": runs,
                "review_events": [*case.review_events, event],
                "status": CaseStatus.REVIEWING,
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def _review_summary(self, case: CaseRecord) -> dict[str, object]:
        region_counts = {state: 0 for state in (ReviewState.ACCEPTED, ReviewState.MODIFIED, ReviewState.REJECTED)}
        for roi in case.rois:
            if roi.review_state in region_counts:
                region_counts[roi.review_state] += 1
        candidate_counts = {state: 0 for state in (ReviewState.ACCEPTED, ReviewState.MODIFIED, ReviewState.REJECTED)}
        for run in case.analysis_runs:
            for candidate in run.candidate_regions:
                if candidate.status in candidate_counts:
                    candidate_counts[candidate.status] += 1
        return {
            **case.review_summary,
            "accepted_regions": region_counts[ReviewState.ACCEPTED],
            "modified_regions": region_counts[ReviewState.MODIFIED],
            "rejected_regions": region_counts[ReviewState.REJECTED],
            "accepted_candidates": candidate_counts[ReviewState.ACCEPTED],
            "modified_candidates": candidate_counts[ReviewState.MODIFIED],
            "rejected_candidates": candidate_counts[ReviewState.REJECTED],
            "total_review_events": len(case.review_events),
            "status": case.status,
        }


def _review_event(
    *,
    case_id: str,
    actor: ReviewActorIdentity,
    action: str,
    target_id: str,
    before_state: str | None = None,
    after_state: str | None = None,
    notes: str | None = None,
) -> ReviewEvent:
    return ReviewEvent(
        event_id=f"event_{uuid4().hex[:10]}",
        case_id=case_id,
        actor=actor.actor_id,
        actor_id=actor.actor_id,
        role=actor.role,
        institution=actor.institution,
        auth_source=actor.auth_source,
        action=action,
        target_id=target_id,
        before_state=before_state,
        after_state=after_state,
        timestamp=datetime.now(timezone.utc),
        notes=notes,
    )


def _review_identity_snapshot(actor: ReviewActorIdentity) -> dict[str, str]:
    return {
        "actor_id": actor.actor_id,
        "role": actor.role.value,
        "institution": actor.institution,
        "auth_source": actor.auth_source,
    }


def _modified_mask_provenance(actor: ReviewActorIdentity) -> str:
    if actor.role == ReviewerRole.PHYSICIAN:
        return "physician_modified_mask"
    if actor.role == ReviewerRole.PROJECT_REVIEWER:
        return "project_reviewer_modified_mask"
    return "engineering_reviewer_modified_mask"


def _find_candidate(case: CaseRecord, candidate_id: str) -> CandidateRegion | None:
    for run in reversed(case.analysis_runs):
        for candidate in run.candidate_regions:
            if candidate.candidate_id == candidate_id:
                return candidate
    return None


def _find_candidate_with_run(case: CaseRecord, candidate_id: str) -> tuple[Any | None, CandidateRegion | None]:
    for run in reversed(case.analysis_runs):
        for candidate in run.candidate_regions:
            if candidate.candidate_id == candidate_id:
                return run, candidate
    return None, None


def _candidate_signal_masks(metadata: dict[str, Any]) -> dict[str, Any]:
    value = metadata.get("video_signal_segmentation") or metadata.get("signal_masks") or {}
    return dict(value) if isinstance(value, dict) else {}


def _annotation_targets_candidate(annotation: ManualAnnotationRecord, candidate_id: str) -> bool:
    return (
        annotation.label == AnnotationLabel.IGNORE
        and annotation.source.source_type == AnnotationSourceType.MODEL_CANDIDATE
        and annotation.source.candidate_id == candidate_id
    )


def _trusted_physician(actor: ReviewActorIdentity | None) -> bool:
    return bool(actor and actor.role == ReviewerRole.PHYSICIAN and actor.auth_source in TRUSTED_PHYSICIAN_AUTH_SOURCES)


def _has_independent_physician_review(annotation: ManualAnnotationRecord) -> bool:
    submitter = annotation.submitted_by
    reviewer = annotation.reviewed_by
    return bool(
        submitter
        and reviewer
        and reviewer.actor_id
        not in {
            annotation.latest_author.actor_id,
            submitter.actor_id,
        }
    )


def _is_qualifying_ignore_annotation(annotation: ManualAnnotationRecord) -> bool:
    return bool(
        annotation.label == AnnotationLabel.IGNORE
        and annotation.source.source_type == AnnotationSourceType.MODEL_CANDIDATE
        and annotation.source.candidate_id
        and annotation.status in {AnnotationStatus.ACCEPTED, AnnotationStatus.MODIFIED}
        and annotation.positive_pixel_count > 0
        and _trusted_physician(annotation.latest_author)
        and _trusted_physician(annotation.submitted_by)
        and _trusted_physician(annotation.reviewed_by)
        and _has_independent_physician_review(annotation)
    )


def _validate_ignore_annotation_link(
    annotation: ManualAnnotationRecord,
    *,
    case: CaseRecord,
    run: Any,
    candidate: CandidateRegion,
    annotation_repository: AnnotationRepository | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    def fail(code: str, message: str) -> NoReturn:
        raise ActivityIgnoreMaskError(code, message)

    if annotation.case_id != case.case_id:
        fail("ignore_annotation_case_mismatch", "Ignore annotation case does not match the candidate case")
    if annotation.source.candidate_id != candidate.candidate_id:
        fail("ignore_annotation_candidate_mismatch", "Ignore annotation candidate link does not match")
    if annotation.source.run_id != run.run_id or candidate.run_id != run.run_id:
        fail("ignore_annotation_run_mismatch", "Ignore annotation run link does not match the candidate run")
    expected_key = f"model_candidate:{candidate.candidate_id}"
    if annotation.source.source_key != expected_key or annotation.source.source_id not in {None, expected_key}:
        fail("ignore_annotation_source_key_mismatch", "Ignore annotation source key does not match the candidate")
    candidate_frame_index = candidate.metadata.get("frame_index")
    if candidate_frame_index is not None:
        try:
            normalized_frame_index = int(candidate_frame_index)
        except (TypeError, ValueError) as exc:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_candidate_frame_invalid",
                "Candidate frame index is invalid",
            ) from exc
        if annotation.source.frame_index != normalized_frame_index:
            fail("ignore_annotation_frame_mismatch", "Ignore annotation frame does not match the candidate frame")
    if (
        annotation.original_width != annotation.source.original_width
        or annotation.original_height != annotation.source.original_height
    ):
        fail("ignore_annotation_dimension_metadata_mismatch", "Ignore annotation dimensions disagree with its source")
    if annotation.source_checksum != annotation.source.source_checksum:
        fail("ignore_annotation_source_checksum_mismatch", "Ignore annotation source checksums disagree")

    candidate_path = _candidate_source_path(dict(candidate.metadata))
    if candidate_path is None or not candidate_path.is_file():
        fail("ignore_annotation_candidate_source_missing", "Current candidate source image is missing")
    descriptor_path = resolve_path(annotation.source.source_path).resolve()
    snapshot_path = resolve_path(annotation.source_snapshot_path).resolve()
    for name, path in (("descriptor", descriptor_path), ("snapshot", snapshot_path)):
        if not path.is_file():
            fail("ignore_annotation_source_missing", f"Ignore annotation {name} source image is missing")
        if checksum_for_file(path) != annotation.source_checksum:
            fail("ignore_annotation_source_checksum_mismatch", f"Ignore annotation {name} source checksum changed")
    if checksum_for_file(candidate_path) != annotation.source_checksum:
        fail("ignore_annotation_candidate_source_mismatch", "Current candidate source image changed after annotation")

    expected_size = (annotation.original_width, annotation.original_height)
    candidate_metadata = dict(candidate.metadata)
    declared_width = candidate_metadata.get("image_width") or candidate_metadata.get("source_video_width")
    declared_height = candidate_metadata.get("image_height") or candidate_metadata.get("source_video_height")
    if declared_width is not None and declared_height is not None:
        try:
            declared_size = (int(declared_width), int(declared_height))
        except (TypeError, ValueError) as exc:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_candidate_dimension_invalid",
                "Candidate source dimensions are invalid",
            ) from exc
        if declared_size != expected_size:
            fail(
                "ignore_annotation_candidate_dimension_mismatch",
                f"Candidate source dimensions {declared_size} do not match {expected_size}",
            )
    for name, path in (("candidate", candidate_path), ("descriptor", descriptor_path), ("snapshot", snapshot_path)):
        try:
            with Image.open(path) as image:
                image.load()
                actual_size = image.size
        except (OSError, ValueError) as exc:
            raise ActivityIgnoreMaskError(
                "ignore_annotation_source_invalid",
                f"Ignore annotation {name} source cannot be decoded",
            ) from exc
        if actual_size != expected_size:
            fail(
                "ignore_annotation_source_size_mismatch",
                f"Ignore annotation {name} source size {actual_size} does not match {expected_size}",
            )

    mask_path = resolve_path(annotation.mask_path).resolve()
    if not mask_path.is_file():
        fail("ignore_annotation_mask_missing", f"Ignore annotation mask is missing: {mask_path}")
    actual_sha256 = checksum_for_file(mask_path)
    if actual_sha256 != annotation.mask_checksum:
        fail("ignore_annotation_mask_checksum_mismatch", "Ignore annotation mask checksum changed")
    try:
        with Image.open(mask_path) as image:
            image.load()
            if image.size != expected_size:
                fail(
                    "ignore_annotation_mask_size_mismatch",
                    f"Ignore annotation mask size {image.size} does not match {expected_size}",
                )
            mask = np.asarray(image.convert("L"), dtype=np.uint8) > 0
    except ActivityIgnoreMaskError:
        raise
    except (OSError, ValueError) as exc:
        raise ActivityIgnoreMaskError(
            "ignore_annotation_mask_invalid",
            f"Ignore annotation mask cannot be decoded: {mask_path}",
        ) from exc
    if int(mask.sum()) != annotation.positive_pixel_count or not mask.any():
        fail("ignore_annotation_mask_content_mismatch", "Ignore annotation mask content does not match metadata")

    if annotation_repository is None:
        fail("ignore_annotation_repository_unavailable", "Ignore annotation version repository is unavailable")
    versions = annotation_repository.versions(annotation.annotation_id)
    version = next((item for item in versions if item.version == annotation.current_version), None)
    if version is None:
        fail("ignore_annotation_version_missing", "Ignore annotation current version record is missing")
    if resolve_path(version.mask_path).resolve() != mask_path or version.mask_checksum != actual_sha256:
        fail("ignore_annotation_version_mismatch", "Ignore annotation current version path or checksum does not match")
    if (
        version.author != annotation.latest_author
        or version.geometry != annotation.geometry
        or version.positive_pixel_count != annotation.positive_pixel_count
    ):
        fail("ignore_annotation_version_mismatch", "Ignore annotation current version provenance does not match")

    reviewer = annotation.reviewed_by
    provenance = {
        "source_type": "physician_ignore_annotation",
        "annotation_id": annotation.annotation_id,
        "version": annotation.current_version,
        "case_id": annotation.case_id,
        "run_id": run.run_id,
        "candidate_id": candidate.candidate_id,
        "path": str(mask_path),
        "sha256": actual_sha256,
        "source_path": str(candidate_path),
        "source_sha256": annotation.source_checksum,
        "original_width": annotation.original_width,
        "original_height": annotation.original_height,
        "review_state": annotation.status.value,
        "reviewed_at": annotation.reviewed_at.isoformat() if annotation.reviewed_at else None,
        "reviewer": _review_identity_snapshot(reviewer) if reviewer else None,
        "submitted_by": _review_identity_snapshot(annotation.submitted_by) if annotation.submitted_by else None,
        "latest_author": _review_identity_snapshot(annotation.latest_author),
    }
    return mask, provenance


def _union_reviewed_ignore_annotations(
    annotations: list[ManualAnnotationRecord],
    *,
    case: CaseRecord,
    run: Any,
    candidate: CandidateRegion,
    annotation_repository: AnnotationRepository,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    combined: np.ndarray | None = None
    provenance: list[dict[str, Any]] = []
    for annotation in sorted(annotations, key=lambda item: (item.annotation_id, item.current_version)):
        mask, item_provenance = _validate_ignore_annotation_link(
            annotation,
            case=case,
            run=run,
            candidate=candidate,
            annotation_repository=annotation_repository,
        )
        combined = mask.copy() if combined is None else combined | mask
        provenance.append(item_provenance)
    if combined is None or not combined.any():
        raise ActivityIgnoreMaskError(
            "ignore_annotation_union_empty",
            "Reviewed ignore annotation union is empty",
        )
    return combined, provenance


def _activity_evidence_paths(signal_masks: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    physician_ignore = signal_masks.get("physician_ignore_mask")
    if isinstance(physician_ignore, dict):
        for value in (physician_ignore.get("path"),):
            if value:
                paths.add(str(resolve_path(str(value)).resolve()))
        annotations = physician_ignore.get("annotations")
        if isinstance(annotations, list):
            for annotation in annotations:
                if isinstance(annotation, dict) and annotation.get("path"):
                    paths.add(str(resolve_path(str(annotation["path"])).resolve()))
    spectrum = signal_masks.get("bone_activity_spectrum")
    if not isinstance(spectrum, dict):
        return paths
    if spectrum.get("activity_class_map_path"):
        paths.add(str(resolve_path(str(spectrum["activity_class_map_path"])).resolve()))
    for key in ("low_activity_candidate", "transition_candidate", "high_activity_candidate", "ignore_region"):
        item = spectrum.get(key)
        if isinstance(item, dict) and item.get("path"):
            paths.add(str(resolve_path(str(item["path"])).resolve()))
    return paths


def _validate_activity_spectrum_evidence(
    spectrum: dict[str, Any],
    *,
    expected_size: tuple[int, int],
) -> None:
    records: list[tuple[str, Any, str | None]] = [
        ("activity_class_map", spectrum.get("activity_class_map_path"), None),
    ]
    for key in ("low_activity_candidate", "transition_candidate", "high_activity_candidate", "ignore_region"):
        item = spectrum.get(key)
        records.append(
            (
                key,
                item.get("path") if isinstance(item, dict) else None,
                str(item.get("sha256") or "") if isinstance(item, dict) else None,
            )
        )
    for label, raw_path, expected_sha256 in records:
        if not raw_path:
            raise ActivityIgnoreMaskError(
                "activity_spectrum_evidence_missing",
                f"Activity spectrum evidence path is missing: {label}",
            )
        path = resolve_path(str(raw_path)).resolve()
        if not path.is_file():
            raise ActivityIgnoreMaskError(
                "activity_spectrum_evidence_missing",
                f"Activity spectrum evidence file is missing: {path}",
            )
        if expected_sha256 and checksum_for_file(path) != expected_sha256:
            raise ActivityIgnoreMaskError(
                "activity_spectrum_evidence_checksum_mismatch",
                f"Activity spectrum evidence checksum changed: {label}",
            )
        try:
            with Image.open(path) as image:
                image.load()
                actual_size = image.size
        except (OSError, ValueError) as exc:
            raise ActivityIgnoreMaskError(
                "activity_spectrum_evidence_invalid",
                f"Activity spectrum evidence cannot be decoded: {path}",
            ) from exc
        if actual_size != expected_size:
            raise ActivityIgnoreMaskError(
                "activity_spectrum_evidence_size_mismatch",
                f"Activity spectrum evidence size {actual_size} does not match {expected_size}",
            )


def _replace_activity_evidence(
    current: list[EvidenceArtifact],
    *,
    stale_paths: set[str],
    additions: list[EvidenceArtifact],
) -> list[EvidenceArtifact]:
    retained = [item for item in current if str(resolve_path(item.path).resolve()) not in stale_paths]
    by_key = {(str(resolve_path(item.path).resolve()), item.checksum): item for item in retained}
    for item in additions:
        by_key[(str(resolve_path(item.path).resolve()), item.checksum)] = item
    return list(by_key.values())


def _physician_ignore_annotation_artifacts(
    case_id: str,
    run_id: str,
    union_record: dict[str, Any],
    provenance: list[dict[str, Any]],
) -> list[EvidenceArtifact]:
    records = [
        {"path": union_record.get("path"), "sha256": union_record.get("sha256")},
        *provenance,
    ]
    artifacts: list[EvidenceArtifact] = []
    for record in records:
        raw_path = record.get("path")
        if not raw_path:
            continue
        path = resolve_path(str(raw_path)).resolve()
        if not path.is_file():
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.ROI_MASK,
                path=str(path),
                checksum=str(record.get("sha256") or checksum_for_file(path)),
            )
        )
    return artifacts


def _sample_weight_for_review_state(state: str) -> float:
    normalized = state.lower()
    if normalized in {"accepted", "modified"}:
        return 4.0
    if normalized == "rejected":
        return 0.5
    return 1.0


def _candidate_source_path(metadata: dict[str, Any]) -> Path | None:
    for key in ("source_path", "evidence_path", "overlay_path"):
        value = metadata.get(key)
        if not value:
            continue
        path = resolve_path(str(value))
        if path.exists():
            return path
    return None


def _prompt_geometry(request_geometry: dict[str, Any] | None, metadata: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        request_geometry,
        metadata.get("review_geometry"),
        metadata.get("bbox_normalized"),
        metadata.get("source_bbox_normalized"),
    ]
    for geometry in candidates:
        if isinstance(geometry, dict) and geometry.get("type") == "rect":
            normalized = normalized_rect_geometry(geometry)
            if normalized.get("width", 0) > 0 and normalized.get("height", 0) > 0:
                return normalized
    bbox = metadata.get("bbox_xyxy") or metadata.get("source_bbox_xyxy")
    width = metadata.get("image_width") or metadata.get("source_video_width")
    height = metadata.get("image_height") or metadata.get("source_video_height")
    return _geometry_from_xyxy(bbox, width=width, height=height)


def _geometry_from_xyxy(bbox: Any, *, width: Any, height: Any) -> dict[str, Any] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        image_width = float(width)
        image_height = float(height)
        x0, y0, x1, y1 = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None
    if image_width <= 0 or image_height <= 0 or x1 <= x0 or y1 <= y0:
        return None
    return normalized_rect_geometry(
        {
            "type": "rect",
            "coordinate_space": "normalized",
            "x": x0 / image_width,
            "y": y0 / image_height,
            "width": (x1 - x0) / image_width,
            "height": (y1 - y0) / image_height,
        }
    )


def _run_bone_gate_prompt_fallback(
    *,
    source_path: Path,
    case_id: str,
    candidate_id: str,
    geometry: dict[str, Any],
    prompt_source: str,
    config_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    runtime = dict(load_yaml(config_path).get("runtime") or {})
    runtime_profile = str(runtime.get("runtime_profile") or "development")
    strict_startup = bool(runtime.get("strict_startup"))
    configured_policy = runtime.get("allow_prompt_fallback")
    fallback_allowed = configured_policy is True if strict_startup else configured_policy is not False
    if not fallback_allowed:
        raise PromptFallbackSafetyError(
            code="prompt_fallback_disabled_by_runtime_policy",
            runtime_profile=runtime_profile,
            config_path=config_path,
        )
    model_mapping = _model_mapping("medsam2_osteo_promptable", config_path=config_path)
    if model_mapping is None:
        raise ValueError("medsam2_osteo_promptable is not configured")
    output_dir = ensure_dir(
        resolve_path("artifacts/visual_evidence/osteo_vision/prompt_masks") / case_id / "bone_gate_masks"
    )
    extra = dict(model_mapping.get("extra") or {})
    extra["output_dir"] = str(output_dir)
    model_mapping["extra"] = extra
    adapter = build_adapter(model_spec_from_mapping(model_mapping))
    result = adapter.predict(
        AdapterRequest(
            case_id=f"{case_id}_{candidate_id}_bone_gate",
            input_path=str(source_path),
            input_type="2d_image",
            task_type="segmentation",
            modality="surgical_keyframe",
            metadata={
                "prompts": [{"geometry": geometry, "source": prompt_source}],
                "roi_hints": [{"geometry": geometry, "label": "exposed_bone", "source": prompt_source}],
            },
        )
    )
    payload = result.to_dict()
    mask_path = payload.get("segmentation_mask", {}).get("path")
    if not mask_path:
        raise ValueError("Prompt-assisted bone gate mask was not generated")
    return payload, list(payload.get("warnings", []))


def _model_mapping(
    model_id: str,
    config_path: str | Path = "configs/inference/osteo_vision.yml",
) -> dict[str, Any] | None:
    runtime = dict(load_yaml(config_path).get("runtime") or {})
    for model in runtime.get("models") or []:
        if str(model.get("model_id")) == model_id:
            return dict(model)
    return None


def _bone_gate_entry(
    *,
    mask_path: str,
    overlay_path: str,
    geometry: dict[str, Any],
    prompt_source: str,
    review_state: str,
    status: str = "prompt_assisted_review",
    label_source: str = "prompt_assisted_review",
    fallback_mode: bool = True,
    medical_boundary: str = BONE_GATE_BOUNDARY,
) -> dict[str, Any]:
    return {
        "mask_type": "exposed_bone",
        "available": True,
        "status": status,
        "path": mask_path,
        "overlay_path": overlay_path,
        "format": "png_binary_mask",
        "label_source": label_source,
        "prompt_source": prompt_source,
        "prompt_geometry": geometry,
        "review_state": review_state,
        "fallback_mode": fallback_mode,
        "medical_boundary": medical_boundary,
    }


def _updated_signal_masks(metadata: dict[str, Any], bone_gate_entry: dict[str, Any]) -> dict[str, Any]:
    signal_masks = metadata.get("video_signal_segmentation") or metadata.get("signal_masks") or {}
    signal_masks = dict(signal_masks) if isinstance(signal_masks, dict) else {}
    signal_masks["bone_gate_mask"] = bone_gate_entry
    signal_masks["schema_version"] = signal_masks.get("schema_version") or "osteo-vision-video-signal-masks-v1"
    signal_masks["medical_boundary"] = signal_masks.get("medical_boundary") or BONE_GATE_BOUNDARY
    return signal_masks


def _derive_reviewed_activity_spectrum(
    *,
    signal_masks: dict[str, Any],
    actor: ReviewActorIdentity,
    review_state: str,
    case_id: str,
    candidate_id: str,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    updated = dict(signal_masks)
    trusted_role = actor.role == ReviewerRole.PHYSICIAN
    accepted_state = review_state in {ReviewState.ACCEPTED.value, ReviewState.MODIFIED.value}
    if not trusted_role or not accepted_state:
        updated["bone_activity_spectrum"] = _unavailable_activity_spectrum(
            updated.get("bone_activity_spectrum"),
            status="pending_trusted_reviewed_bone_gate",
        )
        return updated
    bone_gate_value = updated.get("bone_gate_mask")
    bone_gate: dict[str, Any] = dict(bone_gate_value) if isinstance(bone_gate_value, dict) else {}
    fluorescence_value = updated.get("fluorescence_signal_mask")
    fluorescence: dict[str, Any] = dict(fluorescence_value) if isinstance(fluorescence_value, dict) else {}
    gate_path = resolve_path(str(bone_gate.get("path") or ""))
    probability_value = fluorescence.get("probability_path")
    probability_path = resolve_path(str(probability_value or ""))
    if not gate_path.is_file() or not probability_path.is_file():
        updated["bone_activity_spectrum"] = _unavailable_activity_spectrum(
            updated.get("bone_activity_spectrum"),
            status="pending_probability_map",
        )
        return updated
    try:
        with Image.open(probability_path) as probability_image:
            probability = np.asarray(probability_image.convert("L"), dtype=np.float32) / 255.0
        with Image.open(gate_path) as gate_image:
            gate = gate_image.convert("L")
            if gate.size != (probability.shape[1], probability.shape[0]):
                gate = gate.resize((probability.shape[1], probability.shape[0]), Image.Resampling.NEAREST)
            bone_gate_array = np.asarray(gate, dtype=np.uint8) > 0
    except (OSError, ValueError):
        updated["bone_activity_spectrum"] = _unavailable_activity_spectrum(
            updated.get("bone_activity_spectrum"),
            status="invalid_probability_or_bone_gate_map",
        )
        return updated
    if not bone_gate_array.any():
        updated["bone_activity_spectrum"] = _unavailable_activity_spectrum(
            updated.get("bone_activity_spectrum"),
            status="empty_reviewed_bone_gate",
        )
        return updated
    try:
        ignore_mask, ignore_sources = _load_activity_ignore_mask(
            updated,
            expected_size=(probability.shape[1], probability.shape[0]),
        )
    except ActivityIgnoreMaskError as exc:
        updated["bone_activity_spectrum"] = _unavailable_activity_spectrum(
            updated.get("bone_activity_spectrum"),
            status=exc.code,
            failure_reason=str(exc),
        )
        return updated
    threshold = float(fluorescence.get("threshold") or 0.5)
    root = (
        Path(output_root)
        if output_root is not None
        else resolve_path("artifacts/visual_evidence/osteo_vision/bone_activity_spectrum")
    )
    output_dir = ensure_dir(root / case_id)
    updated["bone_activity_spectrum"] = save_bone_activity_candidate_maps(
        probability=probability,
        bone_gate=bone_gate_array,
        threshold=threshold,
        output_dir=output_dir,
        safe_case=_safe_name(f"{case_id}_{candidate_id}"),
        activity_score_path=str(probability_path),
        ignore_mask=ignore_mask,
        ignore_sources=ignore_sources,
    )
    return updated


def _load_activity_ignore_mask(
    signal_masks: dict[str, Any],
    *,
    expected_size: tuple[int, int],
) -> tuple[np.ndarray | None, list[dict[str, Any]]]:
    source_specs = (
        ("physician_ignore_mask", signal_masks.get("physician_ignore_mask")),
        ("ignore_mask", signal_masks.get("ignore_mask")),
        ("uncertain_mask", signal_masks.get("uncertain_mask")),
    )
    combined: np.ndarray | None = None
    sources: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for source_type, raw_record in source_specs:
        if not isinstance(raw_record, dict):
            continue
        record = dict(raw_record)
        raw_path = str(record.get("path") or "").strip()
        if not raw_path:
            if record.get("available") is True:
                raise ActivityIgnoreMaskError(
                    "ignore_mask_source_missing",
                    f"{source_type} is marked available without a path",
                )
            continue
        path = resolve_path(raw_path).resolve()
        if path in seen_paths:
            continue
        seen_paths.add(path)
        if not path.is_file():
            raise ActivityIgnoreMaskError(
                "ignore_mask_source_missing",
                f"{source_type} file is missing: {path}",
            )
        try:
            actual_sha256 = checksum_for_file(path)
            expected_sha256 = str(record.get("sha256") or record.get("checksum") or "").strip().lower()
            if expected_sha256 and actual_sha256 != expected_sha256:
                raise ActivityIgnoreMaskError(
                    "ignore_mask_checksum_mismatch",
                    f"{source_type} checksum does not match its declared value",
                )
            with Image.open(path) as image:
                image.load()
                if image.size != expected_size:
                    raise ActivityIgnoreMaskError(
                        "ignore_mask_size_mismatch",
                        f"{source_type} size {image.size} does not match {expected_size}",
                    )
                mask = np.asarray(image.convert("L"), dtype=np.uint8) > 0
        except ActivityIgnoreMaskError:
            raise
        except (OSError, ValueError) as exc:
            raise ActivityIgnoreMaskError(
                "ignore_mask_invalid",
                f"{source_type} cannot be decoded as a mask: {path}",
            ) from exc
        combined = mask if combined is None else combined | mask
        source_entry = {
            "source_type": source_type,
            "path": str(path),
            "sha256": actual_sha256,
            "label_source": record.get("label_source"),
            "review_state": record.get("review_state"),
        }
        annotations = record.get("annotations")
        if source_type == "physician_ignore_mask" and isinstance(annotations, list):
            source_entry["annotation_count"] = len(annotations)
            sources.extend(dict(item) for item in annotations if isinstance(item, dict))
        sources.append(source_entry)
    return combined, sources


def _unavailable_activity_spectrum(
    current: Any,
    *,
    status: str,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    spectrum = dict(current) if isinstance(current, dict) else {}
    spectrum.update(
        {
            "available": False,
            "status": status,
            "spatial_effect_applied": False,
            "review_required": True,
            "activity_class_map_path": None,
            "partition_check": {"valid": False},
            "failure_reasons": [failure_reason or status],
        }
    )
    for key, label in (
        ("low_activity_candidate", "低活性候选"),
        ("transition_candidate", "过渡复核区"),
        ("high_activity_candidate", "高活性参考"),
    ):
        current_item = spectrum.get(key)
        item = dict(current_item) if isinstance(current_item, dict) else {}
        item.update(
            {
                "available": False,
                "label": item.get("label") or label,
                "positive_area_px": None,
                "bone_gate_fraction": None,
                "path": None,
            }
        )
        spectrum[key] = item
    current_ignore_region = spectrum.get("ignore_region")
    ignore_region = dict(current_ignore_region) if isinstance(current_ignore_region, dict) else {}
    ignore_region.update(
        {
            "available": False,
            "label": "无法判断区",
            "positive_area_px": None,
            "bone_gate_fraction": None,
            "path": None,
            "sha256": None,
            "sources": [],
        }
    )
    spectrum["ignore_region"] = ignore_region
    return spectrum


def _fluorescence_signal_path(metadata: dict[str, Any]) -> Any:
    signal_masks = metadata.get("video_signal_segmentation") or metadata.get("signal_masks") or {}
    if isinstance(signal_masks, dict):
        fluorescence = signal_masks.get("fluorescence_signal_mask")
        if isinstance(fluorescence, dict) and fluorescence.get("path"):
            return fluorescence.get("path")
    return metadata.get("signal_mask_path") or metadata.get("mask_path")


def _run_with_candidate_and_bone_gate(
    run: Any,
    candidate_id: str,
    updated_candidate: CandidateRegion,
    signal_masks: dict[str, Any],
    bone_gate_entry: dict[str, Any],
) -> Any:
    candidates = [
        updated_candidate if candidate.candidate_id == candidate_id else candidate
        for candidate in run.candidate_regions
    ]
    fused_outputs = _patch_run_fused_outputs(
        dict(run.fused_outputs),
        frame_order=updated_candidate.metadata.get("frame_order"),
        frame_index=updated_candidate.metadata.get("frame_index"),
        signal_masks=signal_masks,
        bone_gate_entry=bone_gate_entry,
    )
    return run.model_copy(update={"candidate_regions": candidates, "fused_outputs": fused_outputs})


def _patch_run_fused_outputs(
    fused_outputs: dict[str, Any],
    *,
    frame_order: Any,
    frame_index: Any,
    signal_masks: dict[str, Any],
    bone_gate_entry: dict[str, Any],
) -> dict[str, Any]:
    for key in ("hotspot_outputs", "frame_details"):
        items = fused_outputs.get(key)
        if isinstance(items, list):
            fused_outputs[key] = [
                (
                    _patch_frame_payload(
                        item, frame_order=frame_order, frame_index=frame_index, signal_masks=signal_masks
                    )
                    if _frame_matches(item, frame_order=frame_order, frame_index=frame_index)
                    else item
                )
                for item in items
            ]
    summary = dict(fused_outputs.get("video_segmentation_summary") or {})
    summary["bone_gate_frame_count"] = _count_bone_gate_frames_from_fused_outputs(fused_outputs)
    summary["bone_activity_spectrum_frame_count"] = _count_activity_frames_from_fused_outputs(fused_outputs)
    if summary["bone_gate_frame_count"] > 0:
        summary["bone_gate_mask_status"] = bone_gate_entry.get("status") or "prompt_assisted_review"
    fused_outputs["video_segmentation_summary"] = summary
    _patch_video_segmentation_manifest_file(
        fused_outputs, frame_order=frame_order, frame_index=frame_index, signal_masks=signal_masks
    )
    return fused_outputs


def _patch_frame_payload(
    item: Any,
    *,
    frame_order: Any,
    frame_index: Any,
    signal_masks: dict[str, Any],
) -> Any:
    if not isinstance(item, dict):
        return item
    patched = dict(item)
    patched["signal_masks"] = signal_masks
    patched["video_signal_segmentation"] = signal_masks
    patched["bone_gate_mask_path"] = signal_masks.get("bone_gate_mask", {}).get("path")
    patched["bone_gate_overlay_path"] = signal_masks.get("bone_gate_mask", {}).get("overlay_path")
    for key in ("lesion_evidence",):
        if isinstance(patched.get(key), dict):
            nested = dict(patched[key])
            nested["signal_masks"] = signal_masks
            nested["video_signal_segmentation"] = signal_masks
            nested["bone_gate_mask_path"] = patched["bone_gate_mask_path"]
            nested["bone_gate_overlay_path"] = patched["bone_gate_overlay_path"]
            patched[key] = nested
    return patched


def _patch_video_segmentation_manifest_file(
    fused_outputs: dict[str, Any],
    *,
    frame_order: Any,
    frame_index: Any,
    signal_masks: dict[str, Any],
    strict: bool = False,
) -> None:
    path_value = fused_outputs.get("video_segmentation_manifest_path")
    if not path_value:
        return
    path = resolve_path(str(path_value))
    if not path.is_file():
        if strict:
            raise ActivityIgnoreMaskError(
                "video_segmentation_manifest_missing",
                f"Video segmentation manifest is missing: {path}",
            )
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise ActivityIgnoreMaskError(
                "video_segmentation_manifest_invalid",
                f"Video segmentation manifest is unreadable: {path}",
            ) from exc
        return
    frames = payload.get("frames")
    matched = False
    if isinstance(frames, list):
        for frame in frames:
            if not _frame_matches(frame, frame_order=frame_order, frame_index=frame_index):
                continue
            frame["video_signal_segmentation"] = signal_masks
            matched = True
    if strict and not matched:
        raise ActivityIgnoreMaskError(
            "video_segmentation_manifest_frame_missing",
            "Video segmentation manifest has no frame matching the reviewed candidate",
        )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary["bone_gate_frame_count"] = sum(1 for frame in frames or [] if _frame_has_bone_gate(frame))
    summary["bone_activity_spectrum_frame_count"] = sum(
        1 for frame in frames or [] if _frame_has_activity_spectrum(frame)
    )
    payload["summary"] = summary
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        if strict:
            raise ActivityIgnoreMaskError(
                "video_segmentation_manifest_write_failed",
                f"Video segmentation manifest cannot be updated: {path}",
            ) from exc


def _validate_video_segmentation_manifest_target(
    fused_outputs: dict[str, Any],
    *,
    frame_order: Any,
    frame_index: Any,
) -> None:
    path_value = fused_outputs.get("video_segmentation_manifest_path")
    if not path_value:
        return
    path = resolve_path(str(path_value))
    if not path.is_file():
        raise ActivityIgnoreMaskError(
            "video_segmentation_manifest_missing",
            f"Video segmentation manifest is missing: {path}",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivityIgnoreMaskError(
            "video_segmentation_manifest_invalid",
            f"Video segmentation manifest is unreadable: {path}",
        ) from exc
    frames = payload.get("frames")
    if not isinstance(frames, list) or not any(
        _frame_matches(frame, frame_order=frame_order, frame_index=frame_index) for frame in frames
    ):
        raise ActivityIgnoreMaskError(
            "video_segmentation_manifest_frame_missing",
            "Video segmentation manifest has no frame matching the reviewed candidate",
        )


def _count_bone_gate_frames_from_fused_outputs(fused_outputs: dict[str, Any]) -> int:
    return _count_distinct_signal_frames(fused_outputs, _frame_has_bone_gate)


def _count_activity_frames_from_fused_outputs(fused_outputs: dict[str, Any]) -> int:
    return _count_distinct_signal_frames(fused_outputs, _frame_has_activity_spectrum)


def _count_distinct_signal_frames(fused_outputs: dict[str, Any], predicate: Callable[[Any], bool]) -> int:
    keys: set[str] = set()
    for list_key in ("frame_details", "hotspot_outputs"):
        items = fused_outputs.get(list_key)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not predicate(item):
                continue
            keys.add(
                str(
                    item.get("frame_order") or item.get("frame_index") or item.get("frame_key") or f"{list_key}:{index}"
                )
            )
    return len(keys)


def _frame_matches(item: Any, *, frame_order: Any, frame_index: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if frame_order is not None and str(item.get("frame_order")) == str(frame_order):
        return True
    if frame_index is not None and str(item.get("frame_index")) == str(frame_index):
        return True
    return False


def _frame_has_bone_gate(frame: Any) -> bool:
    if not isinstance(frame, dict):
        return False
    signal = frame.get("video_signal_segmentation")
    if not isinstance(signal, dict):
        return False
    bone_gate = signal.get("bone_gate_mask")
    return isinstance(bone_gate, dict) and bone_gate.get("available") is True


def _frame_has_activity_spectrum(frame: Any) -> bool:
    if not isinstance(frame, dict):
        return False
    signal = frame.get("video_signal_segmentation")
    spectrum = signal.get("bone_activity_spectrum") if isinstance(signal, dict) else None
    return isinstance(spectrum, dict) and spectrum.get("available") is True


def _save_edited_bone_gate_mask(
    *,
    source_path: Path,
    mask_png_base64: str,
    case_id: str,
    candidate_id: str,
) -> tuple[str, str, dict[str, int]]:
    with Image.open(source_path) as source_image:
        rgb_image = source_image.convert("RGB")
    mask = _decode_mask_png(mask_png_base64)
    if mask.size != rgb_image.size:
        mask = mask.resize(rgb_image.size, Image.Resampling.NEAREST)
    mask_array = (np.asarray(mask.convert("L"), dtype=np.uint8) > 0).astype(np.uint8)
    safe_case = _safe_name(f"{case_id}_{candidate_id}_edited")
    output_dir = ensure_dir(resolve_path("artifacts/visual_evidence/osteo_vision/edited_bone_gate_masks") / case_id)
    mask_path = output_dir / f"{safe_case}_mask.png"
    overlay_path = output_dir / f"{safe_case}_overlay.png"
    Image.fromarray(mask_array * 255).save(mask_path)
    Image.fromarray(_mask_overlay(np.asarray(rgb_image, dtype=np.uint8), mask_array)).save(overlay_path)
    return str(mask_path), str(overlay_path), {"width": int(rgb_image.width), "height": int(rgb_image.height)}


def _decode_mask_png(mask_png_base64: str) -> Image.Image:
    encoded = str(mask_png_base64 or "").strip()
    if "," in encoded and encoded.lower().startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid mask_png_base64 payload") from exc
    try:
        with Image.open(BytesIO(raw)) as image:
            return image.convert("L")
    except Exception as exc:  # pragma: no cover - Pillow raises multiple decoder errors.
        raise ValueError("mask_png_base64 is not a readable PNG image") from exc


def _mask_overlay(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    overlay = rgb.copy()
    active: np.ndarray = mask.astype(bool)
    color = np.zeros_like(overlay)
    color[..., 0] = 255
    color[..., 1] = 170
    color[..., 2] = 40
    overlay[active] = (0.55 * overlay[active] + 0.45 * color[active]).astype(np.uint8)
    return overlay


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "case"


def _bone_gate_artifacts(case_id: str, run_id: str, *, mask_path: str, overlay_path: str) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    for path_value, kind in (
        (mask_path, ArtifactKind.ROI_MASK),
        (overlay_path, ArtifactKind.OVERLAY),
    ):
        path = Path(path_value)
        if not path.exists():
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=kind,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts


def _activity_spectrum_artifacts(case_id: str, run_id: str, signal_masks: dict[str, Any]) -> list[EvidenceArtifact]:
    spectrum = signal_masks.get("bone_activity_spectrum") if isinstance(signal_masks, dict) else None
    if not isinstance(spectrum, dict) or spectrum.get("available") is not True:
        return []
    path_values = [spectrum.get("activity_class_map_path")]
    for key in ("low_activity_candidate", "transition_candidate", "high_activity_candidate"):
        item = spectrum.get(key)
        if isinstance(item, dict):
            path_values.append(item.get("path"))
    ignore_region = spectrum.get("ignore_region")
    if isinstance(ignore_region, dict):
        path_values.append(ignore_region.get("path"))
    artifacts: list[EvidenceArtifact] = []
    for path_value in path_values:
        if not path_value:
            continue
        path = Path(str(path_value))
        if not path.exists():
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.ROI_MASK,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts
