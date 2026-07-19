"""Run a round-3 MP4 keyframe, bone-gate, and review-manifest demo check."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.src.api.app import create_app  # noqa: E402
from src.core.paths import ensure_dir, resolve_path  # noqa: E402
from src.reports.writers import write_json  # noqa: E402

DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
    "derived/video_signal_segmentation_20260706/video_signal_segmentation_manifest.csv"
)
BOUNDARY_NOTE = (
    "D046 is public/proxy video data and not real intraoperative ICG jaw osteomyelitis target-domain data. "
    "This check validates the platform MP4/JPEG workflow only."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-signal-manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", default=".pytest_tmp/round3_official_mp4_bone_gate_demo")
    parser.add_argument("--keyframes", type=int, default=2)
    return parser.parse_args()


def run_demo_check(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ensure_dir(resolve_path(args.output_dir))
    os.environ["OSTEO_ARTIFACT_ROOT"] = str(output_dir / "artifacts")
    os.environ["OSTEO_CASE_STORE_PATH"] = str(output_dir / "cases.json")
    video_path = first_readable_video(resolve_path(args.video_signal_manifest))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "round3 official mp4 bone gate demo"}).json()["case_id"]
    input_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {
                "channel": "video",
                "path": str(video_path),
                "mime_type": "video/mp4",
                "metadata": {
                    "input_domain": "D046 public/proxy non-target-domain MP4",
                    "medical_boundary": BOUNDARY_NOTE,
                },
            }
        ],
    )
    input_response.raise_for_status()
    analysis = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={
            "selected_input_ids": [],
            "parameters": {"mode": "video_file", "source_path": str(video_path), "keyframe_count": int(args.keyframes)},
            "roi_hints": [],
        },
    )
    analysis.raise_for_status()
    analyzed_case = analysis.json()
    candidates = analyzed_case["analysis_runs"][-1]["candidate_regions"]
    bone_gate_response = None
    if candidates:
        candidate = candidates[0]
        geometry = candidate.get("metadata", {}).get("bbox_normalized")
        bone_gate_response = client.post(
            f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}/bone-gate-mask",
            json={"geometry": geometry, "review_state": "review_required", "prompt_source": "round3_demo_bbox"},
        )
        bone_gate_response.raise_for_status()
        analyzed_case = bone_gate_response.json()
    export = client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})
    export.raise_for_status()
    latest_run = analyzed_case["analysis_runs"][-1]
    summary = {
        "schema_version": "osteo-vision-round3-official-mp4-bone-gate-demo-check-v1",
        "case_id": case_id,
        "source_video_path": str(video_path),
        "keyframe_count": latest_run.get("quantitative_summary", {}).get("keyframes_extracted"),
        "candidate_count": len(latest_run.get("candidate_regions") or []),
        "bone_gate_generated": bone_gate_response is not None,
        "video_signal_outputs": ["fluorescence_signal_mask", "bone_gate_mask", "risk_mask", "uncertain_mask"],
        "export_summary": export.json().get("summary", {}),
        "medical_boundary": BOUNDARY_NOTE,
    }
    summary_path = output_dir / "round3_official_mp4_bone_gate_demo_summary.json"
    write_json(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    return summary


def first_readable_video(manifest_path: Path) -> Path:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row.get("source_video_path")
            if not value:
                continue
            path = resolve_path(value)
            if path.exists():
                return path
    raise FileNotFoundError(f"No readable source_video_path found in {manifest_path}")


def main() -> int:
    print(json.dumps(run_demo_check(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
