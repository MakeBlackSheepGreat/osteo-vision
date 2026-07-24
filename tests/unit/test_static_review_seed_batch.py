from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from backend.osteo_vision_api.services.static_dataset_review import (
    DATASET_RELATIVE_ROOTS,
    StaticDatasetReviewService,
)
from tools.generate_static_review_seeds import generate_seed_batch


def _write_queue(project_root: Path, dataset_id: str, record_id: str) -> None:
    dataset_root = project_root / DATASET_RELATIVE_ROOTS[dataset_id]
    crop_path = dataset_root / "derived/figure_review/crops" / f"{record_id}.png"
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 24), color=(30, 180, 50)).save(crop_path)
    queue_path = dataset_root / "derived/figure_review/pmc_figure_review_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": record_id,
                        "source_record_id": record_id,
                        "source_group_id": f"group_{dataset_id}",
                        "source_url": f"https://example.org/{record_id}",
                        "cropped_image_path": str(crop_path),
                        "review_state": "review_required",
                        "panel_role": "fluorescence_signal",
                        "license": "CC BY 4.0",
                        "usage_policy": "weak_label_training_seed_with_attribution",
                        "sampling_weight": 0.25,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_batch_generates_only_review_required_non_training_seeds(tmp_path: Path, monkeypatch) -> None:
    _write_queue(tmp_path, "d047", "review_d047")
    _write_queue(tmp_path, "d048", "review_d048")
    monkeypatch.setenv("OSTEO_DATASET_REVIEW_PROJECT_ROOT", str(tmp_path))
    service = StaticDatasetReviewService(tmp_path)

    summary = generate_seed_batch(
        service,
        threshold=0.5,
        colormap="green",
    )

    assert summary["generated_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["queue_seed_count"] == 2
    assert summary["queue_training_eligible_count"] == 0
    assert all(item["review_state"] == "review_required" for item in summary["generated"])
    assert all(item["training_eligible"] is False for item in summary["generated"])
    assert Path(summary["seed_manifest_path"]).is_file()
    assert not Path(summary["reviewed_manifest_path"]).exists()

    rerun = generate_seed_batch(
        service,
        threshold=0.5,
        colormap="green",
    )
    assert rerun["generated_count"] == 0
    assert rerun["skipped_count"] == 2
    assert {item["reason"] for item in rerun["skipped"]} == {"seed_already_exists"}
