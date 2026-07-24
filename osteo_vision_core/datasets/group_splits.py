from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SOURCE_GROUP_KEYS = (
    "source_group_id",
    "group_id",
    "source_video_path",
    "source_path",
    "video_path",
    "patient_id",
    "case_id",
)


def source_group_id(row: dict[str, Any], *, keys: Iterable[str] = SOURCE_GROUP_KEYS) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return normalized_source_group(value)
    raise ValueError("Row has no source grouping field.")


def normalized_source_group(value: str | Path) -> str:
    text = str(value).strip().replace("\\", "/")
    return text.casefold()


def assign_group_split(
    group_id: str,
    *,
    seed: int,
    val_fraction: float,
    test_fraction: float = 0.0,
) -> str:
    safe_val = max(0.0, min(0.8, float(val_fraction)))
    safe_test = max(0.0, min(0.8, float(test_fraction)))
    if safe_val + safe_test > 0.9:
        raise ValueError("val_fraction + test_fraction must be <= 0.9")
    digest = hashlib.sha256(f"{int(seed)}:{normalized_source_group(group_id)}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF)
    if bucket < safe_test:
        return "test"
    if bucket < safe_test + safe_val:
        return "val"
    return "train"


def group_leakage_report(
    rows: Iterable[dict[str, Any]],
    *,
    split_key: str = "split",
    group_keys: Iterable[str] = SOURCE_GROUP_KEYS,
) -> dict[str, Any]:
    split_by_group: dict[str, set[str]] = defaultdict(set)
    row_count = 0
    missing_group_rows: list[str] = []
    for index, row in enumerate(rows):
        row_count += 1
        try:
            group_id = source_group_id(row, keys=group_keys)
        except ValueError:
            missing_group_rows.append(str(row.get("case_id") or index))
            continue
        split = str(row.get(split_key) or "unspecified").strip().lower()
        split_by_group[group_id].add(split)
    leaking = {group: sorted(splits) for group, splits in split_by_group.items() if len(splits) > 1}
    split_group_counts: dict[str, int] = defaultdict(int)
    for splits in split_by_group.values():
        for split in splits:
            split_group_counts[split] += 1
    return {
        "row_count": row_count,
        "group_count": len(split_by_group),
        "split_group_counts": dict(sorted(split_group_counts.items())),
        "leakage_detected": bool(leaking),
        "leaking_group_count": len(leaking),
        "leaking_groups": leaking,
        "missing_group_row_count": len(missing_group_rows),
        "missing_group_rows_first20": missing_group_rows[:20],
        "group_keys": list(group_keys),
        "split_key": split_key,
    }


def assert_no_group_leakage(rows: Iterable[dict[str, Any]], *, context: str) -> dict[str, Any]:
    materialized = list(rows)
    report = group_leakage_report(materialized)
    if report["missing_group_row_count"]:
        raise ValueError(f"{context} has {report['missing_group_row_count']} row(s) without a source grouping field.")
    if report["leakage_detected"]:
        examples = list(report["leaking_groups"].items())[:5]
        raise ValueError(
            f"{context} has {report['leaking_group_count']} source group(s) crossing splits; examples={examples}"
        )
    return report
