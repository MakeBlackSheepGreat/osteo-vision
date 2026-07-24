from __future__ import annotations

import hashlib
from typing import Any


def assign_splits(rows: list[dict[str, Any]], strategy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kind = str(strategy.get("type", "fixed"))
    if kind == "kfold":
        return _assign_kfold(rows, strategy)
    if kind == "external":
        return _assign_external(rows, strategy)
    return _assign_fixed(rows, strategy)


def _assign_fixed(rows: list[dict[str, Any]], strategy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split_column = str(strategy.get("split_column", "split"))
    default_split = str(strategy.get("default_split", "validation"))
    assigned = []
    for row in rows:
        item = dict(row)
        item["_split"] = str(row.get(split_column) or default_split)
        item["_fold"] = str(row.get("fold") or "0")
        assigned.append(item)
    return assigned, {"type": "fixed", "split_column": split_column, "default_split": default_split}


def _assign_external(
    rows: list[dict[str, Any]], strategy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    external_value = str(strategy.get("external_split", "external"))
    assigned = []
    for row in rows:
        item = dict(row)
        item["_split"] = str(row.get("split") or external_value)
        item["_fold"] = "external"
        assigned.append(item)
    return assigned, {"type": "external", "external_split": external_value}


def _assign_kfold(rows: list[dict[str, Any]], strategy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    folds = max(2, int(strategy.get("folds", 5)))
    group_column = str(strategy.get("group_column", "patient_id"))
    assigned = []
    for row in rows:
        item = dict(row)
        group = str(row.get(group_column) or row.get("case_id") or row.get("input_path") or "")
        digest = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16)
        fold = digest % folds
        item["_fold"] = str(fold)
        item["_split"] = "validation"
        assigned.append(item)
    return assigned, {"type": "kfold", "folds": folds, "group_column": group_column}
