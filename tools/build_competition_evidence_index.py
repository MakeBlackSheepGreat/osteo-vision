from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

OFFICIAL_SOURCES = [
    ROOT / "HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf",
    ROOT / "research/literature/inventory/official/competition_official_technical_document_20260527.pdf",
]

EVIDENCE_FILES = [
    "research/reports/planning/official_competition_problem_alignment_20260704_zh.md",
    "research/reports/modeling/r01_r08_remediation_20260710_zh.md",
    "research/reports/modeling/keyframe_convnext2d_proxy_segmenter_20260710_grouped_zh.md",
    "research/reports/modeling/keyframe_threshold_eval_20260710_grouped_test/keyframe_threshold_eval.json",
    "research/reports/modeling/dual_channel_ablation_20260710_dual_channel.json",
    "research/reports/modeling/video_signal_multimask_v2_training_20260710_multimask_v2_grouped.json",
    "research/reports/modeling/public_video_4k_validation_20260711_zh.md",
    "research/reports/modeling/public_video_dynamic_quantification_20260711_zh.md",
    "research/reports/modeling/layered_dataset_registry_quality_20260711_zh.md",
    "research/reports/modeling/video_active_review_queue_20260711_zh.md",
    "research/reports/modeling/d047_pmc_jaw_fluorescence_dataset_20260711_zh.md",
    "research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/pmc_jaw_fluorescence_figure_manifest.json",
    "research/reports/modeling/d048_open_clinical_bone_fluorescence_dataset_20260711_zh.md",
    "research/reports/modeling/live_stream_and_static_review_20260711_zh.md",
    "research/reports/modeling/static_panel_crop_suggestions_20260711_zh.md",
    "research/datasets/public-candidates/d047_d048_static_figure_seed_manifest.json",
    "research/datasets/public-candidates/d047_d048_static_crop_suggestion_manifest.json",
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/mp4_keyframe_segmentation_proxy_20260710_grouped/keyframe_segmentation_proxy_manifest.csv",
    "research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/open_clinical_bone_fluorescence_manifest.json",
    "backend/src/services/active_review_queue.py",
    "tools/build_keyframe_training_manifest_from_review.py",
    "src/datasets/training_admission.py",
    "src/io/live_stream.py",
    "tests/smoke/test_live_stream_analysis.py",
    "backend/src/services/static_dataset_review.py",
    "src/datasets/static_panel_detection.py",
    "tools/build_static_panel_crop_suggestions.py",
    "tools/generate_static_review_seeds.py",
    "frontend/src/components/StaticCropEditor.vue",
    "frontend/src/pages/DatasetReviewPage.vue",
    "artifacts/data_review/static_seed_batch_20260711.json",
    "artifacts/platform_smoke/dataset_crop_review_ui_20260711.png",
    "artifacts/data_review/d047_d048_52_crop_suggestions_contact_sheet.jpg",
    "artifacts/platform_smoke/dataset_crop_suggestions_ui_20260711.png",
    "research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.md",
    "research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.docx",
    "research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.pdf",
    "research/reports/submission/internal_verification_20260711_zh.md",
]

DATA_BOUNDARIES = {
    "literature": "候选造影剂、荧光机制、定量和标准化依据；不包含本项目原创实验结果。",
    "proxy_engineering": "公开异域视频、代理标注、公开 CBCT 和压力样本；用于工程链路与相对比较。",
    "physician_review": "当前目标域医生关键帧和像素级金标准暂缺。",
    "enterprise_device": "当前企业原始双通道样片、滤光片曲线和目标硬件实机证据暂缺。",
}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "exists": exists,
        "type": "directory" if path.is_dir() else "file",
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path),
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


def model_entries(config_path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    models = payload.get("runtime", {}).get("models", [])
    entries: list[dict[str, Any]] = []
    for mapping in models:
        checkpoint_value = mapping.get("checkpoint_path")
        checkpoint = ROOT / str(checkpoint_value) if checkpoint_value else None
        extra = dict(mapping.get("extra") or {})
        runtime_allowed = bool(extra.get("runtime_allowed", True))
        enabled = bool(mapping.get("enabled", True))
        checkpoint_exists = bool(checkpoint and checkpoint.is_file())
        checkpoint_ready = (
            checkpoint_exists
            or mapping.get("family") in {"fluorescence_hotspot_segmenter", "fixture"}
            or bool(extra.get("prompt_fallback_enabled"))
        )
        entries.append(
            {
                "model_id": mapping.get("model_id"),
                "family": mapping.get("family"),
                "enabled": enabled,
                "runtime_allowed": runtime_allowed,
                "checkpoint": file_entry(checkpoint) if checkpoint else None,
                "checkpoint_ready_for_warmup": checkpoint_ready,
                "runtime_eligible_by_static_config": enabled and runtime_allowed and checkpoint_ready,
                "intended_use": mapping.get("intended_use"),
                "clinical_claim_allowed": bool(mapping.get("clinical_claim_allowed", False)),
                "input_domain": extra.get("input_domain"),
                "target_domain": extra.get("target_domain"),
                "review_boundary": extra.get("review_boundary"),
                "threshold": extra.get("threshold") or extra.get("head_thresholds"),
            }
        )
    return entries


def build_payload(config_path: Path) -> dict[str, Any]:
    status_lines = [line for line in git_value("status", "--short").splitlines() if line]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "official_requirements": {
            "competition_id": "HT-202604",
            "core_items": [
                "新型荧光造影剂设计",
                "白光/荧光多模态融合与处理",
                "AI 辅助显微成像判读",
            ],
            "scoring": {
                "innovation": 20,
                "scientific_rationale": 20,
                "feasibility": 30,
                "application_value": 20,
                "completeness": 10,
            },
            "device_input_boundary": {
                "resolution": "3840x2160",
                "storage": "USB3.0",
                "image_format": "JPEG",
                "video_format": "MP4",
            },
        },
        "official_sources": [
            {**file_entry(path), "git_tracked": False, "distribution": "local_only"} for path in OFFICIAL_SOURCES
        ],
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "status_entry_count": len(status_lines),
            "clean": not status_lines,
            "status": status_lines,
        },
        "config": file_entry(config_path),
        "models": model_entries(config_path),
        "evidence_files": [file_entry(ROOT / value) for value in EVIDENCE_FILES],
        "evidence_tiers": DATA_BOUNDARIES,
        "medical_boundary": (
            "平台输出用于荧光/灌注信号候选区、骨面待复核门控、边界风险、"
            "不确定性和医生复核辅助，不提供自动确诊或疾病终判。"
        ),
        "external_dependencies": [
            "候选造影剂实物合成、光谱、选择性、安全性和组织仿体验证",
            "真实目标域白光/NIR JPEG 或 MP4 与医生金标准",
            "企业原始双通道、滤光片曲线和目标硬件实机验证",
        ],
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 参赛工程证据索引",
        "",
        f"生成时间：{payload['generated_at_utc']}",
        "",
        "## 官方要求",
        "",
        "- 赛题编号：HT-202604",
        "- 核心内容：新型荧光造影剂设计、白光/荧光多模态融合与处理、AI 辅助显微成像判读。",
        "- 设备边界：3840×2160、USB3.0、JPEG、MP4。",
        "",
        "## Git 状态",
        "",
        f"- 分支：`{payload['git']['branch']}`",
        f"- 提交：`{payload['git']['commit']}`",
        f"- 工作区条目：{payload['git']['status_entry_count']}",
        "",
        "## 模型清单",
        "",
        "| model_id | family | enabled | runtime_allowed | checkpoint | SHA256 | 用途边界 |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for model in payload["models"]:
        checkpoint = model.get("checkpoint") or {}
        digest = checkpoint.get("sha256") or "-"
        lines.append(
            "| {model_id} | {family} | {enabled} | {runtime_allowed} | {checkpoint_exists} | `{digest}` | {use} |".format(
                model_id=model.get("model_id"),
                family=model.get("family"),
                enabled=model.get("enabled"),
                runtime_allowed=model.get("runtime_allowed"),
                checkpoint_exists=checkpoint.get("exists", False),
                digest=digest,
                use=str(model.get("intended_use") or "-").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 关键证据文件",
            "",
            "| 路径 | 存在 | SHA256 |",
            "|---|---:|---|",
        ]
    )
    for item in payload["evidence_files"]:
        lines.append(f"| `{item['path']}` | {item['exists']} | `{item.get('sha256') or '-'}` |")
    lines.extend(
        [
            "",
            "## 证据分层",
            "",
            *[f"- `{key}`：{value}" for key, value in payload["evidence_tiers"].items()],
            "",
            "## 外部依赖",
            "",
            *[f"- {value}" for value in payload["external_dependencies"]],
            "",
            "## 医学边界",
            "",
            payload["medical_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    parser.add_argument(
        "--output-json",
        default="research/reports/submission/competition_evidence_index_20260711.json",
    )
    parser.add_argument(
        "--output-md",
        default="research/reports/submission/competition_evidence_index_20260711_zh.md",
    )
    args = parser.parse_args()

    config_path = (ROOT / args.config).resolve()
    payload = build_payload(config_path)
    output_json = (ROOT / args.output_json).resolve()
    output_md = (ROOT / args.output_md).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(markdown(payload), encoding="utf-8")
    print(output_json)
    print(output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
