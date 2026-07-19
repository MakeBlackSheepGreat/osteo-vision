"""Run a proxy official-device 4K JPEG/MP4 smoke and write timing evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tracemalloc
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

import cv2
import numpy as np
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OFFICIAL_WIDTH = 3840
OFFICIAL_HEIGHT = 2160

T = TypeVar("T")


def main() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    args = parse_args()
    output_dir = (
        Path(args.output_dir) if args.output_dir else ROOT / "artifacts" / "platform_smoke" / f"{timestamp()}_4k"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OSTEO_ARTIFACT_ROOT"] = str(output_dir / "artifacts")
    os.environ["OSTEO_CASE_STORE_PATH"] = str(output_dir / "cases.sqlite")

    timings: list[dict[str, Any]] = []

    from backend.src.api.app import create_app

    client = TestClient(create_app())
    input_dir = output_dir / "input"

    white_path = timed(
        "generate_official_4k_white_jpeg",
        lambda: create_official_jpeg(input_dir / "official_white_4k.jpg", channel="white"),
        timings,
    )
    fluor_path = timed(
        "generate_official_4k_icg_jpeg",
        lambda: create_official_jpeg(input_dir / "official_icg_4k.jpg", channel="fluorescence"),
        timings,
    )
    video_path = timed(
        "generate_official_4k_mp4",
        lambda: create_official_video(input_dir / "official_4k_proxy.mp4", frames=args.frames, fps=args.fps),
        timings,
    )

    case = timed(
        "create_case",
        lambda: checked_json(client.post("/cases", json={"title": "official 4K pressure smoke"})),
        timings,
    )
    case_id = str(case["case_id"])
    white_upload = timed(
        "upload_official_4k_white_jpeg",
        lambda: upload_fixture(client, white_path, white_path.name, "image/jpeg"),
        timings,
    )
    fluor_upload = timed(
        "upload_official_4k_icg_jpeg",
        lambda: upload_fixture(client, fluor_path, fluor_path.name, "image/jpeg"),
        timings,
    )
    video_upload = timed(
        "upload_official_4k_mp4",
        lambda: upload_fixture(client, video_path, video_path.name, "video/mp4"),
        timings,
    )
    upload_job = timed(
        "read_upload_keyframe_job",
        lambda: checked_json(client.get(f"/uploads/jobs/{video_upload['keyframe_job_id']}")),
        timings,
    )
    timed(
        "attach_official_4k_jpeg_inputs",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/inputs",
                json=[
                    {"channel": "white_light", "path": white_upload["path"], "mime_type": "image/jpeg"},
                    {"channel": "fluorescence", "path": fluor_upload["path"], "mime_type": "image/jpeg"},
                ],
            )
        ),
        timings,
    )
    fusion_case = timed(
        "run_official_4k_jpeg_fusion",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/analysis-runs",
                json={
                    "selected_input_ids": [],
                    "parameters": {"threshold": args.threshold, "colormap": "green", "alpha": 0.45},
                    "roi_hints": [],
                },
            )
        ),
        timings,
    )
    timed(
        "attach_official_4k_mp4_input",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/inputs",
                json=[{"channel": "video", "path": video_upload["path"], "mime_type": "video/mp4"}],
            )
        ),
        timings,
    )
    video_job = timed(
        "run_official_4k_mp4_keyframe_analysis",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/analysis-jobs",
                json={
                    "selected_input_ids": [],
                    "parameters": {
                        "mode": "video_file",
                        "keyframe_count": args.keyframes,
                        "keyframe_timestamps_sec": requested_timestamps(args.keyframes, args.fps, args.frames),
                        "hotspot_threshold": args.threshold,
                    },
                    "roi_hints": [],
                },
            )
        ),
        timings,
    )
    analysis_job = timed(
        "read_official_4k_mp4_analysis_job",
        lambda: checked_json(client.get(f"/analysis-jobs/{video_job['job_id']}")),
        timings,
    )
    final_case = timed("load_final_case", lambda: checked_json(client.get(f"/cases/{case_id}")), timings)
    export_payload = timed(
        "export_official_4k_case_bundle",
        lambda: checked_json(
            client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})
        ),
        timings,
    )

    fusion_run = fusion_case["analysis_runs"][-1]
    video_run = final_case["analysis_runs"][-1]
    summary = {
        "schema_version": "osteo-vision-official-4k-pressure-smoke-v1",
        "case_id": case_id,
        "output_dir": str(output_dir),
        "generated_inputs": {
            "white_jpeg": file_record(white_path),
            "fluorescence_jpeg": file_record(fluor_path),
            "video_mp4": file_record(video_path),
            "video_frames": args.frames,
            "video_fps": args.fps,
        },
        "official_profile": {
            "white": profile_record(white_upload),
            "fluorescence": profile_record(fluor_upload),
            "video": profile_record(video_upload),
        },
        "upload_job": trim_job(upload_job),
        "analysis_job": trim_job(analysis_job),
        "fusion_run": {
            "run_id": fusion_run.get("run_id"),
            "status": fusion_run.get("status"),
            "overlay_path": fusion_run.get("fused_outputs", {}).get("outputs", {}).get("overlay_path"),
            "positive_area_fraction": fusion_run.get("quantitative_summary", {}).get("positive_area_fraction"),
        },
        "video_run": {
            "run_id": video_run.get("run_id"),
            "status": video_run.get("status"),
            "keyframes_extracted": video_run.get("quantitative_summary", {}).get("keyframes_extracted"),
            "hotspot_candidate_count": video_run.get("quantitative_summary", {}).get("hotspot_candidate_count"),
            "timeline_manifest_path": video_run.get("fused_outputs", {}).get("timeline_manifest_path"),
            "frame_details_manifest_path": video_run.get("fused_outputs", {}).get("frame_details_manifest_path"),
        },
        "case_artifact_count": len(final_case.get("artifacts", [])),
        "export": {
            "bundle_path": export_payload.get("bundle_path"),
            "bundle_exists": Path(str(export_payload.get("bundle_path", ""))).exists(),
            "summary": export_payload.get("summary", {}),
        },
        "timings": timings,
        "memory_final": memory_snapshot(),
        "interpretation": {
            "domain": "proxy official-resolution engineering smoke",
            "not_clinical_performance": True,
            "not_real_intraoperative_icg_jaw_osteomyelitis_video": True,
        },
        "pass": pressure_passed(white_upload, fluor_upload, video_upload, upload_job, analysis_job, export_payload),
    }
    summary_path = output_dir / "official_4k_pressure_smoke_summary.json"
    report_path = output_dir / "official_4k_pressure_smoke_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="", help="Directory for smoke evidence artifacts.")
    parser.add_argument("--frames", type=int, default=12, help="Synthetic 4K MP4 frame count.")
    parser.add_argument("--fps", type=float, default=6.0, help="Synthetic 4K MP4 FPS.")
    parser.add_argument("--keyframes", type=int, default=3, help="Keyframes requested for MP4 analysis.")
    parser.add_argument("--threshold", type=float, default=0.6, help="Hotspot/fusion threshold.")
    return parser.parse_args()


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def timed(name: str, func: Callable[[], T], timings: list[dict[str, Any]]) -> T:
    start_memory = memory_snapshot()
    started = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - started
    end_memory = memory_snapshot()
    timings.append(
        {
            "name": name,
            "elapsed_sec": round(elapsed, 4),
            "rss_start_mb": start_memory.get("rss_mb"),
            "rss_end_mb": end_memory.get("rss_mb"),
            "rss_delta_mb": memory_delta(start_memory, end_memory),
            "heap_start_mb": start_memory.get("heap_current_mb"),
            "heap_end_mb": end_memory.get("heap_current_mb"),
            "heap_delta_mb": memory_delta(start_memory, end_memory, key="heap_current_mb"),
        }
    )
    return result


def memory_snapshot() -> dict[str, Any]:
    try:
        import psutil

        process = psutil.Process(os.getpid())
        info = process.memory_info()
        return {
            "rss_mb": round(info.rss / (1024 * 1024), 3),
            "vms_mb": round(info.vms / (1024 * 1024), 3),
            "percent": round(process.memory_percent(), 4),
        }
    except Exception as exc:
        current, peak = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)
        return {
            "rss_mb": None,
            "vms_mb": None,
            "percent": None,
            "heap_current_mb": round(current / (1024 * 1024), 3),
            "heap_peak_mb": round(peak / (1024 * 1024), 3),
            "error": str(exc),
        }


def memory_delta(start_memory: dict[str, Any], end_memory: dict[str, Any], *, key: str = "rss_mb") -> float | None:
    start = start_memory.get(key)
    end = end_memory.get(key)
    if not isinstance(start, int | float) or not isinstance(end, int | float):
        return None
    return round(float(end) - float(start), 3)


def create_official_jpeg(path: Path, *, channel: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.linspace(0, 1, OFFICIAL_WIDTH, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, OFFICIAL_HEIGHT, dtype=np.float32)[:, None]
    if channel == "white":
        blue = np.broadcast_to(80 + 45 * x + 16 * y, (OFFICIAL_HEIGHT, OFFICIAL_WIDTH))
        green = np.broadcast_to(92 + 38 * y, (OFFICIAL_HEIGHT, OFFICIAL_WIDTH))
        red = np.broadcast_to(122 + 38 * (1 - x) + 12 * y, (OFFICIAL_HEIGHT, OFFICIAL_WIDTH))
        image = np.dstack([blue, green, red]).astype(np.uint8)
        cv2.putText(
            image, "official 4K white-light proxy", (140, 220), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (235, 235, 235), 8
        )
    else:
        image = np.zeros((OFFICIAL_HEIGHT, OFFICIAL_WIDTH, 3), dtype=np.uint8)
        image[:, :, 1] = (24 + 42 * y).astype(np.uint8)
        cv2.circle(image, (OFFICIAL_WIDTH // 2, OFFICIAL_HEIGHT // 2), 260, (0, 255, 0), -1)
        cv2.circle(image, (OFFICIAL_WIDTH // 2 + 620, OFFICIAL_HEIGHT // 2 - 260), 170, (0, 210, 0), -1)
        cv2.putText(image, "ICG proxy hotspot", (140, 220), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 225, 0), 8)
    cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return path


def create_official_video(path: Path, *, frames: int, fps: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, frames)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (OFFICIAL_WIDTH, OFFICIAL_HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("Could not create official 4K proxy MP4 with OpenCV VideoWriter.")
    base_x = np.linspace(0, 1, OFFICIAL_WIDTH, dtype=np.float32)[None, :]
    base_y = np.linspace(0, 1, OFFICIAL_HEIGHT, dtype=np.float32)[:, None]
    for index in range(frame_count):
        frame = np.zeros((OFFICIAL_HEIGHT, OFFICIAL_WIDTH, 3), dtype=np.uint8)
        frame[:, :, 0] = (32 + 26 * base_x).astype(np.uint8)
        frame[:, :, 1] = (32 + 24 * base_y).astype(np.uint8)
        frame[:, :, 2] = (42 + 20 * (1 - base_x)).astype(np.uint8)
        center_x = int(520 + index * (OFFICIAL_WIDTH - 1040) / max(1, frame_count - 1))
        center_y = int(OFFICIAL_HEIGHT * (0.46 + 0.08 * np.sin(index / max(1, frame_count - 1) * np.pi)))
        cv2.circle(frame, (center_x, center_y), 210, (0, 255, 0), -1)
        cv2.rectangle(frame, (OFFICIAL_WIDTH - 780, 280), (OFFICIAL_WIDTH - 260, 620), (0, 175, 0), -1)
        cv2.putText(
            frame, f"4K MP4 proxy frame {index:02d}", (140, 210), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (230, 245, 255), 8
        )
        writer.write(frame)
    writer.release()
    return path


def requested_timestamps(keyframes: int, fps: float, frames: int) -> list[float]:
    count = max(1, min(keyframes, frames))
    if count == 1:
        return [0.0]
    duration = max(0.0, (frames - 1) / fps) if fps > 0 else float(frames - 1)
    return [round(index * duration / (count - 1), 3) for index in range(count)]


def upload_fixture(client: TestClient, path: Path, filename: str, content_type: str) -> dict[str, Any]:
    response = client.post(
        "/uploads/raw",
        content=path.read_bytes(),
        headers={"content-type": content_type, "x-filename": filename},
    )
    return checked_json(response)


def checked_json(response: Any) -> dict[str, Any]:
    response.raise_for_status()
    return response.json()


def profile_record(upload: dict[str, Any]) -> dict[str, Any]:
    metadata = upload.get("metadata") if isinstance(upload.get("metadata"), dict) else {}
    profile = metadata.get("official_input_profile") if isinstance(metadata.get("official_input_profile"), dict) else {}
    return {
        "input_type": upload.get("input_type"),
        "status": profile.get("status"),
        "observed_resolution": profile.get("observed_resolution"),
        "target_resolution": profile.get("target_resolution"),
        "format_match": profile.get("format_match", profile.get("container_match")),
        "resolution_match": profile.get("resolution_match"),
        "warnings": [warning.get("code") for warning in upload.get("warnings", []) if isinstance(warning, dict)],
    }


def file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else None}


def trim_job(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    return {
        "job_id": payload.get("job_id"),
        "kind": payload.get("kind"),
        "status": payload.get("status"),
        "error": payload.get("error"),
        "progress": payload.get("progress"),
        "keyframes": len(result.get("keyframes") or []),
        "run_id": result.get("run_id"),
        "run_status": result.get("run_status"),
    }


def pressure_passed(
    white_upload: dict[str, Any],
    fluor_upload: dict[str, Any],
    video_upload: dict[str, Any],
    upload_job: dict[str, Any],
    analysis_job: dict[str, Any],
    export_payload: dict[str, Any],
) -> bool:
    records = [profile_record(white_upload), profile_record(fluor_upload), profile_record(video_upload)]
    return all(record.get("resolution_match") is True for record in records) and all(
        [
            upload_job.get("status") == "completed",
            analysis_job.get("status") == "completed",
            Path(str(export_payload.get("bundle_path", ""))).exists(),
        ]
    )


def render_markdown(summary: dict[str, Any]) -> str:
    timings = "\n".join(
        f"| {item['name']} | {item['elapsed_sec']} | {item.get('rss_start_mb')} | {item.get('rss_end_mb')} | {item.get('rss_delta_mb')} | {item.get('heap_start_mb')} | {item.get('heap_end_mb')} | {item.get('heap_delta_mb')} |"
        for item in summary.get("timings", [])
    )
    profile_rows = "\n".join(
        f"| {name} | {record.get('status')} | {record.get('observed_resolution')} | {record.get('format_match')} | {record.get('resolution_match')} | {', '.join(record.get('warnings') or []) or '无'} |"
        for name, record in summary.get("official_profile", {}).items()
    )
    return f"""# 官方 4K MP4/JPEG 代理压力验证

日期：{timestamp()}

本验证使用合成 3840x2160 JPEG 与 MP4，只用于官方设备输入规格、上传、抽帧、分析和导出链路压力验证；不代表真实术中 ICG 颌骨骨髓炎数据，也不代表临床模型性能。

## 结论

- 验证通过：`{summary.get('pass')}`
- 病例：`{summary.get('case_id')}`
- 输出目录：`{summary.get('output_dir')}`
- 证据包：`{summary.get('export', {}).get('bundle_path')}`
- timeline manifest：`{summary.get('video_run', {}).get('timeline_manifest_path')}`

## 官方规格检查

| 输入 | 状态 | 观测分辨率 | 格式/容器匹配 | 分辨率匹配 | 警告 |
|---|---|---:|---:|---:|---|
{profile_rows}

## 链路摘要

- JPEG 融合 run：`{summary.get('fusion_run', {}).get('status')}`，阳性面积 `{summary.get('fusion_run', {}).get('positive_area_fraction')}`。
- MP4 分析 run：`{summary.get('video_run', {}).get('status')}`，关键帧 `{summary.get('video_run', {}).get('keyframes_extracted')}`，热点候选 `{summary.get('video_run', {}).get('hotspot_candidate_count')}`。
- 导出总 artifact：`{summary.get('export', {}).get('summary', {}).get('total_artifact_count')}`。

## 性能记录

| 阶段 | 耗时秒 | RSS 起始 MB | RSS 结束 MB | RSS 增量 MB | Python heap 起始 MB | Python heap 结束 MB | Python heap 增量 MB |
|---|---:|---:|---:|---:|---:|---:|---:|
{timings}

## 边界

- 这是代理 4K 工程 smoke，不是长时真实手术视频压力测试。
- 背景任务仍在本地 FastAPI/TestClient 进程内验证，不等同正式部署队列。
- MP4 结果仍来自 2D hotspot 启发式，只验证 AI 辅助判读工程链路，不代表真实训练模型或临床性能。
"""


if __name__ == "__main__":
    main()
