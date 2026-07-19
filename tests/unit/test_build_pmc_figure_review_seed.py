from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from src.datasets.registry import record_from_row, validate_registry
from tools.build_pmc_figure_review_seed import (
    apply_review_updates,
    build_review_records,
    load_review_updates,
)


def _record(record_id: str, pmcid: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "record_id": record_id,
        "pmcid": pmcid,
        "caption": "clinical and fluorescence panels",
        "license": "CC BY",
        "usage_policy": "weak_label_training_seed_with_attribution",
        "training_seed_allowed": True,
        "local_path": f"raw/{pmcid}/{record_id}.jpg",
        "sample_weight": 0.25,
    }
    record.update(overrides)
    return record


def test_reference_nd_and_schematic_records_are_excluded() -> None:
    rows = build_review_records(
        [
            _record("usable", "PMC1"),
            _record("nd", "PMC2", usage_policy="reference_only_no_derivatives"),
            _record(
                "schematic",
                "PMC3",
                usage_policy="literature_reference_only",
                training_seed_allowed=False,
            ),
        ]
    )
    assert [row["source_record_id"] for row in rows] == ["usable"]


def test_unreviewed_figure_has_no_crop_mask_or_training_permission() -> None:
    row = build_review_records([_record("figure_2", "PMC10")])[0]
    assert row["crop_bbox"] is None
    assert row["cropped_image_path"] is None
    assert row["mask_path"] is None
    assert row["training_eligible"] is False
    assert row["sample_weight"] == 1.0
    assert row["sampling_weight"] == 0.25


def test_pmcid_is_the_source_group_id() -> None:
    rows = build_review_records([_record("figure_2", "PMC10"), _record("figure_3", "PMC10")])
    assert {row["source_group_id"] for row in rows} == {"PMC10"}


def _reviewable_source(tmp_path: Path, *, record_id: str = "figure_2", pmcid: str = "PMC10") -> dict[str, object]:
    image_path = tmp_path / f"{record_id}.png"
    Image.new("RGB", (100, 80), (30, 60, 90)).save(image_path)
    return _record(
        record_id,
        pmcid,
        local_path=str(image_path),
        source_page_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        asset_url=f"https://cdn.example.test/{record_id}.png",
        sha256="0" * 64,
        medical_scene="jaw_osteonecrosis_autofluorescence_surgery",
        fluorescence="bone_autofluorescence_blue_light",
    )


def test_accepted_crop_and_nonempty_mask_are_promoted_with_provenance(tmp_path: Path) -> None:
    records = build_review_records([_reviewable_source(tmp_path)])
    source_mask = np.zeros((80, 100), dtype=np.uint8)
    source_mask[20:50, 30:70] = 255
    source_mask_path = tmp_path / "source_mask.png"
    Image.fromarray(source_mask).save(source_mask_path)
    update_path = tmp_path / "updates.json"
    update_path.write_text("{}", encoding="utf-8")

    updated, training, skipped = apply_review_updates(
        records,
        [
            {
                "record_id": "figure_2",
                "crop_bbox": [20, 10, 80, 60],
                "review_state": "accepted",
                "panel_role": "fluorescence_signal",
                "mask_path": str(source_mask_path),
            }
        ],
        output_dir=tmp_path / "derived",
        review_update_path=update_path,
    )

    assert skipped == []
    assert updated[0]["training_eligible"] is True
    assert Path(updated[0]["cropped_image_path"]).is_file()
    assert Path(updated[0]["mask_path"]).is_file()
    row = training[0]
    assert row["source_group_id"] == "PMC10"
    assert row["domain_tier"] == "near_domain"
    assert row["sample_weight"] == 4.0
    assert row["sampling_weight"] == 0.25
    assert row["license"] == "CC BY"
    assert len(row["checksum"]) == 64
    quality = validate_registry([record_from_row(row)], verify_checksums=True)
    assert quality["passed"] is True


def test_prompt_polygon_can_create_prompt_assisted_mask(tmp_path: Path) -> None:
    records = build_review_records([_reviewable_source(tmp_path)])
    update_path = tmp_path / "updates.csv"
    update_path.write_text("record_id\nfigure_2\n", encoding="utf-8")
    _updated, training, skipped = apply_review_updates(
        records,
        [
            {
                "record_id": "review_figure_2",
                "crop_bbox": {"x": 0.2, "y": 0.25, "width": 0.6, "height": 0.5, "coordinate_space": "normalized"},
                "review_state": "modified",
                "panel_role": "bone_autofluorescence",
                "prompt_info": {
                    "coordinate_space": "normalized_crop",
                    "polygon": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
                },
            }
        ],
        output_dir=tmp_path / "derived",
        review_update_path=update_path,
    )
    assert skipped == []
    assert training[0]["label_type"] == "prompt_assisted_mask"
    assert float(training[0]["positive_area_fraction"]) > 0


def test_crop_without_mask_or_prompt_stays_ineligible(tmp_path: Path) -> None:
    records = build_review_records([_reviewable_source(tmp_path)])
    update_path = tmp_path / "updates.json"
    update_path.write_text("{}", encoding="utf-8")
    updated, training, skipped = apply_review_updates(
        records,
        [{"record_id": "figure_2", "crop_bbox": [0, 0, 50, 50], "review_state": "accepted"}],
        output_dir=tmp_path / "derived",
        review_update_path=update_path,
    )
    assert training == []
    assert updated[0]["training_eligible"] is False
    assert skipped[0]["reason"] == "missing_mask_or_rasterizable_prompt"


def test_review_updates_load_json_and_csv(tmp_path: Path) -> None:
    json_path = tmp_path / "updates.json"
    json_path.write_text(json.dumps({"records": [{"record_id": "a"}]}), encoding="utf-8")
    csv_path = tmp_path / "updates.csv"
    csv_path.write_text("record_id,review_state\nb,accepted\n", encoding="utf-8")
    assert load_review_updates(json_path)[0]["record_id"] == "a"
    assert load_review_updates(csv_path)[0]["record_id"] == "b"


def test_pathology_panel_cannot_enter_fluorescence_segmentation_training(tmp_path: Path) -> None:
    records = build_review_records([_reviewable_source(tmp_path)])
    update_path = tmp_path / "updates.json"
    update_path.write_text("{}", encoding="utf-8")
    _updated, training, skipped = apply_review_updates(
        records,
        [
            {
                "record_id": "figure_2",
                "crop_bbox": [0, 0, 100, 80],
                "review_state": "accepted",
                "panel_role": "histopathology",
                "prompt_info": {"coordinate_space": "crop_pixels", "bbox": [10, 10, 50, 50]},
            }
        ],
        output_dir=tmp_path / "derived",
        review_update_path=update_path,
    )
    assert training == []
    assert skipped[-1]["reason"] == "panel_role_not_trainable:histopathology"


def test_same_pmcid_crops_keep_one_split(tmp_path: Path) -> None:
    sources = [
        _reviewable_source(tmp_path, record_id="figure_2", pmcid="PMC_SHARED"),
        _reviewable_source(tmp_path, record_id="figure_3", pmcid="PMC_SHARED"),
    ]
    records = build_review_records(sources)
    update_path = tmp_path / "updates.json"
    update_path.write_text("{}", encoding="utf-8")
    updates = [
        {
            "record_id": source["record_id"],
            "crop_bbox": [0, 0, 100, 80],
            "review_state": "modified",
            "panel_role": "fluorescence_signal",
            "prompt_info": {"coordinate_space": "crop_pixels", "bbox": [10, 10, 50, 50]},
        }
        for source in sources
    ]
    _updated, training, skipped = apply_review_updates(
        records,
        updates,
        output_dir=tmp_path / "derived",
        review_update_path=update_path,
    )
    assert skipped == []
    assert {row["source_group_id"] for row in training} == {"PMC_SHARED"}
    assert len({row["split"] for row in training}) == 1
