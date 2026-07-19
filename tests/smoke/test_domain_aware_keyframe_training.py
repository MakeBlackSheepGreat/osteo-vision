from __future__ import annotations

import csv
from argparse import Namespace
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.train_keyframe_segmentation_proxy import train_keyframe_proxy


def test_domain_aware_keyframe_training_smoke(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    for index, split in enumerate(("train", "train", "val")):
        image_path = tmp_path / f"image_{index}.png"
        mask_path = tmp_path / f"mask_{index}.png"
        image = np.full((24, 32, 3), 20 + index * 10, dtype=np.uint8)
        mask = np.zeros((24, 32), dtype=np.uint8)
        image[6:18, 9:23, 1] = 220
        mask[6:18, 9:23] = 255
        Image.fromarray(image).save(image_path)
        Image.fromarray(mask).save(mask_path)
        rows.append(
            {
                "case_id": f"case_{index}",
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "split": split,
                "sample_weight": "1.0",
                "review_state": "modified" if index == 0 else "review_required",
                "domain_tier": "near_target" if index == 0 else "proxy",
                "source_group_id": f"group_{index}",
            }
        )
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = train_keyframe_proxy(
        Namespace(
            seed=19,
            device="cpu",
            image_shape="24x32",
            manifest=[str(manifest)],
            synthetic_train_size=2,
            synthetic_val_size=1,
            base_channels=2,
            learning_rate=1e-3,
            batch_size=2,
            max_train_batches=1,
            threshold=0.5,
            output_checkpoint=str(tmp_path / "domain_aware.pt"),
            model_id="domain_aware_smoke",
            runtime_allowed=False,
            report_dir=str(tmp_path / "reports"),
            report_stamp="smoke",
            domain_aware=True,
            domain_adaptation_config={
                "enabled": True,
                "augmentation": {"probability": 1.0, "jpeg_probability": 0.0},
            },
        )
    )
    assert Path(result["checkpoint_path"]).exists()
    assert result["metrics"]["case_count"] == 1
