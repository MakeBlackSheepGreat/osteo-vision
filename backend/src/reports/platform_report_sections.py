from __future__ import annotations

import json
from typing import Any

from backend.src.core.disclaimers import ICG_SIGNAL_LIMITATION, PLATFORM_SAFETY_DISCLAIMER
from backend.src.domains.cases.schemas import CaseRecord


def latest_quantification_from_report(report: dict[str, Any]) -> dict[str, Any]:
    latest_run = report.get("latest_analysis_run") if isinstance(report.get("latest_analysis_run"), dict) else {}
    quantification = latest_run.get("quantitative_summary") if isinstance(latest_run, dict) else {}
    return quantification if isinstance(quantification, dict) else {}


def quality_flag_markdown_lines(case: CaseRecord) -> list[str]:
    if not case.quality_flags:
        return ["- No blocking quality flags recorded."]
    return [f"- `{flag.code}`: {flag.message}" for flag in case.quality_flags]


def artifact_markdown_lines(case: CaseRecord) -> list[str]:
    if not case.artifacts:
        return ["- No evidence artifacts recorded."]
    return [f"- `{artifact.kind}`: `{artifact.path}`" for artifact in case.artifacts]


def quantification_summary_lines(quantification: dict[str, Any], *, limit: int = 12) -> list[str]:
    if not quantification:
        return ["- No quantitative summary recorded."]
    return [f"- {key}: {quantification[key]}" for key in sorted(quantification)[:limit]]


def platform_safety_lines() -> list[str]:
    # 报告、Markdown、DICOM 共享同一组边界文案，避免某个导出格式遗失医生复核边界。
    return [PLATFORM_SAFETY_DISCLAIMER, ICG_SIGNAL_LIMITATION]


def json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
