from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from tools.materialize_static_crop_suggestions import materialize_static_crop_suggestions


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_materializes_review_only_atomic_crops_and_complete_pairs(tmp_path: Path) -> None:
    dataset_root = tmp_path / "d048_open_clinical_bone_fluorescence"
    source_path = dataset_root / "raw/PMC1/figure.jpg"
    source_path.parent.mkdir(parents=True)
    Image.new("RGB", (240, 100), color=(40, 60, 80)).save(source_path)
    rows = []
    for label, role, x in (("A", "paired_white_light", 0), ("B", "paired_fluorescence", 120)):
        rows.append(
            {
                "dataset_id": "d048",
                "record_id": f"review_PMC1_panel_{label.lower()}",
                "parent_record_id": "review_PMC1",
                "source_group_id": "PMC1",
                "source_image_path": str(source_path),
                "source_checksum": _sha256(source_path),
                "panel_label": label,
                "suggested_crop_bbox": {"x": x, "y": 0, "width": 120, "height": 100},
                "suggested_panel_role": role,
                "suggested_pair_id": "PMC1_pair",
                "suggested_pair_alignment": "approximate_view",
                "review_state": "review_required",
                "training_eligible": False,
            }
        )
    input_path = tmp_path / "suggestions.json"
    output_path = tmp_path / "paired.json"
    input_path.write_text(json.dumps({"records": rows}), encoding="utf-8")

    result = materialize_static_crop_suggestions(input_path, output_path)

    assert result["atomic_record_count"] == 2
    assert result["pair_count"] == 1
    assert result["training_eligible_count"] == 0
    pair = result["pairs"][0]
    assert pair["pair_alignment"] == "approximate_view"
    assert pair["pixel_registration_supervision_allowed"] is False
    assert pair["stress_evaluation_eligible"] is True
    assert Path(pair["white_image_path"]).is_file()
    assert Path(pair["fluorescence_image_path"]).is_file()
    assert all(record["review_state"] == "review_required" for record in result["atomic_records"])


def test_sequence_without_white_light_is_not_promoted_to_dual_channel_pair(tmp_path: Path) -> None:
    dataset_root = tmp_path / "d047_pmc_jaw_fluorescence_figures"
    source_path = dataset_root / "raw/PMC2/figure.jpg"
    source_path.parent.mkdir(parents=True)
    Image.new("RGB", (200, 100), color=(20, 40, 60)).save(source_path)
    rows = [
        {
            "dataset_id": "d047",
            "record_id": f"review_PMC2_panel_{label.lower()}",
            "source_group_id": "PMC2",
            "source_image_path": str(source_path),
            "source_checksum": _sha256(source_path),
            "suggested_crop_bbox": {"x": index * 100, "y": 0, "width": 100, "height": 100},
            "suggested_panel_role": "fluorescence_signal",
            "suggested_pair_id": "PMC2_sequence",
            "suggested_pair_alignment": "sequential",
        }
        for index, label in enumerate(("A", "B"))
    ]
    input_path = tmp_path / "suggestions.json"
    output_path = tmp_path / "paired.json"
    input_path.write_text(json.dumps({"records": rows}), encoding="utf-8")

    result = materialize_static_crop_suggestions(input_path, output_path)

    assert result["pair_count"] == 0
    assert result["incomplete_pair_ids"] == ["PMC2_sequence"]
