from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "research/reports/release/platform_evidence_manifest.yml"


def sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_path(value: str | Path) -> Path:
    candidate = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"Evidence path escapes the repository: {value}") from exc
    return candidate


def file_entry(path: Path, *, required: bool, category: str) -> dict[str, Any]:
    exists = path.exists()
    try:
        relative_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        relative_path = str(path)
    return {
        "path": relative_path,
        "category": category,
        "required": required,
        "exists": exists,
        "type": "directory" if path.is_dir() else "file",
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path),
        "git_tracked": git_is_tracked(path),
    }


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip()


def git_is_tracked(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative.as_posix()],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def project_versions() -> dict[str, str | None]:
    python_project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    root_node = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    frontend_node = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    return {
        "python": str(python_project.get("version") or ""),
        "root_node": str(root_node.get("version") or ""),
        "frontend": str(frontend_node.get("version") or ""),
    }


def model_entries(config_path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    models = payload.get("runtime", {}).get("models", [])
    entries: list[dict[str, Any]] = []
    for raw_mapping in models:
        if not isinstance(raw_mapping, dict):
            continue
        mapping = dict(raw_mapping)
        checkpoint_value = mapping.get("checkpoint_path")
        checkpoint = repository_path(str(checkpoint_value)) if checkpoint_value else None
        extra = dict(mapping.get("extra") or {})
        runtime_allowed = bool(extra.get("runtime_allowed", True))
        enabled = bool(mapping.get("enabled", True))
        checkpoint_exists = bool(checkpoint and checkpoint.is_file())
        checkpoint_ready = bool(
            checkpoint_exists
            or mapping.get("family") in {"fluorescence_hotspot_segmenter", "fixture"}
            or extra.get("prompt_fallback_enabled")
        )
        threshold = extra["threshold"] if "threshold" in extra else extra.get("head_thresholds")
        entries.append(
            {
                "model_id": mapping.get("model_id"),
                "family": mapping.get("family"),
                "enabled": enabled,
                "runtime_allowed": runtime_allowed,
                "runtime_eligible_by_static_config": enabled and runtime_allowed and checkpoint_ready,
                "checkpoint": file_entry(checkpoint, required=True, category="checkpoint") if checkpoint else None,
                "intended_use": mapping.get("intended_use"),
                "clinical_claim_allowed": bool(mapping.get("clinical_claim_allowed", False)),
                "input_domain": extra.get("input_domain"),
                "target_domain": bool(extra.get("target_domain", False)),
                "review_boundary": extra.get("review_boundary"),
                "threshold": threshold,
            }
        )
    return entries


def load_manifest(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Evidence manifest must contain a mapping.")
    if not isinstance(payload.get("evidence_files"), list):
        raise ValueError("Evidence manifest requires an evidence_files list.")
    if not isinstance(payload.get("local_runtime_evidence", []), list):
        raise ValueError("local_runtime_evidence must be a list.")
    return payload


def build_payload(manifest_path: Path, *, config_override: str | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    config_path = repository_path(config_override or str(manifest.get("strict_config") or ""))
    if not config_path.is_file():
        raise FileNotFoundError(f"Strict runtime config is missing: {config_path}")

    required_entries = [
        file_entry(repository_path(str(value)), required=True, category="versioned_evidence")
        for value in manifest["evidence_files"]
    ]
    local_entries = [
        file_entry(repository_path(str(value)), required=False, category="local_runtime_evidence")
        for value in manifest.get("local_runtime_evidence", [])
    ]
    status_lines = [line for line in git_value("status", "--short").splitlines() if line]
    missing_required = [entry["path"] for entry in required_entries if not entry["exists"]]
    missing_local = [entry["path"] for entry in local_entries if not entry["exists"]]
    versions = project_versions()
    manifest_version = str(manifest.get("project_version") or "")
    normalized_python_version = versions["python"].replace("rc", "-rc.") if versions["python"] else None
    version_consistent = bool(
        manifest_version
        and normalized_python_version == manifest_version
        and versions["root_node"] == manifest_version
        and versions["frontend"] == manifest_version
    )

    return {
        "schema_version": "osteo-vision-platform-evidence-index-v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "project_versions": {**versions, "manifest": manifest_version, "consistent": version_consistent},
        "input_contract": {
            "image_formats": ["JPEG"],
            "video_formats": ["MP4", "AVI (controlled transcode)"],
            "reference_resolution": "3840x2160",
            "metadata": "offline manifest or manually entered metadata",
        },
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "nearest_tag": git_value("describe", "--tags", "--abbrev=0"),
            "status_entry_count": len(status_lines),
            "clean": not status_lines,
            "status": status_lines,
        },
        "manifest": file_entry(manifest_path, required=True, category="evidence_manifest"),
        "config": file_entry(config_path, required=True, category="strict_runtime_config"),
        "models": model_entries(config_path),
        "evidence_files": required_entries,
        "local_runtime_evidence": local_entries,
        "boundaries": dict(manifest.get("boundaries") or {}),
        "summary": {
            "required_evidence_count": len(required_entries),
            "missing_required_count": len(missing_required),
            "missing_required": missing_required,
            "local_runtime_evidence_count": len(local_entries),
            "missing_local_runtime_count": len(missing_local),
            "missing_local_runtime": missing_local,
            "ready_for_release": not missing_required and version_consistent,
        },
        "medical_boundary": (
            "平台输出用于荧光/灌注信号候选、骨面复核、边界风险、不确定性、离线三维参考和医生复核辅助；"
            "不提供自动确诊、切除成功率或真实术中导航结论。"
        ),
        "external_validation_needs": [
            "候选造影剂实物合成、光谱、选择性、安全性和组织验证",
            "真实目标域白光/ICG JPEG 或 MP4 与医生像素级金标准",
            "真实设备全倍率/全工作距离标定、下颌仿体与术中导航验证",
        ],
    }


def markdown(payload: dict[str, Any]) -> str:
    versions = payload["project_versions"]
    summary = payload["summary"]
    lines = [
        "# 平台工程证据索引",
        "",
        f"生成时间：{payload['generated_at_utc']}",
        "",
        "## 版本与状态",
        "",
        f"- Manifest 版本：`{versions['manifest']}`",
        f"- Python / 根 Node / 前端：`{versions['python']}` / `{versions['root_node']}` / `{versions['frontend']}`",
        f"- 版本一致：`{versions['consistent']}`",
        f"- 分支：`{payload['git']['branch']}`",
        f"- 生成基线提交：`{payload['git']['commit']}`",
        f"- 最近标签：`{payload['git']['nearest_tag']}`",
        f"- 工作区条目：`{payload['git']['status_entry_count']}`",
        "",
        "## 输入契约",
        "",
        f"- 图像格式：{', '.join(payload['input_contract']['image_formats'])}",
        f"- 视频格式：{', '.join(payload['input_contract']['video_formats'])}",
        f"- 参考分辨率：`{payload['input_contract']['reference_resolution']}`",
        f"- 元数据：{payload['input_contract']['metadata']}",
        "",
        "## 模型清单",
        "",
        "| model_id | family | enabled | runtime_allowed | checkpoint | target_domain | 用途边界 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for model in payload["models"]:
        checkpoint = model.get("checkpoint") or {}
        lines.append(
            "| {model_id} | {family} | {enabled} | {runtime_allowed} | {checkpoint_exists} | "
            "{target_domain} | {use} |".format(
                model_id=model.get("model_id"),
                family=model.get("family"),
                enabled=model.get("enabled"),
                runtime_allowed=model.get("runtime_allowed"),
                checkpoint_exists=checkpoint.get("exists", False),
                target_domain=model.get("target_domain", False),
                use=str(model.get("intended_use") or "-").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 版本化证据",
            "",
            "| 路径 | 存在 | Git | SHA256 |",
            "|---|---:|---:|---|",
        ]
    )
    for item in payload["evidence_files"]:
        lines.append(f"| `{item['path']}` | {item['exists']} | {item['git_tracked']} | `{item.get('sha256') or '-'}` |")
    lines.extend(
        [
            "",
            "## 本地运行证据",
            "",
            "| 路径 | 存在 | SHA256 |",
            "|---|---:|---|",
        ]
    )
    for item in payload["local_runtime_evidence"]:
        lines.append(f"| `{item['path']}` | {item['exists']} | `{item.get('sha256') or '-'}` |")
    lines.extend(["", "## 证据边界", ""])
    lines.extend(f"- `{key}`：{value}" for key, value in payload["boundaries"].items())
    lines.extend(
        [
            "",
            "## 完整性",
            "",
            f"- 必需证据：{summary['required_evidence_count']}，缺失：{summary['missing_required_count']}",
            f"- 本地运行证据：{summary['local_runtime_evidence_count']}，缺失：{summary['missing_local_runtime_count']}",
            f"- 可用于离线发布：`{summary['ready_for_release']}`",
            "",
            "## 外部验证需求",
            "",
            *[f"- {value}" for value in payload["external_validation_needs"]],
            "",
            "## 医学边界",
            "",
            payload["medical_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a versioned platform evidence index.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(ROOT)))
    parser.add_argument("--config", default=None, help="Override the strict config recorded in the manifest.")
    parser.add_argument("--stamp", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = repository_path(args.manifest)
    payload = build_payload(manifest_path, config_override=args.config)
    output_json = repository_path(
        args.output_json or f"research/reports/release/platform_evidence_index_{args.stamp}.json"
    )
    output_md = repository_path(
        args.output_md or f"research/reports/release/platform_evidence_index_{args.stamp}_zh.md"
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(markdown(payload), encoding="utf-8")
    print(output_json)
    print(output_md)
    return 0 if payload["summary"]["ready_for_release"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
