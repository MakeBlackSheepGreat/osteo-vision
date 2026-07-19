from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import yaml

from tools.run_public_video_4k_validation import (
    configured_segmentation_model_id,
    latency_summary,
    probe_video,
)


def test_latency_summary_reports_p50_and_p95() -> None:
    summary = latency_summary([1.0, 2.0, 3.0, 4.0, 10.0])

    assert summary["count"] == 5
    assert summary["p50"] == 3.0
    assert summary["p95"] == 8.8


def test_probe_video_records_fps_resolution_and_duration(tmp_path: Path) -> None:
    path = tmp_path / "sample.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (64, 48))
    assert writer.isOpened()
    for _ in range(10):
        writer.write(np.full((48, 64, 3), 80, dtype=np.uint8))
    writer.release()

    probe = probe_video(path)

    assert probe["opened"] is True
    assert probe["width"] == 64
    assert probe["height"] == 48
    assert probe["fps"] == 5.0
    assert probe["frame_count"] == 10
    assert probe["duration_sec"] == 2.0


def test_public_video_validation_resolves_configured_segmentation_mainline(tmp_path: Path) -> None:
    config = tmp_path / "inference.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "tasks": {
                        "segmentation": {
                            "pipeline": "segmentation",
                            "model_id": "promoted_residual",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert configured_segmentation_model_id(config) == "promoted_residual"
