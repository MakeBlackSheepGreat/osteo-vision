from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def test_video_active_review_queue_cli_writes_queue_and_patch(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    mask_path = tmp_path / "mask.png"
    Image.new("RGB", (32, 24), color=(30, 80, 45)).save(image_path)
    mask = Image.new("L", (32, 24), color=0)
    ImageDraw.Draw(mask).rectangle((7, 5, 22, 18), fill=255)
    mask.save(mask_path)
    manifest = tmp_path / "frame_details_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "case_id": "case_cli",
                "run_id": "run_cli",
                "source_path": "public_proxy.mp4",
                "source_record_id": "public_proxy_record",
                "source_group_id": "public_proxy_group",
                "source_url": "https://example.org/public-proxy",
                "license": "CC BY 4.0",
                "usage_policy": "proxy_training_allowed_with_boundary",
                "sampling_weight": 0.5,
                "training_eligible": True,
                "frames": [
                    {
                        "frame_key": "10-0",
                        "frame_index": 10,
                        "timestamp_sec": 2.0,
                        "evidence_path": str(image_path),
                        "mask_path": str(mask_path),
                        "positive_area_fraction": 0.0,
                        "input_domain": "public_proxy_non_target_domain",
                        "target_domain_flag": False,
                        "temporal_stability": {
                            "instability_score": 0.08,
                            "flicker_warning": True,
                        },
                        "video_signal_segmentation": {
                            "risk_mask": {"summary": {"uncertain_area_fraction": 0.9}},
                            "bone_gate_mask": {"status": "not_available_pending_review"},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/build_video_active_review_queue.py",
            "--input",
            str(manifest),
            "--output-dir",
            str(output_dir),
            "--max-frames",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["selected_count"] == 1
    assert result["training_patch_row_count"] == 0
    queue = json.loads((output_dir / "video_active_review_queue.json").read_text(encoding="utf-8"))
    assert queue["rows"][0]["review_state"] == "review_required"
    assert (output_dir / "video_active_review_queue.csv").exists()
    assert (output_dir / "video_active_review_training_patch.json").exists()
    assert (output_dir / "video_active_review_training_patch.csv").exists()

    updates_path = tmp_path / "review_updates.json"
    updates_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "review_id": queue["rows"][0]["review_id"],
                        "review_state": "accepted",
                        "review_notes": "cli smoke review",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reviewed = subprocess.run(
        [
            sys.executable,
            "tools/build_video_active_review_queue.py",
            "--input",
            str(manifest),
            "--output-dir",
            str(output_dir),
            "--review-updates",
            str(updates_path),
            "--max-frames",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert reviewed.returncode == 0, reviewed.stderr
    reviewed_result = json.loads(reviewed.stdout)
    assert reviewed_result["training_patch_row_count"] == 1
    patch = json.loads((output_dir / "video_active_review_training_patch.json").read_text(encoding="utf-8"))
    assert patch["rows"][0]["review_state"] == "accepted"
    assert patch["rows"][0]["sample_weight"] == 4.0
    assert patch["rows"][0]["training_eligible"] is True
    assert patch["rows"][0]["source_group_id"] == "public_proxy_group"
    assert len(patch["rows"][0]["image_checksum"]) == 64
    assert len(patch["rows"][0]["label_checksum"]) == 64
