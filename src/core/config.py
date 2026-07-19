from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import project_root, resolve_path


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must contain a mapping: {p}")
    data["_config_path"] = str(p)
    data["_project_root"] = str(project_root())
    return data


def config_hash(path: str | Path) -> str:
    p = resolve_path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def runtime_config(config: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(config.get("runtime") or {})
    runtime.setdefault("model_version", "micf-fixture-v0")
    runtime.setdefault("default_task_type", "classification")
    runtime.setdefault("default_threshold", 0.5)
    runtime.setdefault("use_fixture_model", True)
    return runtime
