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
    quant_rows = _quantification_rows(case)
    write_quantification_csv(paths.quantification_csv, quant_rows)
    return report, quant_rows, review_rows


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
