from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.datasets.registry import REGISTRY_FIELDS, sha256_file
from src.datasets.training_admission import (
    DEFAULT_TASK_BY_MANUAL_MASK_TYPE,
    MANUAL_ANNOTATION_MASK_TYPES,
    TrainingAdmissionError,
    admit_keyframe_training_rows,
)


def test_manual_ignore_label_is_preserved_for_bone_activity_training() -> None:
    assert "ignore" in MANUAL_ANNOTATION_MASK_TYPES
    assert DEFAULT_TASK_BY_MANUAL_MASK_TYPE["ignore"] == "bone_activity_segmentation"


def test_admission_preserves_provenance_and_creates_grouped_validation_split(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    for index in range(3):
        source_path = tmp_path / f"source_{index}.mp4"
        source_path.write_bytes(f"source-{index}".encode())
        image_path, mask_path = _write_image_mask(tmp_path, index)
        group_id = str(source_path)
        rows.append(_source_row(source_path, group_id=group_id))
        rows.append(
            _training_row(
                image_path,
                mask_path,
                record_id=f"train-{index}",
                group_id=group_id,
            )
        )
    registry, quality = _write_registry_evidence(tmp_path, rows)

    result = admit_keyframe_training_rows(registry, quality)

    assert len(result.rows) == 3
    assert {row["split"] for row in result.rows} == {"train", "val"}
    assert all(row["source_group_id"] == row["group_id"] for row in result.rows)
    assert all(row["domain_tier"] == "derived_proxy" for row in result.rows)
    assert all(row["sample_weight"] == "1.0" for row in result.rows)
    assert all(row["sampling_weight"] == "0.5" for row in result.rows)
    assert all("no target-domain clinical ground truth" in row["medical_boundary"] for row in result.rows)
    assert result.summary["admitted_count"] == 3
    assert result.summary["isolated_count"] == 0
    assert result.summary["registry_sha256"] == sha256_file(registry)
    assert result.summary["quality_report_sha256"] == sha256_file(quality)
    assert result.summary["split_policy"]["name"] == "deterministic_group_fallback"


def test_admission_isolates_ineligible_rejected_and_no_derivatives_rows(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    cases = (
        ("ineligible", {"training_eligible": "false"}),
        ("missing-eligibility", {"training_eligible": ""}),
        ("rejected", {"review_state": "rejected", "sample_weight": "0.5"}),
        ("no-derivatives", {"usage_policy": "no_derivatives", "license": "CC BY-NC-ND 4.0"}),
    )
    for index, (name, overrides) in enumerate(cases):
        source_path = tmp_path / f"{name}.mp4"
        source_path.write_bytes(name.encode())
        image_path, mask_path = _write_image_mask(tmp_path, index)
        rows.append(_source_row(source_path, group_id=str(source_path)))
        rows.append(
            _training_row(
                image_path,
                mask_path,
                record_id=name,
                group_id=str(source_path),
                **overrides,
            )
        )
    registry, quality = _write_registry_evidence(tmp_path, rows)

    with pytest.raises(TrainingAdmissionError, match="No keyframe rows passed"):
        admit_keyframe_training_rows(registry, quality)


def test_admission_refuses_failed_or_stale_quality_report(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"source")
    image_path, mask_path = _write_image_mask(tmp_path, 0)
    rows = [
        _source_row(source_path, group_id=str(source_path)),
        _training_row(image_path, mask_path, record_id="train", group_id=str(source_path)),
    ]
    registry, quality = _write_registry_evidence(tmp_path, rows)
    payload = json.loads(quality.read_text(encoding="utf-8"))
    payload["passed"] = False
    payload["error_count"] = 1
    quality.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TrainingAdmissionError, match="quality gate did not pass"):
        admit_keyframe_training_rows(registry, quality)


def test_admission_isolates_empty_and_size_mismatched_masks(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    for index in range(2):
        source_path = tmp_path / f"valid_source_{index}.mp4"
        source_path.write_bytes(f"valid-{index}".encode())
        image_path, mask_path = _write_image_mask(tmp_path, index)
        rows.extend(
            [
                _source_row(source_path, group_id=str(source_path)),
                _training_row(image_path, mask_path, record_id=f"valid-{index}", group_id=str(source_path)),
            ]
        )
    for index, mode in enumerate(("empty", "mismatch"), start=10):
        source_path = tmp_path / f"bad_source_{mode}.mp4"
        source_path.write_bytes(mode.encode())
        image_path, mask_path = _write_image_mask(tmp_path, index)
        if mode == "empty":
            Image.fromarray(np.zeros((20, 24), dtype=np.uint8)).save(mask_path)
        else:
            Image.fromarray(np.ones((10, 12), dtype=np.uint8) * 255).save(mask_path)
        rows.extend(
            [
                _source_row(source_path, group_id=str(source_path)),
                _training_row(
                    image_path,
                    mask_path,
                    record_id=mode,
                    group_id=str(source_path),
                    label_type="human_reviewed_mask" if mode == "mismatch" else "proxy_mask",
                ),
            ]
        )
    registry, quality = _write_registry_evidence(tmp_path, rows)
    result = admit_keyframe_training_rows(registry, quality)
    assert result.summary["admitted_count"] == 2
    assert result.summary["isolated_count"] == 2
    assert result.summary["isolation_reason_counts"]["empty_mask"] == 1
    assert result.summary["isolation_reason_counts"]["mask_size_mismatch"] == 1


def test_article_crop_inherits_training_license_by_source_id(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    for index in range(2):
        source_id = f"PMC{index}_figure_2"
        source_image = tmp_path / f"source_figure_{index}.jpg"
        Image.new("RGB", (24, 20), (20, 40, 60)).save(source_image)
        image_path, mask_path = _write_image_mask(tmp_path, index + 20)
        rows.extend(
            [
                _registry_row(
                    record_id=f"figure::{source_id}",
                    source_id=source_id,
                    local_path=str(source_image),
                    label_path="",
                    label_type="none",
                    review_state="unlabeled",
                    checksum=sha256_file(source_image),
                    group_id=f"PMC{index}",
                    artifact_role="source_article_figure",
                    license="CC BY 4.0",
                    usage_policy="weak_label_training_seed_with_attribution",
                    training_eligible="false",
                ),
                _training_row(
                    image_path,
                    mask_path,
                    record_id=f"crop-{index}",
                    group_id=f"PMC{index}",
                    source_id=source_id,
                    license="derived reviewed crop",
                    usage_policy="training_allowed_by_license_with_attribution",
                ),
            ]
        )
    registry, quality = _write_registry_evidence(tmp_path, rows)
    result = admit_keyframe_training_rows(registry, quality)
    assert result.summary["admitted_count"] == 2
    assert all("CC BY 4.0" in row["license"] for row in result.rows)


def test_reviewed_finetune_stage_excludes_proxy_and_pending_labels(
    tmp_path: Path,
) -> None:
    rows: list[dict[str, str]] = []
    for index in range(3):
        source_path = tmp_path / f"review_source_{index}.mp4"
        source_path.write_bytes(f"source-{index}".encode())
        image_path, mask_path = _write_image_mask(tmp_path, index + 40)
        rows.append(_source_row(source_path, group_id=str(source_path)))
        overrides = (
            {
                "label_type": "human_reviewed_mask",
                "review_state": "accepted",
                "sample_weight": "4.0",
            }
            if index < 2
            else {
                "label_type": "proxy_mask",
                "review_state": "review_required",
            }
        )
        rows.append(
            _training_row(
                image_path,
                mask_path,
                record_id=f"reviewed-{index}",
                group_id=str(source_path),
                **overrides,
            )
        )
    registry, quality = _write_registry_evidence(tmp_path, rows)

    result = admit_keyframe_training_rows(
        registry,
        quality,
        admission_stage="reviewed_finetune",
    )

    assert result.summary["admission_stage"] == "reviewed_finetune"
    assert result.summary["admitted_count"] == 2
    assert result.summary["isolated_count"] == 1
    assert result.summary["isolation_reason_counts"]["stage_requires_reviewed_label"] == 1
    assert result.summary["isolation_reason_counts"]["stage_rejects_proxy_label"] == 1


def test_independent_evaluation_stage_preserves_frozen_test_split(
    tmp_path: Path,
) -> None:
    rows: list[dict[str, str]] = []
    for index in range(2):
        source_path = tmp_path / f"evaluation_source_{index}.mp4"
        source_path.write_bytes(f"source-{index}".encode())
        image_path, mask_path = _write_image_mask(tmp_path, index + 50)
        rows.append(_source_row(source_path, group_id=str(source_path)))
        rows.append(
            _training_row(
                image_path,
                mask_path,
                record_id=f"evaluation-{index}",
                group_id=str(source_path),
                label_type="physician_mask",
                review_state="modified",
                sample_weight="4.0",
                usage_policy="independent_evaluation_frozen",
                split="test",
            )
        )
    registry, quality = _write_registry_evidence(tmp_path, rows)

    result = admit_keyframe_training_rows(
        registry,
        quality,
        admission_stage="independent_evaluation",
    )

    assert result.summary["admission_stage"] == "independent_evaluation"
    assert result.summary["split_policy"]["name"] == "frozen_independent_test"
    assert {row["split"] for row in result.rows} == {"test"}


def _write_image_mask(root: Path, index: int) -> tuple[Path, Path]:
    image_path = root / f"image_{index}.png"
    mask_path = root / f"mask_{index}.png"
    image = np.zeros((20, 24, 3), dtype=np.uint8)
    mask = np.zeros((20, 24), dtype=np.uint8)
    image[4:16, 6:18, 1] = 220
    mask[4:16, 6:18] = 255
    Image.fromarray(image).save(image_path)
    Image.fromarray(mask).save(mask_path)
    return image_path, mask_path


def _source_row(path: Path, *, group_id: str) -> dict[str, str]:
    return _registry_row(
        record_id=f"source::{path.stem}",
        source_id=path.stem,
        local_path=str(path),
        label_path="",
        label_type="none",
        review_state="unlabeled",
        sample_weight="1.0",
        sampling_weight="1.0",
        checksum=sha256_file(path),
        group_id=group_id,
        artifact_role="source_video",
        license="CC0-1.0",
        usage_policy="training_allowed",
        training_eligible="true",
    )


def _training_row(
    image_path: Path,
    mask_path: Path,
    *,
    record_id: str,
    group_id: str,
    **overrides: str,
) -> dict[str, str]:
    values = _registry_row(
        record_id=record_id,
        source_id="derived",
        local_path=str(image_path),
        label_path=str(mask_path),
        label_type="proxy_mask",
        review_state="review_required",
        sample_weight="1.0",
        sampling_weight="0.5",
        checksum=sha256_file(image_path),
        label_checksum=sha256_file(mask_path),
        group_id=group_id,
        artifact_role="training_keyframe::fluorescence_hotspot",
        license="derived artifact; see upstream source",
        usage_policy="training_allowed",
        training_eligible="true",
        medical_boundary="Proxy fluorescence keyframe; no target-domain clinical ground truth.",
    )
    values.update(overrides)
    return values


def _registry_row(**overrides: str) -> dict[str, str]:
    defaults = {
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
        "sampling_weight": "1.0",
        "target_domain_flag": "false",
        "license": "CC0-1.0",
        "usage_policy": "training_allowed",
        "training_eligible": "true",
        "checksum": "",
        "split": "train",
        "group_id": "group",
        "artifact_role": "training_keyframe::fluorescence_hotspot",
        "medical_boundary": "Proxy data for engineering validation.",
    }
    defaults.update(overrides)
    return {field: defaults.get(field, "") for field in REGISTRY_FIELDS}


def _write_registry_evidence(tmp_path: Path, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    registry = tmp_path / "layered_registry.csv"
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
    return registry, quality
