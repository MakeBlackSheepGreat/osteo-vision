from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from src.core.paths import ensure_dir


def write_json(path: str | Path, payload: dict[str, Any]) -> str:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def write_markdown(path: str | Path, title: str, sections: dict[str, Any]) -> str:
    p = Path(path)
    ensure_dir(p.parent)
    lines = [f"# {title}", ""]
    for name, content in sections.items():
        lines.extend([f"## {name}", "", _format_markdown_value(content), ""])
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> str:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return str(p)


def _format_markdown_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"
    return str(value)
