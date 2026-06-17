from __future__ import annotations

from typing import Any

from backend.src.core.disclaimers import ICG_SIGNAL_LIMITATION, RESEARCH_PROTOTYPE_DISCLAIMER
from backend.src.domains.cases.schemas import CaseRecord


def build_platform_markdown(case: CaseRecord, report: dict[str, Any]) -> str:
    latest_run = case.analysis_runs[-1] if case.analysis_runs else None
    quantification = latest_run.quantitative_summary if latest_run else {}
    lines = [
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
        "## Quality And Safety",
        "",
    ]
    if case.quality_flags:
        for flag in case.quality_flags:
            lines.append(f"- `{flag.code}`: {flag.message}")
    else:
        lines.append("- No blocking quality flags recorded.")
    lines.extend(
        [
            "",
            "## Quantification",
            "",
            "```json",
            _json_block(quantification),
            "```",
            "",
            "## Review State",
            "",
            "```json",
            _json_block(report.get("review_summary", {})),
            "```",
            "",
            "## Artifacts",
            "",
        ]
    )
    for artifact in case.artifacts:
        lines.append(f"- `{artifact.kind}`: `{artifact.path}`")
    lines.extend(
        [
            "",
            "## Disclaimer",
            "",
            RESEARCH_PROTOTYPE_DISCLAIMER,
            "",
            ICG_SIGNAL_LIMITATION,
            "",
        ]
    )
    return "\n".join(lines)


def _json_block(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
