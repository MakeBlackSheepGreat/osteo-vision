from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_candidate_runtime_gate(
    *,
    checkpoint_path: str | Path,
    model_id: str,
    selection_summary_path: str | Path,
    runtime_promotion_sidecar_path: str | Path,
    tiling_smoke_path: str | Path,
    mainline_comparator_path: str | Path,
    runtime_preflight_path: str | Path,
    competition_flow_path: str | Path,
    production_preflight_path: str | Path,
    production_config_path: str | Path,
) -> dict[str, Any]:
    checkpoint = Path(checkpoint_path).resolve()
    selection_path = Path(selection_summary_path).resolve()
    promotion_path = Path(runtime_promotion_sidecar_path).resolve()
    smoke_path = Path(tiling_smoke_path).resolve()
    comparator_path = Path(mainline_comparator_path).resolve()
    preflight_path = Path(runtime_preflight_path).resolve()
    flow_path = Path(competition_flow_path).resolve()
    production_preflight_path = Path(production_preflight_path).resolve()
    production_path = Path(production_config_path).resolve()
    selection = _load_json(selection_path)
    promotion = _load_json(promotion_path)
    smoke = _load_json(smoke_path)
    comparator = _load_json(comparator_path)
    preflight = _load_json(preflight_path)
    flow = _load_json(flow_path)
    production_preflight = _load_json(production_preflight_path)
    production = _load_yaml(production_path)
    checkpoint_sha = _sha256_file(checkpoint)
    recommendation = _mapping(selection.get("recommendation"))
    selected_family = next(
        (
            item
            for item in selection.get("candidate_families") or []
            if isinstance(item, dict) and str(item.get("model_family")) == str(recommendation.get("selected_family"))
        ),
        {},
    )
    selection_gates = _mapping(selected_family.get("gates"))
    smoke_checks = _mapping(smoke.get("checks"))
    smoke_input = _mapping(smoke.get("input"))
    smoke_inference = _mapping(smoke.get("inference"))
    comparator_checks = _mapping(comparator.get("checks"))
    comparator_input = _mapping(comparator.get("input"))
    comparator_inference = _mapping(comparator.get("inference"))
    comparable_protocol = all(
        (
            smoke_input.get("width") == comparator_input.get("width"),
            smoke_input.get("height") == comparator_input.get("height"),
            smoke_inference.get("mode") == comparator_inference.get("mode") == "tiled",
            smoke_inference.get("tile_size") == comparator_inference.get("tile_size"),
            smoke_inference.get("tile_overlap") == comparator_inference.get("tile_overlap"),
            smoke_inference.get("tile_count") == comparator_inference.get("tile_count"),
            smoke_inference.get("tile_batch_size") == comparator_inference.get("tile_batch_size"),
            smoke_inference.get("tta_enabled") == comparator_inference.get("tta_enabled"),
            smoke_inference.get("use_amp") == comparator_inference.get("use_amp"),
            smoke_inference.get("output_profile") == comparator_inference.get("output_profile"),
        )
    )
    verified_models = [item for item in preflight.get("verified_models") or [] if isinstance(item, dict)]
    verified_candidate = next((item for item in verified_models if str(item.get("model_id")) == model_id), {})
    flow_runtime = _mapping(flow.get("runtime"))
    flow_models = _mapping(flow.get("models"))
    flow_video_execution = _mapping(flow_models.get("video_execution"))
    flow_demo_check = _mapping(flow.get("demo_check"))
    flow_model_ids = [str(value) for value in flow_video_execution.get("model_ids") or []]
    flow_analysis_methods = [str(value) for value in flow_video_execution.get("analysis_methods") or []]
    flow_missing_formats = [str(value) for value in flow_demo_check.get("missing_required_formats") or []]
    flow_frame_evidence = _flow_frame_evidence(flow_video_execution, model_id=model_id)
    production_runtime = _mapping(production.get("runtime"))
    production_required_ids = [str(value) for value in production_runtime.get("required_model_ids") or []]
    production_models = [item for item in production_runtime.get("models") or [] if isinstance(item, dict)]
    production_model_ids = [str(item.get("model_id") or "") for item in production_models]
    production_tasks = _mapping(production_runtime.get("tasks"))
    production_segmentation = _mapping(production_tasks.get("segmentation"))
    production_selected_model = str(production_segmentation.get("model_id") or "")

    checks = {
        "checkpoint_exists": checkpoint.is_file(),
        "selection_summary_passed": bool(selection_gates) and all(bool(value) for value in selection_gates.values()),
        "selection_model_matches": str(recommendation.get("selected_model_id")) == model_id,
        "selection_checkpoint_matches": _same_path(recommendation.get("selected_checkpoint"), checkpoint),
        "promotion_checkpoint_sha_matches": str(promotion.get("checkpoint_sha256")) == checkpoint_sha,
        "promotion_model_matches": str(promotion.get("model_id")) == model_id,
        "promotion_runtime_allowed": promotion.get("runtime_allowed") is True,
        "promotion_clinical_claim_blocked": promotion.get("clinical_claim_allowed") is False,
        "tiling_smoke_passed": smoke_checks.get("pass") is True,
        "tiling_smoke_checkpoint_matches": str(_mapping(smoke.get("checkpoint")).get("sha256")) == checkpoint_sha,
        "official_4k_tiled": smoke_input.get("is_official_4k_resolution") is True
        and smoke_inference.get("mode") == "tiled"
        and int(smoke_inference.get("tile_count") or 0) > 1,
        "repeat_runtime_evidence": int(smoke_inference.get("benchmark_runs") or 0) >= 3,
        "mainline_4k_comparator_passed": comparator_checks.get("pass") is True,
        "mainline_4k_comparator_matches_protocol": comparable_protocol,
        "strict_runtime_preflight_passed": preflight.get("passed") is True
        and preflight.get("strict_startup") is True
        and preflight.get("runtime_profile") == "competition_strict",
        "strict_runtime_candidate_verified": str(verified_candidate.get("checkpoint_sha256")) == checkpoint_sha
        and verified_candidate.get("runtime_allowed") is True,
        "competition_flow_passed": flow_demo_check.get("pass") is True,
        "competition_flow_runtime_matches_preflight": flow_runtime.get("config_bound") is True
        and flow_runtime.get("readiness_passed") is True
        and flow_runtime.get("strict_startup") is True
        and flow_runtime.get("runtime_profile") == "competition_strict"
        and str(flow_runtime.get("config_sha256") or "") == str(preflight.get("config_sha256") or ""),
        "competition_flow_candidate_configured": str(flow_models.get("configured_segmentation_model_id") or "")
        == model_id,
        "competition_flow_candidate_exercised": model_id in flow_model_ids
        and "trainable_keyframe_segmenter" in flow_analysis_methods
        and flow_demo_check.get("keyframe_mainline_model_exercised") is True,
        "competition_flow_no_heuristic_fallback": flow_demo_check.get("keyframe_fallback_used") is False
        and "heuristic_hotspot_fallback" not in flow_analysis_methods,
        "competition_flow_probability_map_exported": "probability_map" not in flow_missing_formats
        and "probability_map" in [str(value) for value in flow_demo_check.get("required_formats_present") or []],
        "competition_flow_frame_models_verified": flow_frame_evidence["frame_count"] > 0
        and flow_frame_evidence["all_candidate_model_and_method"],
        "competition_flow_frame_probability_files_verified": flow_frame_evidence["frame_count"] > 0
        and flow_frame_evidence["all_probability_files_exist"],
        "competition_flow_claim_boundary_preserved": flow_demo_check.get("clinical_claim_allowed") is False
        and flow_demo_check.get("non_target_domain_disclosed") is True,
        "production_config_candidate_not_selected": model_id not in production_required_ids
        and model_id not in production_model_ids
        and production_selected_model != model_id,
        "production_strict_runtime_remains_ready": production_preflight.get("passed") is True
        and production_preflight.get("strict_startup") is True
        and production_preflight.get("runtime_profile") == "competition_strict"
        and str(production_preflight.get("config_sha256")) == _sha256_file(production_path),
    }
    checks["pass"] = all(checks.values())
    candidate_e2e_p95 = _number(smoke_inference.get("end_to_end_latency_ms_p95"))
    continuous_playback_risk = candidate_e2e_p95 is None or candidate_e2e_p95 > 1000.0
    comparison = {
        "available": True,
        "strictly_comparable": comparable_protocol,
        "mainline_model_id": comparator.get("model_id"),
        "mainline_evidence": _evidence(comparator_path),
        "mainline_metrics": _runtime_metrics(comparator_inference, comparator_input),
        "candidate_metrics": _runtime_metrics(smoke_inference, smoke_input),
        "candidate_delta_percent": {
            "model_latency_p50": _percent_delta(
                smoke_inference.get("model_latency_ms_p50"), comparator_inference.get("model_latency_ms_p50")
            ),
            "model_latency_p95": _percent_delta(
                smoke_inference.get("model_latency_ms_p95"), comparator_inference.get("model_latency_ms_p95")
            ),
            "end_to_end_latency_p50": _percent_delta(
                smoke_inference.get("end_to_end_latency_ms_p50"),
                comparator_inference.get("end_to_end_latency_ms_p50"),
            ),
            "end_to_end_latency_p95": _percent_delta(
                smoke_inference.get("end_to_end_latency_ms_p95"),
                comparator_inference.get("end_to_end_latency_ms_p95"),
            ),
            "peak_gpu_memory": _percent_delta(
                smoke_inference.get("peak_gpu_memory_mb"), comparator_inference.get("peak_gpu_memory_mb")
            ),
        },
    }
    return {
        "schema_version": "osteo-vision-keyframe-candidate-runtime-gate-v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "candidate": {
            "model_id": model_id,
            "model_family": promotion.get("model_family"),
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": checkpoint_sha,
            "threshold": promotion.get("threshold"),
        },
        "technical_gate_passed": checks["pass"],
        "competition_runtime_selected": False,
        "automatic_replacement_performed": False,
        "checks": checks,
        "runtime_metrics": _runtime_metrics(smoke_inference, smoke_input),
        "mainline_comparison": comparison,
        "competition_flow": {
            "passed": flow_demo_check.get("pass") is True,
            "case_id": flow.get("case_id"),
            "configured_segmentation_model_id": flow_models.get("configured_segmentation_model_id"),
            "executed_model_ids": flow_model_ids,
            "analysis_methods": flow_analysis_methods,
            "fallback_used": flow_demo_check.get("keyframe_fallback_used"),
            "missing_required_formats": flow_missing_formats,
            "runtime_config_sha256": flow_runtime.get("config_sha256"),
            "frame_evidence": flow_frame_evidence,
        },
        "runtime_risks": {
            "continuous_playback_full_evidence_latency": continuous_playback_risk,
            "candidate_end_to_end_p95_ms": candidate_e2e_p95,
            "boundary": (
                "The measured full-evidence 4K end-to-end P95 is unsuitable for per-frame continuous playback "
                "refresh. Keyframe analysis and the separate fast-output live path require independent gates."
            ),
        },
        "gate_policy": smoke.get("gate_policy"),
        "production_config": {
            "path": str(production_path),
            "sha256": _sha256_file(production_path),
            "required_model_ids": production_required_ids,
            "configured_model_ids": production_model_ids,
            "selected_segmentation_model": production_selected_model,
            "candidate_selected": False,
            "preflight_passed_after_gate": production_preflight.get("passed") is True,
        },
        "evidence": {
            "selection_summary": _evidence(selection_path),
            "runtime_promotion_sidecar": _evidence(promotion_path),
            "tiling_smoke": _evidence(smoke_path),
            "mainline_4k_comparator": _evidence(comparator_path),
            "runtime_preflight": _evidence(preflight_path),
            "competition_flow": _evidence(flow_path),
            "competition_flow_video_segmentation_manifest": flow_frame_evidence["manifest_evidence"],
            "production_runtime_preflight_after_gate": _evidence(production_preflight_path),
        },
        "medical_boundary": (
            "The gate covers deterministic platform execution on a synthetic 4K keyframe and public proxy-label "
            "evaluation. Target-domain intraoperative ICG jaw osteomyelitis performance remains unmeasured, and "
            "all candidate regions require physician review."
        ),
    }


def render_report(report: dict[str, Any], *, language: str) -> str:
    candidate = _mapping(report.get("candidate"))
    metrics = _mapping(report.get("runtime_metrics"))
    production = _mapping(report.get("production_config"))
    comparison = _mapping(report.get("mainline_comparison"))
    mainline_metrics = _mapping(comparison.get("mainline_metrics"))
    deltas = _mapping(comparison.get("candidate_delta_percent"))
    risks = _mapping(report.get("runtime_risks"))
    flow = _mapping(report.get("competition_flow"))
    policy = _mapping(report.get("gate_policy"))
    checks = _mapping(report.get("checks"))
    failed = [name for name, passed in checks.items() if name != "pass" and passed is not True]
    if language == "zh":
        return f"""# Residual Attention U-Net 4K 候选运行门控

## 结论

- 技术门控通过：`{report.get('technical_gate_passed')}`
- 候选模型：`{candidate.get('model_id')}`
- 阈值：`{candidate.get('threshold')}`
- 比赛配置已选择候选：`{report.get('competition_runtime_selected')}`
- 自动替换已执行：`{report.get('automatic_replacement_performed')}`
- 失败检查：`{failed}`

## 4K 运行指标

- 输入：`{metrics.get('input_size')}`；切片：`{metrics.get('tile_size')}`，重叠 `{metrics.get('tile_overlap')}`，共 `{metrics.get('tile_count')}` 块。
- 重复运行：`{metrics.get('benchmark_runs')}` 次。
- 模型 P50/P95：`{metrics.get('model_latency_ms_p50')}` / `{metrics.get('model_latency_ms_p95')}` ms。
- 端到端 P50/P95：`{metrics.get('end_to_end_latency_ms_p50')}` / `{metrics.get('end_to_end_latency_ms_p95')}` ms。
- GPU 峰值显存：`{metrics.get('peak_gpu_memory_mb')}` MB。
- 前景比例范围：`{metrics.get('positive_area_fraction_min')}` - `{metrics.get('positive_area_fraction_max')}`。

## 失败门槛

- 必须使用官方 4K 尺寸、CUDA、tiled 模式和确定性重复掩膜。
- 端到端 P95 上限：`{policy.get('max_end_to_end_p95_ms')}` ms；模型 P95 上限：`{policy.get('max_model_p95_ms')}` ms。
- GPU 峰值显存上限：`{policy.get('max_peak_gpu_memory_mb')}` MB。
- 前景比例范围：`{policy.get('min_positive_fraction')}` - `{policy.get('max_positive_fraction')}`。

## 同协议主线对比

- 可比：`{comparison.get('strictly_comparable')}`；主线模型：`{comparison.get('mainline_model_id')}`。
- 主线模型 P50/P95：`{mainline_metrics.get('model_latency_ms_p50')}` / `{mainline_metrics.get('model_latency_ms_p95')}` ms。
- 主线端到端 P50/P95：`{mainline_metrics.get('end_to_end_latency_ms_p50')}` / `{mainline_metrics.get('end_to_end_latency_ms_p95')}` ms。
- 主线 GPU 峰值显存：`{mainline_metrics.get('peak_gpu_memory_mb')}` MB。
- 候选相对变化：模型 P50 `{deltas.get('model_latency_p50')}`%，模型 P95 `{deltas.get('model_latency_p95')}`%，端到端 P50 `{deltas.get('end_to_end_latency_p50')}`%，端到端 P95 `{deltas.get('end_to_end_latency_p95')}`%，显存 `{deltas.get('peak_gpu_memory')}`%。
- 延迟变化为负数时表示候选耗时降低；显存变化为正数时表示候选占用增加。

## 运行风险

- 连续播放全证据延迟风险：`{risks.get('continuous_playback_full_evidence_latency')}`。
- 候选端到端 P95 为 `{risks.get('candidate_end_to_end_p95_ms')}` ms；该结果只支持离线关键帧全证据处理，无法支持逐帧实时播放刷新。

## 完整比赛流

- 完整流程通过：`{flow.get('passed')}`；病例：`{flow.get('case_id')}`。
- 配置模型：`{flow.get('configured_segmentation_model_id')}`；实际执行模型：`{flow.get('executed_model_ids')}`。
- 分析方法：`{flow.get('analysis_methods')}`；启发式回退：`{flow.get('fallback_used')}`。
- 缺失必需格式：`{flow.get('missing_required_formats')}`。
- 逐帧模型与方法核验：`{_mapping(flow.get('frame_evidence')).get('all_candidate_model_and_method')}`；逐帧概率图文件核验：`{_mapping(flow.get('frame_evidence')).get('all_probability_files_exist')}`。

## 配置边界

- 当前比赛分割模型：`{production.get('selected_segmentation_model')}`。
- 当前比赛必需模型：`{production.get('required_model_ids')}`。
- 候选模型仍未写入比赛配置；本轮仅生成独立候选门控配置与运行证据。
- 门控完成后主线严格预检：`{production.get('preflight_passed_after_gate')}`。

## 医学边界

本门控覆盖合成 4K 关键帧的确定性平台运行和公开代理标签评估。真实术中 ICG 颌骨骨髓炎目标域性能仍未测量，所有候选区域均需医生复核。
"""
    return f"""# Residual Attention U-Net 4K Candidate Runtime Gate

## Verdict

- Technical gate passed: `{report.get('technical_gate_passed')}`
- Candidate model: `{candidate.get('model_id')}`
- Threshold: `{candidate.get('threshold')}`
- Candidate selected by competition config: `{report.get('competition_runtime_selected')}`
- Automatic replacement performed: `{report.get('automatic_replacement_performed')}`
- Failed checks: `{failed}`

## 4K Runtime

- Input: `{metrics.get('input_size')}`; tile `{metrics.get('tile_size')}`, overlap `{metrics.get('tile_overlap')}`, `{metrics.get('tile_count')}` tiles.
- Repeated runs: `{metrics.get('benchmark_runs')}`.
- Model P50/P95: `{metrics.get('model_latency_ms_p50')}` / `{metrics.get('model_latency_ms_p95')}` ms.
- End-to-end P50/P95: `{metrics.get('end_to_end_latency_ms_p50')}` / `{metrics.get('end_to_end_latency_ms_p95')}` ms.
- Peak GPU memory: `{metrics.get('peak_gpu_memory_mb')}` MB.
- Positive-area fraction range: `{metrics.get('positive_area_fraction_min')}` - `{metrics.get('positive_area_fraction_max')}`.

## Failure Thresholds

- Official 4K dimensions, CUDA, tiled execution, and deterministic repeated masks are required.
- End-to-end P95 limit: `{policy.get('max_end_to_end_p95_ms')}` ms; model P95 limit: `{policy.get('max_model_p95_ms')}` ms.
- Peak GPU memory limit: `{policy.get('max_peak_gpu_memory_mb')}` MB.
- Positive-area fraction range: `{policy.get('min_positive_fraction')}` - `{policy.get('max_positive_fraction')}`.

## Same-Protocol Mainline Comparison

- Comparable: `{comparison.get('strictly_comparable')}`; mainline model: `{comparison.get('mainline_model_id')}`.
- Mainline model P50/P95: `{mainline_metrics.get('model_latency_ms_p50')}` / `{mainline_metrics.get('model_latency_ms_p95')}` ms.
- Mainline end-to-end P50/P95: `{mainline_metrics.get('end_to_end_latency_ms_p50')}` / `{mainline_metrics.get('end_to_end_latency_ms_p95')}` ms.
- Mainline peak GPU memory: `{mainline_metrics.get('peak_gpu_memory_mb')}` MB.
- Candidate deltas: model P50 `{deltas.get('model_latency_p50')}`%, model P95 `{deltas.get('model_latency_p95')}`%, end-to-end P50 `{deltas.get('end_to_end_latency_p50')}`%, end-to-end P95 `{deltas.get('end_to_end_latency_p95')}`%, GPU memory `{deltas.get('peak_gpu_memory')}`%.
- Negative latency deltas indicate lower candidate latency; positive memory deltas indicate higher candidate usage.

## Runtime Risk

- Continuous-playback full-evidence latency risk: `{risks.get('continuous_playback_full_evidence_latency')}`.
- Candidate end-to-end P95 is `{risks.get('candidate_end_to_end_p95_ms')}` ms. This supports offline full-evidence keyframes and cannot sustain per-frame playback refresh.

## Full Competition Flow

- Full flow passed: `{flow.get('passed')}`; case: `{flow.get('case_id')}`.
- Configured model: `{flow.get('configured_segmentation_model_id')}`; executed models: `{flow.get('executed_model_ids')}`.
- Analysis methods: `{flow.get('analysis_methods')}`; heuristic fallback: `{flow.get('fallback_used')}`.
- Missing required formats: `{flow.get('missing_required_formats')}`.
- Per-frame model and method verified: `{_mapping(flow.get('frame_evidence')).get('all_candidate_model_and_method')}`; per-frame probability files verified: `{_mapping(flow.get('frame_evidence')).get('all_probability_files_exist')}`.

## Configuration Boundary

- Current competition segmentation model: `{production.get('selected_segmentation_model')}`.
- Current competition required models: `{production.get('required_model_ids')}`.
- The candidate remains outside the competition config; this run produced isolated candidate-gate evidence.
- Mainline strict preflight after the gate: `{production.get('preflight_passed_after_gate')}`.

## Medical Boundary

{report.get('medical_boundary')}
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an auditable strict 4K runtime gate for a keyframe candidate.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--selection-summary", required=True)
    parser.add_argument("--runtime-promotion-sidecar", required=True)
    parser.add_argument("--tiling-smoke", required=True)
    parser.add_argument("--mainline-comparator", required=True)
    parser.add_argument("--runtime-preflight", required=True)
    parser.add_argument("--competition-flow", required=True)
    parser.add_argument("--production-preflight", required=True)
    parser.add_argument("--production-config", default="configs/inference/osteo_vision_competition_strict.yml")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--report-zh", required=True)
    parser.add_argument("--report-en", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_candidate_runtime_gate(
        checkpoint_path=args.checkpoint,
        model_id=args.model_id,
        selection_summary_path=args.selection_summary,
        runtime_promotion_sidecar_path=args.runtime_promotion_sidecar,
        tiling_smoke_path=args.tiling_smoke,
        mainline_comparator_path=args.mainline_comparator,
        runtime_preflight_path=args.runtime_preflight,
        competition_flow_path=args.competition_flow,
        production_preflight_path=args.production_preflight,
        production_config_path=args.production_config,
    )
    output = Path(args.output_json).resolve()
    report_zh = Path(args.report_zh).resolve()
    report_en = Path(args.report_en).resolve()
    for path in (output, report_zh, report_en):
        path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_zh.write_text(render_report(report, language="zh"), encoding="utf-8")
    report_en.write_text(render_report(report, language="en"), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("technical_gate_passed") is True else 1


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _runtime_metrics(inference: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_size": [input_payload.get("width"), input_payload.get("height")],
        "tile_size": inference.get("tile_size"),
        "tile_overlap": inference.get("tile_overlap"),
        "tile_count": inference.get("tile_count"),
        "tile_batch_size": inference.get("tile_batch_size"),
        "benchmark_runs": inference.get("benchmark_runs"),
        "model_latency_ms_p50": inference.get("model_latency_ms_p50"),
        "model_latency_ms_p95": inference.get("model_latency_ms_p95"),
        "end_to_end_latency_ms_p50": inference.get("end_to_end_latency_ms_p50"),
        "end_to_end_latency_ms_p95": inference.get("end_to_end_latency_ms_p95"),
        "peak_gpu_memory_mb": inference.get("peak_gpu_memory_mb"),
        "positive_area_fraction_min": inference.get("positive_area_fraction_min"),
        "positive_area_fraction_max": inference.get("positive_area_fraction_max"),
    }


def _percent_delta(candidate: Any, baseline: Any) -> float | None:
    candidate_value = _number(candidate)
    baseline_value = _number(baseline)
    if candidate_value is None or baseline_value is None or baseline_value == 0.0:
        return None
    return round((candidate_value - baseline_value) / baseline_value * 100.0, 3)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_path(value: Any, expected: Path) -> bool:
    return bool(value) and Path(str(value)).resolve() == expected


def _evidence(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": _sha256_file(path)}


def _flow_frame_evidence(video_execution: dict[str, Any], *, model_id: str) -> dict[str, Any]:
    raw_manifest_path = str(video_execution.get("manifest_path") or "").strip()
    manifest_path = _resolve_artifact_path(raw_manifest_path)
    manifest_exists = manifest_path is not None and manifest_path.is_file()
    manifest = _load_json(manifest_path) if manifest_exists and manifest_path is not None else {}
    frames = [item for item in manifest.get("frames") or [] if isinstance(item, dict)]
    frame_checks: list[dict[str, Any]] = []
    for frame in frames:
        segmentation = _mapping(frame.get("segmentation_result"))
        probability_path = _resolve_artifact_path(str(segmentation.get("probability_path") or ""))
        probability_exists = False
        probability_size_bytes = 0
        if probability_path is not None and probability_path.is_file():
            probability_exists = True
            probability_size_bytes = probability_path.stat().st_size
        frame_checks.append(
            {
                "frame_order": frame.get("frame_order"),
                "frame_index": frame.get("frame_index"),
                "model_id": segmentation.get("model_id"),
                "analysis_method": segmentation.get("analysis_method"),
                "candidate_model_and_method": str(segmentation.get("model_id") or "") == model_id
                and segmentation.get("analysis_method") == "trainable_keyframe_segmenter",
                "probability_path": str(probability_path) if probability_path is not None else None,
                "probability_exists": probability_exists,
                "probability_size_bytes": probability_size_bytes,
            }
        )
    return {
        "manifest_evidence": (
            {"path": str(manifest_path), "exists": True, "sha256": _sha256_file(manifest_path)}
            if manifest_exists and manifest_path is not None
            else {"path": str(manifest_path) if manifest_path is not None else None, "exists": False, "sha256": None}
        ),
        "frame_count": len(frame_checks),
        "all_candidate_model_and_method": bool(frame_checks)
        and all(item["candidate_model_and_method"] for item in frame_checks),
        "all_probability_files_exist": bool(frame_checks)
        and all(item["probability_exists"] and item["probability_size_bytes"] > 0 for item in frame_checks),
        "frames": frame_checks,
    }


def _resolve_artifact_path(value: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
