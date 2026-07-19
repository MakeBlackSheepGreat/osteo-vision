from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import case_artifact_dir
from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.annotations.repository import AnnotationRepository
from backend.src.domains.cases.enums import CaseStatus, InputChannel
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import (
    AnalysisRun,
    CandidateRegion,
    CaseInputAsset,
    CaseRecord,
)
from backend.src.services.analysis_outputs import (
    bone_activity_checkpoint_artifacts as _bone_activity_checkpoint_artifacts,
)
from backend.src.services.analysis_outputs import fusion_artifacts as _fusion_artifacts
from backend.src.services.analysis_outputs import fusion_candidate_regions as _fusion_candidate_regions
from backend.src.services.analysis_outputs import fusion_fused_outputs as _fusion_fused_outputs
from backend.src.services.analysis_outputs import fusion_quantitative_summary as _fusion_quantitative_summary
from backend.src.services.analysis_outputs import merge_roi_hints as _merge_roi_hints
from backend.src.services.analysis_outputs import missing_dual_channel_warning as _missing_dual_channel_warning
from backend.src.services.analysis_outputs import patient_conditioning_artifacts as _patient_conditioning_artifacts
from backend.src.services.analysis_outputs import three_channel_quality_artifacts as _three_channel_quality_artifacts
from backend.src.services.analysis_outputs import video_artifacts as _video_artifacts
from backend.src.services.analysis_outputs import video_fused_outputs as _video_fused_outputs
from backend.src.services.analysis_outputs import video_quantitative_summary as _video_quantitative_summary
from backend.src.services.clinical_context_assessment import (
    assess_clinical_context,
    clinical_context_warnings,
)
from backend.src.services.keyframe_report_loader import keyframe_report_for_analysis as _keyframe_report_for_analysis
from backend.src.services.keyframe_report_loader import numeric_sequence as _numeric_sequence
from backend.src.services.keyframe_segmentation import analyze_keyframe_segmentations as _analyze_keyframe_segmentations
from backend.src.services.keyframe_segmentation import keyframe_segmentation_warnings as _keyframe_segmentation_warnings
from backend.src.services.patient_conditioning_gate import (
    resolve_trusted_reviewed_bone_gate,
    target_domain_input_gate,
)
from backend.src.services.three_d_evidence import build_three_d_evidence as _build_three_d_evidence
from backend.src.services.video_analysis_details import build_video_frame_details as _video_frame_details
from backend.src.services.video_analysis_details import build_video_timeline_summary as _video_timeline_summary
from backend.src.services.video_hotspot_outputs import build_hotspot_candidate_regions as _hotspot_candidate_regions
from backend.src.services.video_hotspot_outputs import summarize_hotspot_outputs as _hotspot_summary
from backend.src.services.video_keyframe_metrics import (
    video_fluorescence_dynamics_summary,
    video_inference_performance_summary,
    video_temporal_summary,
)
from backend.src.services.video_segmentation_manifest import (
    write_video_frame_details_manifest as _write_video_frame_details_manifest,
)
from backend.src.services.video_segmentation_manifest import (
    write_video_segmentation_outputs as _write_video_segmentation_outputs,
)
from src.core.config import load_yaml
from src.core.paths import artifact_dirs
from src.core.schemas import AdapterRequest
from src.core.task_package import default_task_package, load_task_package
from src.engine.inference import MedicalImagingInferenceService
from src.io.live_stream import LiveStreamCaptureConfig, capture_live_keyframes
from src.models.adapters import build_adapter, model_spec_from_mapping
from src.preprocess.fluorescence import fuse_white_light_fluorescence
from src.preprocess.three_channel_quality import assess_three_channel_quality

_BONE_ACTIVITY_ENGINEERING_CANDIDATE_MODEL_ID = "bone_activity_multitask_d074_proxy_candidate"
_BONE_ACTIVITY_ENGINEERING_CANDIDATE_FAMILY = "bone_activity_multitask"


class AnalysisService:
    def __init__(
        self,
        repo: CaseRepository,
        config_path: str = "configs/inference/osteo_vision.yml",
        annotation_repository: AnnotationRepository | None = None,
    ) -> None:
        self.repo = repo
        self.config_path = config_path
        self.annotation_repository = annotation_repository

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
        effective_parameters = dict(parameters)
        effective_parameters.update(_clinical_context_analysis_parameters(case))
        if case.three_d_evidence and not isinstance(effective_parameters.get("three_d_evidence"), dict):
            effective_parameters["three_d_evidence"] = case.three_d_evidence
        effective_roi_hints = _merge_roi_hints(case, roi_hints)
        run_parameters = (
            {**effective_parameters, "roi_hints": effective_roi_hints} if effective_roi_hints else effective_parameters
        )
        run = AnalysisRun(
            run_id=run_id,
            case_id=case.case_id,
            method_id=self._method_id(),
            parameters=run_parameters,
            status="running",
        )
        selected_inputs, selection_warnings = self._select_inputs(case, selected_input_ids)
        selection_warnings = [
            *selection_warnings,
            *clinical_context_warnings(effective_parameters["clinical_context_assessment"]),
        ]
        if any(warning.get("blocking") for warning in selection_warnings):
            return self._finish_failed_run(case, run, selection_warnings)

        # start_analysis 只负责分流：实时预览、MP4 keyframe、双通道 JPEG 分别独立维护。
        white = self._pick_input(selected_inputs, InputChannel.WHITE_LIGHT)
        fluor = self._pick_input(selected_inputs, InputChannel.FLUORESCENCE)
        device_overlay = self._pick_input(selected_inputs, InputChannel.DEVICE_OVERLAY)
        video = self._pick_input(selected_inputs, InputChannel.VIDEO)
        video_analysis_requested = bool(
            effective_parameters.get("mode") in {"realtime_video", "video_file"} or (video and not (white and fluor))
        )
        if video_analysis_requested and not str(effective_parameters.get("segmentation_model_id") or "").strip():
            effective_parameters["segmentation_model_id"] = self._configured_segmentation_model_id()
            run_parameters = (
                {**effective_parameters, "roi_hints": effective_roi_hints}
                if effective_roi_hints
                else effective_parameters
            )
            run = run.model_copy(update={"parameters": run_parameters})
        if effective_parameters.get("mode") == "realtime_video":
            try:
                return self._complete_realtime_video_analysis(
                    case,
                    run,
                    output_dir=output_dir,
                    parameters=effective_parameters,
                    selection_warnings=selection_warnings,
                    effective_roi_hints=effective_roi_hints,
                )
            except Exception as exc:
                failure = {
                    "code": "realtime_analysis_failed",
                    "message": "Realtime capture or analysis stopped after an unexpected failure.",
                    "blocking": True,
                    "failure_stage": "realtime_pipeline",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                return self._finish_failed_run(case, run, [*selection_warnings, failure])
        if effective_parameters.get("mode") == "video_file" or (video and not (white and fluor)):
            return self._complete_video_file_analysis(
                case,
                run,
                output_dir=output_dir,
                video=video,
                parameters=effective_parameters,
                selection_warnings=selection_warnings,
                effective_roi_hints=effective_roi_hints,
            )
        return self._complete_dual_channel_analysis(
            case,
            run,
            output_dir=output_dir,
            white=white,
            fluor=fluor,
            device_overlay=device_overlay,
            parameters=effective_parameters,
            selection_warnings=selection_warnings,
            effective_roi_hints=effective_roi_hints,
        )

    def _finish_failed_run(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        warnings: list[dict[str, Any]],
    ) -> CaseRecord:
        run = run.model_copy(update={"status": "failed", "warnings": warnings})
        updated = case.model_copy(
            update={
                "analysis_runs": [*case.analysis_runs, run],
                "warnings": [*case.warnings, *warnings],
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def _complete_realtime_video_analysis(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        *,
        output_dir: Path,
        parameters: dict[str, Any],
        selection_warnings: list[dict[str, Any]],
        effective_roi_hints: list[dict[str, Any]],
    ) -> CaseRecord:
        source_path = str(parameters.get("source_path") or "camera://browser/default")
        browser_frame_paths = _browser_frame_paths(parameters.get("browser_frame_paths"))
        if source_path.startswith("camera://browser") and not browser_frame_paths:
            realtime_warnings = [
                {
                    "code": "realtime_stream_not_connected",
                    "message": "Browser camera preview is local to the browser and has no backend frame transport.",
                    "blocking": False,
                }
            ]
            all_warnings = [*selection_warnings, *realtime_warnings]
            run = run.model_copy(
                update={
                    "status": "completed",
                    "fused_outputs": {
                        "mode": "realtime_preview_only",
                        "source_path": source_path,
                        "stream_ai_connected": False,
                        "analysis_available": False,
                        "decision_support_available": False,
                        "roi_hints": effective_roi_hints,
                        "disclaimer_context": disclaimer_context(),
                    },
                    "quantitative_summary": {
                        "roi_hint_count": len(effective_roi_hints),
                        "stream_ai_connected": False,
                    },
                    "warnings": all_warnings,
                }
            )
            updated = case.model_copy(
                update={
                    "analysis_runs": [*case.analysis_runs, run],
                    "warnings": [*case.warnings, *all_warnings],
                }
            )
            updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
            self.repo.save(updated)
            return updated

        analysis_mode = "browser_frame_keyframes" if browser_frame_paths else "realtime_stream_keyframes"
        if browser_frame_paths:
            capture_report = _browser_frame_capture_report(
                browser_frame_paths,
                output_dir / "live_stream" / run.run_id / "frame_index_manifest.json",
                max_frames=max(1, int(parameters.get("keyframe_count", 5))),
                captured_at=str(parameters.get("browser_frame_captured_at") or ""),
                session_id=str(parameters.get("browser_camera_session_id") or ""),
                sequence=parameters.get("browser_frame_sequence"),
                trigger=str(parameters.get("browser_frame_trigger") or "manual"),
            )
        else:
            capture_report = capture_live_keyframes(
                source_path,
                output_dir / "live_stream" / run.run_id,
                config=LiveStreamCaptureConfig(
                    max_keyframes=max(1, int(parameters.get("keyframe_count", 5))),
                    keyframe_stride=max(1, int(parameters.get("live_keyframe_stride", 15))),
                    queue_size=max(1, int(parameters.get("live_queue_size", 8))),
                    open_timeout_sec=max(0.1, float(parameters.get("live_open_timeout_sec", 5.0))),
                    read_timeout_sec=max(0.1, float(parameters.get("live_read_timeout_sec", 2.0))),
                    capture_timeout_sec=max(0.1, float(parameters.get("live_capture_timeout_sec", 15.0))),
                    jpeg_quality=min(100, max(1, int(parameters.get("live_jpeg_quality", 92)))),
                ),
            )
        live_warnings = [
            *selection_warnings,
            *list(capture_report.get("warnings") or []),
        ]
        keyframes = list(capture_report.get("keyframes") or [])
        if not keyframes:
            if not any(bool(item.get("blocking")) for item in live_warnings):
                live_warnings.append(
                    {
                        "code": "live_stream_no_keyframes",
                        "message": "The configured live source produced no analyzable keyframes.",
                        "blocking": True,
                    }
                )
            return self._finish_failed_run(case, run, live_warnings)

        segmentation_model_id = str(parameters.get("segmentation_model_id") or self._configured_segmentation_model_id())
        hotspot_outputs = _analyze_keyframe_segmentations(
            keyframes,
            output_dir / "keyframe_segmentations" / run.run_id,
            case_id=case.case_id,
            config_path=self.config_path,
            model_id=segmentation_model_id,
            threshold=float(parameters.get("hotspot_threshold", parameters.get("threshold", 0.6))),
            colormap=str(parameters.get("colormap", "green")),
            roi_hints=effective_roi_hints,
            allow_heuristic_fallback=self._heuristic_keyframe_fallback_allowed(),
        )
        segmentation_warnings = _keyframe_segmentation_warnings(hotspot_outputs)
        live_warnings.extend(segmentation_warnings)
        if any(bool(item.get("blocking")) for item in segmentation_warnings):
            failed_run = run.model_copy(
                update={
                    "fused_outputs": {
                        "mode": analysis_mode,
                        "source_path": source_path,
                        "segmentation_model_id": segmentation_model_id,
                        "keyframes": keyframes,
                        "keyframe_segmentations": hotspot_outputs,
                        "analysis_available": False,
                        "decision_support_available": False,
                        "stream_ai_connected": False,
                        "disclaimer_context": disclaimer_context(),
                    },
                    "quantitative_summary": {
                        "keyframes_extracted": len(keyframes),
                        "analysis_available": False,
                    },
                }
            )
            return self._finish_failed_run(case, failed_run, live_warnings)
        max_frame_age_ms = max(1.0, float(parameters.get("live_max_frame_age_ms", 2000.0)))
        frame_age_summary = _apply_live_frame_age_gate(
            keyframes,
            hotspot_outputs,
            max_frame_age_ms=max_frame_age_ms,
        )
        all_warnings = list(live_warnings)
        frame_details = _video_frame_details(keyframes, hotspot_outputs, keyframe_report=capture_report)
        _merge_live_frame_age_details(frame_details, keyframes)
        timeline_summary = _video_timeline_summary(capture_report)
        three_d_evidence = _build_three_d_evidence(
            parameters=parameters,
            source_inputs=[],
            analysis_mode=analysis_mode,
            run_id=run.run_id,
        )
        video_segmentation_outputs = _write_video_segmentation_outputs(
            output_dir / "video_segmentation" / run.run_id,
            case_id=case.case_id,
            run_id=run.run_id,
            source_path=source_path,
            keyframe_report=capture_report,
            frame_details=frame_details,
            hotspot_outputs=hotspot_outputs,
            three_d_evidence=three_d_evidence,
            analysis_mode=analysis_mode,
        )
        frame_details_manifest_path = _write_video_frame_details_manifest(
            output_dir / "frame_details" / run.run_id,
            case_id=case.case_id,
            run_id=run.run_id,
            source_path=source_path,
            keyframe_report=capture_report,
            frame_details=frame_details,
            three_d_evidence=three_d_evidence,
            analysis_mode=analysis_mode,
        )
        displayable_outputs = [item for item in hotspot_outputs if item.get("display_allowed") is True]
        displayable_keyframes = [item for item in keyframes if item.get("display_allowed") is True]
        displayable_frame_details = [item for item in frame_details if item.get("display_allowed") is True]
        analysis_available = bool(displayable_outputs)
        if frame_age_summary["stale_frame_count"]:
            all_warnings.append(
                {
                    "code": "live_result_stale",
                    "message": "One or more live-stream results exceeded the configured frame-age display limit.",
                    "blocking": False,
                    **frame_age_summary,
                }
            )
        if not analysis_available:
            all_warnings.append(
                {
                    "code": "all_live_results_stale",
                    "message": "No live-stream analysis result remained within the configured display-age limit.",
                    "blocking": True,
                    **frame_age_summary,
                }
            )
        video_candidates = _hotspot_candidate_regions(run.run_id, displayable_outputs, frame_details=frame_details)
        hotspot_summary = _hotspot_summary(displayable_outputs)
        temporal_summary = video_temporal_summary(displayable_frame_details)
        inference_performance = video_inference_performance_summary(frame_details)
        fluorescence_dynamics = video_fluorescence_dynamics_summary(displayable_frame_details)
        fused_outputs = _video_fused_outputs(
            source_path=source_path,
            video=None,
            keyframes=keyframes,
            hotspot_outputs=hotspot_outputs,
            segmentation_model_id=segmentation_model_id,
            frame_details=frame_details,
            keyframe_report=capture_report,
            timeline_summary=timeline_summary,
            temporal_summary=temporal_summary,
            frame_details_manifest_path=frame_details_manifest_path,
            video_segmentation_outputs=video_segmentation_outputs,
            roi_hints=effective_roi_hints,
            three_d_evidence=three_d_evidence,
            analysis_mode=analysis_mode,
        )
        fused_outputs.update(
            {
                "stream_ai_connected": True,
                "analysis_available": analysis_available,
                "decision_support_available": analysis_available,
                "live_capture": capture_report,
                "frame_age_gate": frame_age_summary,
            }
        )
        quantitative_summary = _video_quantitative_summary(
            keyframe_report=capture_report,
            keyframes=displayable_keyframes,
            roi_hints=effective_roi_hints,
            video_segmentation_outputs=video_segmentation_outputs,
            temporal_summary=temporal_summary,
            hotspot_summary=hotspot_summary,
            inference_performance=inference_performance,
            fluorescence_dynamics=fluorescence_dynamics,
        )
        quantitative_summary.update(
            {
                "live_keyframes_captured": len(keyframes),
                "live_keyframes_displayable": len(displayable_keyframes),
                "live_frames_read": capture_report.get("frames_read", 0),
                "live_frames_dropped": capture_report.get("frames_dropped", 0),
                "live_frame_age_gate": frame_age_summary,
            }
        )
        run = run.model_copy(
            update={
                "status": "completed" if analysis_available else "failed",
                "candidate_regions": video_candidates,
                "fused_outputs": fused_outputs,
                "quantitative_summary": quantitative_summary,
                "warnings": all_warnings,
            }
        )
        video_artifacts = _video_artifacts(
            case.case_id,
            run.run_id,
            keyframes=keyframes,
            hotspot_outputs=displayable_outputs,
            keyframe_report=capture_report,
            frame_details_manifest_path=frame_details_manifest_path,
            video_segmentation_outputs=video_segmentation_outputs,
        )
        updated = case.model_copy(
            update={
                "analysis_runs": [*case.analysis_runs, run],
                "artifacts": [*case.artifacts, *video_artifacts],
                "status": CaseStatus.ANALYZED if analysis_available else case.status,
                "warnings": [*case.warnings, *all_warnings],
            }
        )
        updated = updated.model_copy(update={"review_summary": self._review_summary(updated)})
        self.repo.save(updated)
        return updated

    def _complete_video_file_analysis(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        *,
        output_dir: Path,
        video: CaseInputAsset | None,
        parameters: dict[str, Any],
        selection_warnings: list[dict[str, Any]],
        effective_roi_hints: list[dict[str, Any]],
    ) -> CaseRecord:
        source_path = parameters.get("source_path") or (video.path if video else None)
        if not source_path:
            missing_video_warnings = [
                {
                    "code": "missing_video_input",
                    "message": "Video input is required for keyframe extraction.",
                    "blocking": True,
                }
            ]
            return self._finish_failed_run(case, run, missing_video_warnings)

        frame_count = int(parameters.get("keyframe_count", 5))
        sampling_strategy = str(parameters.get("keyframe_sampling_strategy", "quality_peak"))
        keyframe_report = _keyframe_report_for_analysis(
            source_path,
            output_dir / "keyframes" / run.run_id,
            max_frames=frame_count,
            sampling_strategy=sampling_strategy,
            requested_frame_indexes=_numeric_sequence(
                parameters.get("keyframe_frame_indexes", parameters.get("requested_frame_indexes")),
                cast_type=int,
            ),
            requested_timestamps_sec=_numeric_sequence(
                parameters.get(
                    "keyframe_timestamps_sec",
                    parameters.get("requested_timestamps_sec"),
                ),
                cast_type=float,
            ),
        )
        video_warnings = [*selection_warnings, *keyframe_report.get("warnings", [])]
        keyframes = keyframe_report.get("keyframes", [])
        segmentation_model_id = str(parameters.get("segmentation_model_id") or self._configured_segmentation_model_id())
        hotspot_outputs = _analyze_keyframe_segmentations(
            keyframes,
            output_dir / "keyframe_segmentations" / run.run_id,
            case_id=case.case_id,
            config_path=self.config_path,
            model_id=segmentation_model_id,
            threshold=float(parameters.get("hotspot_threshold", parameters.get("threshold", 0.6))),
            colormap=str(parameters.get("colormap", "green")),
            roi_hints=effective_roi_hints,
            allow_heuristic_fallback=self._heuristic_keyframe_fallback_allowed(),
        )
        segmentation_warnings = _keyframe_segmentation_warnings(hotspot_outputs)
        video_warnings.extend(segmentation_warnings)
        if any(bool(item.get("blocking")) for item in segmentation_warnings):
            failed_run = run.model_copy(
                update={
                    "fused_outputs": {
                        "mode": "video_file_keyframes",
                        "source_path": str(source_path),
                        "segmentation_model_id": segmentation_model_id,
                        "keyframes": keyframes,
                        "keyframe_segmentations": hotspot_outputs,
                        "analysis_available": False,
                        "decision_support_available": False,
                        "disclaimer_context": disclaimer_context(),
                    },
                    "quantitative_summary": {
                        "keyframes_extracted": len(keyframes),
                        "analysis_available": False,
                    },
                }
            )
            return self._finish_failed_run(case, failed_run, video_warnings)
        frame_details = _video_frame_details(keyframes, hotspot_outputs, keyframe_report=keyframe_report)
        timeline_summary = _video_timeline_summary(keyframe_report)
        three_d_evidence = _build_three_d_evidence(
            parameters=parameters,
            source_inputs=[item for item in [video] if item is not None],
            analysis_mode="video_file_keyframes",
            run_id=run.run_id,
        )
        video_segmentation_outputs = (
            _write_video_segmentation_outputs(
                output_dir / "video_segmentation" / run.run_id,
                case_id=case.case_id,
                run_id=run.run_id,
                source_path=str(source_path),
                keyframe_report=keyframe_report,
                frame_details=frame_details,
                hotspot_outputs=hotspot_outputs,
                three_d_evidence=three_d_evidence,
            )
            if keyframes
            else {}
        )
        frame_details_manifest_path = (
            _write_video_frame_details_manifest(
                output_dir / "frame_details" / run.run_id,
                case_id=case.case_id,
                run_id=run.run_id,
                source_path=str(source_path),
                keyframe_report=keyframe_report,
                frame_details=frame_details,
                three_d_evidence=three_d_evidence,
            )
            if keyframes
            else None
        )
        video_candidates = _hotspot_candidate_regions(run.run_id, hotspot_outputs, frame_details=frame_details)
        hotspot_summary = _hotspot_summary(hotspot_outputs)
        temporal_summary = video_temporal_summary(frame_details)
        inference_performance = video_inference_performance_summary(frame_details)
        fluorescence_dynamics = video_fluorescence_dynamics_summary(frame_details)
        fused_outputs = _video_fused_outputs(
            source_path=str(source_path),
            video=video,
            keyframes=keyframes,
            hotspot_outputs=hotspot_outputs,
            segmentation_model_id=segmentation_model_id,
            frame_details=frame_details,
            keyframe_report=keyframe_report,
            timeline_summary=timeline_summary,
            temporal_summary=temporal_summary,
            frame_details_manifest_path=frame_details_manifest_path,
            video_segmentation_outputs=video_segmentation_outputs,
            roi_hints=effective_roi_hints,
            three_d_evidence=three_d_evidence,
        )
        quantitative_summary = _video_quantitative_summary(
            keyframe_report=keyframe_report,
            keyframes=keyframes,
            roi_hints=effective_roi_hints,
            video_segmentation_outputs=video_segmentation_outputs,
            temporal_summary=temporal_summary,
            hotspot_summary=hotspot_summary,
            inference_performance=inference_performance,
            fluorescence_dynamics=fluorescence_dynamics,
        )
        run = run.model_copy(
            update={
                "status": "completed" if keyframes else "failed",
                "candidate_regions": video_candidates,
                "fused_outputs": fused_outputs,
                "quantitative_summary": quantitative_summary,
                "warnings": video_warnings,
            }
        )
        video_artifacts = _video_artifacts(
            case.case_id,
            run.run_id,
            keyframes=keyframes,
            hotspot_outputs=hotspot_outputs,
            keyframe_report=keyframe_report,
            frame_details_manifest_path=frame_details_manifest_path,
            video_segmentation_outputs=video_segmentation_outputs,
        )
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

    def _complete_dual_channel_analysis(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        *,
        output_dir: Path,
        white: CaseInputAsset | None,
        fluor: CaseInputAsset | None,
        device_overlay: CaseInputAsset | None,
        parameters: dict[str, Any],
        selection_warnings: list[dict[str, Any]],
        effective_roi_hints: list[dict[str, Any]],
    ) -> CaseRecord:
        fused_outputs: dict[str, Any] = {}
        analysis_warnings: list[dict[str, Any]] = list(selection_warnings)
        candidate_regions: list[CandidateRegion] = []
        quantitative_summary: dict[str, Any] = {}
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
            three_d_evidence = _build_three_d_evidence(
                parameters=parameters,
                source_inputs=[item for item in [white, fluor] if item is not None],
                analysis_mode="dual_channel_fusion",
                run_id=run.run_id,
            )
            fused_outputs = _fusion_fused_outputs(
                fusion_report,
                outputs=outputs,
                roi_hints=effective_roi_hints,
                three_d_evidence=three_d_evidence,
            )
            three_channel_quality = assess_three_channel_quality(
                white.path,
                fluor.path,
                device_overlay.path if device_overlay else None,
                output_dir / "three_channel_quality",
                metadata={
                    "white_light": white.metadata,
                    "fluorescence": fluor.metadata,
                    "device_overlay": device_overlay.metadata if device_overlay else {},
                },
                software_overlay_path=outputs.get("overlay_path"),
                synchronization_tolerance_ms=float(parameters.get("synchronization_tolerance_ms", 100.0)),
            )
            fused_outputs["three_channel_quality"] = three_channel_quality
            if device_overlay:
                fused_outputs["device_overlay_reference"] = {
                    "input_id": device_overlay.input_id,
                    "path": device_overlay.path,
                    "dimensions": device_overlay.dimensions,
                    "evidence_role": "device_display_reference",
                    "analysis_input_allowed": False,
                    "used_for_model_inference": False,
                }
            dual_channel_ai, dual_channel_ai_warnings = self._dual_channel_ai(
                case_id=case.case_id,
                white_path=white.path,
                fluorescence_path=fluor.path,
                output_dir=output_dir / "dual_channel_ai",
            )
            fused_outputs["dual_channel_ai"] = dual_channel_ai
            analysis_warnings.extend(dual_channel_ai_warnings)
            registration = fusion_report.get("fusion", {}).get("registration_details", {})
            registration = registration if isinstance(registration, dict) else {}
            patient_conditioning, patient_conditioning_warnings = self._patient_conditioned_ai(
                case=case,
                white=white,
                fluorescence=fluor,
                registered_fluorescence_path=str(outputs.get("normalized_fluorescence_path") or ""),
                registration_evidence=registration,
                clinical_context_assessment=parameters.get("clinical_context_assessment"),
                output_dir=output_dir / "patient_conditioning",
            )
            fused_outputs["patient_conditioning_evidence"] = patient_conditioning
            analysis_warnings.extend(patient_conditioning_warnings)
            bone_activity_checkpoint, bone_activity_warnings = self._bone_activity_checkpoint_ai(
                case=case,
                white=white,
                fluorescence=fluor,
                registered_fluorescence_path=str(outputs.get("normalized_fluorescence_path") or ""),
                registration_evidence=registration,
                output_dir=output_dir / "bone_activity_checkpoint",
            )
            fused_outputs["bone_activity_checkpoint_evidence"] = bone_activity_checkpoint
            analysis_warnings.extend(bone_activity_warnings)
            analysis_warnings.extend(fusion_report.get("warnings", []))
            quantitative_summary = _fusion_quantitative_summary(fusion_report, roi_hints=effective_roi_hints)
            quantitative_summary["patient_conditioning"] = patient_conditioning.get("quantification", {})
            quantitative_summary["bone_activity_checkpoint"] = _bone_activity_checkpoint_quantification(
                bone_activity_checkpoint
            )
            candidate_regions = _fusion_candidate_regions(run.run_id, fusion_report, roi_hints=effective_roi_hints)
            fusion_artifacts = _fusion_artifacts(case.case_id, run.run_id, outputs)
            fusion_artifacts.extend(_three_channel_quality_artifacts(case.case_id, run.run_id, three_channel_quality))
            fusion_artifacts.extend(_patient_conditioning_artifacts(case.case_id, run.run_id, patient_conditioning))
            fusion_artifacts.extend(
                _bone_activity_checkpoint_artifacts(case.case_id, run.run_id, bone_activity_checkpoint)
            )
        else:
            fusion_artifacts = []
            analysis_warnings.append(_missing_dual_channel_warning())
        run = run.model_copy(
            update={
                "status": "completed" if fused_outputs else "failed",
                "candidate_regions": candidate_regions,
                "fused_outputs": fused_outputs,
                "quantitative_summary": quantitative_summary,
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

    def _dual_channel_ai(
        self,
        *,
        case_id: str,
        white_path: str,
        fluorescence_path: str,
        output_dir: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        runtime = load_yaml(self.config_path).get("runtime", {})
        mapping = next(
            (dict(item) for item in runtime.get("models", []) if item.get("family") == "dual_channel_segmenter"),
            None,
        )
        if not mapping:
            return {
                "available": False,
                "execution_state": "skipped",
                "reason": "model_not_configured",
                "traditional_fusion_fallback_available": True,
            }, []
        mapping["extra"] = {
            **dict(mapping.get("extra") or {}),
            "output_dir": str(output_dir),
        }
        input_boundary = {
            "input_domain": str(mapping["extra"].get("input_domain", "non_target_domain_proxy")),
            "white_light_source": str(mapping["extra"].get("white_light_source", "synthetic_white_light_proxy")),
            "target_domain": bool(mapping["extra"].get("target_domain", False)),
        }
        try:
            adapter = build_adapter(model_spec_from_mapping(mapping))
            adapter_status = adapter.warmup()
            if not adapter_status.available:
                payload = {
                    "available": False,
                    "execution_state": "skipped",
                    "reason": "adapter_warmup_unavailable",
                    "adapter_status": adapter_status.to_dict(),
                    "input_boundary": input_boundary,
                    "traditional_fusion_fallback_available": True,
                }
                return payload, list(adapter_status.warnings)
            result = adapter.predict(
                AdapterRequest(
                    case_id=case_id,
                    input_path=white_path,
                    input_type="dual_channel_image",
                    task_type="segmentation",
                    modality="white_light_fluorescence",
                    metadata={"fluorescence_path": fluorescence_path},
                )
            )
            payload = result.to_dict()
            payload["execution_state"] = "completed"
            payload["adapter_status"] = adapter_status.to_dict()
            payload["input_boundary"] = input_boundary
            payload["traditional_fusion_fallback_available"] = True
            result_warnings = payload.get("warnings", [])
            return payload, list(result_warnings) if isinstance(result_warnings, list) else []
        except Exception as exc:
            return (
                {
                    "available": False,
                    "execution_state": "failed_recovered",
                    "reason": "dual_channel_ai_failed",
                    "detail": str(exc),
                    "input_boundary": input_boundary,
                    "traditional_fusion_fallback_available": True,
                },
                [
                    {
                        "code": "dual_channel_ai_failed",
                        "message": f"Dual-channel AI was skipped after a recoverable failure: {exc}",
                        "blocking": False,
                    }
                ],
            )

    def _patient_conditioned_ai(
        self,
        *,
        case: CaseRecord,
        white: CaseInputAsset,
        fluorescence: CaseInputAsset,
        registered_fluorescence_path: str,
        registration_evidence: dict[str, Any],
        clinical_context_assessment: Any,
        output_dir: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        assessment = dict(clinical_context_assessment) if isinstance(clinical_context_assessment, dict) else {}
        clinical_feature_vector = assessment.get("clinical_feature_vector")
        runtime = load_yaml(self.config_path).get("runtime", {})
        mapping = next(
            (dict(item) for item in runtime.get("models", []) if item.get("family") == "patient_conditioned_segmenter"),
            None,
        )
        if not mapping:
            return (
                _patient_conditioning_fallback(
                    "patient_conditioned_model_not_configured",
                    clinical_feature_vector=clinical_feature_vector,
                ),
                [],
            )

        registration_verified = bool(
            registration_evidence.get("applied") is True
            and registered_fluorescence_path
            and Path(registered_fluorescence_path).is_file()
        )
        if not registration_verified:
            payload = _patient_conditioning_fallback(
                "dual_channel_registration_unverified",
                clinical_feature_vector=clinical_feature_vector,
            )
            payload.update(
                {
                    "model_id": mapping.get("model_id"),
                    "model_family": mapping.get("family"),
                    "registration_evidence": registration_evidence,
                }
            )
            return payload, [
                {
                    "code": "patient_conditioning_registration_unverified",
                    "message": "Patient-conditioned inference retained the conventional fusion result because registration evidence was incomplete.",
                    "blocking": False,
                }
            ]

        reviewed_gate, bone_gate_selection = resolve_trusted_reviewed_bone_gate(
            self.annotation_repository,
            case_id=case.case_id,
            white_light=white,
        )
        target_domain_verified, target_domain_gate = target_domain_input_gate(
            case,
            white_light=white,
            fluorescence=fluorescence,
        )
        snapshot = assessment.get("clinical_context_snapshot")
        declared_boundary = snapshot.get("clinical_use_boundary") if isinstance(snapshot, dict) else None
        assessment["spatial_conditioning_authorized"] = bool(
            target_domain_verified
            and reviewed_gate is not None
            and declared_boundary == "restricted_spatial_conditioning_with_physician_review"
        )
        mapping["extra"] = {
            **dict(mapping.get("extra") or {}),
            "output_dir": str(output_dir),
        }
        try:
            adapter = build_adapter(model_spec_from_mapping(mapping))
            adapter_status = adapter.warmup()
            if not adapter_status.available:
                payload = _patient_conditioning_fallback(
                    "patient_conditioned_model_unavailable",
                    clinical_feature_vector=clinical_feature_vector,
                )
                payload.update(
                    {
                        "model_id": mapping.get("model_id"),
                        "model_family": mapping.get("family"),
                        "adapter_status": adapter_status.to_dict(),
                        "reviewed_bone_gate_selection": bone_gate_selection,
                        "target_domain_input_gate": target_domain_gate,
                        "registration_evidence": registration_evidence,
                    }
                )
                return payload, _nonblocking_patient_conditioning_warnings(adapter_status.warnings)
            result = adapter.predict(
                AdapterRequest(
                    case_id=case.case_id,
                    input_path=white.path,
                    input_type="dual_channel_image",
                    task_type="segmentation",
                    modality="white_light_fluorescence",
                    metadata={
                        "fluorescence_path": registered_fluorescence_path,
                        "original_fluorescence_path": fluorescence.path,
                        "dual_channel_registration_verified": True,
                        "clinical_context_assessment": assessment,
                        "reviewed_bone_gate": reviewed_gate,
                        "target_domain_input_verified": target_domain_verified,
                    },
                )
            )
            result_payload = result.to_dict()
            prediction = result_payload.get("prediction")
            prediction = prediction if isinstance(prediction, dict) else {}
            quantification = result_payload.get("quantification")
            quantification = quantification if isinstance(quantification, dict) else {}
            payload = {
                **prediction,
                "model_id": result_payload.get("model_id"),
                "model_family": result_payload.get("model_family"),
                "segmentation_mask": result_payload.get("segmentation_mask") or {},
                "lesion_evidence": result_payload.get("lesion_evidence") or {},
                "quantification": quantification,
                "adapter_status": adapter_status.to_dict(),
                "execution_state": "completed",
                "reviewed_bone_gate_selection": bone_gate_selection,
                "target_domain_input_gate": target_domain_gate,
                "registration_evidence": registration_evidence,
            }
            payload["effective_present_fraction"] = payload.get("clinical_present_fraction")
            payload["physician_reviewed_bone_gate"] = bone_gate_selection.get("status") == "selected"
            difference_pixels = quantification.get("difference_area_px")
            try:
                width, height = white.dimensions or (0, 0)
                payload["difference_area_fraction"] = (
                    float(difference_pixels) / float(width * height)
                    if difference_pixels is not None and width > 0 and height > 0
                    else None
                )
            except (TypeError, ValueError):
                payload["difference_area_fraction"] = None
            warnings = result_payload.get("warnings")
            warnings = warnings if isinstance(warnings, list) else []
            return payload, _nonblocking_patient_conditioning_warnings(warnings)
        except Exception as exc:
            payload = _patient_conditioning_fallback(
                "patient_conditioned_inference_failed",
                clinical_feature_vector=clinical_feature_vector,
            )
            payload.update(
                {
                    "model_id": mapping.get("model_id"),
                    "model_family": mapping.get("family"),
                    "detail": str(exc),
                    "reviewed_bone_gate_selection": bone_gate_selection,
                    "target_domain_input_gate": target_domain_gate,
                    "registration_evidence": registration_evidence,
                }
            )
            return payload, [
                {
                    "code": "patient_conditioned_inference_failed",
                    "message": "Patient-conditioned inference failed closed and retained the conventional fusion result.",
                    "blocking": False,
                    "details": {"error_type": type(exc).__name__, "error": str(exc)},
                }
            ]

    def _bone_activity_checkpoint_ai(
        self,
        *,
        case: CaseRecord,
        white: CaseInputAsset,
        fluorescence: CaseInputAsset,
        registered_fluorescence_path: str,
        registration_evidence: dict[str, Any],
        output_dir: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        runtime = load_yaml(self.config_path).get("runtime", {})
        mappings = runtime.get("models", []) if isinstance(runtime, dict) else []
        mapping = next(
            (
                dict(item)
                for item in mappings
                if isinstance(item, dict)
                and item.get("model_id") == _BONE_ACTIVITY_ENGINEERING_CANDIDATE_MODEL_ID
                and item.get("family") == _BONE_ACTIVITY_ENGINEERING_CANDIDATE_FAMILY
            ),
            None,
        )
        if not mapping:
            return _bone_activity_checkpoint_fallback("explicit_candidate_not_configured"), []

        extra = dict(mapping.get("extra") or {})
        input_domain = str(extra.get("input_domain") or "unrecorded")
        execution_authorized = bool(
            extra.get("candidate_only") is True
            and extra.get("engineering_candidate_execution_allowed") is True
            and extra.get("mainline_replacement_allowed") is not True
            and mapping.get("clinical_claim_allowed") is not True
        )
        if not execution_authorized:
            payload = _bone_activity_checkpoint_fallback(
                "engineering_candidate_execution_not_authorized",
                model_id=str(mapping.get("model_id") or ""),
                model_family=str(mapping.get("family") or ""),
                input_domain=input_domain,
            )
            return payload, [
                {
                    "code": "bone_activity_candidate_execution_not_authorized",
                    "message": "Bone-activity checkpoint execution was skipped because its engineering-candidate gates were incomplete.",
                    "blocking": False,
                }
            ]

        registered_path = Path(registered_fluorescence_path).expanduser().resolve()
        registration_verified = bool(registration_evidence.get("applied") is True and registered_path.is_file())
        if not registered_path.is_file():
            payload = _bone_activity_checkpoint_fallback(
                "registered_fluorescence_input_missing",
                model_id=str(mapping.get("model_id") or ""),
                model_family=str(mapping.get("family") or ""),
                input_domain=input_domain,
            )
            payload["registration_evidence"] = registration_evidence
            return payload, [
                {
                    "code": "bone_activity_registered_input_missing",
                    "message": "Bone-activity engineering inference was skipped because the registered fluorescence artifact was unavailable.",
                    "blocking": False,
                }
            ]

        reviewed_gate, bone_gate_selection = resolve_trusted_reviewed_bone_gate(
            self.annotation_repository,
            case_id=case.case_id,
            white_light=white,
        )
        target_domain_verified, target_domain_gate = target_domain_input_gate(
            case,
            white_light=white,
            fluorescence=fluorescence,
        )
        mapping["extra"] = {**extra, "output_dir": str(output_dir)}
        try:
            adapter = build_adapter(model_spec_from_mapping(mapping))
            adapter_status = adapter.warmup()
            if not adapter_status.available:
                payload = _bone_activity_checkpoint_fallback(
                    "bone_activity_checkpoint_unavailable",
                    model_id=str(mapping.get("model_id") or ""),
                    model_family=str(mapping.get("family") or ""),
                    input_domain=input_domain,
                )
                payload.update(
                    {
                        "adapter_status": adapter_status.to_dict(),
                        "reviewed_bone_gate_selection": bone_gate_selection,
                        "target_domain_input_gate": target_domain_gate,
                        "registration_evidence": registration_evidence,
                    }
                )
                return payload, _nonblocking_bone_activity_warnings(adapter_status.warnings)

            result = adapter.predict(
                AdapterRequest(
                    case_id=case.case_id,
                    input_path=white.path,
                    input_type="dual_channel_image",
                    task_type="segmentation",
                    modality="white_light_fluorescence",
                    metadata={
                        "fluorescence_path": str(registered_path),
                        "original_fluorescence_path": fluorescence.path,
                        "dual_channel_registration_verified": registration_verified,
                        "reviewed_bone_gate": reviewed_gate,
                        "target_domain_input_verified": target_domain_verified,
                    },
                )
            )
            result_payload = result.to_dict()
            prediction_value = result_payload.get("prediction")
            prediction = dict(prediction_value) if isinstance(prediction_value, dict) else {}
            raw_value = prediction.get("raw_engineering_outputs")
            raw = dict(raw_value) if isinstance(raw_value, dict) else {}
            payload = {
                **prediction,
                "model_id": result_payload.get("model_id"),
                "model_family": result_payload.get("model_family"),
                "input_domain": input_domain,
                "training_domain": {
                    "input_domain": input_domain,
                    "target_domain": extra.get("target_domain") is True,
                },
                "engineering_inference_executed": prediction.get("engineering_inference_executed") is True,
                "proxy_checkpoint": prediction.get("proxy_checkpoint") is True,
                "spatial_candidates_available": prediction.get("spatial_candidates_available") is True,
                "spatial_effect_applied": prediction.get("spatial_effect_applied") is True,
                "checkpoint_sha256": prediction.get("checkpoint_sha256"),
                "manifest_sha256": prediction.get("manifest_sha256"),
                "raw_engineering_outputs": raw,
                "evidence_manifest_path": prediction.get("evidence_manifest_path"),
                "evidence_manifest_sha256": prediction.get("evidence_manifest_sha256"),
                "failure_reasons": list(prediction.get("failure_reasons") or []),
                "medical_boundary": prediction.get("medical_boundary")
                or "Bone-activity checkpoint evidence remains restricted to physician-reviewed research validation.",
                "segmentation_mask": result_payload.get("segmentation_mask") or {},
                "lesion_evidence": result_payload.get("lesion_evidence") or {},
                "quantification": result_payload.get("quantification") or {},
                "adapter_status": adapter_status.to_dict(),
                "execution_state": "completed",
                "reviewed_bone_gate_selection": bone_gate_selection,
                "target_domain_input_gate": target_domain_gate,
                "registration_evidence": registration_evidence,
            }
            spatial_authorized = bool(
                payload["proxy_checkpoint"] is False
                and registration_verified
                and target_domain_verified
                and reviewed_gate is not None
                and bone_gate_selection.get("status") == "selected"
                and prediction.get("target_domain_promotion_ready") is True
                and prediction.get("runtime_replacement_allowed") is True
            )
            if payload["spatial_candidates_available"] and not spatial_authorized:
                payload = _force_bone_activity_checkpoint_spatial_fallback(
                    payload,
                    "platform_spatial_authorization_gate_failed",
                )
            if payload["proxy_checkpoint"]:
                payload = _force_bone_activity_checkpoint_spatial_fallback(
                    payload,
                    "non_target_domain_proxy",
                )
            warnings = result_payload.get("warnings")
            warnings = warnings if isinstance(warnings, list) else []
            return payload, _nonblocking_bone_activity_warnings(warnings)
        except Exception as exc:
            payload = _bone_activity_checkpoint_fallback(
                "bone_activity_checkpoint_inference_failed",
                model_id=str(mapping.get("model_id") or ""),
                model_family=str(mapping.get("family") or ""),
                input_domain=input_domain,
            )
            payload.update(
                {
                    "detail": str(exc),
                    "reviewed_bone_gate_selection": bone_gate_selection,
                    "target_domain_input_gate": target_domain_gate,
                    "registration_evidence": registration_evidence,
                }
            )
            return payload, [
                {
                    "code": "bone_activity_checkpoint_inference_failed",
                    "message": "Bone-activity checkpoint execution failed closed and produced no spatial candidates.",
                    "blocking": False,
                    "details": {"error_type": type(exc).__name__, "error": str(exc)},
                }
            ]

    def diagnose_case(self, case: CaseRecord, task_type: str = "classification") -> dict[str, Any]:
        service = MedicalImagingInferenceService.from_config(self.config_path)
        inputs = case.inputs or []
        if not inputs:
            return {
                "status": "missing_inputs",
                "case_id": case.case_id,
                "warnings": [
                    {
                        "code": "missing_inputs",
                        "message": "No inputs stored for case.",
                        "blocking": True,
                    }
                ],
            }
        primary = inputs[0]
        result = service.diagnose(primary.path, task_type=task_type).to_dict()
        return result

    def _pick_input(self, assets: list[CaseInputAsset], channel: InputChannel) -> CaseInputAsset | None:
        return next((asset for asset in reversed(assets) if asset.channel == channel), None)

    def _select_inputs(
        self, case: CaseRecord, selected_input_ids: list[str]
    ) -> tuple[list[CaseInputAsset], list[dict[str, Any]]]:
        if not selected_input_ids:
            inputs = list(case.inputs)
            white_count = sum(asset.channel == InputChannel.WHITE_LIGHT for asset in inputs)
            fluor_count = sum(asset.channel == InputChannel.FLUORESCENCE for asset in inputs)
            overlay_count = sum(asset.channel == InputChannel.DEVICE_OVERLAY for asset in inputs)
            if white_count > 1 or fluor_count > 1 or overlay_count > 1:
                return (
                    inputs,
                    [
                        {
                            "code": "multiple_image_inputs_require_explicit_selection",
                            "message": "Cases with multiple white-light or fluorescence images require an explicit image pair.",
                            "blocking": True,
                            "details": {
                                "white_light_count": white_count,
                                "fluorescence_count": fluor_count,
                                "device_overlay_count": overlay_count,
                            },
                        }
                    ],
                )
            return inputs, []
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
        pair_warning = _validate_selected_image_pair(selected)
        return selected, [pair_warning] if pair_warning else []

    def _method_id(self) -> str:
        try:
            task_package = load_task_package("configs/tasks/osteo_vision.yml")
        except Exception:
            task_package = default_task_package()
        return task_package.task_id

    def _configured_segmentation_model_id(self) -> str:
        runtime = load_yaml(self.config_path).get("runtime") or {}
        tasks = runtime.get("tasks") if isinstance(runtime, dict) else None
        segmentation = tasks.get("segmentation") if isinstance(tasks, dict) else None
        model_id = segmentation.get("model_id") if isinstance(segmentation, dict) else None
        resolved = str(model_id or "").strip()
        if resolved:
            return resolved
        if isinstance(runtime, dict) and bool(runtime.get("strict_startup")):
            raise ValueError("Strict runtime requires runtime.tasks.segmentation.model_id.")
        return "convnext2d_keyframe_proxy_segmenter"

    def _heuristic_keyframe_fallback_allowed(self) -> bool:
        runtime = load_yaml(self.config_path).get("runtime") or {}
        if not isinstance(runtime, dict):
            return True
        configured = runtime.get("allow_heuristic_keyframe_fallback")
        if configured is None:
            return not bool(runtime.get("strict_startup"))
        return bool(configured)

    def _review_summary(self, case: CaseRecord) -> dict[str, Any]:
        analysis_run = case.analysis_runs[-1] if case.analysis_runs else None
        return {
            "status": case.status,
            "run_id": analysis_run.run_id if analysis_run else None,
            "candidate_regions": len(analysis_run.candidate_regions) if analysis_run else 0,
            "artifact_count": len(case.artifacts),
            "disclaimer": disclaimer_context(),
        }


def _browser_frame_paths(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _validate_selected_image_pair(selected: list[CaseInputAsset]) -> dict[str, Any] | None:
    white = [asset for asset in selected if asset.channel == InputChannel.WHITE_LIGHT]
    fluor = [asset for asset in selected if asset.channel == InputChannel.FLUORESCENCE]
    overlays = [asset for asset in selected if asset.channel == InputChannel.DEVICE_OVERLAY]
    if not white and not fluor:
        return None
    if len(white) != 1 or len(fluor) != 1:
        return {
            "code": "selected_image_pair_incomplete",
            "message": "JPEG fusion requires exactly one white-light image and one fluorescence image.",
            "blocking": True,
            "details": {
                "white_light_input_ids": [asset.input_id for asset in white],
                "fluorescence_input_ids": [asset.input_id for asset in fluor],
            },
        }
    if len(overlays) > 1:
        return {
            "code": "multiple_device_overlays_require_explicit_selection",
            "message": "JPEG fusion accepts at most one device overlay reference.",
            "blocking": True,
            "details": {"device_overlay_input_ids": [asset.input_id for asset in overlays]},
        }
    white_pair = _input_pair_identity(white[0])
    fluor_pair = _input_pair_identity(fluor[0])
    pair_metadata_absent = white_pair == ("", "") and fluor_pair == ("", "")
    if not pair_metadata_absent and (not all(white_pair) or not all(fluor_pair)):
        return {
            "code": "selected_image_pair_metadata_incomplete",
            "message": "Admitted synchronized JPEG inputs require matching batch_id and pair_id metadata.",
            "blocking": True,
            "details": {"white_light_pair": list(white_pair), "fluorescence_pair": list(fluor_pair)},
        }
    if not pair_metadata_absent and white_pair != fluor_pair:
        return {
            "code": "selected_image_pair_mismatch",
            "message": "The selected white-light and fluorescence images belong to different admitted pairs.",
            "blocking": True,
            "details": {"white_light_pair": list(white_pair), "fluorescence_pair": list(fluor_pair)},
        }
    if overlays:
        overlay_pair = _input_pair_identity(overlays[0])
        if overlay_pair != ("", "") and (pair_metadata_absent or overlay_pair != white_pair):
            return {
                "code": "selected_device_overlay_pair_mismatch",
                "message": "The selected device overlay belongs to a different admitted image pair.",
                "blocking": True,
                "details": {"image_pair": list(white_pair), "device_overlay_pair": list(overlay_pair)},
            }
    return None


def _input_pair_identity(asset: CaseInputAsset) -> tuple[str, str]:
    batch_id = asset.metadata.get("batch_id")
    pair_id = asset.metadata.get("pair_id")
    return (
        batch_id.strip() if isinstance(batch_id, str) else "",
        pair_id.strip() if isinstance(pair_id, str) else "",
    )


def _browser_frame_capture_report(
    frame_paths: list[str],
    manifest_path: Path,
    *,
    max_frames: int,
    captured_at: str = "",
    session_id: str = "",
    sequence: Any = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    captured_timestamp = (
        captured_at if _parse_utc_datetime(captured_at) is not None else datetime.now(timezone.utc).isoformat()
    )
    keyframes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for path_text in frame_paths[:max_frames]:
        path = Path(path_text)
        if not path.is_file():
            warnings.append(
                {
                    "code": "browser_frame_missing",
                    "message": "A browser-captured frame path is unavailable to the backend.",
                    "blocking": False,
                    "path": path_text,
                }
            )
            continue
        order = len(keyframes) + 1
        keyframes.append(
            {
                "order": order,
                "frame_index": order - 1,
                "timestamp_sec": 0.0,
                "capture_timestamp": captured_timestamp,
                "frame_age_ms": 0.0,
                "path": str(path),
                "evidence_path": str(path),
                "selection_reason": "browser_current_frame_upload",
                "camera_session_id": session_id or None,
                "camera_sequence": sequence,
                "capture_trigger": trigger,
            }
        )

    report: dict[str, Any] = {
        "schema_version": "osteo-vision-browser-frame-capture-v1",
        "source_uri": "camera://browser/default",
        "source_kind": "browser_frame_upload",
        "capture_backend": "browser_canvas_jpeg_upload",
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "frames_read": len(keyframes),
        "frames_dropped": max(0, len(frame_paths[:max_frames]) - len(keyframes)),
        "started_at": captured_timestamp,
        "ended_at": captured_timestamp,
        "camera_session_id": session_id or None,
        "camera_sequence": sequence,
        "capture_trigger": trigger,
        "keyframes": keyframes,
        "keyframe_count": len(keyframes),
        "quality_summary": {
            "frames_saved": len(keyframes),
            "source_pts_available": False,
            "source_buffer_age_verified": False,
            "transport": "browser_canvas_jpeg_upload",
        },
        "frame_index_manifest_path": str(manifest_path),
        "warnings": warnings,
    }
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _apply_live_frame_age_gate(
    keyframes: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
    *,
    max_frame_age_ms: float,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    ages: list[float] = []
    stale_count = 0
    unmatched_output_count = 0
    frame_state: dict[tuple[str, str], dict[str, Any]] = {}
    for frame in keyframes:
        age_ms = float(frame.get("frame_age_ms") or 0.0)
        captured_at = _parse_utc_datetime(frame.get("capture_timestamp"))
        if captured_at is not None:
            age_ms = max(age_ms, (now - captured_at).total_seconds() * 1000.0)
        age_ms = round(max(0.0, age_ms), 3)
        display_allowed = age_ms <= max_frame_age_ms
        frame["analysis_frame_age_ms"] = age_ms
        frame["max_frame_age_ms"] = float(max_frame_age_ms)
        frame["display_allowed"] = display_allowed
        frame["stale"] = not display_allowed
        frame["frame_age_gate_reason"] = "within_limit" if display_allowed else "frame_age_limit_exceeded"
        ages.append(age_ms)
        stale_count += int(not display_allowed)
        if frame.get("order") is not None:
            frame_state[("order", str(frame["order"]))] = frame
        if frame.get("frame_index") is not None:
            frame_state[("index", str(frame["frame_index"]))] = frame
    for output in hotspot_outputs:
        by_order = (
            frame_state.get(("order", str(output["frame_order"]))) if output.get("frame_order") is not None else None
        )
        by_index = (
            frame_state.get(("index", str(output["frame_index"]))) if output.get("frame_index") is not None else None
        )
        if by_order is not None and by_index is not None and by_order is not by_index:
            unmatched_output_count += 1
            output["analysis_frame_age_ms"] = None
            output["max_frame_age_ms"] = float(max_frame_age_ms)
            output["display_allowed"] = False
            output["stale"] = True
            output["frame_age_gate_reason"] = "frame_identity_conflict"
            continue
        matched_frame = by_order or by_index
        if matched_frame is None:
            unmatched_output_count += 1
            output["analysis_frame_age_ms"] = None
            output["max_frame_age_ms"] = float(max_frame_age_ms)
            output["display_allowed"] = False
            output["stale"] = True
            output["frame_age_gate_reason"] = "unmatched_capture_frame"
            continue
        output["capture_timestamp"] = matched_frame.get("capture_timestamp")
        output["analysis_frame_age_ms"] = matched_frame["analysis_frame_age_ms"]
        output["max_frame_age_ms"] = matched_frame["max_frame_age_ms"]
        output["display_allowed"] = matched_frame["display_allowed"]
        output["stale"] = matched_frame["stale"]
        output["frame_age_gate_reason"] = matched_frame["frame_age_gate_reason"]
    ordered = sorted(ages)
    return {
        "available": bool(ordered),
        "max_frame_age_ms": float(max_frame_age_ms),
        "frame_count": len(ordered),
        "stale_frame_count": stale_count,
        "displayable_frame_count": len(ordered) - stale_count,
        "unmatched_output_count": unmatched_output_count,
        "displayable_output_count": sum(output.get("display_allowed") is True for output in hotspot_outputs),
        "p50_frame_age_ms": _quantile(ordered, 0.50),
        "p95_frame_age_ms": _quantile(ordered, 0.95),
        "max_observed_frame_age_ms": round(ordered[-1], 3) if ordered else None,
    }


def _merge_live_frame_age_details(
    frame_details: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
) -> None:
    by_order = {str(frame["order"]): frame for frame in keyframes if frame.get("order") is not None}
    by_index = {str(frame["frame_index"]): frame for frame in keyframes if frame.get("frame_index") is not None}
    for detail in frame_details:
        frame = (by_order.get(str(detail["frame_order"])) if detail.get("frame_order") is not None else None) or (
            by_index.get(str(detail["frame_index"])) if detail.get("frame_index") is not None else None
        )
        if frame is None:
            continue
        detail["capture_timestamp"] = frame.get("capture_timestamp")
        detail["capture_frame_age_ms"] = frame.get("frame_age_ms")
        detail["analysis_frame_age_ms"] = frame.get("analysis_frame_age_ms")
        detail["max_frame_age_ms"] = frame.get("max_frame_age_ms")
        detail["display_allowed"] = frame.get("display_allowed")
        detail["stale"] = frame.get("stale")
        detail["frame_age_gate_reason"] = frame.get("frame_age_gate_reason")


def _parse_utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clinical_context_analysis_parameters(case: CaseRecord) -> dict[str, Any]:
    assessment = assess_clinical_context(case.clinical_context, revision=case.version)
    return {
        "clinical_context_snapshot": assessment["clinical_context_snapshot"],
        "clinical_context_revision": assessment["clinical_context_revision"],
        "clinical_context_checksum": assessment["clinical_context_checksum"],
        "clinical_context_assessment": assessment,
        "clinical_context_quality": assessment["clinical_context_quality"],
        "clinical_feature_vector": assessment["clinical_feature_vector"],
        "rule_based_risk_summary": assessment["rule_based_risk_summary"],
        "contextual_risk_prior": assessment["rule_based_risk_summary"],
        "calibration_evidence": assessment["calibration_evidence"],
        "calibration_status": assessment["calibration_evidence"]["status"],
        "spatial_effect_applied": False,
    }


def _patient_conditioning_fallback(
    reason: str,
    *,
    clinical_feature_vector: Any = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "osteo-vision-patient-conditioned-runtime-v1",
        "available": False,
        "execution_state": "failed_closed",
        "spatial_effect_applied": False,
        "safe_fallback_applied": True,
        "failure_reasons": [reason],
        "target_domain_promotion_ready": False,
        "runtime_replacement_allowed": False,
        "proxy_checkpoint": True,
        "physician_reviewed_bone_gate": False,
        "quantification": {
            "difference_area_px": 0,
            "spatial_effect_area_px": 0,
            "delta_abs_mean": 0.0,
        },
        "medical_boundary": (
            "Patient-conditioned spatial output is unavailable; the platform retained conventional fusion "
            "evidence for physician review."
        ),
    }
    if isinstance(clinical_feature_vector, dict):
        vector = dict(clinical_feature_vector)
        names = [str(item) for item in vector.get("feature_names") or []]
        vector.update(
            {
                "checkpoint_context_eligible": False,
                "checkpoint_consumed_mask": [False] * len(names),
                "spatial_effect_applied_mask": [False] * len(names),
                "checkpoint_consumed_feature_names": [],
                "spatially_applied_feature_names": [],
                "checkpoint_consumed_count": 0,
                "spatially_applied_count": 0,
                "checkpoint_consumption_status": "not_invoked_failed_closed",
            }
        )
        payload["clinical_feature_vector"] = vector
    return payload


def _nonblocking_patient_conditioning_warnings(
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in warnings:
        details_value = item.get("details")
        details = dict(details_value) if isinstance(details_value, dict) else {}
        normalized.append(
            {
                **dict(item),
                "blocking": False,
                "details": {
                    **details,
                    "recovery": "image_only_or_conventional_fusion_fallback",
                },
            }
        )
    return normalized


def _bone_activity_checkpoint_fallback(
    reason: str,
    *,
    model_id: str | None = None,
    model_family: str | None = None,
    input_domain: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-bone-activity-runtime-evidence-v1",
        "available": False,
        "model_id": model_id,
        "model_family": model_family,
        "input_domain": input_domain,
        "training_domain": {"input_domain": input_domain, "target_domain": False},
        "execution_state": "failed_closed",
        "engineering_inference_executed": False,
        "proxy_checkpoint": True,
        "spatial_candidates_available": False,
        "spatial_effect_applied": False,
        "safe_fallback_applied": True,
        "checkpoint_sha256": None,
        "manifest_sha256": None,
        "raw_engineering_outputs": {
            "available": False,
            "spatial_use_allowed": False,
            "path": None,
            "sha256": None,
        },
        "evidence_manifest_path": None,
        "evidence_manifest_sha256": None,
        "failure_reasons": [reason],
        "bone_activity_spectrum": _unavailable_bone_activity_checkpoint_spectrum([reason], None),
        "segmentation_mask": {
            "available": False,
            "path": None,
            "format": None,
            "physician_review_required": True,
            "safe_fallback_applied": True,
        },
        "quantification": {"spatial_candidates_available": False},
        "medical_boundary": (
            "Bone-activity checkpoint spatial output is unavailable. Conventional fusion and physician review "
            "remain the active evidence path."
        ),
    }


def _force_bone_activity_checkpoint_spatial_fallback(
    evidence: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    payload = dict(evidence)
    failure_reasons = list(dict.fromkeys([*(str(item) for item in payload.get("failure_reasons") or []), reason]))
    raw_value = payload.get("raw_engineering_outputs")
    raw = dict(raw_value) if isinstance(raw_value, dict) else {}
    raw["spatial_use_allowed"] = False
    payload.update(
        {
            "available": False,
            "spatial_candidates_available": False,
            "spatial_effect_applied": False,
            "safe_fallback_applied": True,
            "failure_reasons": failure_reasons,
            "raw_engineering_outputs": raw,
            "bone_activity_spectrum": _unavailable_bone_activity_checkpoint_spectrum(
                failure_reasons,
                raw.get("path"),
            ),
            "segmentation_mask": {
                "available": False,
                "path": None,
                "format": None,
                "physician_review_required": True,
                "safe_fallback_applied": True,
            },
        }
    )
    quantification_value = payload.get("quantification")
    quantification = dict(quantification_value) if isinstance(quantification_value, dict) else {}
    quantification = {
        key: value
        for key, value in quantification.items()
        if not key.endswith("_area_px") and not key.endswith("_bone_gate_fraction")
    }
    quantification["spatial_candidates_available"] = False
    payload["quantification"] = quantification
    lesion_value = payload.get("lesion_evidence")
    lesion = dict(lesion_value) if isinstance(lesion_value, dict) else {}
    lesion.update(
        {
            "available": False,
            "bone_activity_spectrum": payload["bone_activity_spectrum"],
            "raw_engineering_outputs": raw,
        }
    )
    payload["lesion_evidence"] = lesion
    return payload


def _unavailable_bone_activity_checkpoint_spectrum(
    failure_reasons: list[str],
    raw_path: Any,
) -> dict[str, Any]:
    unavailable = {"available": False, "positive_area_px": None, "bone_gate_fraction": None, "path": None}
    return {
        "schema_version": "osteo-vision-bone-activity-spectrum-v2",
        "available": False,
        "status": "safe_fallback_engineering_evidence_only",
        "failure_reasons": list(failure_reasons),
        "activity_score": {"available": False, "path": None, "scale": [0.0, 1.0]},
        "activity_class_map_path": None,
        "low_activity_candidate": {**unavailable, "label": "Low-activity candidate"},
        "transition_candidate": {**unavailable, "label": "Transition review region"},
        "high_activity_candidate": {**unavailable, "label": "High-activity reference"},
        "ignore_region": {**unavailable, "label": "Unavailable region", "sources": ["safety_gate"]},
        "calibration_status": "pending_target_domain_validation",
        "spatial_effect_applied": False,
        "review_required": True,
        "raw_engineering_outputs_path": str(raw_path) if raw_path else None,
        "confidence_statement": "Engineering outputs remain unavailable for spatial clinical use.",
    }


def _bone_activity_checkpoint_quantification(evidence: dict[str, Any]) -> dict[str, Any]:
    raw_value = evidence.get("raw_engineering_outputs")
    raw = dict(raw_value) if isinstance(raw_value, dict) else {}
    return {
        "model_id": evidence.get("model_id"),
        "engineering_inference_executed": evidence.get("engineering_inference_executed") is True,
        "proxy_checkpoint": evidence.get("proxy_checkpoint") is True,
        "spatial_candidates_available": evidence.get("spatial_candidates_available") is True,
        "spatial_effect_applied": evidence.get("spatial_effect_applied") is True,
        "safe_fallback_applied": evidence.get("safe_fallback_applied", True) is True,
        "checkpoint_sha256": evidence.get("checkpoint_sha256"),
        "manifest_sha256": evidence.get("manifest_sha256"),
        "raw_engineering_outputs_sha256": raw.get("sha256"),
        "evidence_manifest_sha256": evidence.get("evidence_manifest_sha256"),
        "failure_reasons": list(evidence.get("failure_reasons") or []),
    }


def _nonblocking_bone_activity_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in warnings:
        details_value = item.get("details")
        details = dict(details_value) if isinstance(details_value, dict) else {}
        normalized.append(
            {
                **dict(item),
                "blocking": False,
                "details": {**details, "recovery": "conventional_fusion_and_physician_review"},
            }
        )
    return normalized


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * fraction))))
    return round(values[index], 3)
