"""Run MP4 robustness smoke cases for official-resolution and invalid video inputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tracemalloc
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_official_4k_pressure_smoke import (  # noqa: E402
    checked_json,
    create_official_video,
    file_record,
    memory_snapshot,
    pressure_passed,
    profile_record,
    requested_timestamps,
    timed,
    timestamp,
    trim_job,
    upload_fixture,
)


def main() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    args = parse_args()
    output_dir = (
        Path(args.output_dir) if args.output_dir else ROOT / "artifacts" / "platform_smoke" / f"{timestamp()}_mp4_edges"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OSTEO_ARTIFACT_ROOT"] = str(output_dir / "artifacts")
    os.environ["OSTEO_CASE_STORE_PATH"] = str(output_dir / "cases.sqlite")

    timings: list[dict[str, Any]] = []
    from backend.src.api.app import create_app

    client = TestClient(create_app())
    input_dir = output_dir / "input"
    extended_video = timed(
        "generate_extended_4k_mp4",
        lambda: create_official_video(input_dir / "extended_4k_proxy.mp4", frames=args.frames, fps=args.fps),
        timings,
    )
    lowres_video = timed(
        "generate_lowres_profile_warning_mp4",
        lambda: create_lowres_video(input_dir / "lowres_profile_warning.mp4", frames=12, fps=args.fps),
        timings,
    )
    corrupt_signature = write_bytes(input_dir / "html_named_mp4.mp4", b"<html>captcha</html>")
    corrupt_ftyp = write_bytes(
        input_dir / "corrupt_ftyp.mp4",
        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"not-a-decodable-video",
    )

    case = timed(
        "create_edge_case",
        lambda: checked_json(client.post("/cases", json={"title": "MP4 edge case smoke"})),
        timings,
    )
    case_id = str(case["case_id"])
    extended_upload = timed(
        "upload_extended_4k_mp4",
        lambda: upload_fixture(client, extended_video, extended_video.name, "video/mp4"),
        timings,
    )
    upload_job = timed(
        "read_extended_upload_job",
        lambda: checked_json(client.get(f"/uploads/jobs/{extended_upload['keyframe_job_id']}")),
        timings,
    )
    timed(
        "attach_extended_4k_mp4_input",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/inputs",
                json=[{"channel": "video", "path": extended_upload["path"], "mime_type": "video/mp4"}],
            )
        ),
        timings,
    )
    analysis_job_payload = timed(
        "run_extended_4k_mp4_analysis",
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
        "read_extended_analysis_job",
        lambda: checked_json(client.get(f"/analysis-jobs/{analysis_job_payload['job_id']}")),
        timings,
    )
    final_case = timed("load_edge_case", lambda: checked_json(client.get(f"/cases/{case_id}")), timings)
    export_payload = timed(
        "export_extended_case_bundle",
        lambda: checked_json(
            client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})
        ),
        timings,
    )

    lowres_upload = timed(
        "upload_lowres_profile_warning_mp4",
        lambda: checked_json(
            client.post(
                "/uploads/raw",
                params={"keyframe_mode": "none"},
                content=lowres_video.read_bytes(),
                headers={"content-type": "video/mp4", "x-filename": lowres_video.name},
            )
        ),
        timings,
    )
    bad_signature_response = timed(
        "upload_bad_mp4_signature",
        lambda: client.post(
            "/uploads/raw",
            content=corrupt_signature.read_bytes(),
            headers={"content-type": "video/mp4", "x-filename": corrupt_signature.name},
        ),
        timings,
    )
    corrupt_ftyp_response = timed(
        "upload_corrupt_ftyp_mp4",
        lambda: client.post(
            "/uploads/raw",
            content=corrupt_ftyp.read_bytes(),
            headers={"content-type": "video/mp4", "x-filename": corrupt_ftyp.name},
        ),
        timings,
    )

    video_run = final_case["analysis_runs"][-1]
    summary = {
        "schema_version": "osteo-vision-mp4-edge-case-smoke-v1",
        "case_id": case_id,
        "output_dir": str(output_dir),
        "generated_inputs": {
            "extended_4k_mp4": file_record(extended_video),
            "lowres_mp4": file_record(lowres_video),
            "bad_signature_mp4": file_record(corrupt_signature),
            "corrupt_ftyp_mp4": file_record(corrupt_ftyp),
            "extended_frames": args.frames,
            "extended_fps": args.fps,
        },
        "extended_4k": {
            "upload_profile": profile_record(extended_upload),
            "upload_job": trim_job(upload_job),
            "analysis_job": trim_job(analysis_job),
            "run_id": video_run.get("run_id"),
            "run_status": video_run.get("status"),
            "keyframes_extracted": video_run.get("quantitative_summary", {}).get("keyframes_extracted"),
            "hotspot_candidate_count": video_run.get("quantitative_summary", {}).get("hotspot_candidate_count"),
            "timeline_manifest_path": video_run.get("fused_outputs", {}).get("timeline_manifest_path"),
            "frame_details_manifest_path": video_run.get("fused_outputs", {}).get("frame_details_manifest_path"),
            "export_summary": export_payload.get("summary", {}),
            "bundle_path": export_payload.get("bundle_path"),
        },
        "profile_warning_case": {
            "status_code": 200,
            "upload_profile": profile_record(lowres_upload),
            "warning_codes": [item.get("code") for item in lowres_upload.get("warnings", []) if isinstance(item, dict)],
        },
        "rejected_cases": {
            "bad_signature": response_record(bad_signature_response),
            "corrupt_ftyp": response_record(corrupt_ftyp_response),
        },
        "timings": timings,
        "memory_final": memory_snapshot(),
        "interpretation": {
            "domain": "proxy MP4 robustness smoke",
            "not_clinical_performance": True,
            "not_real_intraoperative_icg_jaw_osteomyelitis_video": True,
        },
        "pass": edge_passed(
            extended_upload=extended_upload,
            upload_job=upload_job,
            analysis_job=analysis_job,
            export_payload=export_payload,
            lowres_upload=lowres_upload,
            bad_signature_response=bad_signature_response,
            corrupt_ftyp_response=corrupt_ftyp_response,
        ),
    }
    summary_path = output_dir / "mp4_edge_case_smoke_summary.json"
    report_path = output_dir / "mp4_edge_case_smoke_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="", help="Directory for smoke evidence artifacts.")
    parser.add_argument("--frames", type=int, default=48, help="Extended synthetic 4K MP4 frame count.")
    parser.add_argument("--fps", type=float, default=6.0, help="Synthetic MP4 FPS.")
    parser.add_argument("--keyframes", type=int, default=5, help="Keyframes requested for extended MP4 analysis.")
    parser.add_argument("--threshold", type=float, default=0.6, help="Hotspot threshold.")
    return parser.parse_args()


def create_lowres_video(path: Path, *, frames: int, fps: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1920, 1080
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not create low-resolution MP4 with OpenCV VideoWriter.")
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    for index in range(max(1, frames)):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 0] = (30 + 20 * x).astype(np.uint8)
        frame[:, :, 1] = (40 + 30 * y).astype(np.uint8)
        frame[:, :, 2] = (55 + 25 * (1 - x)).astype(np.uint8)
        cv2.circle(frame, (280 + index * 35, height // 2), 80, (0, 255, 0), -1)
        cv2.putText(frame, "lowres MP4 profile warning", (70, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (230, 245, 255), 5)
        writer.write(frame)
    writer.release()
    return path


def write_bytes(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def response_record(response: Any) -> dict[str, Any]:
    try:
        detail = response.json().get("detail")
    except Exception:
        detail = response.text
    return {"status_code": response.status_code, "detail": detail}


def edge_passed(
    *,
    extended_upload: dict[str, Any],
    upload_job: dict[str, Any],
    analysis_job: dict[str, Any],
    export_payload: dict[str, Any],
    lowres_upload: dict[str, Any],
    bad_signature_response: Any,
    corrupt_ftyp_response: Any,
) -> bool:
    lowres_warnings = [item.get("code") for item in lowres_upload.get("warnings", []) if isinstance(item, dict)]
    corrupt_detail = response_record(corrupt_ftyp_response).get("detail")
    corrupt_code = corrupt_detail.get("code") if isinstance(corrupt_detail, dict) else None
    return pressure_passed(
        extended_upload,
        extended_upload,
        extended_upload,
        upload_job,
        analysis_job,
        export_payload,
    ) and all(
        [
            profile_record(lowres_upload).get("resolution_match") is False,
            "official_video_resolution_mismatch" in lowres_warnings,
            bad_signature_response.status_code == 415,
            corrupt_ftyp_response.status_code == 422,
            corrupt_code == "upload_content_unreadable",
        ]
    )


def render_markdown(summary: dict[str, Any]) -> str:
    edge = summary.get("extended_4k", {})
    profile_case = summary.get("profile_warning_case", {})
    rejected = summary.get("rejected_cases", {})
    timings = "\n".join(
        f"| {item['name']} | {item['elapsed_sec']} | {item.get('rss_delta_mb')} | {item.get('heap_delta_mb')} |"
        for item in summary.get("timings", [])
    )
    return f"""# MP4 鲁棒性 Edge Smoke

本验证使用合成 MP4，覆盖更长 4K 代理视频、非官方分辨率 warning 和坏 MP4 阻断。它只证明工程链路与异常处理，不代表真实术中 ICG 颌骨骨髓炎数据或模型性能。

## 结论

- 验证通过：`{summary.get('pass')}`
- 病例：`{summary.get('case_id')}`
- 输出目录：`{summary.get('output_dir')}`

## 更长 4K 代理 MP4

- 帧数：`{summary.get('generated_inputs', {}).get('extended_frames')}`
- FPS：`{summary.get('generated_inputs', {}).get('extended_fps')}`
- 官方 profile：`{edge.get('upload_profile', {}).get('status')}`
- 上传 keyframe job：`{edge.get('upload_job', {}).get('status')}`
- 分析 job：`{edge.get('analysis_job', {}).get('status')}`
- 提取关键帧：`{edge.get('keyframes_extracted')}`
- 热点候选：`{edge.get('hotspot_candidate_count')}`
- timeline manifest：`{edge.get('timeline_manifest_path')}`
- evidence bundle：`{edge.get('bundle_path')}`

## 异常输入

- 低分辨率 MP4：HTTP `{profile_case.get('status_code')}`，profile `{profile_case.get('upload_profile', {}).get('status')}`，warning `{profile_case.get('warning_codes')}`。
- 坏签名 MP4：HTTP `{rejected.get('bad_signature', {}).get('status_code')}`，detail `{rejected.get('bad_signature', {}).get('detail')}`。
- 伪 ftyp 不可解码 MP4：HTTP `{rejected.get('corrupt_ftyp', {}).get('status_code')}`，detail `{rejected.get('corrupt_ftyp', {}).get('detail')}`。

## 性能记录

| 阶段 | 耗时秒 | RSS 增量 MB | Python heap 增量 MB |
|---|---:|---:|---:|
{timings}
"""


if __name__ == "__main__":
    main()
