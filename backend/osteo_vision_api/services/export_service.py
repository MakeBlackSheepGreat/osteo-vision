from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.osteo_vision_api.core.artifacts import artifact_root
from backend.osteo_vision_api.domains.cases.enums import CaseStatus
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord, ExportRequest, ExportResponse
from backend.osteo_vision_api.services.export_bundle import (
    ExportPaths,
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
from backend.osteo_vision_api.services.export_core_files import write_core_export_files
from backend.osteo_vision_api.services.manual_annotation_service import ManualAnnotationService
from osteo_vision_core.reports.writers import write_json


class ExportService:
    def __init__(
        self,
        repo: CaseRepository,
        artifact_dir: str | Path,
        annotation_service: ManualAnnotationService | None = None,
    ) -> None:
        self.repo = repo
        self.artifact_dir = artifact_root(artifact_dir)
        self.annotation_service = annotation_service

    def export_case(self, case: CaseRecord, request: ExportRequest) -> ExportResponse:
        paths = export_paths(self.artifact_dir, case.case_id)
        selected_artifacts = selected_case_artifacts(case, request.selected_artifacts)
        _report, quant_rows, review_rows = write_core_export_files(case, request, paths)
        annotation_rows, annotation_files = self._write_annotation_audit(case, paths)
        self._attach_annotation_summary_to_report(paths, annotation_rows, annotation_files)
        included_entries = [artifact_payload(artifact) for artifact in selected_artifacts]
        write_json(paths.bundle_manifest, bundle_manifest_payload(case.case_id, paths, included_entries))
        write_evidence_zip(
            paths.bundle,
            core_files=paths.core_bundle_files,
            case_artifacts=selected_artifacts,
            additional_files=annotation_files,
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
                annotation_audit_rows=annotation_rows,
            ),
            artifact_entries=[*manifest_artifacts, *included_entries],
        )

    def _write_annotation_audit(
        self,
        case: CaseRecord,
        paths: ExportPaths,
    ) -> tuple[list[dict[str, Any]], list[tuple[Path, str]]]:
        if self.annotation_service is not None:
            return self.annotation_service.build_case_annotation_audit(
                case,
                json_path=paths.annotation_audit_json,
                csv_path=paths.annotation_audit_csv,
                registry_path=paths.annotation_manifest_registry,
            )
        empty = {
            "schema_version": "osteo-vision-case-annotation-audit-v1",
            "case_id": case.case_id,
            "annotation_count": 0,
            "version_count": 0,
            "file_packaging_allowed": False,
            "rows": [],
            "medical_boundary": "No annotation repository was attached to this export service.",
        }
        write_json(paths.annotation_audit_json, empty)
        paths.annotation_audit_csv.write_text(
            "annotation_id,case_id,label,status,current_version,version\n", encoding="utf-8"
        )
        write_json(
            paths.annotation_manifest_registry,
            {
                "schema_version": "osteo-vision-case-annotation-manifest-registry-v1",
                "case_id": case.case_id,
                "items": [],
            },
        )
        return [], []

    @staticmethod
    def _attach_annotation_summary_to_report(
        paths: ExportPaths,
        rows: list[dict[str, Any]],
        package_files: list[tuple[Path, str]],
    ) -> None:
        report = json.loads(paths.report_json.read_text(encoding="utf-8"))
        status_counts: dict[str, int] = {}
        for row in rows:
            status = str(row.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        report["annotation_audit"] = {
            "version_record_count": len(rows),
            "status_counts": status_counts,
            "training_eligible_current_version_count": sum(
                1 for row in rows if row.get("is_current_version") and row.get("training_eligible")
            ),
            "packaged_evidence_file_count": len(package_files),
            "audit_json_path": str(paths.annotation_audit_json),
            "audit_csv_path": str(paths.annotation_audit_csv),
            "manifest_registry_path": str(paths.annotation_manifest_registry),
            "medical_boundary": "Annotation audit records preserve physician review and training-admission boundaries.",
        }
        write_json(paths.report_json, report)
        with paths.report_md.open("a", encoding="utf-8") as handle:
            handle.write("\n## 医生标注审计\n\n")
            handle.write(f"- 版本记录数：{len(rows)}\n")
            handle.write(f"- 已打包授权证据文件数：{len(package_files)}\n")
            handle.write(f"- 状态统计：{json.dumps(status_counts, ensure_ascii=False)}\n")
            handle.write("- 医学边界：标注、复核与训练准入记录属于研发验证证据，保留医生复核边界。\n")
