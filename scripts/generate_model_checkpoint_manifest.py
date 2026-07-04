from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import load_yaml, runtime_config
from src.core.paths import ensure_dir, resolve_path
from src.models.adapters import build_adapters, inventory_from_adapters
from src.models.lesion_segmenter import checkpoint_sha256
from src.reports.writers import write_json

DEFAULT_CONFIG = "configs/inference/osteo_vision.yml"
DEFAULT_OUTPUT_DIR = "research/reports/modeling"


def build_model_checkpoint_manifest(config_path: str | Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    runtime = runtime_config(config)
    rows = []
    for item in inventory_from_adapters(build_adapters(runtime)):
        spec = item["spec"]
        status = item["status"]
        checkpoint = _checkpoint_record(spec.get("checkpoint_path"))
        artifact_manifest = _load_sidecar_json(checkpoint.get("artifact_manifest_path"))
        model_card = _load_sidecar_json(checkpoint.get("model_card_path"))
        rows.append(
            {
                "model_id": spec.get("model_id"),
                "family": spec.get("family"),
                "enabled": spec.get("enabled"),
                "available": status.get("available"),
                "status_reasons": status.get("reasons") or [],
                "task_types": spec.get("task_types") or [],
                "input_types": spec.get("input_types") or [],
                "checkpoint": checkpoint,
                "artifact_manifest": _sidecar_summary(artifact_manifest),
                "model_card": _sidecar_summary(model_card),
                "manifest_model_id_matches": _sidecar_model_id_matches(spec.get("model_id"), artifact_manifest),
                "intended_use": spec.get("intended_use"),
                "clinical_claim_allowed": bool(spec.get("clinical_claim_allowed")),
                "source_url": spec.get("source_url"),
                "license": spec.get("license"),
                "dependency_group": spec.get("dependency_group"),
                "medical_boundary": _medical_boundary(spec),
            }
        )
    return {
        "schema_version": "osteo-vision-model-checkpoint-manifest-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "config_path": str(resolve_path(config_path)),
        "model_version": runtime.get("model_version"),
        "model_count": len(rows),
        "available_model_count": sum(1 for row in rows if row["available"]),
        "runtime_fixture_fallback_enabled": bool(runtime.get("use_fixture_model")),
        "model_selection_policy": runtime.get("model_selection_policy"),
        "models": rows,
        "summary": _summary(rows),
    }


def write_manifest_bundle(payload: dict[str, Any], *, output_dir: str | Path, date_stamp: str | None = None) -> dict[str, str]:
    stamp = date_stamp or datetime.now(UTC).strftime("%Y%m%d")
    out_dir = ensure_dir(resolve_path(output_dir))
    json_path = out_dir / f"model_checkpoint_manifest_{stamp}.json"
    csv_path = out_dir / f"model_checkpoint_manifest_{stamp}.csv"
    zh_path = out_dir / f"model_checkpoint_manifest_{stamp}_zh.md"
    en_path = out_dir / f"model_checkpoint_manifest_{stamp}_en.md"
    write_json(json_path, payload)
    _write_csv(csv_path, payload["models"])
    zh_path.write_text(render_manifest_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_manifest_report(payload, language="en"), encoding="utf-8")
    return {
        "json_manifest": str(json_path),
        "csv_manifest": str(csv_path),
        "zh_report": str(zh_path),
        "en_report": str(en_path),
    }


def render_manifest_report(payload: dict[str, Any], *, language: str) -> str:
    models = list(payload.get("models") or [])
    available = [row for row in models if row.get("available")]
    unavailable = [row for row in models if not row.get("available")]
    if language == "zh":
        lines = [
            "# 模型 Checkpoint Manifest",
            "",
            "## 结论",
            "",
            f"- 配置：`{payload.get('config_path')}`",
            f"- 模型版本：`{payload.get('model_version')}`",
            f"- 模型总数：{payload.get('model_count')}；当前可用：{payload.get('available_model_count')}。",
            f"- Fixture fallback：{payload.get('runtime_fixture_fallback_enabled')}；选择策略：`{payload.get('model_selection_policy')}`。",
            "",
            "## 当前可用模型",
            "",
            *_model_lines(available, language="zh"),
            "",
            "## 不可用或待实现模型",
            "",
            *_model_lines(unavailable, language="zh"),
            "",
            "## 边界",
            "",
            "当前可用模型仍以 CBCT ROI 代理和 2D 荧光热点启发式为主，不得写成真实术中 ICG 颌骨骨髓炎临床性能。该 manifest 只用于说明工程链路、checkpoint 来源、可用性和缺失项。",
        ]
    else:
        lines = [
            "# Model Checkpoint Manifest",
            "",
            "## Summary",
            "",
            f"- Config: `{payload.get('config_path')}`",
            f"- Model version: `{payload.get('model_version')}`",
            f"- Total models: {payload.get('model_count')}; available now: {payload.get('available_model_count')}.",
            f"- Fixture fallback: {payload.get('runtime_fixture_fallback_enabled')}; selection policy: `{payload.get('model_selection_policy')}`.",
            "",
            "## Available Models",
            "",
            *_model_lines(available, language="en"),
            "",
            "## Unavailable Or Pending Models",
            "",
            *_model_lines(unavailable, language="en"),
            "",
            "## Boundary",
            "",
            "The currently available models are CBCT ROI proxy and 2D fluorescence hotspot heuristic baselines. They must not be reported as real intraoperative ICG jaw osteomyelitis clinical performance. This manifest documents engineering readiness, checkpoint provenance, availability, and gaps.",
        ]
    return "\n".join(lines) + "\n"


def _checkpoint_record(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {
            "path": None,
            "exists": False,
            "sha256": None,
            "size_bytes": None,
            "artifact_manifest_path": None,
            "model_card_path": None,
        }
    path = resolve_path(path_value)
    exists = path.exists()
    stem = path.with_suffix("")
    return {
        "path": str(path),
        "exists": exists,
        "sha256": checkpoint_sha256(path) if exists and path.is_file() else None,
        "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        "artifact_manifest_path": str(stem.with_name(f"{stem.name}_manifest.json")),
        "model_card_path": str(stem.with_name(f"{stem.name}_model_card.json")),
    }


def _load_sidecar_json(path_value: str | None) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _sidecar_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"exists": False}
    return {
        "exists": True,
        "model_id": payload.get("model_id"),
        "model_family": payload.get("model_family"),
        "clinical_claim_allowed": payload.get("clinical_claim_allowed"),
        "metrics": payload.get("metrics") or {},
        "warnings": payload.get("warnings") or payload.get("limitations") or [],
    }


def _sidecar_model_id_matches(model_id: Any, payload: dict[str, Any] | None) -> bool | None:
    if not payload:
        return None
    return str(payload.get("model_id")) == str(model_id)


def _medical_boundary(spec: dict[str, Any]) -> str:
    family = str(spec.get("family") or "")
    if family in {"convnext3d_segmenter", "d025_lesion_segmenter"}:
        return "D025 CBCT lesion ROI proxy; not target-domain intraoperative ICG jaw osteomyelitis evidence."
    if family == "fluorescence_hotspot_segmenter":
        return "Heuristic 2D fluorescence hotspot baseline; not trained target-domain diagnosis."
    if family == "fixture":
        return "Deterministic fixture fallback for tests and demos only."
    return "Configured candidate model; availability depends on adapter implementation, dependencies, and weights."


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "available_model_ids": [str(row["model_id"]) for row in rows if row["available"]],
        "unavailable_model_ids": [str(row["model_id"]) for row in rows if not row["available"]],
        "checkpointed_model_ids": [
            str(row["model_id"]) for row in rows if row.get("checkpoint", {}).get("exists")
        ],
        "models_with_missing_checkpoint": [
            str(row["model_id"])
            for row in rows
            if row.get("checkpoint", {}).get("path") and not row.get("checkpoint", {}).get("exists")
        ],
        "models_allowing_clinical_claims": [
            str(row["model_id"]) for row in rows if row.get("clinical_claim_allowed")
        ],
    }


def _model_lines(rows: list[dict[str, Any]], *, language: str) -> list[str]:
    if not rows:
        return ["- 无。" if language == "zh" else "- None."]
    lines: list[str] = []
    for row in rows:
        checkpoint = row.get("checkpoint") or {}
        reasons = row.get("status_reasons") or []
        reasons_text = "; ".join(str(item) for item in reasons) if reasons else ("无" if language == "zh" else "none")
        if language == "zh":
            lines.append(
                f"- `{row.get('model_id')}` / `{row.get('family')}`：checkpoint 存在={checkpoint.get('exists')}；临床声明={row.get('clinical_claim_allowed')}；原因：{reasons_text}。"
            )
        else:
            lines.append(
                f"- `{row.get('model_id')}` / `{row.get('family')}`: checkpoint exists={checkpoint.get('exists')}; clinical claim={row.get('clinical_claim_allowed')}; reasons: {reasons_text}."
            )
    return lines


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model_id",
        "family",
        "enabled",
        "available",
        "checkpoint_path",
        "checkpoint_exists",
        "checkpoint_sha256",
        "artifact_manifest_exists",
        "model_card_exists",
        "manifest_model_id_matches",
        "clinical_claim_allowed",
        "status_reasons",
        "medical_boundary",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            checkpoint = row.get("checkpoint") or {}
            writer.writerow(
                {
                    "model_id": row.get("model_id"),
                    "family": row.get("family"),
                    "enabled": row.get("enabled"),
                    "available": row.get("available"),
                    "checkpoint_path": checkpoint.get("path"),
                    "checkpoint_exists": checkpoint.get("exists"),
                    "checkpoint_sha256": checkpoint.get("sha256"),
                    "artifact_manifest_exists": row.get("artifact_manifest", {}).get("exists"),
                    "model_card_exists": row.get("model_card", {}).get("exists"),
                    "manifest_model_id_matches": row.get("manifest_model_id_matches"),
                    "clinical_claim_allowed": row.get("clinical_claim_allowed"),
                    "status_reasons": "; ".join(str(item) for item in row.get("status_reasons") or []),
                    "medical_boundary": row.get("medical_boundary"),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an auditable model checkpoint manifest.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--date-stamp", default=datetime.now(UTC).strftime("%Y%m%d"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_model_checkpoint_manifest(args.config)
    paths = write_manifest_bundle(payload, output_dir=args.output_dir, date_stamp=args.date_stamp)
    print(json.dumps({"paths": paths, "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
