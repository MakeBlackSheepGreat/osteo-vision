from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from tools.build_keyframe_segmentation_proxy_manifest import build_proxy_manifest, video_sample_indices


def test_build_keyframe_proxy_manifest_from_image(tmp_path: Path) -> None:
    image_path = tmp_path / "fluorescence_like.jpg"
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[12:32, 20:44, 1] = 240
    Image.fromarray(image).save(image_path)

    result = build_proxy_manifest(_args(tmp_path, [image_path]))

    manifest_path = Path(result["manifest_path"])
    rows = list(csv.DictReader(manifest_path.open("r", encoding="utf-8", newline="")))
    assert len(rows) == 1
    assert rows[0]["source_type"] == "image"
    assert rows[0]["label_source"] == "fluorescence_intensity_proxy_mask"
    assert rows[0]["quality_status"] == "accepted"
    assert int(rows[0]["component_count"]) >= 1
    assert float(rows[0]["positive_area_fraction"]) > 0
    assert float(rows[0]["largest_component_fraction"]) > 0
    assert Path(rows[0]["image_path"]).exists()
    assert Path(rows[0]["mask_path"]).exists()
    summary_text = Path(result["summary_path"]).read_text(encoding="utf-8")
    assert "Pseudo masks" in summary_text
    assert Path(result["review_seed_csv_path"]).exists()
    assert Path(result["preview_grid_path"]).exists()


def test_build_keyframe_proxy_manifest_from_mp4(tmp_path: Path) -> None:
    cv2 = pytest_import_cv2()
    video_path = tmp_path / "fluorescence_like.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (64, 48))
    for index in range(5):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        frame[12:32, 12 + index : 36 + index, 1] = 245
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release()

    result = build_proxy_manifest(_args(tmp_path, [video_path], max_frames_per_video=3))

    rows = list(csv.DictReader(Path(result["manifest_path"]).open("r", encoding="utf-8", newline="")))
    assert len(rows) == 3
    assert {row["source_type"] for row in rows} == {"video"}
    assert all(row["frame_index"] for row in rows)
    assert all(float(row["positive_area_fraction"]) > 0 for row in rows)
    assert all(row["quality_status"] == "accepted" for row in rows)
    assert len({row["split"] for row in rows}) == 1
    assert len({row["source_group_id"] for row in rows}) == 1
    assert result["source_group_split"]["leakage_detected"] is False


def test_video_sample_indices_even_and_stride() -> None:
    assert video_sample_indices(frame_count=10, max_frames=3, frame_stride=0) == [0, 4, 9]
    assert video_sample_indices(frame_count=10, max_frames=3, frame_stride=2) == [0, 2, 4]


def _args(tmp_path: Path, inputs: list[Path], **overrides: object) -> argparse.Namespace:
    values = {
        "input": [str(path) for path in inputs],
        "output_dir": str(tmp_path / "derived"),
        "manifest_name": "keyframe_segmentation_proxy_manifest.csv",
        "dataset_id": "test_proxy",
        "input_domain": "unit_test_proxy",
        "domain_tier": "proxy",
        "fluorescence_attribute": "fluorescence_like",
        "threshold": 0.55,
        "min_component_area": 8,
        "min_positive_area_fraction": 0.0005,
        "max_positive_area_fraction": 0.6,
        "max_frames_per_video": 4,
        "frame_stride": 0,
        "max_samples": 0,
        "preview_sample_count": 6,
        "review_seed_sample_count": 5,
        "val_fraction": 0.2,
        "test_fraction": 0.1,
        "seed": 20260704,
        "include_empty": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def pytest_import_cv2():
    import pytest

    return pytest.importorskip("cv2")
