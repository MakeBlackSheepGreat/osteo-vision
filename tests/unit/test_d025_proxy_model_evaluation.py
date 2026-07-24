from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import torch

from scripts.evaluate_d025_proxy_model import evaluate_checkpoint
from osteo_vision_core.models.lesion_segmenter import TinyLesionSegmenter3D


def test_d025_proxy_evaluation_writes_reports_and_failure_previews(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    case_paths = [
        _write_case(cache_dir / "case_001.npz", lesion_slice=2),
        _write_case(cache_dir / "case_002.npz", lesion_slice=5),
    ]
    manifest_path = tmp_path / "manifest.csv"
    _write_manifest(manifest_path, case_paths)

    checkpoint_path = tmp_path / "checkpoint.pt"
    model = TinyLesionSegmenter3D(base_channels=1)
    for parameter in model.parameters():
        torch.nn.init.constant_(parameter, 0.0)
    torch.save(
        {
            "model_id": "d025_lesion_smoke_segmenter",
            "model_family": "d025_lesion_segmenter",
            "model_config": {"in_channels": 1, "out_channels": 2, "base_channels": 1},
            "state_dict": model.state_dict(),
            "training": {"case_count": 2},
            "metrics": {},
        },
        checkpoint_path,
    )

    payload = evaluate_checkpoint(
        argparse.Namespace(
            manifest=str(manifest_path),
            checkpoint=str(checkpoint_path),
            report_dir=str(tmp_path / "reports"),
            asset_root=str(tmp_path / "assets"),
            split="val",
            max_cases=0,
            thresholds="0.5",
            failure_count=1,
            device="cpu",
        )
    )

    outputs = payload["outputs"]
    assert Path(outputs["json_path"]).exists()
    assert Path(outputs["csv_path"]).exists()
    assert Path(outputs["zh_report_path"]).exists()
    assert Path(outputs["en_report_path"]).exists()
    assert payload["evaluation"]["case_count"] == 2
    assert payload["evaluation"]["best_threshold"] == 0.5
    assert payload["evaluation"]["best_summary"]["dice"]["available"] is True

    with Path(outputs["csv_path"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["threshold"] == "0.5"

    failure = payload["evaluation"]["failure_cases"][0]
    assert Path(failure["preview_path"]).exists()
    assert "D025 CBCT lesion ROI proxy" in payload["evaluation"]["medical_boundary"]


def _write_case(path: Path, *, lesion_slice: int) -> Path:
    image = np.zeros((8, 8, 8), dtype=np.float32)
    image[lesion_slice, 2:6, 2:6] = 1.0
    label = np.zeros((8, 8, 8), dtype=np.int64)
    label[lesion_slice, 3:5, 3:5] = 1
    np.savez_compressed(path, image=image, label=label)
    return path


def _write_manifest(path: Path, case_paths: list[Path]) -> None:
    fieldnames = [
        "case_id",
        "cache_path",
        "split",
        "fold",
        "diagnosis_group",
        "original_shape",
        "original_spacing",
        "target_shape",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, case_path in enumerate(case_paths, start=1):
            writer.writerow(
                {
                    "case_id": f"case_{index:03d}",
                    "cache_path": str(case_path),
                    "split": "val",
                    "fold": "0",
                    "diagnosis_group": "proxy",
                    "original_shape": "8x8x8",
                    "original_spacing": "1x1x1",
                    "target_shape": "8x8x8",
                }
            )
