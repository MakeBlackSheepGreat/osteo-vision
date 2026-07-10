from __future__ import annotations

from typing import Any

from backend.src.core.disclaimers import disclaimer_context
from backend.src.domains.cases.schemas import CaseRecord, ExportRequest
from backend.src.reports.dicom_secondary_capture import write_secondary_capture_dicom
from backend.src.reports.platform_markdown import build_platform_markdown
from backend.src.reports.platform_report import build_platform_report
from backend.src.reports.quantification_csv import write_quantification_csv
from backend.src.services.export_bundle import ExportPaths
from backend.src.services.review_manifest import REVIEW_MANIFEST_FIELDS, build_review_manifest
from src.reports.writers import write_csv, write_json


def write_core_export_files(
    case: CaseRecord,
    request: ExportRequest,
    paths: ExportPaths,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    # 核心报告、复核清单和定量 CSV 先落盘，再统一进入 ZIP 与 manifest。
    report = build_platform_report(
        case,
        export_meta={
            "export_format": request.export_format,
            "selected_artifacts": request.selected_artifacts,
            **disclaimer_context(),
        },
    )
    write_json(paths.report_json, report)
    paths.report_md.write_text(build_platform_markdown(case, report), encoding="utf-8")
    write_secondary_capture_dicom(paths.dicom, case, report)
    review_manifest, review_rows = build_review_manifest(case)
    write_json(paths.review_manifest_json, review_manifest)
    write_csv(paths.review_manifest_csv, review_rows, REVIEW_MANIFEST_FIELDS)
    write_json(paths.three_d_scene_manifest, _three_d_scene_manifest_payload(case))
    quant_rows = _quantification_rows(case)
    write_quantification_csv(paths.quantification_csv, quant_rows)
    return report, quant_rows, review_rows


def _three_d_scene_manifest_payload(case: CaseRecord) -> dict[str, Any]:
    latest_run = case.analysis_runs[-1] if case.analysis_runs else None
    fused_outputs = latest_run.fused_outputs if latest_run is not None else {}
    evidence = fused_outputs.get("three_d_evidence") if isinstance(fused_outputs.get("three_d_evidence"), dict) else {}
    if case.three_d_evidence:
        evidence = {**evidence, **case.three_d_evidence}
    scene_manifest_v2 = evidence.get("scene_manifest_v2") if isinstance(evidence.get("scene_manifest_v2"), dict) else {}
    if scene_manifest_v2:
        return {
            "schema_version": "osteo-vision-exported-three-d-scene-manifest-v1",
            "case_id": case.case_id,
            "run_id": evidence.get("run_id"),
            "modeling_job_id": case.three_d_modeling.get("job_id"),
            "available": True,
            "scene_manifest_v2": scene_manifest_v2,
            "three_d_evidence_boundary": evidence.get("boundary_note") or evidence.get("data_boundary"),
        }
    return {
        "schema_version": "osteo-vision-exported-three-d-scene-manifest-v1",
        "case_id": case.case_id,
        "run_id": latest_run.run_id if latest_run is not None else None,
        "available": False,
        "scene_manifest_v2": None,
        "three_d_evidence_boundary": (
            "No Slicer-like CBCT/STL scene graph is attached. The exported 3D layer remains unavailable for "
            "navigation and can only be reconstructed after CBCT/STL import and modeling."
        ),
    }


def _quantification_rows(case: CaseRecord) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in case.analysis_runs:
        quant = run.quantitative_summary or {}
        rows.append(
            {
                "case_id": case.case_id,
                "run_id": run.run_id,
                "roi_id": "",
                **quant,
                "review_state": case.status,
            }
        )
    return rows
