from __future__ import annotations

from typing import Any

from backend.src.domains.cases.schemas import CaseRecord
from backend.src.reports.platform_report_sections import (
    artifact_markdown_lines,
    json_block,
    latest_quantification_from_report,
    platform_safety_lines,
    three_d_evidence_markdown_lines,
    quality_flag_markdown_lines,
    video_signal_markdown_lines,
)


def build_platform_markdown(case: CaseRecord, report: dict[str, Any]) -> str:
    quantification = latest_quantification_from_report(report)
    sections = [
        *_case_section(case),
        *_quality_section(case),
        *_json_section("Quantification", quantification),
        *_video_signal_section(report),
        *_three_d_evidence_section(report),
        *_json_section("Review State", report.get("review_summary", {})),
        *_artifact_section(case),
        *_disclaimer_section(),
    ]
    return "\n".join(sections)


def _case_section(case: CaseRecord) -> list[str]:
    return [
        "# Osteo Vision Evidence Report",
        "",
        "## Case",
        "",
        f"- Case ID: `{case.case_id}`",
        f"- Title: `{case.title}`",
        f"- Status: `{case.status}`",
        f"- Inputs: `{len(case.inputs)}`",
        f"- Review events: `{len(case.review_events)}`",
        "",
    ]


def _quality_section(case: CaseRecord) -> list[str]:
    return ["## Quality And Safety", "", *quality_flag_markdown_lines(case), ""]


def _json_section(title: str, value: object) -> list[str]:
    return ["## " + title, "", "```json", json_block(value), "```", ""]


def _video_signal_section(report: dict[str, Any]) -> list[str]:
    section = report.get("video_signal_segmentation")
    section = section if isinstance(section, dict) else {}
    return ["## Fluorescence Perfusion Risk Prompts", "", *video_signal_markdown_lines(section), ""]


def _three_d_evidence_section(report: dict[str, Any]) -> list[str]:
    section = report.get("three_d_evidence")
    section = section if isinstance(section, dict) else {}
    return ["## CBCT/STL 3D Evidence Reference", "", *three_d_evidence_markdown_lines(section), ""]


def _artifact_section(case: CaseRecord) -> list[str]:
    return ["## Artifacts", "", *artifact_markdown_lines(case), ""]


def _disclaimer_section() -> list[str]:
    return ["## Disclaimer", "", *platform_safety_lines(), ""]
