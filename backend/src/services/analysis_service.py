from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import case_artifact_dir, checksum_for_file
from backend.src.domains.cases.enums import ArtifactKind, CaseStatus, InputChannel, ReviewState
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, CaseInputAsset, CaseRecord, CandidateRegion, EvidenceArtifact
from backend.src.core.disclaimers import disclaimer_context
from src.core.config import load_yaml, runtime_config
from src.core.paths import artifact_dirs
from src.core.schemas import AdapterRequest
from src.core.task_package import load_task_package, default_task_package
from src.engine.inference import MedicalImagingInferenceService
from src.preprocess.fluorescence import fuse_white_light_fluorescence


class AnalysisService:
    def __init__(self, repo: CaseRepository, config_path: str = "configs/inference/osteo_vision.yml") -> None:
        self.repo = repo
        self.config_path = config_path

    def start_analysis(self, case: CaseRecord, selected_input_ids: list[str], parameters: dict[str, Any], roi_hints: list[dict[str, Any]]) -> CaseRecord:
        selected_inputs = [asset for asset in case.inputs if asset.input_id in selected_input_ids] or list(case.inputs)
        white = self._pick_input(selected_inputs, InputChannel.WHITE_LIGHT)
        fluor = self._pick_input(selected_inputs, InputChannel.FLUORESCENCE)
        artifacts = artifact_dirs(load_yaml(self.config_path))
        output_dir = case_artifact_dir(artifacts["visual"] / "cases", case.case_id)
        run_id = f"run_{uuid4().hex[:10]}"
        run = AnalysisRun(run_id=run_id, case_id=case.case_id, method_id=self._method_id(), parameters=parameters, status="running")
        fused_outputs: dict[str, Any] = {}
        warnings: list[dict[str, Any]] = []
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
            )
            outputs = fusion_report.get("outputs", {})
            fused_outputs = {**fusion_report, "outputs": outputs, "disclaimer_context": disclaimer_context()}
            warnings.extend(fusion_report.get("warnings", []))
            quant = fusion_report.get("quantification", {})
            candidate_regions = [
                CandidateRegion(
                    candidate_id=f"cand_{uuid4().hex[:10]}",
                    run_id=run_id,
                    score=float(quant.get("mean_intensity", 0.0)),
                    risk_type="fluorescence_hotspot",
                    confidence=float(quant.get("p95_intensity", 0.0)),
                    status=ReviewState.REVIEW_REQUIRED,
                    explanation="Derived from fluorescence quantification heuristics.",
                )
            ]
            fusion_artifacts = _fusion_artifacts(case.case_id, run_id, outputs)
        else:
            fusion_artifacts = []
            warnings.append(
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
                "quantitative_summary": fused_outputs.get("quantification", {}),
                "warnings": warnings,
            }
        )
        updated = case.model_copy(
            update={
                "analysis_runs": [*case.analysis_runs, run],
                "artifacts": [*case.artifacts, *fusion_artifacts],
                "status": CaseStatus.ANALYZED if fused_outputs else case.status,
                "warnings": [*case.warnings, *warnings],
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
            return {"status": "missing_inputs", "case_id": case.case_id, "warnings": [{"code": "missing_inputs", "message": "No inputs stored for case.", "blocking": True}]}
        primary = inputs[0]
        result = service.diagnose(primary.path, task_type=task_type).to_dict()
        return result

    def _pick_input(self, assets: list[CaseInputAsset], channel: InputChannel) -> CaseInputAsset | None:
        return next((asset for asset in assets if asset.channel == channel), None)

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
