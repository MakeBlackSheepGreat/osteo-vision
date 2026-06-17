from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import artifact_root, checksum_for_file, manifest_record
from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.enums import ArtifactKind, CaseStatus
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, EvidenceArtifact, ExportRequest, ExportResponse
from backend.src.reports.platform_markdown import build_platform_markdown
from backend.src.reports.platform_report import build_platform_report
from backend.src.reports.quantification_csv import write_quantification_csv
from src.reports.writers import write_json


class ExportService:
    def __init__(self, repo: CaseRepository, artifact_dir: str | Path) -> None:
        self.repo = repo
        self.artifact_dir = artifact_root(artifact_dir)

    def export_case(self, case: CaseRecord, request: ExportRequest) -> ExportResponse:
        export_dir = artifact_root(self.artifact_dir / case.case_id / f"export_{uuid4().hex[:8]}")
        report = build_platform_report(case, export_meta={"export_format": request.export_format, "selected_artifacts": request.selected_artifacts, **disclaimer_context()})
        report_json_path = export_dir / f"{case.case_id}_report.json"
        report_md_path = export_dir / f"{case.case_id}_report.md"
        manifest_path = export_dir / f"{case.case_id}_manifest.json"
        bundle_path = export_dir / f"{case.case_id}_bundle.json"
        write_json(report_json_path, report)
        report_md_path.write_text(build_platform_markdown(case, report), encoding="utf-8")
        quant_rows: list[dict[str, Any]] = []
        for run in case.analysis_runs:
            quant = run.quantitative_summary or {}
            quant_rows.append(
                {
                    "case_id": case.case_id,
                    "run_id": run.run_id,
                    "roi_id": "",
                    **quant,
                    "review_state": case.status,
                }
            )
        quant_csv_path = export_dir / f"{case.case_id}_quantification.csv"
        write_quantification_csv(quant_csv_path, quant_rows)
        bundle_payload = {
            "case_id": case.case_id,
            "report_json": str(report_json_path),
            "report_md": str(report_md_path),
            "quantification_csv": str(quant_csv_path),
            "artifacts": report.get("artifacts", []),
            "disclaimer": disclaimer_context(),
        }
        write_json(bundle_path, bundle_payload)
        manifest = {
            "case_id": case.case_id,
            "bundle_path": str(bundle_path),
            "report_path": str(report_json_path),
            "report_md_path": str(report_md_path),
            "quantification_csv_path": str(quant_csv_path),
            "artifacts": [
                manifest_record(ArtifactKind.REPORT_JSON.value, report_json_path),
                manifest_record(ArtifactKind.REPORT_MD.value, report_md_path),
                manifest_record(ArtifactKind.QUANTIFICATION_CSV.value, quant_csv_path),
                manifest_record(ArtifactKind.EVIDENCE_BUNDLE.value, bundle_path),
            ],
            "disclaimer": disclaimer_context(),
        }
        write_json(manifest_path, manifest)
        artifacts = list(case.artifacts)
        artifacts.extend(
            [
                EvidenceArtifact(artifact_id=f"artifact_{uuid4().hex[:10]}", case_id=case.case_id, kind=ArtifactKind.REPORT_JSON, path=str(report_json_path), checksum=checksum_for_file(report_json_path)),
                EvidenceArtifact(artifact_id=f"artifact_{uuid4().hex[:10]}", case_id=case.case_id, kind=ArtifactKind.REPORT_MD, path=str(report_md_path), checksum=checksum_for_file(report_md_path)),
                EvidenceArtifact(artifact_id=f"artifact_{uuid4().hex[:10]}", case_id=case.case_id, kind=ArtifactKind.QUANTIFICATION_CSV, path=str(quant_csv_path), checksum=checksum_for_file(quant_csv_path)),
                EvidenceArtifact(artifact_id=f"artifact_{uuid4().hex[:10]}", case_id=case.case_id, kind=ArtifactKind.EVIDENCE_BUNDLE, path=str(bundle_path), checksum=checksum_for_file(bundle_path)),
            ]
        )
        updated = case.model_copy(update={"artifacts": artifacts, "status": CaseStatus.EXPORTED})
        updated = updated.model_copy(update={"review_summary": {**case.review_summary, "exported": True}})
        self.repo.save(updated)
        return ExportResponse(bundle_path=str(bundle_path), report_path=str(report_json_path), manifest_path=str(manifest_path), case_id=case.case_id)
