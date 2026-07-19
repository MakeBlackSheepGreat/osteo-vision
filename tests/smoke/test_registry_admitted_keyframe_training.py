from __future__ import annotations

import csv
import json
from argparse import Namespace
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from scripts.train_keyframe_segmentation_proxy import train_keyframe_proxy
from src.datasets.registry import REGISTRY_FIELDS, sha256_file


def test_registry_admitted_keyframe_training_smoke(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    for index in range(3):
        source_path = tmp_path / f"source_{index}.mp4"
        source_path.write_bytes(f"source-{index}".encode())
        image_path = tmp_path / f"image_{index}.png"
        mask_path = tmp_path / f"mask_{index}.png"
        image = np.full((24, 32, 3), 20, dtype=np.uint8)
        mask = np.zeros((24, 32), dtype=np.uint8)
        image[5:19, 8:24, 1] = 220
        mask[5:19, 8:24] = 255
        Image.fromarray(image).save(image_path)
        Image.fromarray(mask).save(mask_path)
        rows.extend(
            [
                _row(
                    record_id=f"source-{index}",
                    local_path=str(source_path),
                    label_path="",
                    label_type="none",
                    review_state="unlabeled",
                    checksum=sha256_file(source_path),
                    group_id=str(source_path),
                    artifact_role="source_video",
                    license="CC0-1.0",
                ),
                _row(
                    record_id=f"keyframe-{index}",
                    local_path=str(image_path),
                    label_path=str(mask_path),
                    checksum=sha256_file(image_path),
                    label_checksum=sha256_file(mask_path),
                    group_id=str(source_path),
                    artifact_role="training_keyframe::fluorescence_hotspot",
                    license="derived artifact; see upstream source",
                ),
            ]
        )
    registry = tmp_path / "registry.csv"
    with registry.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    quality = tmp_path / "quality.json"
    quality.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-layered-dataset-registry-v1",
                "registry_path": str(registry.resolve()),
                "registry_sha256": sha256_file(registry),
                "record_count": len(rows),
                "passed": True,
                "error_count": 0,
            }
        ),
        encoding="utf-8",
    )

    result = train_keyframe_proxy(
        Namespace(
            seed=31,
            device="cpu",
            image_shape="24x32",
            manifest=[],
            registry=str(registry),
            quality_report=str(quality),
            synthetic_train_size=2,
            synthetic_val_size=1,
            base_channels=2,
            learning_rate=1e-3,
            batch_size=1,
            max_train_batches=1,
            threshold=0.5,
            output_checkpoint=str(tmp_path / "registry_admitted.pt"),
            model_id="registry_admitted_smoke",
            runtime_allowed=False,
            report_dir=str(tmp_path / "reports"),
            report_stamp="registry_smoke",
            domain_aware=True,
            domain_adaptation_config={"enabled": True, "augmentation": {"probability": 0.0}},
        )
    )

    checkpoint = torch.load(result["checkpoint_path"], map_location="cpu", weights_only=False)
    training = checkpoint["training"]
    assert training["source"] == "layered_registry_admission"
    assert training["registry_sha256"] == sha256_file(registry)
    assert training["quality_report_sha256"] == sha256_file(quality)
    assert training["training_admission"]["admitted_count"] == 3
    assert training["training_admission"]["isolated_count"] == 0
    assert training["train_samples"] == 2
    assert training["val_samples"] == 1


def _row(**overrides: str) -> dict[str, str]:
    values = {
        "record_id": "record",
        "source_id": "source",
        "source_url": "https://example.org/source",
        "direct_download_url": "https://example.org/download",
        "local_path": "",
        "label_path": "",
        "medical_scene": "fluorescence-guided surgery proxy",
        "fluorescence": "yes",
        "domain_tier": "derived_proxy",
        "label_type": "proxy_mask",
        "review_state": "review_required",
        "sample_weight": "1.0",
        "sampling_weight": "0.5",
        "target_domain_flag": "false",
        "license": "CC0-1.0",
        "usage_policy": "training_allowed",
        "training_eligible": "true",
        "checksum": "",
        "split": "train",
        "group_id": "group",
        "artifact_role": "training_keyframe::fluorescence_hotspot",
        "medical_boundary": "Proxy fluorescence data; requires physician review.",
    }
    values.update(overrides)
    return {field: values.get(field, "") for field in REGISTRY_FIELDS}
