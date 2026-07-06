"""Run a local end-to-end platform smoke flow and write an evidence summary."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "artifacts" / "platform_smoke" / timestamp()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OSTEO_ARTIFACT_ROOT"] = str(output_dir / "artifacts")
    os.environ["OSTEO_CASE_STORE_PATH"] = str(output_dir / "cases.sqlite")

    from backend.src.api.app import create_app

    client = TestClient(create_app())
    case = client.post("/cases", json={"title": "platform smoke"}).json()
    case_id = case["case_id"]

    white_upload = upload_fixture(
        client, ROOT / "tests" / "fixtures" / "platform" / "white.png", "white.png", "image/png"
    )
    fluor_upload = upload_fixture(
        client,
        ROOT / "tests" / "fixtures" / "platform" / "fluorescence.png",
        "fluorescence.png",
        "image/png",
    )
    inputs_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": white_upload["path"], "mime_type": "image/png"},
            {"channel": "fluorescence", "path": fluor_upload["path"], "mime_type": "image/png"},
        ],
    )
    inputs_response.raise_for_status()

    fusion_response = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"threshold": 0.6, "colormap": "green"}, "roi_hints": []},
    )
    fusion_response.raise_for_status()

    video_path = create_video(output_dir / "input" / "official_sample.mp4")
    video_upload = upload_fixture(client, video_path, "official_sample.mp4", "video/mp4")
    upload_job = client.get(f"/uploads/jobs/{video_upload['keyframe_job_id']}").json()
    video_input_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[{"channel": "video", "path": video_upload["path"], "mime_type": "video/mp4"}],
    )
    video_input_response.raise_for_status()

    analysis_job_response = client.post(
        f"/cases/{case_id}/analysis-jobs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 3}, "roi_hints": []},
    )
    analysis_job_response.raise_for_status()
    analysis_job = client.get(f"/analysis-jobs/{analysis_job_response.json()['job_id']}").json()

    final_case = client.get(f"/cases/{case_id}").json()
    export_response = client.post(
        f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []}
    )
    export_response.raise_for_status()
    export_payload = export_response.json()

    summary = {
        "case_id": case_id,
        "output_dir": str(output_dir),
        "white_upload": trim_upload(white_upload),
        "fluorescence_upload": trim_upload(fluor_upload),
        "video_upload": trim_upload(video_upload),
        "upload_job": trim_job(upload_job),
        "analysis_job": trim_job(analysis_job),
        "analysis_run_count": len(final_case.get("analysis_runs", [])),
        "artifact_count": len(final_case.get("artifacts", [])),
        "export": export_payload,
        "bundle_exists": Path(export_payload["bundle_path"]).exists(),
        "disclaimer": final_case.get("disclaimer_version", "platform-safety-v1"),
    }
    summary_path = output_dir / "platform_smoke_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), **summary}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="", help="Directory for smoke evidence artifacts.")
    return parser.parse_args()


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def upload_fixture(client: TestClient, path: Path, filename: str, content_type: str) -> dict[str, Any]:
    response = client.post(
        "/uploads/raw",
        content=path.read_bytes(),
        headers={"content-type": content_type, "x-filename": filename},
    )
    response.raise_for_status()
    return response.json()


def create_video(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (96, 64))
    for index in range(8):
        frame = np.full((64, 96, 3), 28 + index * 18, dtype=np.uint8)
        cv2.putText(frame, f"f{index}", (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 240, 255), 2)
        writer.write(frame)
    writer.release()
    return path


def trim_upload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": payload.get("path"),
        "input_type": payload.get("input_type"),
        "size_bytes": payload.get("size_bytes"),
        "keyframe_job_id": payload.get("keyframe_job_id"),
        "keyframe_job_status": payload.get("keyframe_job_status"),
        "keyframes": len(payload.get("keyframes") or []),
    }


def trim_job(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") or {}
    return {
        "job_id": payload.get("job_id"),
        "kind": payload.get("kind"),
        "status": payload.get("status"),
        "error": payload.get("error"),
        "keyframes": len(result.get("keyframes") or []),
        "run_id": result.get("run_id"),
        "run_status": result.get("run_status"),
    }


if __name__ == "__main__":
    main()
