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
from src.reports.writers import write_csv
from src.reports.writers import write_json


REVIEW_MANIFEST_FIELDS = [
    "case_id",
    "record_type",
    "run_id",
    "roi_id",
    "candidate_id",
    "review_state",
    "label",
    "source",
    "actor",
    "action",
    "target_id",
    "timestamp",
    "score",
    "confidence",
    "risk_type",
    "frame_index",
    "timestamp_sec",
    "image_width",
    "image_height",
    "bbox_xyxy",
    "bbox_normalized",
    "geometry",
    "mask_path",
    "overlay_path",
    "source_path",
    "notes",
    "medical_boundary",
]


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
        review_manifest_json_path = export_dir / f"{case.case_id}_review_manifest.json"
        review_manifest_csv_path = export_dir / f"{case.case_id}_review_manifest.csv"
        manifest_path = export_dir / f"{case.case_id}_manifest.json"
        bundle_manifest_path = export_dir / f"{case.case_id}_bundle_manifest.json"
        bundle_path = export_dir / f"{case.case_id}_evidence_bundle.zip"
        selected_case_artifacts = _selected_case_artifacts(case, request.selected_artifacts)
        write_json(report_json_path, report)
        report_md_path.write_text(build_platform_markdown(case, report), encoding="utf-8")
        write_secondary_capture_dicom(dicom_path, case, report)
        review_manifest, review_rows = _build_review_manifest(case)
        write_json(review_manifest_json_path, review_manifest)
        write_csv(review_manifest_csv_path, review_rows, REVIEW_MANIFEST_FIELDS)
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
            "review_manifest_json": str(review_manifest_json_path),
            "review_manifest_csv": str(review_manifest_csv_path),
            "included_artifacts": [
                _artifact_payload(artifact) for artifact in selected_case_artifacts
            ],
            "disclaimer": disclaimer_context(),
        }
        write_json(bundle_manifest_path, bundle_payload)
        _write_evidence_zip(
            bundle_path,
            core_files=[
                report_json_path,
                report_md_path,
                dicom_path,
                quant_csv_path,
                review_manifest_json_path,
                review_manifest_csv_path,
                bundle_manifest_path,
            ],
            case_artifacts=selected_case_artifacts,
        )
        manifest_artifacts = [
            manifest_record(ArtifactKind.REPORT_JSON.value, report_json_path),
            manifest_record(ArtifactKind.REPORT_MD.value, report_md_path),
            manifest_record(ArtifactKind.DICOM_SECONDARY_CAPTURE.value, dicom_path),
            manifest_record(ArtifactKind.QUANTIFICATION_CSV.value, quant_csv_path),
            manifest_record(ArtifactKind.REVIEW_MANIFEST_JSON.value, review_manifest_json_path),
            manifest_record(ArtifactKind.REVIEW_MANIFEST_CSV.value, review_manifest_csv_path),
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
            "review_manifest_json_path": str(review_manifest_json_path),
            "review_manifest_csv_path": str(review_manifest_csv_path),
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
                    kind=ArtifactKind.REVIEW_MANIFEST_JSON,
                    path=str(review_manifest_json_path),
                    checksum=checksum_for_file(review_manifest_json_path),
                ),
                EvidenceArtifact(
                    artifact_id=f"artifact_{uuid4().hex[:10]}",
                    case_id=case.case_id,
                    kind=ArtifactKind.REVIEW_MANIFEST_CSV,
                    path=str(review_manifest_csv_path),
                    checksum=checksum_for_file(review_manifest_csv_path),
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
                review_manifest_rows=review_rows,
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


def _build_review_manifest(case: CaseRecord) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = [
        _candidate_manifest_entry(case.case_id, run.run_id, run.method_id, candidate)
        for run in case.analysis_runs
        for candidate in run.candidate_regions
    ]
    rois = [_roi_manifest_entry(roi) for roi in case.rois]
    review_events = [
        event.model_dump(mode="json")
        for event in sorted(case.review_events, key=lambda item: item.timestamp)
    ]
    rows = [
        *[_candidate_review_row(case.case_id, candidate) for candidate in candidates],
        *[_roi_review_row(roi) for roi in rois],
        *[_review_event_row(event) for event in review_events],
    ]
    payload = {
        "schema_version": "osteo-vision-review-manifest-v1",
        "case_id": case.case_id,
        "generated_from": "ExportService.export_case",
        "review_source_scope": {
            "rois": "Doctor-created or AI-promoted regions available in this case record.",
            "candidate_regions": "AI candidate regions produced by JPEG/MP4 keyframe or image analysis runs.",
            "review_events": "Human review actions recorded through the case review API.",
        },
        "training_use": {
            "allowed_scope": "prototype_retraining_or_error_analysis_after_deidentification",
            "requires_physician_review": True,
            "non_target_domain_warning": (
                "Public, proxy, synthetic, or CBCT-derived samples must not be described as real "
                "intraoperative ICG jaw osteomyelitis data."
            ),
        },
        "medical_boundary": disclaimer_context(),
        "summary": {
            "roi_count": len(rois),
            "candidate_region_count": len(candidates),
            "review_event_count": len(review_events),
            "accepted_candidate_count": sum(1 for item in candidates if item.get("status") == "accepted"),
            "accepted_roi_count": sum(1 for item in rois if item.get("review_state") == "accepted"),
        },
        "candidates": candidates,
        "rois": rois,
        "review_events": review_events,
    }
    return payload, rows


def _candidate_manifest_entry(
    case_id: str,
    run_id: str,
    method_id: str | None,
    candidate: Any,
) -> dict[str, Any]:
    metadata = candidate.metadata or {}
    return {
        "case_id": case_id,
        "run_id": run_id,
        "method_id": method_id,
        "candidate_id": candidate.candidate_id,
        "status": str(candidate.status),
        "score": candidate.score,
        "confidence": candidate.confidence,
        "risk_type": candidate.risk_type,
        "explanation": candidate.explanation,
        "frame_index": metadata.get("frame_index"),
        "frame_order": metadata.get("frame_order"),
        "timestamp_sec": metadata.get("timestamp_sec"),
        "model_id": metadata.get("model_id"),
        "model_family": metadata.get("model_family"),
        "analysis_method": metadata.get("analysis_method"),
        "bbox_xyxy": metadata.get("bbox_xyxy") or metadata.get("source_bbox_xyxy"),
        "bbox_normalized": metadata.get("bbox_normalized") or metadata.get("source_bbox_normalized"),
        "mask_path": metadata.get("mask_path"),
        "overlay_path": metadata.get("overlay_path"),
        "source_path": metadata.get("source_path"),
        "image_width": metadata.get("image_width") or metadata.get("source_video_width"),
        "image_height": metadata.get("image_height") or metadata.get("source_video_height"),
        "spatial_mapping": metadata.get("spatial_mapping"),
        "temporal_stability": metadata.get("temporal_stability"),
        "metadata": metadata,
    }


def _roi_manifest_entry(roi: Any) -> dict[str, Any]:
    return {
        "case_id": roi.case_id,
        "roi_id": roi.roi_id,
        "candidate_id": roi.candidate_id,
        "source": str(roi.source),
        "review_state": str(roi.review_state),
        "label": roi.label,
        "geometry": roi.geometry,
        "metrics": roi.metrics,
        "frame_index": roi.metrics.get("frame_index") if isinstance(roi.metrics, dict) else None,
        "timestamp_sec": roi.metrics.get("timestamp_sec") if isinstance(roi.metrics, dict) else None,
    }


def _candidate_review_row(case_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "record_type": "candidate_region",
        "run_id": candidate.get("run_id"),
        "candidate_id": candidate.get("candidate_id"),
        "review_state": candidate.get("status"),
        "score": candidate.get("score"),
        "confidence": candidate.get("confidence"),
        "risk_type": candidate.get("risk_type"),
        "frame_index": candidate.get("frame_index"),
        "timestamp_sec": candidate.get("timestamp_sec"),
        "image_width": candidate.get("image_width"),
        "image_height": candidate.get("image_height"),
        "bbox_xyxy": _compact_json(candidate.get("bbox_xyxy")),
        "bbox_normalized": _compact_json(candidate.get("bbox_normalized")),
        "mask_path": candidate.get("mask_path"),
        "overlay_path": candidate.get("overlay_path"),
        "source_path": candidate.get("source_path"),
        "notes": candidate.get("explanation"),
        "medical_boundary": "research_prototype_physician_review_required",
    }


def _roi_review_row(roi: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": roi.get("case_id"),
        "record_type": "roi",
        "roi_id": roi.get("roi_id"),
        "candidate_id": roi.get("candidate_id"),
        "review_state": roi.get("review_state"),
        "label": roi.get("label"),
        "source": roi.get("source"),
        "frame_index": roi.get("frame_index"),
        "timestamp_sec": roi.get("timestamp_sec"),
        "geometry": _compact_json(roi.get("geometry")),
        "notes": _compact_json(roi.get("metrics")),
        "medical_boundary": "research_prototype_physician_review_required",
    }


def _review_event_row(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": event.get("case_id"),
        "record_type": "review_event",
        "actor": event.get("actor"),
        "action": event.get("action"),
        "target_id": event.get("target_id"),
        "timestamp": event.get("timestamp"),
        "review_state": event.get("after_state"),
        "notes": event.get("notes"),
        "medical_boundary": "research_prototype_physician_review_required",
    }


def _compact_json(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _export_summary(
    *,
    case: CaseRecord,
    bundle_path: Path,
    manifest_artifacts: list[dict[str, Any]],
    included_artifacts: list[dict[str, Any]],
    quantification_rows: list[dict[str, Any]],
    review_manifest_rows: list[dict[str, Any]],
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
        "roi_count": len(case.rois),
        "review_event_count": len(case.review_events),
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
