from __future__ import annotations

import csv
from argparse import Namespace
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.train_keyframe_segmentation_proxy import build_datasets


def test_build_datasets_merges_manifests_and_reads_sample_weight(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    mask_path = tmp_path / "mask.png"
    image = np.zeros((24, 32, 3), dtype=np.uint8)
    image[6:18, 8:20, 1] = 230
    mask = np.zeros((24, 32), dtype=np.uint8)
    mask[6:18, 8:20] = 255
    Image.fromarray(image).save(image_path)
    Image.fromarray(mask).save(mask_path)

    proxy_manifest = tmp_path / "proxy.csv"
    review_manifest = tmp_path / "review.csv"
    _write_manifest(
        proxy_manifest,
        [
            {
                "case_id": "proxy_train",
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "split": "train",
                "sample_weight": "1.0",
                "label_source": "fluorescence_intensity_proxy_mask",
            },
            {
                "case_id": "proxy_val",
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "split": "val",
                "sample_weight": "1.0",
                "label_source": "fluorescence_intensity_proxy_mask",
            },
        ],
    )
    _write_manifest(
        review_manifest,
        [
            {
                "case_id": "review_train",
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "split": "train",
                "sample_weight": "4.0",
                "label_source": "human_reviewed_roi_geometry_mask",
                "review_state": "modified",
            }
        ],
    )

    train_dataset, val_dataset, summary = build_datasets(
        Namespace(
            manifest=[str(proxy_manifest), str(review_manifest)],
            synthetic_train_size=4,
            synthetic_val_size=2,
        ),
        image_shape=(24, 32),
    )

    assert len(train_dataset) == 2
    assert len(val_dataset) == 1
    assert summary["manifest_paths"] == [str(proxy_manifest), str(review_manifest)]
    assert summary["sample_weight_stats"]["max"] == 4.0
    assert summary["label_source_counts"]["human_reviewed_roi_geometry_mask"] == 1
    _image, _target, weight = train_dataset[1]
    assert float(weight.item()) == 4.0


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
