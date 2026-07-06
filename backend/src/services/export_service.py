from __future__ import annotations

from pathlib import Path

from backend.src.core.artifacts import artifact_root
from backend.src.domains.cases.enums import CaseStatus
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, ExportRequest, ExportResponse
from backend.src.services.export_bundle import (
    artifact_payload,
    bundle_manifest_payload,
    core_manifest_artifacts,
    export_evidence_artifacts,
    export_manifest_payload,
    export_paths,
    export_summary,
    selected_case_artifacts,
    write_evidence_zip,
)
from backend.src.services.export_core_files import write_core_export_files
from src.reports.writers import write_json


class ExportService:
    def __init__(self, repo: CaseRepository, artifact_dir: str | Path) -> None:
        self.repo = repo
        self.artifact_dir = artifact_root(artifact_dir)

    def export_case(self, case: CaseRecord, request: ExportRequest) -> ExportResponse:
        paths = export_paths(self.artifact_dir, case.case_id)
        selected_artifacts = selected_case_artifacts(case, request.selected_artifacts)
        _report, quant_rows, review_rows = write_core_export_files(case, request, paths)
        included_entries = [artifact_payload(artifact) for artifact in selected_artifacts]
        write_json(paths.bundle_manifest, bundle_manifest_payload(case.case_id, paths, included_entries))
        write_evidence_zip(
            paths.bundle,
            core_files=paths.core_bundle_files,
            case_artifacts=selected_artifacts,
        )
        manifest_artifacts = core_manifest_artifacts(paths)
        write_json(paths.manifest, export_manifest_payload(case.case_id, paths, manifest_artifacts, included_entries))
        artifacts = [*case.artifacts, *export_evidence_artifacts(case.case_id, paths)]
        updated = case.model_copy(update={"artifacts": artifacts, "status": CaseStatus.EXPORTED})
        updated = updated.model_copy(update={"review_summary": {**case.review_summary, "exported": True}})
        self.repo.save(updated)
        return ExportResponse(
            bundle_path=str(paths.bundle),
            report_path=str(paths.report_json),
            manifest_path=str(paths.manifest),
            case_id=case.case_id,
            dicom_path=str(paths.dicom),
            summary=export_summary(
                case=case,
                bundle_path=paths.bundle,
                manifest_artifacts=manifest_artifacts,
                included_artifacts=included_entries,
                quantification_rows=quant_rows,
                review_manifest_rows=review_rows,
            ),
            artifact_entries=[*manifest_artifacts, *included_entries],
        )
