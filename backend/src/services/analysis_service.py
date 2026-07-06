from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import case_artifact_dir
from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.enums import CaseStatus, InputChannel
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, CandidateRegion, CaseInputAsset, CaseRecord
from backend.src.services.analysis_outputs import (
    fusion_artifacts as _fusion_artifacts,
    fusion_candidate_regions as _fusion_candidate_regions,
    fusion_fused_outputs as _fusion_fused_outputs,
    fusion_quantitative_summary as _fusion_quantitative_summary,
    merge_roi_hints as _merge_roi_hints,
    missing_dual_channel_warning as _missing_dual_channel_warning,
    video_artifacts as _video_artifacts,
    video_fused_outputs as _video_fused_outputs,
    video_quantitative_summary as _video_quantitative_summary,
)
from backend.src.services.keyframe_report_loader import (
    keyframe_report_for_analysis as _keyframe_report_for_analysis,
    numeric_sequence as _numeric_sequence,
)
from backend.src.services.keyframe_segmentation import (
    analyze_keyframe_segmentations as _analyze_keyframe_segmentations,
    keyframe_segmentation_warnings as _keyframe_segmentation_warnings,
)
from backend.src.services.video_analysis_details import (
    build_video_frame_details as _video_frame_details,
    build_video_timeline_summary as _video_timeline_summary,
)
from backend.src.services.video_hotspot_outputs import (
    build_hotspot_candidate_regions as _hotspot_candidate_regions,
    summarize_hotspot_outputs as _hotspot_summary,
)
from backend.src.services.video_keyframe_metrics import video_temporal_summary
from backend.src.services.video_segmentation_manifest import (
    write_video_frame_details_manifest as _write_video_frame_details_manifest,
    write_video_segmentation_outputs as _write_video_segmentation_outputs,
)
from src.core.config import load_yaml
from src.core.paths import artifact_dirs
from src.core.task_package import default_task_package, load_task_package
from src.engine.inference import MedicalImagingInferenceService
from src.preprocess.fluorescence import fuse_white_light_fluorescence


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
            return self._finish_failed_run(case, run, selection_warnings)

        # start_analysis 只负责分流：实时预览、MP4 keyframe、双通道 JPEG 分别独立维护。
        white = self._pick_input(selected_inputs, InputChannel.WHITE_LIGHT)
        fluor = self._pick_input(selected_inputs, InputChannel.FLUORESCENCE)
        video = self._pick_input(selected_inputs, InputChannel.VIDEO)
        if parameters.get("mode") == "realtime_video":
            return self._complete_realtime_video_analysis(
                case,
                run,
                parameters=parameters,
                selection_warnings=selection_warnings,
                effective_roi_hints=effective_roi_hints,
            )
        if parameters.get("mode") == "video_file" or (video and not (white and fluor)):
            return self._complete_video_file_analysis(
                case,
                run,
                output_dir=output_dir,
                video=video,
                parameters=parameters,
                selection_warnings=selection_warnings,
                effective_roi_hints=effective_roi_hints,
            )
        return self._complete_dual_channel_analysis(
            case,
            run,
            output_dir=output_dir,
            white=white,
            fluor=fluor,
            parameters=parameters,
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
            update={"analysis_runs": [*case.analysis_runs, run], "warnings": [*case.warnings, *warnings]}
        )
        self.repo.save(updated)
        return updated

    def _complete_realtime_video_analysis(
        self,
        case: CaseRecord,
        run: AnalysisRun,
        *,
        parameters: dict[str, Any],
        selection_warnings: list[dict[str, Any]],
        effective_roi_hints: list[dict[str, Any]],
    ) -> CaseRecord:
        realtime_warnings = [
            {
                "code": "realtime_stream_not_connected",
                "message": "Realtime browser camera preview is registered; streaming AI inference is not connected in this platform workflow.",
                "blocking": False,
            }
        ]
        all_warnings = [*selection_warnings, *realtime_warnings]
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
                "warnings": all_warnings,
            }
        )
        updated = case.model_copy(
            update={
                "analysis_runs": [*case.analysis_runs, run],
                "status": CaseStatus.ANALYZED,
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
                parameters.get("keyframe_timestamps_sec", parameters.get("requested_timestamps_sec")),
                cast_type=float,
            ),
        )
        video_warnings = [*selection_warnings, *keyframe_report.get("warnings", [])]
        keyframes = keyframe_report.get("keyframes", [])
        segmentation_model_id = str(parameters.get("segmentation_model_id") or "convnext2d_keyframe_proxy_segmenter")
        hotspot_outputs = _analyze_keyframe_segmentations(
            keyframes,
            output_dir / "keyframe_segmentations" / run.run_id,
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
                output_dir / "video_segmentation" / run.run_id,
                case_id=case.case_id,
                run_id=run.run_id,
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
                output_dir / "frame_details" / run.run_id,
                case_id=case.case_id,
                run_id=run.run_id,
                source_path=str(source_path),
                keyframe_report=keyframe_report,
                frame_details=frame_details,
            )
            if keyframes
            else None
        )
        video_candidates = _hotspot_candidate_regions(run.run_id, hotspot_outputs, frame_details=frame_details)
        hotspot_summary = _hotspot_summary(hotspot_outputs)
        temporal_summary = video_temporal_summary(frame_details)
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
        )
        quantitative_summary = _video_quantitative_summary(
            keyframe_report=keyframe_report,
            keyframes=keyframes,
            roi_hints=effective_roi_hints,
            video_segmentation_outputs=video_segmentation_outputs,
            temporal_summary=temporal_summary,
            hotspot_summary=hotspot_summary,
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
            fused_outputs = _fusion_fused_outputs(fusion_report, outputs=outputs, roi_hints=effective_roi_hints)
            analysis_warnings.extend(fusion_report.get("warnings", []))
            quantitative_summary = _fusion_quantitative_summary(fusion_report, roi_hints=effective_roi_hints)
            candidate_regions = _fusion_candidate_regions(run.run_id, fusion_report, roi_hints=effective_roi_hints)
            fusion_artifacts = _fusion_artifacts(case.case_id, run.run_id, outputs)
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
