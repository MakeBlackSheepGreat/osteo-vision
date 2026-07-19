from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.train_keyframe_segmentation_proxy import ManifestKeyframeDataset, load_manifest_rows
from src.datasets.registry import sha256_file
from src.datasets.training_admission import MANUAL_ANNOTATION_ROLE
from tools.build_keyframe_training_manifest_from_manual_annotations import (
    build_manual_annotation_training_manifest,
)


def test_manual_annotation_manifest_is_consumable_by_keyframe_training_dataset(
    tmp_path: Path,
) -> None:
    records = [_record(tmp_path, index=index) for index in (1, 2)]
    records.append(
        {
            **_record(tmp_path, index=3),
            "training_eligible": False,
            "sample_weight": 0.0,
            "sampling_weight": 0.0,
            "actor_role": "engineering",
            "auth_source": "local_runtime",
        }
    )
    source_manifest = tmp_path / "manual_annotations.json"
    source_manifest.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-manual-annotation-training-manifest-v2",
                "eligible_count": 2,
                "excluded_count": 1,
                "records": records,
                "medical_boundary": "Physician review required.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = build_manual_annotation_training_manifest(
        Namespace(
            input=str(source_manifest),
            output_dir=str(tmp_path / "admitted"),
            manifest_name="manual_finetune.csv",
            val_fraction=0.2,
            seed=20260715,
        )
    )

    rows = load_manifest_rows(result["manifest_path"])
    assert len(rows) == 2
    assert {row["split"] for row in rows} == {"train", "val"}
    assert all(row["training_eligible"] == "true" for row in rows)
    assert all(row["target_mask_type"] == "lesion" for row in rows)
    assert all(row["target_task"] == "lesion_segmentation" for row in rows)
    dataset = ManifestKeyframeDataset(rows, image_shape=(32, 48))
    image, target, sample_weight = dataset[0]
    assert tuple(image.shape) == (3, 32, 48)
    assert tuple(target.shape) == (32, 48)
    assert int(target.sum()) > 0
    assert float(sample_weight) == 4.0


def _record(root: Path, *, index: int) -> dict[str, object]:
    image_path = root / f"source_{index}.jpg"
    mask_path = root / f"mask_{index}.png"
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 12:36, 1] = 175 + index
    mask = np.zeros((32, 48), dtype=np.uint8)
    mask[8:24, 12:36] = 255
    Image.fromarray(image).save(image_path)
    Image.fromarray(mask).save(mask_path)
    return {
        "record_id": f"manual-annotation-{index}-v1",
        "annotation_id": f"annotation-{index}",
        "annotation_version": 1,
        "case_id": f"case-{index}",
        "group_id": f"case-{index}",
        "source_snapshot_path": str(image_path),
        "mask_path": str(mask_path),
        "source_checksum": sha256_file(image_path),
        "mask_checksum": sha256_file(mask_path),
        "label_type": "physician_mask",
        "mask_type": "lesion",
        "review_state": "accepted",
        "training_eligible": True,
        "sample_weight": 4.0,
        "sampling_weight": 4.0,
        "original_width": 48,
        "original_height": 32,
        "positive_pixel_count": 384,
        "positive_area_fraction": 0.25,
        "source_type": "case_jpeg",
        "source_id": f"case_jpeg:input-{index}",
        "source_input_id": f"input-{index}",
        "intake_authorization_status": "approved",
        "intake_usage_scope": "research_training",
        "intake_deidentification_confirmed": True,
        "intake_mapping_held_by_institution": True,
        "intake_admission_status": "target_registry_ready",
        "source_input_admission_status": "admitted",
        "source_input_batch_id": f"batch-{index}",
        "source_input_record_id": f"batch-{index}_0001",
        "source_input_checksum": sha256_file(image_path),
        "source_input_checksum_verified": True,
        "actor_id": f"doctor-{index}",
        "actor_role": "physician",
        "institution": "Example Stomatology Hospital",
        "auth_source": "verified_identity_token",
        "submitted_by_actor_id": f"doctor-{index}",
        "submitted_by_role": "physician",
        "submitted_by_institution": "Example Stomatology Hospital",
        "submitted_by_auth_source": "verified_identity_token",
        "reviewer_actor_id": f"reviewer-{index}",
        "reviewer_role": "physician",
        "reviewer_institution": "Example Stomatology Hospital",
        "reviewer_auth_source": "institution_sso",
        "reviewed_at": "2026-07-15T10:00:00+00:00",
        "input_domain": "physician_reviewed_case_annotation_domain_unconfirmed",
        "domain_tier": "case_annotation_domain_unconfirmed",
        "target_domain_flag": False,
        "artifact_role": MANUAL_ANNOTATION_ROLE,
        "usage_policy": "institution_authorized_training_use",
        "license": "authorized institutional research training",
        "medical_scene": "case annotation",
        "medical_boundary": "Physician-reviewed research-validation annotation.",
    }
