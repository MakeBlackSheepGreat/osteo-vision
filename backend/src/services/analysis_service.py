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
from src.core.schemas import AdapterRequest
from src.core.task_package import default_task_package, load_task_package
from src.engine.inference import MedicalImagingInferenceService
from src.models.adapters import build_adapter, model_spec_from_mapping
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
            segmentation_model_id = str(
                parameters.get("segmentation_model_id") or "convnext2d_keyframe_proxy_segmenter"
            )
            hotspot_outputs = _analyze_keyframe_segmentations(
                keyframes,
                output_dir / "keyframe_segmentations" / run_id,
                case_id=case.case_id,
                config_path=self.config_path,
                model_id=segmentation_model_id,
                threshold=float(parameters.get("hotspot_threshold", parameters.get("threshold", 0.6))),
                colormap=str(parameters.get("colormap", "green")),
                roi_hints=effective_roi_hints,
            )
            video_warnings.extend(_keyframe_segmentation_warnings(hotspot_outputs))
            frame_details = _video_frame_details(keyframes, hotspot_outputs, keyframe_report=keyframe_report)
            timeline_summary = _video_timeline_summary(keyframe_report)
            video_segmentation_outputs = (
                _write_video_segmentation_outputs(
                    output_dir / "video_segmentation" / run_id,
                    case_id=case.case_id,
                    run_id=run_id,
                    source_path=str(source_path),
                    keyframe_report=keyframe_report,
                    frame_details=frame_details,
                    hotspot_outputs=hotspot_outputs,
                )
                if keyframes
                else {}
            )
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
            video_candidates = _hotspot_candidate_regions(run_id, hotspot_outputs, frame_details=frame_details)
            hotspot_summary = _hotspot_summary(hotspot_outputs)
            temporal_summary = _video_temporal_summary(frame_details)
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
                        "keyframe_segmentation_outputs": hotspot_outputs,
                        "keyframe_segmentation_model_id": segmentation_model_id,
                        "frame_details": frame_details,
                        "quality_summary": keyframe_report.get("quality_summary", {}),
                        "keyframe_report_source": keyframe_report.get("report_source", "new_analysis_extract"),
                        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
                        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
                        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
                        "timeline_summary": timeline_summary,
                        "temporal_stability_summary": temporal_summary,
                        "frame_details_manifest_path": frame_details_manifest_path,
                        "video_segmentation_manifest_path": video_segmentation_outputs.get(
                            "video_segmentation_manifest_path"
                        ),
                        "segmentation_review_video_path": video_segmentation_outputs.get(
                            "segmentation_review_video_path"
                        ),
                        "mask_review_video_path": video_segmentation_outputs.get("mask_review_video_path"),
                        "video_segmentation_summary": video_segmentation_outputs.get("summary", {}),
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
                        "segmentation_frame_count": video_segmentation_outputs.get("summary", {}).get(
                            "selected_frame_count", 0
                        ),
                        "segmentation_overlay_video_available": bool(
                            video_segmentation_outputs.get("segmentation_review_video_path")
                        ),
                        "hotspot_temporal_instability_frame_count": temporal_summary.get(
                            "instability_frame_count", 0
                        ),
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
                        video_segmentation_outputs.get("video_segmentation_manifest_path"),
                    ],
                ),
                *_video_segmentation_artifacts(case.case_id, run_id, video_segmentation_outputs),
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


def _analyze_keyframe_segmentations(
    keyframes: list[dict[str, Any]],
    output_dir: Any,
    *,
    case_id: str,
    config_path: str,
    model_id: str,
    threshold: float,
    colormap: str,
    roi_hints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    model_adapter, model_warnings = _keyframe_model_adapter(
        config_path,
        model_id=model_id,
        output_dir=output_dir,
    )
    for frame in keyframes:
        source_path = frame.get("evidence_path") or frame.get("path")
        if not source_path:
            continue
        frame_case_id = f"{case_id}_frame_{int(frame.get('order', len(outputs) + 1)):02d}"
        payload: dict[str, Any] | None = None
        analysis_method = "heuristic_hotspot_fallback"
        frame_warnings = list(model_warnings)
        if model_adapter is not None:
            result = model_adapter.predict(
                AdapterRequest(
                    case_id=frame_case_id,
                    input_path=str(source_path),
                    input_type="2d_image",
                    task_type="segmentation",
                    modality="surgical_keyframe",
                    metadata={"roi_hints": roi_hints},
                )
            )
            model_payload = result.to_dict()
            frame_warnings.extend(model_payload.get("warnings", []))
            if model_payload.get("segmentation_mask", {}).get("path"):
                payload = model_payload
                analysis_method = "trainable_keyframe_segmenter"
        if payload is None:
            payload = segment_2d_fluorescence_hotspots(
                source_path,
                output_dir=Path(output_dir) / "hotspot_fallback",
                case_id=frame_case_id,
                threshold=threshold,
                min_component_area=25,
                colormap=colormap,
                model_id="video_keyframe_hotspot_segmenter",
                roi_hints=roi_hints,
            )
            frame_warnings.append(
                {
                    "code": "keyframe_segmenter_fell_back_to_hotspot",
                    "message": "Trainable keyframe segmenter was unavailable for this frame; hotspot fallback was used.",
                    "blocking": False,
                }
            )
        outputs.append(
            {
                "frame_order": frame.get("order"),
                "frame_index": frame.get("frame_index"),
                "timestamp_sec": frame.get("timestamp_sec"),
                "source_path": str(source_path),
                "model_id": payload.get("model_id")
                or payload.get("lesion_evidence", {}).get("source")
                or "video_keyframe_hotspot_segmenter",
                "model_family": payload.get("model_family"),
                "analysis_method": analysis_method,
                "prediction": payload["prediction"],
                "segmentation_mask": payload["segmentation_mask"],
                "lesion_evidence": payload["lesion_evidence"],
                "quantification": payload["quantification"],
                "warnings": frame_warnings,
                "domain_boundary": (
                    "Trainable 2D keyframe segmentation proxy on synthetic or pseudo-labeled data; "
                    "requires physician review and is not a diagnosis."
                    if analysis_method == "trainable_keyframe_segmenter"
                    else "Heuristic keyframe hotspot fallback; requires physician review and is not a diagnosis."
                ),
            }
        )
    return outputs


def _keyframe_model_adapter(config_path: str, *, model_id: str, output_dir: Any) -> tuple[Any | None, list[dict[str, Any]]]:
    model_mapping = _keyframe_model_mapping(config_path, model_id=model_id)
    if not model_mapping:
        return None, [
            {
                "code": "keyframe_segmenter_model_not_configured",
                "message": f"Keyframe segmentation model {model_id} is not configured; hotspot fallback will be used.",
                "blocking": False,
            }
        ]
    extra = dict(model_mapping.get("extra") or {})
    extra["output_dir"] = str(output_dir)
    model_mapping["extra"] = extra
    adapter = build_adapter(model_spec_from_mapping(model_mapping))
    status = adapter.warmup()
    if not status.available:
        return None, [
            *status.warnings,
            {
                "code": "keyframe_segmenter_model_unavailable",
                "message": (
                    f"Keyframe segmentation model {model_id} is unavailable: "
                    f"{'; '.join(status.reasons) or 'unknown reason'}; hotspot fallback will be used."
                ),
                "blocking": False,
            },
        ]
    return adapter, list(status.warnings)


def _keyframe_model_mapping(config_path: str, *, model_id: str) -> dict[str, Any] | None:
    runtime = dict(load_yaml(config_path).get("runtime") or {})
    for model in runtime.get("models") or []:
        if str(model.get("model_id")) == model_id:
            return dict(model)
    return None


def _keyframe_segmentation_warnings(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for output in outputs:
        for item in output.get("warnings", []):
            if not isinstance(item, dict):
                continue
            key = (str(item.get("code")), str(item.get("message")))
            if key in seen:
                continue
            seen.add(key)
            warnings.append(item)
    return warnings


def _video_frame_details(
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    *,
    keyframe_report: dict[str, Any],
) -> list[dict[str, Any]]:
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
    source_width = _positive_float(keyframe_report.get("width"))
    source_height = _positive_float(keyframe_report.get("height"))
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
        evidence_width = _positive_float(frame.get("evidence_width")) or width
        evidence_height = _positive_float(frame.get("evidence_height")) or height
        target_width = source_width or evidence_width or width
        target_height = source_height or evidence_height or height
        frame_index = frame.get("frame_index")
        component_count = int(_positive_float(quantification.get("component_count")))
        positive_fraction = float(quantification.get("positive_area_fraction", 0.0) or 0.0)
        normalized_bbox = _normalized_bbox(bbox, width=width, height=height)
        bbox_source = _scaled_bbox(
            bbox,
            from_width=width,
            from_height=height,
            to_width=target_width,
            to_height=target_height,
        )
        bbox_evidence = _scaled_bbox(
            bbox,
            from_width=width,
            from_height=height,
            to_width=evidence_width,
            to_height=evidence_height,
        )
        bbox_source_normalized = _normalized_bbox(bbox_source, width=target_width, height=target_height)
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
                "top_component_bbox_normalized": normalized_bbox,
                "spatial_mapping": {
                    "schema_version": "osteo-vision-keyframe-spatial-mapping-v1",
                    "mask_coordinate_space": "keyframe_mask_pixels",
                    "evidence_coordinate_space": "keyframe_evidence_pixels",
                    "source_coordinate_space": "source_video_pixels",
                    "mask_width": int(width) if width else None,
                    "mask_height": int(height) if height else None,
                    "evidence_width": int(evidence_width) if evidence_width else None,
                    "evidence_height": int(evidence_height) if evidence_height else None,
                    "source_video_width": int(source_width) if source_width else None,
                    "source_video_height": int(source_height) if source_height else None,
                    "scale_x_mask_to_source": _safe_scale_ratio(target_width, width),
                    "scale_y_mask_to_source": _safe_scale_ratio(target_height, height),
                    "top_component_bbox_evidence_xyxy": bbox_evidence,
                    "top_component_bbox_source_xyxy": bbox_source,
                    "top_component_bbox_source_normalized": bbox_source_normalized,
                    "mapping_status": (
                        "source_video_coordinates_available"
                        if bbox_source and target_width and target_height
                        else "bbox_or_source_geometry_missing"
                    ),
                    "patch_based_inference": {
                        "applied": False,
                        "ready_coordinate_contract": "source_video_pixels_xyxy",
                    },
                },
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
    return _attach_video_temporal_context(details)


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
        "temporal_stability_summary": _video_temporal_summary(frame_details),
        "frames": frame_details,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(manifest_path)


def _write_video_segmentation_outputs(
    output_dir: Any,
    *,
    case_id: str,
    run_id: str,
    source_path: str,
    keyframe_report: dict[str, Any],
    frame_details: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    frames = _video_segmentation_frames(frame_details, hotspot_outputs)
    overlay_paths = [str(frame["fluorescence_overlay_result"]["overlay_path"]) for frame in frames if frame.get("fluorescence_overlay_result", {}).get("overlay_path")]
    mask_paths = [str(frame["segmentation_result"]["mask_path"]) for frame in frames if frame.get("segmentation_result", {}).get("mask_path")]
    fps = _review_video_fps(keyframe_report.get("fps"))
    overlay_video_path = _write_image_sequence_video(
        overlay_paths,
        target_dir / "mp4_keyframe_segmentation_overlay_review.mp4",
        fps=fps,
    )
    mask_video_path = _write_image_sequence_video(
        mask_paths,
        target_dir / "mp4_keyframe_segmentation_mask_review.mp4",
        fps=fps,
    )
    model_summary = _video_segmentation_model_summary(hotspot_outputs)
    summary = {
        "schema_version": "osteo-vision-video-segmentation-summary-v1",
        "selected_frame_count": len(frames),
        "mask_frame_count": len(mask_paths),
        "overlay_frame_count": len(overlay_paths),
        "segmentation_review_video_available": bool(overlay_video_path),
        "mask_review_video_available": bool(mask_video_path),
        "model_id": model_summary["primary_model_id"],
        "model_ids": model_summary["model_ids"],
        "analysis_methods": model_summary["analysis_methods"],
        "analysis_scope": "selected_mp4_keyframes",
        "temporal_stability": _video_temporal_summary(frame_details),
        "medical_boundary": "Research prototype keyframe segmentation; not a clinical diagnosis.",
    }
    manifest_path = target_dir / "video_segmentation_manifest.json"
    payload = {
        "schema_version": "osteo-vision-video-segmentation-manifest-v1",
        "case_id": case_id,
        "run_id": run_id,
        "source_path": source_path,
        "source_video": {
            "width": keyframe_report.get("width"),
            "height": keyframe_report.get("height"),
            "fps": keyframe_report.get("fps"),
            "frame_count": keyframe_report.get("frame_count"),
            "duration_sec": keyframe_report.get("duration_sec"),
        },
        "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
        "frame_index_manifest_path": keyframe_report.get("frame_index_manifest_path"),
        "timeline_manifest_path": keyframe_report.get("timeline_manifest_path"),
        "segmentation_review_video_path": overlay_video_path,
        "mask_review_video_path": mask_video_path,
        "summary": summary,
        "frames": frames,
        "disclaimer": disclaimer_context(),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "video_segmentation_manifest_path": str(manifest_path),
        "segmentation_review_video_path": overlay_video_path,
        "mask_review_video_path": mask_video_path,
        "summary": summary,
    }


def _video_segmentation_frames(
    frame_details: list[dict[str, Any]], hotspot_outputs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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
    frames: list[dict[str, Any]] = []
    for detail in frame_details:
        output = by_order.get(str(detail.get("frame_order"))) or by_index.get(str(detail.get("frame_index"))) or {}
        segmentation_mask = output.get("segmentation_mask") if isinstance(output.get("segmentation_mask"), dict) else {}
        lesion_evidence = output.get("lesion_evidence") if isinstance(output.get("lesion_evidence"), dict) else {}
        quantification = output.get("quantification") if isinstance(output.get("quantification"), dict) else {}
        frames.append(
            {
                "frame_key": detail.get("frame_key"),
                "frame_order": detail.get("frame_order"),
                "frame_index": detail.get("frame_index"),
                "timestamp_sec": detail.get("timestamp_sec"),
                "evidence_path": detail.get("evidence_path") or detail.get("source_path"),
                "preview_path": detail.get("preview_path"),
                "segmentation_result": {
                    "model_id": output.get("model_id") or "video_keyframe_hotspot_segmenter",
                    "model_family": output.get("model_family"),
                    "analysis_method": output.get("analysis_method"),
                    "format": segmentation_mask.get("format", "png_binary_mask"),
                    "mask_path": segmentation_mask.get("path") or detail.get("mask_path"),
                    "probability_path": lesion_evidence.get("probability_path"),
                    "width": segmentation_mask.get("width"),
                    "height": segmentation_mask.get("height"),
                    "threshold": segmentation_mask.get("threshold"),
                    "positive_area_px": segmentation_mask.get("positive_area_px"),
                    "positive_area_fraction": quantification.get("positive_area_fraction"),
                    "component_count": quantification.get("component_count"),
                },
                "fluorescence_overlay_result": {
                    "format": "png_pseudocolor_overlay",
                    "overlay_path": lesion_evidence.get("overlay_path") or detail.get("overlay_path"),
                    "pseudo_color_path": lesion_evidence.get("pseudo_color_path") or detail.get("pseudo_color_path"),
                    "enhanced_path": lesion_evidence.get("enhanced_path"),
                },
                "candidate_result": {
                    "top_component_bbox_xyxy": detail.get("top_component_bbox_xyxy"),
                    "top_component_bbox_normalized": detail.get("top_component_bbox_normalized"),
                    "top_component_bbox_source_xyxy": detail.get("spatial_mapping", {}).get(
                        "top_component_bbox_source_xyxy"
                    ),
                    "top_component_bbox_source_normalized": detail.get("spatial_mapping", {}).get(
                        "top_component_bbox_source_normalized"
                    ),
                    "bbox_temporal_smoothing_candidate_source_xyxy": detail.get(
                        "temporal_stability", {}
                    ).get("bbox_smoothing_candidate_source_xyxy"),
                    "component_count": detail.get("component_count"),
                    "review_required": detail.get("review_required"),
                },
                "spatial_mapping": detail.get("spatial_mapping"),
                "temporal_stability": detail.get("temporal_stability"),
                "medical_boundary": detail.get(
                    "domain_boundary",
                    "Heuristic keyframe hotspot analysis; requires physician review and is not a diagnosis.",
                ),
            }
        )
    return frames


def _video_segmentation_model_summary(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    model_ids = sorted(
        {
            str(output.get("model_id") or "video_keyframe_hotspot_segmenter")
            for output in outputs
            if isinstance(output, dict)
        }
    )
    methods = sorted(
        {str(output.get("analysis_method") or "unknown") for output in outputs if isinstance(output, dict)}
    )
    primary = model_ids[0] if len(model_ids) == 1 else "mixed_keyframe_segmentation"
    return {"primary_model_id": primary, "model_ids": model_ids, "analysis_methods": methods}


def _write_image_sequence_video(paths: list[str], output_path: Path, *, fps: float, max_side: int = 1280) -> str | None:
    existing = [Path(path) for path in paths if path and Path(path).exists()]
    if not existing:
        return None
    try:
        import cv2
    except Exception:
        return None
    first = cv2.imread(str(existing[0]), cv2.IMREAD_COLOR)
    if first is None:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_width, target_height = _review_video_size(first.shape[1], first.shape[0], max_side=max_side)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        max(0.5, float(fps)),
        (target_width, target_height),
    )
    if not writer.isOpened():
        return None
    try:
        for path in existing:
            frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
            writer.write(frame)
    finally:
        writer.release()
    return str(output_path) if output_path.exists() else None


def _review_video_size(width: int, height: int, *, max_side: int) -> tuple[int, int]:
    width = max(2, int(width))
    height = max(2, int(height))
    longest = max(width, height)
    if longest <= max_side:
        return _even(width), _even(height)
    scale = float(max_side) / float(longest)
    return _even(max(2, round(width * scale))), _even(max(2, round(height * scale)))


def _even(value: int) -> int:
    return int(value) if int(value) % 2 == 0 else int(value) - 1


def _review_video_fps(value: Any) -> float:
    try:
        fps = float(value)
    except (TypeError, ValueError):
        return 2.0
    if fps <= 0:
        return 2.0
    return min(8.0, max(1.0, fps))


def _attach_video_temporal_context(frame_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for index, detail in enumerate(frame_details):
        previous_detail = frame_details[index - 1] if index > 0 else None
        next_detail = frame_details[index + 1] if index + 1 < len(frame_details) else None
        window = [
            candidate
            for candidate in (previous_detail, detail, next_detail)
            if isinstance(candidate, dict)
        ]
        fractions = [float(candidate.get("positive_area_fraction") or 0.0) for candidate in window]
        current_fraction = float(detail.get("positive_area_fraction") or 0.0)
        previous_fraction = (
            float(previous_detail.get("positive_area_fraction") or 0.0)
            if isinstance(previous_detail, dict)
            else None
        )
        next_fraction = (
            float(next_detail.get("positive_area_fraction") or 0.0) if isinstance(next_detail, dict) else None
        )
        bbox_source = _detail_source_bbox(detail)
        previous_bbox_source = _detail_source_bbox(previous_detail)
        smoothed_bbox = _median_bbox([_detail_source_bbox(candidate) for candidate in window])
        shift_px = _bbox_center_shift(bbox_source, previous_bbox_source)
        spatial_mapping = detail.get("spatial_mapping") if isinstance(detail.get("spatial_mapping"), dict) else {}
        source_width = _positive_float(spatial_mapping.get("source_video_width") or spatial_mapping.get("mask_width"))
        source_height = _positive_float(spatial_mapping.get("source_video_height") or spatial_mapping.get("mask_height"))
        source_diagonal = (source_width**2 + source_height**2) ** 0.5 if source_width and source_height else 0.0
        shift_fraction = float(shift_px / source_diagonal) if shift_px is not None and source_diagonal else None
        fraction_delta_previous = (
            abs(current_fraction - previous_fraction) if previous_fraction is not None else None
        )
        fraction_delta_next = abs(current_fraction - next_fraction) if next_fraction is not None else None
        instability_score = max(
            [
                value
                for value in (
                    fraction_delta_previous,
                    fraction_delta_next,
                    shift_fraction,
                )
                if value is not None
            ]
            or [0.0]
        )
        enriched_detail = {
            **detail,
            "temporal_stability": {
                "schema_version": "osteo-vision-keyframe-temporal-stability-v1",
                "smoothing_method": "three_frame_moving_average_metadata",
                "smoothing_applied_to_mask": False,
                "positive_area_fraction": current_fraction,
                "positive_area_fraction_smoothed": (
                    round(sum(fractions) / len(fractions), 8) if fractions else current_fraction
                ),
                "positive_area_fraction_delta_previous": (
                    round(fraction_delta_previous, 8) if fraction_delta_previous is not None else None
                ),
                "positive_area_fraction_delta_next": (
                    round(fraction_delta_next, 8) if fraction_delta_next is not None else None
                ),
                "bbox_center_shift_previous_px": round(shift_px, 4) if shift_px is not None else None,
                "bbox_center_shift_previous_fraction": (
                    round(shift_fraction, 8) if shift_fraction is not None else None
                ),
                "bbox_smoothing_candidate_source_xyxy": smoothed_bbox,
                "instability_score": round(float(instability_score), 8),
                "flicker_warning": bool(instability_score >= 0.05),
                "review_note": (
                    "Temporal values stabilize keyframe review metadata only; binary masks remain unchanged "
                    "and require physician review."
                ),
            },
        }
        enriched.append(enriched_detail)
    return enriched


def _video_temporal_summary(frame_details: list[dict[str, Any]]) -> dict[str, Any]:
    stability_items = [
        detail.get("temporal_stability")
        for detail in frame_details
        if isinstance(detail.get("temporal_stability"), dict)
    ]
    instability_scores = [float(item.get("instability_score") or 0.0) for item in stability_items]
    previous_deltas = [
        float(item["positive_area_fraction_delta_previous"])
        for item in stability_items
        if item.get("positive_area_fraction_delta_previous") is not None
    ]
    shift_fractions = [
        float(item["bbox_center_shift_previous_fraction"])
        for item in stability_items
        if item.get("bbox_center_shift_previous_fraction") is not None
    ]
    return {
        "schema_version": "osteo-vision-video-temporal-stability-summary-v1",
        "frame_count": len(frame_details),
        "smoothing_method": "three_frame_moving_average_metadata",
        "smoothing_applied_to_mask": False,
        "instability_frame_count": sum(1 for item in stability_items if item.get("flicker_warning")),
        "max_instability_score": max(instability_scores) if instability_scores else 0.0,
        "mean_positive_area_fraction_delta_previous": (
            sum(previous_deltas) / len(previous_deltas) if previous_deltas else 0.0
        ),
        "max_bbox_center_shift_previous_fraction": max(shift_fractions) if shift_fractions else 0.0,
        "medical_boundary": "Temporal smoothing metadata is for review stability only and is not diagnostic.",
    }


def _detail_source_bbox(detail: Any) -> list[int] | None:
    if not isinstance(detail, dict):
        return None
    spatial_mapping = detail.get("spatial_mapping") if isinstance(detail.get("spatial_mapping"), dict) else {}
    bbox = spatial_mapping.get("top_component_bbox_source_xyxy") or detail.get("top_component_bbox_xyxy")
    return _int_bbox(bbox)


def _median_bbox(bboxes: list[list[int] | None]) -> list[int] | None:
    valid = [bbox for bbox in bboxes if bbox and len(bbox) == 4]
    if not valid:
        return None
    return [int(round(_median([bbox[index] for bbox in valid]))) for index in range(4)]


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float(ordered[middle - 1] + ordered[middle]) / 2.0


def _bbox_center_shift(current: list[int] | None, previous: list[int] | None) -> float | None:
    if not current or not previous:
        return None
    current_x = (float(current[0]) + float(current[2])) / 2.0
    current_y = (float(current[1]) + float(current[3])) / 2.0
    previous_x = (float(previous[0]) + float(previous[2])) / 2.0
    previous_y = (float(previous[1]) + float(previous[3])) / 2.0
    return ((current_x - previous_x) ** 2 + (current_y - previous_y) ** 2) ** 0.5


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


def _hotspot_candidate_regions(
    run_id: str, hotspot_outputs: list[dict[str, Any]], *, frame_details: list[dict[str, Any]]
) -> list[CandidateRegion]:
    details_by_order = {
        str(detail.get("frame_order")): detail for detail in frame_details if detail.get("frame_order") is not None
    }
    details_by_index = {
        str(detail.get("frame_index")): detail for detail in frame_details if detail.get("frame_index") is not None
    }
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
        analysis_method = str(output.get("analysis_method") or "heuristic_hotspot_fallback")
        model_id = str(output.get("model_id") or "video_keyframe_hotspot_segmenter")
        metadata = _hotspot_candidate_metadata(output, quantification)
        detail = (
            details_by_order.get(str(output.get("frame_order")))
            or details_by_index.get(str(output.get("frame_index")))
            or {}
        )
        if detail:
            spatial_mapping = detail.get("spatial_mapping") if isinstance(detail.get("spatial_mapping"), dict) else {}
            temporal_stability = (
                detail.get("temporal_stability") if isinstance(detail.get("temporal_stability"), dict) else {}
            )
            metadata.update(
                {
                    "source_bbox_xyxy": spatial_mapping.get("top_component_bbox_source_xyxy"),
                    "source_bbox_normalized": spatial_mapping.get("top_component_bbox_source_normalized"),
                    "source_video_width": spatial_mapping.get("source_video_width"),
                    "source_video_height": spatial_mapping.get("source_video_height"),
                    "spatial_mapping": spatial_mapping,
                    "temporal_stability": temporal_stability,
                }
            )
        candidates.append(
            CandidateRegion(
                candidate_id=f"cand_video_hotspot_{uuid4().hex[:10]}",
                run_id=run_id,
                score=fraction,
                risk_type=(
                    "video_keyframe_model_segmentation"
                    if analysis_method == "trainable_keyframe_segmenter"
                    else "video_keyframe_hotspot"
                ),
                confidence=_candidate_confidence(quantification),
                status=ReviewState.REVIEW_REQUIRED,
                explanation=(
                    (
                        f"Trainable proxy segmentation model {model_id} on MP4 keyframe "
                        if analysis_method == "trainable_keyframe_segmenter"
                        else "Heuristic fluorescence-like hotspot on MP4 keyframe "
                    )
                    + f"{output.get('frame_index')} at {output.get('timestamp_sec')} seconds; "
                    "physician review required."
                ),
                metadata=metadata,
            )
        )
    return candidates


def _candidate_confidence(quantification: Any) -> float:
    quant = quantification if isinstance(quantification, dict) else {}
    for key in ("max_probability", "mean_probability", "p95_intensity", "max_intensity"):
        value = quant.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


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
        "model_id": output.get("model_id"),
        "model_family": output.get("model_family"),
        "analysis_method": output.get("analysis_method"),
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


def _safe_scale_ratio(numerator: float, denominator: float) -> float | None:
    if numerator <= 0 or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _scaled_bbox(
    bbox: Any,
    *,
    from_width: float,
    from_height: float,
    to_width: float,
    to_height: float,
) -> list[int] | None:
    parsed = _int_bbox(bbox)
    if not parsed or from_width <= 0 or from_height <= 0 or to_width <= 0 or to_height <= 0:
        return None
    scale_x = float(to_width) / float(from_width)
    scale_y = float(to_height) / float(from_height)
    x0, y0, x1, y1 = parsed
    scaled = [
        int(round(x0 * scale_x)),
        int(round(y0 * scale_y)),
        int(round(x1 * scale_x)),
        int(round(y1 * scale_y)),
    ]
    scaled[0] = max(0, min(int(round(to_width)), scaled[0]))
    scaled[2] = max(0, min(int(round(to_width)), scaled[2]))
    scaled[1] = max(0, min(int(round(to_height)), scaled[1]))
    scaled[3] = max(0, min(int(round(to_height)), scaled[3]))
    if scaled[2] <= scaled[0] or scaled[3] <= scaled[1]:
        return None
    return scaled


def _int_bbox(bbox: Any) -> list[int] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        parsed = [int(round(float(value))) for value in bbox]
    except (TypeError, ValueError):
        return None
    if parsed[2] <= parsed[0] or parsed[3] <= parsed[1]:
        return None
    return parsed


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
        ("lesion_evidence", "probability_path", ArtifactKind.PROBABILITY_MAP),
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


def _video_segmentation_artifacts(
    case_id: str, run_id: str, outputs: dict[str, Any]
) -> list[EvidenceArtifact]:
    mapping = [
        ("video_segmentation_manifest_path", ArtifactKind.VIDEO_SEGMENTATION_MANIFEST),
        ("segmentation_review_video_path", ArtifactKind.VIDEO_OVERLAY),
        ("mask_review_video_path", ArtifactKind.VIDEO_MASK),
    ]
    artifacts: list[EvidenceArtifact] = []
    for path_key, kind in mapping:
        path = outputs.get(path_key)
        if not path or not Path(str(path)).exists():
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
