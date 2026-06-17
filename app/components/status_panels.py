from __future__ import annotations

from typing import Any


def warning_markdown(result: dict[str, Any] | None) -> str:
    warnings = (result or {}).get("warnings") or []
    if not warnings:
        return "No warnings."
    return "\n".join(f"- `{item.get('code', 'warning')}`: {item.get('message', '')}" for item in warnings)


def result_markdown(result: dict[str, Any] | None) -> str:
    if not result:
        return "No result yet."
    return (
        f"Status: `{result.get('status')}`\n\n"
        f"Task: `{result.get('task_type')}`\n\n"
        f"Label: `{result.get('class_label')}`\n\n"
        f"Risk: `{result.get('risk_level')}`\n\n"
        f"Probability: `{result.get('probability')}`"
    )

