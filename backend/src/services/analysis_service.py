from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import case_artifact_dir, checksum_for_file
from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.enums import ArtifactKind, CaseStatus, InputChannel, ReviewState
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, CandidateRegion, CaseInputAsset, CaseRecord, EvidenceArtifact
from src.core.config import load_yaml
from src.core.paths import artifact_dirs
from src.core.task_package import default_task_package, load_task_package
from src.engine.inference import MedicalImagingInferenceService
from src.models.hotspot_segmenter import segment_2d_fluorescence_hotspots
from src.preprocess.fluorescence import fuse_white_light_fluorescence
from src.preprocess.video import extract_keyframes


class AnalysisService:
    def __init__(self, repo: CaseRepository, config_path: str = "configs/inference/osteo_vision.yml") -> None:
        self.repo = repo
        self.config_path = config_path

    def start_analysis(
        self,
        case: CaseRecord,
        selected_input_ids: list[str],
        parameters: dict[str, Any],
        roi_hints: list[dict[str, Any]],
    ) -> CaseRecord:
        artifacts = artifact_dirs(load_yaml(self.config_path))
        output_dir = case_artifact_dir(artifacts["visual"] / "cases", case.case_id)
        run_id = f"run_{uuid4().hex[:10]}"
        effective_roi_hints = _merge_roi_hints(case, roi_hints)
        run_parameters = {**parameters, "roi_hints": effective_roi_hints} if effective_roi_hints else dict(parameters)
        run = AnalysisRun(
            run_id=run_id,
            case_id=case.case_id,
            method_id=self._method_id(),
            parameters=run_parameters,
            status="running",
        )
        selected_inputs, selection_warnings = self._select_inputs(case, selected_input_ids)
        if any(warning.get("blocking") for warning in selection_warnings):
            run = run.model_copy(update={"status": "failed", "warnings": selection_warnings})
            updated = case.model_copy(
                update={"analysis_runs": [*case.analysis_runs, run], "warnings": [*case.warnings, *selection_warnings]}
            )
            self.repo.save(updated)
            return updated

        white = self._pick_input(selected_inputs, InputChannel.WHITE_LIGHT)
        fluor = self._pick_input(selected_inputs, InputChannel.FLUORESCENCE)
        if parameters.get("mode") == "realtime_video":
            realtime_warnings = [
                {
                    "code": "realtime_stream_not_connected",
                    "message": "Realtime browser camera preview is registered; streaming AI inference is not connected in this prototype.",
                    "blocking": False,
                }
            ]
            run = run.model_copy(
                update={
                    "status": "completed",
                    "fused_outputs": {
                        "mode": "realtime_video",
                        "source_path": parameters.get("source_path", "camera://browser/default"),
                        "roi_hints": effective_roi_hints,
                        "disclaimer_context": disclaimer_context(),
                    },
                    "quantitative_summary": {"roi_hint_count": len(effective_roi_hints)},
                    "warnings": [*selection_warnings, *realtime_warnings],
                }
            )
            updated = case.model_copy(
                update={
                    "analysis_runs": [*case.analysis_runs, run],
                    "status": CaseStatus.ANALYZED,
                    "warnings": [*case.warnings, *selection_warnings, *realtime_warnings],
                }
            )
            updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
            self.repo.save(updated)
            return updated

        video = self._pick_input(selected_inputs, InputChannel.VIDEO)
        if parameters.get("mode") == "video_file" or (video and not (white and fluor)):
            source_path = parameters.get("source_path") or (video.path if video else None)
            if not source_path:
                missing_video_warnings = [
                    {
                        "code": "missing_video_input",
                        "message": "Video input is required for keyframe extraction.",
                        "blocking": True,
                    }
                ]
                run = run.model_copy(update={"status": "failed", "warnings": missing_video_warnings})
                updated = case.model_copy(
                    update={
                        "analysis_runs": [*case.analysis_runs, run],
                        "warnings": [*case.warnings, *missing_video_warnings],
                    }
                )
                self.repo.save(updated)
                return updated
            frame_count = int(parameters.get("keyframe_count", 5))
            sampling_strategy = str(parameters.get("keyframe_sampling_strategy", "quality_peak"))
            keyframe_report = _keyframe_report_for_analysis(
                source_path,
                output_dir / "keyframes" / run_id,
                max_frames=frame_count,
                sampling_strategy=sampling_strategy,
                requested_frame_indexes=_numeric_sequence(
                    parameters.get("keyframe_frame_indexes", parameters.get("requested_frame_indexes")),
                    cast_type=int,
                ),
                requested_timestamps_sec=_numeric_sequence(
                    parameters.get("keyframe_timestamps_sec", parameters.get("requested_timestamps_sec")),
                    cast_type=float,
                ),
            )
            video_warnings = [*selection_warnings, *keyframe_report.get("warnings", [])]
            keyframes = keyframe_report.get("keyframes", [])
            hotspot_outputs = _analyze_keyframe_hotspots(
                keyframes,
                output_dir / "hotspots" / run_id,
                case_id=case.case_id,
                threshold=float(parameters.get("hotspot_threshold", parameters.get("threshold", 0.6))),
                colormap=str(parameters.get("colormap", "green")),
                roi_hints=effective_roi_hints,
            )
            frame_details = _video_frame_details(keyframes, hotspot_outputs)
            timeline_summary = _video_timeline_summary(keyframe_report)
            frame_details_manifest_path = (
                _write_video_frame_details_manifest(
                    output_dir / "frame_details" / run_id,
                    case_id=case.case_id,
                    run_id=run_id,
                    source_path=str(source_path),
                    keyframe_report=keyframe_report,
                    frame_details=frame_details,
                )
                if keyframes
                else None
            )
            video_candidates = _hotspot_candidate_regions(run_id, hotspot_outputs)
            hotspot_summary = _hotspot_summary(hotspot_outputs)
            run = run.model_copy(
                update={
                    "status": "completed" if keyframes else "failed",
                    "candidate_regions": video_candidates,
                    "fused_outputs": {
                        "mode": "video_file_keyframes",
                        "source_path": str(source_path),
                        "video_metadata": video.metadata if video else {},
                        "keyframes": keyframes,
                        "hotspot_outputs": hotspot_outputs,
                        "frame_details": frame_details,
                        "quality_summary": keyframe_report.get("quality_summary", {}),
                        "keyframe_report_source": keyframe_report.get("report_source", "new_analysis_extract"),
                        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
                        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
                        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
                        "timeline_summary": timeline_summary,
                        "frame_details_manifest_path": frame_details_manifest_path,
                        "roi_hints": effective_roi_hints,
                        "disclaimer_context": disclaimer_context(),
                    },
                    "quantitative_summary": {
                        "frame_count": keyframe_report.get("frame_count"),
                        "duration_sec": keyframe_report.get("duration_sec"),
                        "keyframes_extracted": len(keyframes),
                        "keyframe_source": keyframe_report.get("report_source", "new_analysis_extract"),
                        "roi_hint_count": len(effective_roi_hints),
                        "roi_filter_applied": bool(effective_roi_hints),
                        **hotspot_summary,
                    },
                    "warnings": video_warnings,
                }
            )
            video_artifacts = [
                *_keyframe_artifacts(case.case_id, run_id, keyframes),
                *_hotspot_artifacts(case.case_id, run_id, hotspot_outputs),
                *_video_manifest_artifacts(
                    case.case_id,
                    run_id,
                    [
                        keyframe_report.get("frame_index_manifest_path"),
                        keyframe_report.get("timeline_manifest_path"),
                        frame_details_manifest_path,
                    ],
                ),
            ]
            updated = case.model_copy(
                update={
                    "analysis_runs": [*case.analysis_runs, run],
                    "artifacts": [*case.artifacts, *video_artifacts],
                    "status": CaseStatus.ANALYZED if keyframes else case.status,
                    "warnings": [*case.warnings, *video_warnings],
                }
            )
            updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
            self.repo.save(updated)
            return updated

        fused_outputs: dict[str, Any] = {}
        analysis_warnings: list[dict[str, Any]] = list(selection_warnings)
        candidate_regions: list[CandidateRegion] = []
        if white and fluor:
            fusion_report = fuse_white_light_fluorescence(
                white.path,
                fluor.path,
                output_dir,
                case_id=case.case_id,
                alpha=float(parameters.get("alpha", 0.45)),
                threshold=float(parameters.get("threshold", 0.6)),
                colormap=str(parameters.get("colormap", "green")),
                roi_hints=effective_roi_hints,
            )
            outputs = fusion_report.get("outputs", {})
            fused_outputs = {
                **fusion_report,
                "outputs": outputs,
                "roi_hints": effective_roi_hints,
                "disclaimer_context": disclaimer_context(),
            }
            analysis_warnings.extend(fusion_report.get("warnings", []))
            quant = fusion_report.get("quantification", {})
            quantitative_summary = {**quant, "roi_hint_count": len(effective_roi_hints)}
            candidate_score = float(quant.get("roi_mean_intensity", quant.get("mean_intensity", 0.0)))
            candidate_confidence = float(quant.get("roi_p95_intensity", quant.get("p95_intensity", 0.0)))
            candidate_regions = [
                CandidateRegion(
                    candidate_id=f"cand_{uuid4().hex[:10]}",
                    run_id=run_id,
                    score=candidate_score,
                    risk_type="fluorescence_hotspot",
                    confidence=candidate_confidence,
                    status=ReviewState.REVIEW_REQUIRED,
                    explanation=(
                        "Derived from ROI-constrained fluorescence quantification heuristics."
                        if effective_roi_hints
                        else "Derived from fluorescence quantification heuristics."
                    ),
                )
            ]
            fusion_artifacts = _fusion_artifacts(case.case_id, run_id, outputs)
        else:
            fusion_artifacts = []
            analysis_warnings.append(
                {
                    "code": "missing_dual_channel_pair",
                    "message": "Dual-channel white-light and fluorescence inputs are required for fusion.",
                    "blocking": True,
                }
            )
        run = run.model_copy(
            update={
                "status": "completed" if fused_outputs else "failed",
                "candidate_regions": candidate_regions,
                "fused_outputs": fused_outputs,
                "quantitative_summary": quantitative_summary if fused_outputs else {},
                "warnings": analysis_warnings,
            }
        )
        updated = case.model_copy(
            update={
                "analysis_runs": [*case.analysis_runs, run],
                "artifacts": [*case.artifacts, *fusion_artifacts],
                "status": CaseStatus.ANALYZED if fused_outputs else case.status,
                "warnings": [*case.warnings, *analysis_warnings],
            }
        )
        if fused_outputs:
            updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def diagnose_case(self, case: CaseRecord, task_type: str = "classification") -> dict[str, Any]:
        service = MedicalImagingInferenceService.from_config(self.config_path)
        inputs = case.inputs or []
        if not inputs:
            return {
                "status": "missing_inputs",
                "case_id": case.case_id,
                "warnings": [{"code": "missing_inputs", "message": "No inputs stored for case.", "blocking": True}],
            }
        primary = inputs[0]
        result = service.diagnose(primary.path, task_type=task_type).to_dict()
        return result

    def _pick_input(self, assets: list[CaseInputAsset], channel: InputChannel) -> CaseInputAsset | None:
        return next((asset for asset in assets if asset.channel == channel), None)

    def _select_inputs(
        self, case: CaseRecord, selected_input_ids: list[str]
    ) -> tuple[list[CaseInputAsset], list[dict[str, Any]]]:
        if not selected_input_ids:
            return list(case.inputs), []
        selected_set = set(selected_input_ids)
        selected = [asset for asset in case.inputs if asset.input_id in selected_set]
        missing = [
            input_id for input_id in selected_input_ids if input_id not in {asset.input_id for asset in selected}
        ]
        if missing:
            return (
                selected,
                [
                    {
                        "code": "selected_input_not_found",
                        "message": "One or more selected input IDs are not attached to this case.",
                        "blocking": True,
                        "details": {"missing_input_ids": missing},
                    }
                ],
            )
        return selected, []

    def _method_id(self) -> str:
        try:
            task_package = load_task_package("configs/tasks/osteo_vision.yml")
        except Exception:
            task_package = default_task_package()
        return task_package.task_id

    def _review_summary(self, case: CaseRecord) -> dict[str, Any]:
        analysis_run = case.analysis_runs[-1] if case.analysis_runs else None
        return {
            "status": case.status,
            "run_id": analysis_run.run_id if analysis_run else None,
            "candidate_regions": len(analysis_run.candidate_regions) if analysis_run else 0,
            "artifact_count": len(case.artifacts),
            "disclaimer": disclaimer_context(),
        }


def _fusion_artifacts(case_id: str, run_id: str, outputs: dict[str, Any]) -> list[EvidenceArtifact]:
    mapping = {
        "overlay_path": ArtifactKind.OVERLAY,
        "heatmap_path": ArtifactKind.HEATMAP,
        "normalized_fluorescence_path": ArtifactKind.NORMALIZED_FLUORESCENCE,
        "colorbar_path": ArtifactKind.COLORBAR,
        "report_path": ArtifactKind.REPORT_JSON,
        "markdown_report_path": ArtifactKind.REPORT_MD,
    }
    artifacts: list[EvidenceArtifact] = []
    for output_key, kind in mapping.items():
        path = outputs.get(output_key)
        if not path:
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


def _merge_roi_hints(case: CaseRecord, request_hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in request_hints:
        roi_id = str(hint.get("roi_id") or f"request_roi_{len(merged) + 1}")
        merged.append({**hint, "roi_id": roi_id, "source": hint.get("source", "request")})
        seen.add(roi_id)
    for roi in case.rois:
        if roi.roi_id in seen:
            continue
        merged.append(
            {
                "roi_id": roi.roi_id,
                "source": roi.source.value,
                "geometry": roi.geometry,
                "label": roi.label,
                "review_state": roi.review_state.value,
                "candidate_id": roi.candidate_id,
            }
        )
        seen.add(roi.roi_id)
    return merged


def _keyframe_artifacts(case_id: str, run_id: str, keyframes: list[dict[str, Any]]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    for frame in keyframes:
        path = frame.get("evidence_path") or frame.get("path")
        if not path:
            continue
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.KEYFRAME,
                path=str(path),
                checksum=checksum_for_file(path),
            )
        )
    return artifacts


def _keyframe_report_for_analysis(
    source_path: Any,
    output_dir: Any,
    *,
    max_frames: int,
    sampling_strategy: str,
    requested_frame_indexes: list[int],
    requested_timestamps_sec: list[float],
) -> dict[str, Any]:
    if requested_frame_indexes or requested_timestamps_sec:
        return extract_keyframes(
            source_path,
            output_dir,
            max_frames=max_frames,
            sampling_strategy="manual",
            requested_frame_indexes=requested_frame_indexes,
            requested_timestamps_sec=requested_timestamps_sec,
        )
    reusable = _load_reusable_upload_keyframes(source_path, max_frames=max_frames, sampling_strategy=sampling_strategy)
    if reusable is not None:
        return reusable
    return extract_keyframes(
        source_path,
        output_dir,
        max_frames=max_frames,
        sampling_strategy=sampling_strategy,
    )


def _numeric_sequence(value: Any, *, cast_type: type[int] | type[float]) -> list[Any]:
    raw_items = value if isinstance(value, list) else [value] if value is not None else []
    parsed: list[Any] = []
    for item in raw_items:
        try:
            parsed.append(cast_type(item))
        except (TypeError, ValueError):
            continue
    return parsed


def _load_reusable_upload_keyframes(
    source_path: Any,
    *,
    max_frames: int,
    sampling_strategy: str,
) -> dict[str, Any] | None:
    source = Path(str(source_path))
    manifest_path = source.parent / "keyframes" / source.stem / "keyframe_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload_source = payload.get("source_path")
    if not payload_source or Path(str(payload_source)).resolve() != source.resolve():
        return None
    payload_strategy = str(payload.get("sampling_strategy") or payload.get("sampling") or "").lower()
    if payload_strategy != sampling_strategy.lower().strip():
        return None
    keyframes = [frame for frame in payload.get("keyframes") or [] if isinstance(frame, dict)]
    requested_count = max(1, int(max_frames))
    if len(keyframes) < requested_count:
        return None
    selected_keyframes = keyframes[:requested_count]
    if not _keyframe_paths_exist(selected_keyframes):
        return None
    selection_trace = dict(payload.get("selection_trace") or {})
    selection_trace.update(
        {
            "selected_indexes": [frame.get("frame_index") for frame in selected_keyframes],
            "reused_from_manifest": str(manifest_path),
        }
    )
    quality_summary = dict(payload.get("quality_summary") or {})
    quality_summary.update({"frames_saved": len(selected_keyframes), "reused_from_upload_preextract": True})
    frame_index_manifest_path = payload.get("frame_index_manifest_path")
    if not frame_index_manifest_path:
        sibling_frame_index_manifest = manifest_path.with_name("frame_index_manifest.json")
        if sibling_frame_index_manifest.exists():
            frame_index_manifest_path = str(sibling_frame_index_manifest)
    timeline_manifest_path = payload.get("timeline_manifest_path")
    if not timeline_manifest_path:
        sibling_timeline_manifest = manifest_path.with_name("timeline_manifest.json")
        if sibling_timeline_manifest.exists():
            timeline_manifest_path = str(sibling_timeline_manifest)
    return {
        **payload,
        "keyframes": selected_keyframes,
        "selection_trace": selection_trace,
        "quality_summary": quality_summary,
        "report_source": "reused_upload_preextract",
        "source_manifest_path": str(manifest_path),
        "keyframe_manifest_path": str(manifest_path),
        "frame_index_manifest_path": frame_index_manifest_path,
        "timeline_manifest_path": timeline_manifest_path,
    }


def _keyframe_paths_exist(keyframes: list[dict[str, Any]]) -> bool:
    for frame in keyframes:
        path = frame.get("evidence_path") or frame.get("path")
        if not path or not Path(str(path)).exists():
            return False
    return True


def _analyze_keyframe_hotspots(
    keyframes: list[dict[str, Any]],
    output_dir: Any,
    *,
    case_id: str,
    threshold: float,
    colormap: str,
    roi_hints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for frame in keyframes:
        source_path = frame.get("evidence_path") or frame.get("path")
        if not source_path:
            continue
        frame_case_id = f"{case_id}_frame_{int(frame.get('order', len(outputs) + 1)):02d}"
        payload = segment_2d_fluorescence_hotspots(
            source_path,
            output_dir=output_dir,
            case_id=frame_case_id,
            threshold=threshold,
            min_component_area=25,
            colormap=colormap,
            model_id="video_keyframe_hotspot_segmenter",
            roi_hints=roi_hints,
        )
        outputs.append(
            {
                "frame_order": frame.get("order"),
                "frame_index": frame.get("frame_index"),
                "timestamp_sec": frame.get("timestamp_sec"),
                "source_path": str(source_path),
                "prediction": payload["prediction"],
                "segmentation_mask": payload["segmentation_mask"],
                "lesion_evidence": payload["lesion_evidence"],
                "quantification": payload["quantification"],
                "domain_boundary": "Heuristic keyframe hotspot analysis; requires physician review and is not a diagnosis.",
            }
        )
    return outputs


def _video_frame_details(keyframes: list[dict[str, Any]], hotspot_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_order = {
        str(output.get("frame_order")): output
        for output in hotspot_outputs
        if output.get("frame_order") is not None
    }
    by_index = {
        str(output.get("frame_index")): output
        for output in hotspot_outputs
        if output.get("frame_index") is not None
    }
    details: list[dict[str, Any]] = []
    for detail_index, frame in enumerate(keyframes):
        hotspot_candidate = by_order.get(str(frame.get("order"))) or by_index.get(str(frame.get("frame_index"))) or {}
        hotspot: dict[str, Any] = hotspot_candidate if isinstance(hotspot_candidate, dict) else {}
        quantification_candidate = hotspot.get("quantification")
        quantification: dict[str, Any] = (
            quantification_candidate if isinstance(quantification_candidate, dict) else {}
        )
        lesion_evidence_candidate = hotspot.get("lesion_evidence")
        lesion_evidence: dict[str, Any] = (
            lesion_evidence_candidate if isinstance(lesion_evidence_candidate, dict) else {}
        )
        segmentation_mask_candidate = hotspot.get("segmentation_mask")
        segmentation_mask: dict[str, Any] = (
            segmentation_mask_candidate if isinstance(segmentation_mask_candidate, dict) else {}
        )
        candidates = lesion_evidence.get("candidates")
        top_component = candidates[0] if isinstance(candidates, list) and candidates else {}
        top_component = top_component if isinstance(top_component, dict) else {}
        bbox = top_component.get("bbox_xyxy")
        width = _positive_float(segmentation_mask.get("width"))
        height = _positive_float(segmentation_mask.get("height"))
        frame_index = frame.get("frame_index")
        component_count = int(_positive_float(quantification.get("component_count")))
        positive_fraction = float(quantification.get("positive_area_fraction", 0.0) or 0.0)
        details.append(
            {
                "frame_key": f"{frame_index}-{detail_index}",
                "frame_order": frame.get("order"),
                "frame_index": frame_index,
                "timestamp_sec": frame.get("timestamp_sec"),
                "preview_path": frame.get("preview_path") or frame.get("path"),
                "evidence_path": frame.get("evidence_path"),
                "source_path": hotspot.get("source_path") or frame.get("evidence_path") or frame.get("path"),
                "overlay_path": lesion_evidence.get("overlay_path"),
                "mask_path": segmentation_mask.get("path"),
                "pseudo_color_path": lesion_evidence.get("pseudo_color_path"),
                "positive_area_fraction": positive_fraction,
                "roi_positive_area_fraction": float(
                    quantification.get("roi_positive_area_fraction", 0.0) or 0.0
                ),
                "component_count": component_count,
                "p95_intensity": quantification.get("p95_intensity"),
                "top_component": top_component,
                "top_component_bbox_xyxy": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
                "top_component_bbox_normalized": _normalized_bbox(bbox, width=width, height=height),
                "selection_score": frame.get("selection_score"),
                "selection_rank": frame.get("selection_rank"),
                "quality": frame.get("quality", {}),
                "review_required": component_count > 0 or positive_fraction > 0,
                "domain_boundary": hotspot.get(
                    "domain_boundary",
                    "Heuristic keyframe hotspot analysis; requires physician review and is not a diagnosis.",
                ),
            }
        )
    return details


def _video_timeline_summary(keyframe_report: dict[str, Any]) -> dict[str, Any]:
    selection_trace = keyframe_report.get("selection_trace") if isinstance(keyframe_report.get("selection_trace"), dict) else {}
    candidates = selection_trace.get("candidates") if isinstance(selection_trace, dict) else []
    candidate_items = [candidate for candidate in candidates if isinstance(candidate, dict)] if isinstance(candidates, list) else []
    deduplication = selection_trace.get("deduplication") if isinstance(selection_trace, dict) else {}
    deduplication = deduplication if isinstance(deduplication, dict) else {}
    frame_count = _positive_int(keyframe_report.get("frame_count"))
    max_entries = _positive_int(keyframe_report.get("max_timeline_entries")) or 5000
    stride = max(1, int(np_ceil_div(frame_count, max_entries))) if frame_count else 1
    duplicate_items = [item for item in candidate_items if item.get("skipped_as_duplicate")]
    selected_items = [item for item in candidate_items if item.get("selected")]
    return {
        "schema_version": "osteo-vision-timeline-summary-v1",
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_scope": "full_duration_index_with_scored_candidates",
        "sampling_strategy": keyframe_report.get("sampling_strategy") or keyframe_report.get("sampling"),
        "frame_count": frame_count,
        "fps": keyframe_report.get("fps"),
        "duration_sec": keyframe_report.get("duration_sec"),
        "timeline_stride": stride,
        "max_timeline_entries": max_entries,
        "selected_frame_count": len(keyframe_report.get("keyframes") or []),
        "candidate_frame_count": len(candidate_items),
        "duplicate_candidate_count": int(deduplication.get("duplicate_candidate_count") or 0),
        "skipped_duplicate_count": int(deduplication.get("skipped_duplicate_count") or 0),
        "backfilled_duplicate_count": int(deduplication.get("backfilled_duplicate_count") or 0),
        "deduplication": deduplication,
        "selected_trace": _timeline_trace_items(selected_items, limit=8),
        "duplicate_trace": _timeline_trace_items(duplicate_items, limit=8),
        "candidate_trace": _timeline_trace_items(candidate_items, limit=12),
    }


def _timeline_trace_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    trace_items: list[dict[str, Any]] = []
    for item in items[:limit]:
        trace_items.append(
            {
                "frame_index": item.get("frame_index"),
                "selection_rank": item.get("selection_rank"),
                "selection_score": item.get("selection_score"),
                "selected": bool(item.get("selected")),
                "skipped_as_duplicate": bool(item.get("skipped_as_duplicate")),
                "selected_after_duplicate_backfill": bool(item.get("selected_after_duplicate_backfill")),
                "duplicate_of_frame_index": item.get("duplicate_of_frame_index"),
                "duplicate_similarity": item.get("duplicate_similarity"),
                "duplicate_group": item.get("duplicate_group"),
            }
        )
    return trace_items


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def np_ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return numerator
    return (numerator + denominator - 1) // denominator


def _write_video_frame_details_manifest(
    output_dir: Any,
    *,
    case_id: str,
    run_id: str,
    source_path: str,
    keyframe_report: dict[str, Any],
    frame_details: list[dict[str, Any]],
) -> str:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "frame_details_manifest.json"
    payload = {
        "schema_version": "osteo-vision-frame-details-manifest-v1",
        "case_id": case_id,
        "run_id": run_id,
        "source_path": source_path,
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
        "sampling_strategy": keyframe_report.get("sampling_strategy") or keyframe_report.get("sampling"),
        "video_frame_count": keyframe_report.get("frame_count"),
        "duration_sec": keyframe_report.get("duration_sec"),
        "selected_frame_count": len(frame_details),
        "frames": frame_details,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(manifest_path)


def _hotspot_summary(hotspot_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    fractions = [
        float(output.get("quantification", {}).get("positive_area_fraction", 0.0)) for output in hotspot_outputs
    ]
    component_counts = [int(output.get("quantification", {}).get("component_count", 0)) for output in hotspot_outputs]
    roi_fractions = [
        float(output.get("quantification", {}).get("roi_positive_area_fraction", 0.0)) for output in hotspot_outputs
    ]
    return {
        "hotspot_frame_count": len(hotspot_outputs),
        "hotspot_candidate_count": sum(component_counts),
        "hotspot_max_positive_area_fraction": max(fractions) if fractions else 0.0,
        "hotspot_mean_positive_area_fraction": sum(fractions) / len(fractions) if fractions else 0.0,
        "hotspot_roi_max_positive_area_fraction": max(roi_fractions) if roi_fractions else 0.0,
        "hotspot_roi_mean_positive_area_fraction": sum(roi_fractions) / len(roi_fractions) if roi_fractions else 0.0,
    }


def _hotspot_candidate_regions(run_id: str, hotspot_outputs: list[dict[str, Any]]) -> list[CandidateRegion]:
    ranked = sorted(
        hotspot_outputs,
        key=lambda item: float(item.get("quantification", {}).get("positive_area_fraction", 0.0)),
        reverse=True,
    )
    candidates: list[CandidateRegion] = []
    for output in ranked[:3]:
        quantification = output.get("quantification", {})
        fraction = float(quantification.get("positive_area_fraction", 0.0))
        if fraction <= 0:
            continue
        metadata = _hotspot_candidate_metadata(output, quantification)
        candidates.append(
            CandidateRegion(
                candidate_id=f"cand_video_hotspot_{uuid4().hex[:10]}",
                run_id=run_id,
                score=fraction,
                risk_type="video_keyframe_hotspot",
                confidence=float(quantification.get("p95_intensity", quantification.get("max_intensity", 0.0))),
                status=ReviewState.REVIEW_REQUIRED,
                explanation=(
                    "Heuristic fluorescence-like hotspot on MP4 keyframe "
                    f"{output.get('frame_index')} at {output.get('timestamp_sec')} seconds; physician review required."
                ),
                metadata=metadata,
            )
        )
    return candidates


def _hotspot_candidate_metadata(output: dict[str, Any], quantification: Any) -> dict[str, Any]:
    quant = quantification if isinstance(quantification, dict) else {}
    lesion_evidence = output.get("lesion_evidence") if isinstance(output.get("lesion_evidence"), dict) else {}
    hotspot_candidates = lesion_evidence.get("candidates") if isinstance(lesion_evidence, dict) else []
    top_candidate = hotspot_candidates[0] if isinstance(hotspot_candidates, list) and hotspot_candidates else {}
    top_candidate = top_candidate if isinstance(top_candidate, dict) else {}
    segmentation_mask = output.get("segmentation_mask") if isinstance(output.get("segmentation_mask"), dict) else {}
    width = _positive_float(segmentation_mask.get("width")) if isinstance(segmentation_mask, dict) else 0.0
    height = _positive_float(segmentation_mask.get("height")) if isinstance(segmentation_mask, dict) else 0.0
    bbox = top_candidate.get("bbox_xyxy")
    normalized = _normalized_bbox(bbox, width=width, height=height)
    return {
        "frame_order": output.get("frame_order"),
        "frame_index": output.get("frame_index"),
        "timestamp_sec": output.get("timestamp_sec"),
        "source_path": output.get("source_path"),
        "overlay_path": lesion_evidence.get("overlay_path") if isinstance(lesion_evidence, dict) else None,
        "mask_path": segmentation_mask.get("path") if isinstance(segmentation_mask, dict) else None,
        "positive_area_fraction": quant.get("positive_area_fraction"),
        "component_count": quant.get("component_count"),
        "top_component": top_candidate,
        "bbox_xyxy": bbox if isinstance(bbox, list) and len(bbox) == 4 else None,
        "bbox_normalized": normalized,
        "image_width": int(width) if width else None,
        "image_height": int(height) if height else None,
    }


def _positive_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed > 0 else 0.0


def _normalized_bbox(bbox: Any, *, width: float, height: float) -> dict[str, Any] | None:
    if not isinstance(bbox, list) or len(bbox) != 4 or width <= 0 or height <= 0:
        return None
    try:
        x0, y0, x1, y1 = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None
    x = max(0.0, min(1.0, x0 / width))
    y = max(0.0, min(1.0, y0 / height))
    rect_width = max(0.0, min(1.0 - x, (x1 - x0) / width))
    rect_height = max(0.0, min(1.0 - y, (y1 - y0) / height))
    if rect_width <= 0 or rect_height <= 0:
        return None
    return {
        "type": "rect",
        "coordinate_space": "normalized",
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(rect_width, 6),
        "height": round(rect_height, 6),
    }


def _hotspot_artifacts(case_id: str, run_id: str, hotspot_outputs: list[dict[str, Any]]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    mapping = [
        ("segmentation_mask", "path", ArtifactKind.ROI_MASK),
        ("lesion_evidence", "pseudo_color_path", ArtifactKind.HEATMAP),
        ("lesion_evidence", "overlay_path", ArtifactKind.OVERLAY),
    ]
    for output in hotspot_outputs:
        for parent_key, path_key, kind in mapping:
            path = output.get(parent_key, {}).get(path_key)
            if not path:
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


def _video_manifest_artifacts(case_id: str, run_id: str, paths: list[Any]) -> list[EvidenceArtifact]:
    artifacts: list[EvidenceArtifact] = []
    seen: set[str] = set()
    for path in paths:
        if not path:
            continue
        normalized = str(path)
        if normalized in seen or not Path(normalized).exists():
            continue
        seen.add(normalized)
        artifacts.append(
            EvidenceArtifact(
                artifact_id=f"artifact_{uuid4().hex[:10]}",
                case_id=case_id,
                run_id=run_id,
                kind=ArtifactKind.REPORT_JSON,
                path=normalized,
                checksum=checksum_for_file(normalized),
            )
        )
    return artifacts
