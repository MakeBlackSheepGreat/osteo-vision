from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from backend.src.core.artifacts import artifact_root, checksum_for_file, manifest_record
from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.enums import ArtifactKind, CaseStatus
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, EvidenceArtifact, ExportRequest, ExportResponse
from backend.src.reports.platform_markdown import build_platform_markdown
from backend.src.reports.platform_report import build_platform_report
from backend.src.reports.quantification_csv import write_quantification_csv
from backend.src.reports.dicom_secondary_capture import write_secondary_capture_dicom
from src.reports.writers import write_json


class ExportService:
    def __init__(self, repo: CaseRepository, artifact_dir: str | Path) -> None:
        self.repo = repo
        self.artifact_dir = artifact_root(artifact_dir)

    def export_case(self, case: CaseRecord, request: ExportRequest) -> ExportResponse:
        export_dir = artifact_root(self.artifact_dir / case.case_id / f"export_{uuid4().hex[:8]}")
        report = build_platform_report(
            case,
            export_meta={
                "export_format": request.export_format,
                "selected_artifacts": request.selected_artifacts,
                **disclaimer_context(),
            },
        )
        report_json_path = export_dir / f"{case.case_id}_report.json"
        report_md_path = export_dir / f"{case.case_id}_report.md"
        dicom_path = export_dir / f"{case.case_id}_secondary_capture.dcm"
        manifest_path = export_dir / f"{case.case_id}_manifest.json"
        bundle_manifest_path = export_dir / f"{case.case_id}_bundle_manifest.json"
        bundle_path = export_dir / f"{case.case_id}_evidence_bundle.zip"
        selected_case_artifacts = _selected_case_artifacts(case, request.selected_artifacts)
        write_json(report_json_path, report)
        report_md_path.write_text(build_platform_markdown(case, report), encoding="utf-8")
        write_secondary_capture_dicom(dicom_path, case, report)
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
            "dicom_secondary_capture": str(dicom_path),
            "quantification_csv": str(quant_csv_path),
            "included_artifacts": [
                _artifact_payload(artifact) for artifact in selected_case_artifacts
            ],
            "disclaimer": disclaimer_context(),
        }
        write_json(bundle_manifest_path, bundle_payload)
        _write_evidence_zip(
            bundle_path,
            core_files=[report_json_path, report_md_path, dicom_path, quant_csv_path, bundle_manifest_path],
            case_artifacts=selected_case_artifacts,
        )
        manifest_artifacts = [
            manifest_record(ArtifactKind.REPORT_JSON.value, report_json_path),
            manifest_record(ArtifactKind.REPORT_MD.value, report_md_path),
            manifest_record(ArtifactKind.DICOM_SECONDARY_CAPTURE.value, dicom_path),
            manifest_record(ArtifactKind.QUANTIFICATION_CSV.value, quant_csv_path),
            manifest_record("bundle_manifest", bundle_manifest_path),
            manifest_record(ArtifactKind.EVIDENCE_BUNDLE.value, bundle_path),
        ]
        included_entries = [_artifact_payload(artifact) for artifact in selected_case_artifacts]
        manifest = {
            "case_id": case.case_id,
            "bundle_path": str(bundle_path),
            "bundle_manifest_path": str(bundle_manifest_path),
            "report_path": str(report_json_path),
            "report_md_path": str(report_md_path),
            "dicom_secondary_capture_path": str(dicom_path),
            "quantification_csv_path": str(quant_csv_path),
            "artifacts": manifest_artifacts,
            "included_artifacts": included_entries,
            "disclaimer": disclaimer_context(),
        }
        write_json(manifest_path, manifest)
        artifacts = list(case.artifacts)
        artifacts.extend(
            [
                EvidenceArtifact(
                    artifact_id=f"artifact_{uuid4().hex[:10]}",
                    case_id=case.case_id,
                    kind=ArtifactKind.REPORT_JSON,
                    path=str(report_json_path),
                    checksum=checksum_for_file(report_json_path),
                ),
                EvidenceArtifact(
                    artifact_id=f"artifact_{uuid4().hex[:10]}",
                    case_id=case.case_id,
                    kind=ArtifactKind.REPORT_MD,
                    path=str(report_md_path),
                    checksum=checksum_for_file(report_md_path),
                ),
                EvidenceArtifact(
                    artifact_id=f"artifact_{uuid4().hex[:10]}",
                    case_id=case.case_id,
                    kind=ArtifactKind.DICOM_SECONDARY_CAPTURE,
                    path=str(dicom_path),
                    checksum=checksum_for_file(dicom_path),
                ),
                EvidenceArtifact(
                    artifact_id=f"artifact_{uuid4().hex[:10]}",
                    case_id=case.case_id,
                    kind=ArtifactKind.QUANTIFICATION_CSV,
                    path=str(quant_csv_path),
                    checksum=checksum_for_file(quant_csv_path),
                ),
                EvidenceArtifact(
                    artifact_id=f"artifact_{uuid4().hex[:10]}",
                    case_id=case.case_id,
                    kind=ArtifactKind.EVIDENCE_BUNDLE,
                    path=str(bundle_path),
                    checksum=checksum_for_file(bundle_path),
                ),
            ]
        )
        updated = case.model_copy(update={"artifacts": artifacts, "status": CaseStatus.EXPORTED})
        updated = updated.model_copy(update={"review_summary": {**case.review_summary, "exported": True}})
        self.repo.save(updated)
        return ExportResponse(
            bundle_path=str(bundle_path),
            report_path=str(report_json_path),
            manifest_path=str(manifest_path),
            case_id=case.case_id,
            dicom_path=str(dicom_path),
            summary=_export_summary(
                case=case,
                bundle_path=bundle_path,
                manifest_artifacts=manifest_artifacts,
                included_artifacts=included_entries,
                quantification_rows=quant_rows,
            ),
            artifact_entries=[*manifest_artifacts, *included_entries],
        )


def _selected_case_artifacts(case: CaseRecord, selected_artifacts: list[str]) -> list[EvidenceArtifact]:
    if not selected_artifacts:
        return list(case.artifacts)
    selected = set(selected_artifacts)
    return [
        artifact
        for artifact in case.artifacts
        if artifact.artifact_id in selected or artifact.path in selected or artifact.kind.value in selected
    ]


def _artifact_payload(artifact: EvidenceArtifact) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_id": artifact.artifact_id,
        "kind": artifact.kind.value,
        "path": artifact.path,
        "checksum": artifact.checksum,
    }
    path = Path(artifact.path)
    payload["exists"] = path.exists()
    payload["size_bytes"] = path.stat().st_size if path.exists() and path.is_file() else None
    return payload


def _export_summary(
    *,
    case: CaseRecord,
    bundle_path: Path,
    manifest_artifacts: list[dict[str, Any]],
    included_artifacts: list[dict[str, Any]],
    quantification_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    bundle_size = bundle_path.stat().st_size if bundle_path.exists() else None
    return {
        "schema_version": "osteo-vision-export-summary-v1",
        "case_id": case.case_id,
        "analysis_run_count": len(case.analysis_runs),
        "candidate_region_count": sum(len(run.candidate_regions) for run in case.analysis_runs),
        "core_artifact_count": len(manifest_artifacts),
        "included_artifact_count": len(included_artifacts),
        "total_artifact_count": len(manifest_artifacts) + len(included_artifacts),
        "quantification_row_count": len(quantification_rows),
        "bundle_size_bytes": bundle_size,
        "formats": sorted({str(item.get("kind", "")) for item in [*manifest_artifacts, *included_artifacts] if item.get("kind")}),
        "dicom_included": any(item.get("kind") == ArtifactKind.DICOM_SECONDARY_CAPTURE.value for item in manifest_artifacts),
    }


def _write_evidence_zip(bundle_path: Path, *, core_files: list[Path], case_artifacts: list[EvidenceArtifact]) -> None:
    seen: set[str] = set()
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in core_files:
            _add_file(archive, file_path, f"reports/{file_path.name}", seen)
        for artifact in case_artifacts:
            path = Path(artifact.path)
            if path.exists() and path.is_file():
                _add_file(archive, path, f"artifacts/{artifact.kind.value}/{path.name}", seen)


def _add_file(archive: ZipFile, path: Path, arcname: str, seen: set[str]) -> None:
    if arcname in seen:
        return
    archive.write(path, arcname)
    seen.add(arcname)
