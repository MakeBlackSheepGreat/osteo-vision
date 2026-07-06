from __future__ import annotations

from backend.src.domains.cases.schemas import CaseRecord
from backend.src.reports.platform_report import build_platform_report
from backend.src.reports.platform_report_sections import (
    artifact_markdown_lines,
    latest_quantification_from_report,
    platform_safety_lines,
    quality_flag_markdown_lines,
)


def test_platform_report_sections_keep_empty_state_and_safety_boundary() -> None:
    case = CaseRecord(case_id="case_report_sections", title="sections")
    report = build_platform_report(case)

    assert latest_quantification_from_report(report) == {}
    assert quality_flag_markdown_lines(case) == ["- No blocking quality flags recorded."]
    assert artifact_markdown_lines(case) == ["- No evidence artifacts recorded."]
    assert "Platform software for research and competition validation" in platform_safety_lines()[0]
