from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from backend.osteo_vision_api.services.static_dataset_review import (
    DATASET_RELATIVE_ROOTS,
    StaticDatasetReviewService,
)


def _write_queue(project_root: Path, *, record_count: int = 1) -> Path:
    dataset_root = project_root / DATASET_RELATIVE_ROOTS["d047"]
    crop_dir = dataset_root / "derived/figure_review/crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for index in range(record_count):
        record_id = f"review_fixture_{index}"
        image_path = crop_dir / f"fixture_{index}.png"
        Image.new("RGB", (32, 24), color=(40 + index, 90, 55)).save(image_path)
        records.append(
            {
                "record_id": record_id,
                "source_record_id": f"source_{index}",
                "source_group_id": f"group_{index}",
                "local_path": str(image_path),
                "cropped_image_path": str(image_path),
                "review_state": "review_required",
                "license": "CC BY 4.0",
                "usage_policy": "weak_label_training_seed_with_attribution",
            }
        )
    queue_path = dataset_root / "derived/figure_review/pmc_figure_review_queue.json"
    queue_path.write_text(json.dumps({"records": records}), encoding="utf-8")
    return queue_path


def _mask_base64() -> str:
    values = np.zeros((24, 32), dtype=np.uint8)
    values[4:18, 7:24] = 255
    buffer = BytesIO()
    Image.fromarray(values).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_queue_and_manifest_indexes_reload_after_external_changes(tmp_path: Path) -> None:
    queue_path = _write_queue(tmp_path, record_count=1)
    service = StaticDatasetReviewService(tmp_path)

    first_records = service._queue_records()
    second_records = service._queue_records()
    cache = service._queue_cache[queue_path.resolve()]
    assert len(first_records) == 1
    assert second_records[0][1]["record_id"] == "review_fixture_0"
    assert service._queue_manifest("d047", queue_path.parents[2])[0] is cache.records

    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))
    queue_payload["records"].append(
        {
            "record_id": "review_fixture_1",
            "source_record_id": "source_1",
            "source_group_id": "group_1",
            "local_path": str(queue_path.parent / "fixture_1.png"),
            "cropped_image_path": str(queue_path.parent / "fixture_1.png"),
            "review_state": "review_required",
            "license": "CC BY 4.0",
        }
    )
    Image.new("RGB", (32, 24), color=(41, 90, 55)).save(queue_path.parent / "fixture_1.png")
    queue_path.write_text(json.dumps(queue_payload), encoding="utf-8")

    assert len(service._queue_records()) == 2
    assert service._find_source_record("review_fixture_1")[1]["source_record_id"] == "source_1"


def test_review_manifest_cache_is_invalidated_by_save_mask(tmp_path: Path) -> None:
    _write_queue(tmp_path)
    service = StaticDatasetReviewService(tmp_path)
    service.list_queue()
    assert service._reviewed_records_by_id() == {}

    saved = service.save_mask(
        "review_fixture_0",
        mask_png_base64=_mask_base64(),
        review_state="accepted",
        reviewer_notes="checked",
        reviewer_role="physician",
    )

    assert saved["training_eligible"] is True
    assert service._reviewed_records_by_id()["review_fixture_0"]["review_state"] == "accepted"
    queue_item = next(row for row in service.list_queue()["items"] if row["record_id"] == "review_fixture_0")
    assert queue_item["physician_reviewed"] is True
    assert queue_item["mask_path"] == saved["mask_path"]


def test_queue_skips_malformed_record_fields(tmp_path: Path) -> None:
    queue_path = _write_queue(tmp_path)
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    payload["records"][0]["record_kind"] = "source_figure"
    payload["records"][0]["crop_suggestion_child_count"] = "invalid"
    queue_path.write_text(json.dumps(payload), encoding="utf-8")

    listed = StaticDatasetReviewService(tmp_path).list_queue()

    assert listed["record_count"] == 0
    assert listed["skipped_invalid_record_count"] == 1
