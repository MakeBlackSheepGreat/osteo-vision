from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from backend.osteo_vision_api.core.artifacts import artifact_root, checksum_for_file, manifest_record
from backend.osteo_vision_api.core.disclaimers import disclaimer_context
from backend.osteo_vision_api.domains.cases.enums import ArtifactKind
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord, EvidenceArtifact


@dataclass(frozen=True)
class ExportPaths:
    report_json: Path
    report_md: Path
    dicom: Path
    review_manifest_json: Path
    review_manifest_csv: Path
    annotation_audit_json: Path
    annotation_audit_csv: Path
    annotation_manifest_registry: Path
    three_d_scene_manifest: Path
    quantification_csv: Path
    manifest: Path
    bundle_manifest: Path
    bundle: Path

    @property
    def core_bundle_files(self) -> list[Path]:
        return [
            self.report_json,
            self.report_md,
            self.dicom,
            self.quantification_csv,
            self.review_manifest_json,
            self.review_manifest_csv,
            self.annotation_audit_json,
            self.annotation_audit_csv,
            self.annotation_manifest_registry,
            self.three_d_scene_manifest,
            self.bundle_manifest,
        ]


def export_paths(artifact_dir: Path, case_id: str) -> ExportPaths:
    export_dir = artifact_root(artifact_dir / case_id / f"export_{uuid4().hex[:8]}")
    return ExportPaths(
        report_json=export_dir / f"{case_id}_report.json",
        report_md=export_dir / f"{case_id}_report.md",
        dicom=export_dir / f"{case_id}_secondary_capture.dcm",
        review_manifest_json=export_dir / f"{case_id}_review_manifest.json",
        review_manifest_csv=export_dir / f"{case_id}_review_manifest.csv",
        annotation_audit_json=export_dir / f"{case_id}_annotation_audit.json",
        annotation_audit_csv=export_dir / f"{case_id}_annotation_audit.csv",
        annotation_manifest_registry=export_dir / f"{case_id}_annotation_manifest_registry.json",
        three_d_scene_manifest=export_dir / f"{case_id}_three_d_scene_manifest.json",
        quantification_csv=export_dir / f"{case_id}_quantification.csv",
        manifest=export_dir / f"{case_id}_manifest.json",
        bundle_manifest=export_dir / f"{case_id}_bundle_manifest.json",
        bundle=export_dir / f"{case_id}_evidence_bundle.zip",
    )


def bundle_manifest_payload(
    case_id: str,
    paths: ExportPaths,
    included_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "report_json": str(paths.report_json),
        "report_md": str(paths.report_md),
        "dicom_secondary_capture": str(paths.dicom),
        "quantification_csv": str(paths.quantification_csv),
        "review_manifest_json": str(paths.review_manifest_json),
        "review_manifest_csv": str(paths.review_manifest_csv),
        "annotation_audit_json": str(paths.annotation_audit_json),
        "annotation_audit_csv": str(paths.annotation_audit_csv),
        "annotation_manifest_registry": str(paths.annotation_manifest_registry),
        "three_d_scene_manifest": str(paths.three_d_scene_manifest),
        "included_artifacts": included_entries,
        "disclaimer": disclaimer_context(),
    }


def export_manifest_payload(
    case_id: str,
    paths: ExportPaths,
    manifest_artifacts: list[dict[str, Any]],
    included_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "bundle_path": str(paths.bundle),
        "bundle_manifest_path": str(paths.bundle_manifest),
        "report_path": str(paths.report_json),
        "report_md_path": str(paths.report_md),
        "dicom_secondary_capture_path": str(paths.dicom),
        "quantification_csv_path": str(paths.quantification_csv),
        "review_manifest_json_path": str(paths.review_manifest_json),
        "review_manifest_csv_path": str(paths.review_manifest_csv),
        "annotation_audit_json_path": str(paths.annotation_audit_json),
        "annotation_audit_csv_path": str(paths.annotation_audit_csv),
        "annotation_manifest_registry_path": str(paths.annotation_manifest_registry),
        "three_d_scene_manifest_path": str(paths.three_d_scene_manifest),
        "artifacts": manifest_artifacts,
        "included_artifacts": included_entries,
        "disclaimer": disclaimer_context(),
    }


def core_manifest_artifacts(paths: ExportPaths) -> list[dict[str, Any]]:
    return [
        manifest_record(ArtifactKind.REPORT_JSON.value, paths.report_json),
        manifest_record(ArtifactKind.REPORT_MD.value, paths.report_md),
        manifest_record(ArtifactKind.DICOM_SECONDARY_CAPTURE.value, paths.dicom),
        manifest_record(ArtifactKind.QUANTIFICATION_CSV.value, paths.quantification_csv),
        manifest_record(ArtifactKind.REVIEW_MANIFEST_JSON.value, paths.review_manifest_json),
        manifest_record(ArtifactKind.REVIEW_MANIFEST_CSV.value, paths.review_manifest_csv),
        manifest_record(ArtifactKind.ANNOTATION_AUDIT_JSON.value, paths.annotation_audit_json),
        manifest_record(ArtifactKind.ANNOTATION_AUDIT_CSV.value, paths.annotation_audit_csv),
        manifest_record(ArtifactKind.ANNOTATION_MANIFEST_REGISTRY.value, paths.annotation_manifest_registry),
        manifest_record(ArtifactKind.THREE_D_SCENE_MANIFEST.value, paths.three_d_scene_manifest),
        manifest_record("bundle_manifest", paths.bundle_manifest),
        manifest_record(ArtifactKind.EVIDENCE_BUNDLE.value, paths.bundle),
    ]


def export_evidence_artifacts(case_id: str, paths: ExportPaths) -> list[EvidenceArtifact]:
    core_outputs = [
        (ArtifactKind.REPORT_JSON, paths.report_json),
        (ArtifactKind.REPORT_MD, paths.report_md),
        (ArtifactKind.DICOM_SECONDARY_CAPTURE, paths.dicom),
        (ArtifactKind.QUANTIFICATION_CSV, paths.quantification_csv),
        (ArtifactKind.REVIEW_MANIFEST_JSON, paths.review_manifest_json),
        (ArtifactKind.REVIEW_MANIFEST_CSV, paths.review_manifest_csv),
        (ArtifactKind.ANNOTATION_AUDIT_JSON, paths.annotation_audit_json),
        (ArtifactKind.ANNOTATION_AUDIT_CSV, paths.annotation_audit_csv),
        (ArtifactKind.ANNOTATION_MANIFEST_REGISTRY, paths.annotation_manifest_registry),
        (ArtifactKind.THREE_D_SCENE_MANIFEST, paths.three_d_scene_manifest),
        (ArtifactKind.EVIDENCE_BUNDLE, paths.bundle),
    ]
    return [
        EvidenceArtifact(
            artifact_id=f"artifact_{uuid4().hex[:10]}",
            case_id=case_id,
            kind=kind,
            path=str(path),
            checksum=checksum_for_file(path),
        )
        for kind, path in core_outputs
    ]


def selected_case_artifacts(case: CaseRecord, selected_artifacts: list[str]) -> list[EvidenceArtifact]:
    if not selected_artifacts:
        return list(case.artifacts)
    selected = set(selected_artifacts)
    return [
        artifact
        for artifact in case.artifacts
        if artifact.artifact_id in selected or artifact.path in selected or artifact.kind.value in selected
    ]


def artifact_payload(artifact: EvidenceArtifact) -> dict[str, Any]:
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


def export_summary(
    *,
    case: CaseRecord,
    bundle_path: Path,
    manifest_artifacts: list[dict[str, Any]],
    included_artifacts: list[dict[str, Any]],
    quantification_rows: list[dict[str, Any]],
    review_manifest_rows: list[dict[str, Any]],
    annotation_audit_rows: list[dict[str, Any]] | None = None,
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
        "review_manifest_row_count": len(review_manifest_rows),
        "annotation_audit_version_count": len(annotation_audit_rows or []),
        "roi_count": len(case.rois),
        "review_event_count": len(case.review_events),
        "bundle_size_bytes": bundle_size,
        "formats": sorted(
            {str(item.get("kind", "")) for item in [*manifest_artifacts, *included_artifacts] if item.get("kind")}
        ),
        "dicom_included": any(
            item.get("kind") == ArtifactKind.DICOM_SECONDARY_CAPTURE.value for item in manifest_artifacts
        ),
    }


def write_evidence_zip(
    bundle_path: Path,
    *,
    core_files: list[Path],
    case_artifacts: list[EvidenceArtifact],
    additional_files: list[tuple[Path, str]] | None = None,
) -> None:
    # ZIP 内固定 reports/ 与 artifacts/ 两个目录，便于学校评估时直接定位报告和证据图像。
    seen: set[str] = set()
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in core_files:
            _add_file(archive, file_path, f"reports/{file_path.name}", seen)
        for artifact in case_artifacts:
            path = Path(artifact.path)
            if path.exists() and path.is_file():
                _add_file(archive, path, f"artifacts/{artifact.kind.value}/{path.name}", seen)
        for path, arcname in additional_files or []:
            if path.exists() and path.is_file():
                _add_file(archive, path, arcname, seen)


def _add_file(archive: ZipFile, path: Path, arcname: str, seen: set[str]) -> None:
    if arcname in seen:
        return
    archive.write(path, arcname)
    seen.add(arcname)
