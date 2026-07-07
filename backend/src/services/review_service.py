from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import checksum_for_file
from backend.src.domains.cases.enums import CaseStatus, RegionSource, ReviewState
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import (
    BoneGateMaskCreateRequest,
    CandidateRegion,
    CaseRecord,
    EvidenceArtifact,
    RegionOfInterest,
    RegionUpdateRequest,
    ReviewEvent,
    ReviewEventCreateRequest,
)
from backend.src.services.review_geometry import bbox_xyxy_from_geometry, candidate_geometry, normalized_rect_geometry
from src.core.config import load_yaml
from src.core.paths import ensure_dir, resolve_path
from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapter, model_spec_from_mapping


BONE_GATE_BOUNDARY = (
    "Bone gate mask is generated from physician ROI or prompt-assisted review using the MedSAM-like prompt "
    "fallback contract. It is not real MedSAM2 checkpoint inference and is not a clinical diagnosis."
)


class ReviewService:
    def __init__(self, repo: CaseRepository) -> None:
        self.repo = repo

    def update_region(self, case: CaseRecord, region_id: str, request: RegionUpdateRequest) -> CaseRecord:
        rois: list[RegionOfInterest] = []
        found = False
        for roi in case.rois:
            if roi.roi_id != region_id:
                rois.append(roi)
                continue
            found = True
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
        updated = case.model_copy(update={"rois": rois, "status": CaseStatus.REVIEWING})
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def add_review_event(self, case: CaseRecord, request: ReviewEventCreateRequest) -> CaseRecord:
        event = ReviewEvent(
            event_id=f"event_{uuid4().hex[:10]}",
            case_id=case.case_id,
            actor="physician",
            action=request.action,
            target_id=request.target_id,
            before_state=request.before_state,
            after_state=request.after_state,
            timestamp=datetime.now(timezone.utc),
            notes=request.notes,
        )
        updated = case.model_copy(update={"review_events": [*case.review_events, event], "status": CaseStatus.REVIEWING})
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

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

    def add_candidate_roi(self, case: CaseRecord, candidate_id: str) -> CaseRecord:
        candidate = _find_candidate(case, candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate not found: {candidate_id}")
        roi = self.candidate_to_roi(case, candidate)
        rois = [existing for existing in case.rois if existing.roi_id != roi.roi_id]
        updated = case.model_copy(update={"rois": [*rois, roi], "status": CaseStatus.REVIEWING})
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def generate_candidate_bone_gate_mask(
        self,
        case: CaseRecord,
        candidate_id: str,
        request: BoneGateMaskCreateRequest,
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
        event = ReviewEvent(
            event_id=f"event_{uuid4().hex[:10]}",
            case_id=case.case_id,
            actor="physician",
            action="bone_gate_mask_generated",
            target_id=candidate_id,
            before_state=candidate.status.value,
            after_state=request.review_state.value,
            timestamp=datetime.now(timezone.utc),
            notes=request.reviewer_notes or BONE_GATE_BOUNDARY,
        )
        artifacts = [
            *case.artifacts,
            *_bone_gate_artifacts(case.case_id, run.run_id, mask_path=mask_path, overlay_path=overlay_path),
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

    def update_candidate_region(self, case: CaseRecord, candidate_id: str, request: RegionUpdateRequest) -> CaseRecord:
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
                metadata["sample_weight"] = _sample_weight_for_review_state(request.review_state.value)
                if request.geometry is not None:
                    geometry = normalized_rect_geometry(request.geometry)
                    metadata["bbox_normalized"] = geometry
                    metadata["review_geometry"] = geometry
                    metadata["geometry_reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    metadata["geometry_review_source"] = "physician_review"
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
        event = ReviewEvent(
            event_id=f"event_{uuid4().hex[:10]}",
            case_id=case.case_id,
            actor="physician",
            action="candidate_region_state_update",
            target_id=candidate_id,
            before_state=before_state,
            after_state=request.review_state.value,
            timestamp=datetime.now(timezone.utc),
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
        accepted = sum(1 for roi in case.rois if roi.review_state == ReviewState.ACCEPTED)
        modified = sum(1 for roi in case.rois if roi.review_state == ReviewState.MODIFIED)
        rejected = sum(1 for roi in case.rois if roi.review_state == ReviewState.REJECTED)
        candidates = [candidate for run in case.analysis_runs for candidate in run.candidate_regions]
        candidate_accepted = sum(1 for candidate in candidates if candidate.status == ReviewState.ACCEPTED)
        candidate_modified = sum(1 for candidate in candidates if candidate.status == ReviewState.MODIFIED)
        candidate_rejected = sum(1 for candidate in candidates if candidate.status == ReviewState.REJECTED)
        return {
            "accepted_regions": accepted,
            "modified_regions": modified,
            "rejected_regions": rejected,
            "accepted_candidates": candidate_accepted,
            "modified_candidates": candidate_modified,
            "rejected_candidates": candidate_rejected,
            "total_review_events": len(case.review_events),
            "status": case.status,
        }


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
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model_mapping = _model_mapping("medsam2_osteo_promptable")
    if model_mapping is None:
        raise ValueError("medsam2_osteo_promptable is not configured")
    output_dir = ensure_dir(
        resolve_path("artifacts/visual_evidence/osteo_vision/prompt_masks")
        / case_id
        / "bone_gate_masks"
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


def _model_mapping(model_id: str, config_path: str = "configs/inference/osteo_vision.yml") -> dict[str, Any] | None:
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
) -> dict[str, Any]:
    return {
        "mask_type": "exposed_bone",
        "available": True,
        "status": "prompt_assisted_review",
        "path": mask_path,
        "overlay_path": overlay_path,
        "format": "png_binary_mask",
        "label_source": "prompt_assisted_review",
        "prompt_source": prompt_source,
        "prompt_geometry": geometry,
        "review_state": review_state,
        "fallback_mode": True,
        "medical_boundary": BONE_GATE_BOUNDARY,
    }


def _updated_signal_masks(metadata: dict[str, Any], bone_gate_entry: dict[str, Any]) -> dict[str, Any]:
    signal_masks = metadata.get("video_signal_segmentation") or metadata.get("signal_masks") or {}
    signal_masks = dict(signal_masks) if isinstance(signal_masks, dict) else {}
    signal_masks["bone_gate_mask"] = bone_gate_entry
    signal_masks["schema_version"] = signal_masks.get("schema_version") or "osteo-vision-video-signal-masks-v1"
    signal_masks["medical_boundary"] = signal_masks.get("medical_boundary") or BONE_GATE_BOUNDARY
    return signal_masks


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
        updated_candidate if candidate.candidate_id == candidate_id else candidate for candidate in run.candidate_regions
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
                _patch_frame_payload(item, frame_order=frame_order, frame_index=frame_index, signal_masks=signal_masks)
                if _frame_matches(item, frame_order=frame_order, frame_index=frame_index)
                else item
                for item in items
            ]
    summary = dict(fused_outputs.get("video_segmentation_summary") or {})
    summary["bone_gate_frame_count"] = _count_bone_gate_frames_from_fused_outputs(fused_outputs)
    if summary["bone_gate_frame_count"] > 0:
        summary["bone_gate_mask_status"] = "prompt_assisted_review"
    fused_outputs["video_segmentation_summary"] = summary
    _patch_video_segmentation_manifest_file(fused_outputs, frame_order=frame_order, frame_index=frame_index, bone_gate_entry=bone_gate_entry)
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
    bone_gate_entry: dict[str, Any],
) -> None:
    path_value = fused_outputs.get("video_segmentation_manifest_path")
    if not path_value:
        return
    path = resolve_path(str(path_value))
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    frames = payload.get("frames")
    if isinstance(frames, list):
        for frame in frames:
            if not _frame_matches(frame, frame_order=frame_order, frame_index=frame_index):
                continue
            signal = frame.get("video_signal_segmentation") if isinstance(frame, dict) else None
            if not isinstance(signal, dict):
                signal = {}
            signal["bone_gate_mask"] = bone_gate_entry
            frame["video_signal_segmentation"] = signal
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary["bone_gate_frame_count"] = sum(1 for frame in frames or [] if _frame_has_bone_gate(frame))
    payload["summary"] = summary
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _count_bone_gate_frames_from_fused_outputs(fused_outputs: dict[str, Any]) -> int:
    keys: set[str] = set()
    for list_key in ("frame_details", "hotspot_outputs"):
        items = fused_outputs.get(list_key)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not _frame_has_bone_gate(item):
                continue
            keys.add(str(item.get("frame_order") or item.get("frame_index") or item.get("frame_key") or f"{list_key}:{index}"))
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


def _bone_gate_artifacts(case_id: str, run_id: str, *, mask_path: str, overlay_path: str) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    for path_value, kind in ((mask_path, "roi_mask"), (overlay_path, "overlay")):
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
