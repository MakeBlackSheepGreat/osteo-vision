from __future__ import annotations

import csv
import json
from pathlib import Path

from osteo_vision_core.datasets.registry import DatasetRecord, sha256_file, validate_registry
from tools.build_layered_dataset_registry import (
    build_records,
    canonical_split_for_group,
    open_clinical_figure_records,
    pmc_figure_records,
    pmc_reviewed_training_records,
)


def make_record(path: Path, **overrides: object) -> DatasetRecord:
    values: dict[str, object] = {
        "record_id": "r1",
        "source_id": "source-1",
        "source_url": "https://example.org/source",
        "direct_download_url": "",
        "local_path": str(path),
        "label_path": "",
        "medical_scene": "public osteomyelitis debridement",
        "fluorescence": "no",
        "domain_tier": "near_domain",
        "label_type": "none",
        "review_state": "unlabeled",
        "sample_weight": 1.0,
        "target_domain_flag": False,
        "license": "CC-BY-4.0",
        "checksum": sha256_file(path),
        "split": "train",
        "group_id": "group-1",
        "artifact_role": "source_video",
        "medical_boundary": "Non-target-domain public evidence.",
        "usage_policy": "proxy_training_allowed_with_boundary",
        "training_eligible": False,
        "sampling_weight": 1.0,
    }
    values.update(overrides)
    return DatasetRecord(**values)  # type: ignore[arg-type]


def test_valid_registry_passes(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"sample")
    report = validate_registry([make_record(sample)], verify_checksums=True)
    assert report["passed"] is True
    assert report["error_count"] == 0


def test_detects_group_and_sha_leakage(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"duplicate")
    records = [
        make_record(sample, record_id="train", split="train"),
        make_record(sample, record_id="test", split="test"),
    ]
    report = validate_registry(records)
    codes = {issue["code"] for issue in report["issues"]}
    assert "cross_split_group_leakage" in codes
    assert "duplicate_sha_cross_split" in codes
    assert report["passed"] is False


def test_detects_review_weight_and_target_domain_conflicts(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    mask = tmp_path / "mask.png"
    image.write_bytes(b"image")
    mask.write_bytes(b"mask")
    record = make_record(
        image,
        label_path=str(mask),
        label_type="proxy_mask",
        review_state="accepted",
        sample_weight=1.0,
        target_domain_flag=True,
        domain_tier="derived_proxy",
    )
    report = validate_registry([record])
    codes = {issue["code"] for issue in report["issues"]}
    assert "sample_weight_contract_violation" in codes
    assert "target_domain_mislabel" in codes


def test_detects_missing_files_and_unlabeled_conflict(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    record = DatasetRecord(
        record_id="missing",
        source_id="source",
        source_url="https://example.org/source",
        direct_download_url="",
        local_path=str(missing),
        label_path="missing-mask.png",
        medical_scene="proxy scene",
        fluorescence="unknown",
        domain_tier="derived_proxy",
        label_type="none",
        review_state="review_required",
        sample_weight=1.0,
        target_domain_flag=False,
        license="unknown",
        checksum="",
        split="train",
        group_id="group",
        artifact_role="source_video",
        medical_boundary="Proxy data.",
    )
    report = validate_registry([record])
    codes = {issue["code"] for issue in report["issues"]}
    assert {
        "missing_local_file",
        "invalid_or_missing_sha256",
        "unlabeled_record_has_label_path",
    } <= codes


def test_canonical_split_is_stable_and_honors_preferred_split() -> None:
    assert canonical_split_for_group("video-a") == canonical_split_for_group("video-a")
    assert canonical_split_for_group("video-a", preferred="test") == "test"


def test_blocks_no_derivatives_training_and_flags_verification_license(
    tmp_path: Path,
) -> None:
    image = tmp_path / "figure.jpg"
    image.write_bytes(b"figure")
    record = make_record(
        image,
        license="CC BY-NC-ND; source terms require verification",
        usage_policy="reference_only_no_derivatives",
        training_eligible=True,
    )
    report = validate_registry([record])
    codes = {issue["code"] for issue in report["issues"]}
    assert "training_forbidden_by_usage_policy" in codes
    assert "license_requires_verification" in codes


def test_pmc_figure_manifest_maps_to_unlabeled_near_domain_source(
    tmp_path: Path,
) -> None:
    image = tmp_path / "figure.jpg"
    image.write_bytes(b"figure")
    manifest = tmp_path / "pmc.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "PMC1_figure_2",
                        "pmcid": "PMC1",
                        "source_page_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
                        "asset_url": "https://cdn.example/figure.jpg",
                        "local_path": str(image),
                        "medical_scene": "mandibular osteomyelitis fluorescence",
                        "license": "CC BY",
                        "sha256": sha256_file(image),
                        "usage_policy": "weak_label_training_seed_with_attribution",
                        "sample_weight": 0.25,
                        "data_boundary": "Multi-panel article figure without pixel labels.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    records = pmc_figure_records(manifest)
    assert len(records) == 1
    assert records[0].domain_tier == "near_domain"
    assert records[0].label_type == "none"
    assert records[0].review_state == "unlabeled"
    assert records[0].training_eligible is False
    assert records[0].sampling_weight == 0.25
    assert validate_registry(records)["passed"] is True


def test_pmc_reviewed_crop_maps_to_training_eligible_registry_record(
    tmp_path: Path,
) -> None:
    image = tmp_path / "crop.png"
    mask = tmp_path / "mask.png"
    image.write_bytes(b"crop")
    mask.write_bytes(b"mask")
    manifest = tmp_path / "reviewed.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "d047_PMC1_figure_2_crop",
                        "local_path": str(image),
                        "label_path": str(mask),
                        "source_id": "PMC1_figure_2",
                        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
                        "direct_download_url": "https://cdn.example/figure.jpg",
                        "medical_scene": "mandibular osteomyelitis fluorescence",
                        "label_type": "human_reviewed_mask",
                        "review_state": "modified",
                        "sample_weight": 4.0,
                        "sampling_weight": 0.25,
                        "license": "CC BY",
                        "checksum": sha256_file(image),
                        "split": "train",
                        "group_id": "PMC1",
                        "usage_policy": "training_allowed_by_license_with_attribution",
                        "training_eligible": True,
                        "medical_boundary": "Near-domain reviewed crop.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    records, issues = pmc_reviewed_training_records(manifest)
    assert issues == []
    assert len(records) == 1
    assert records[0].group_id == "PMC1"
    assert records[0].sample_weight == 4.0
    assert records[0].sampling_weight == 0.25
    assert records[0].training_eligible is True
    assert validate_registry(records)["passed"] is True


def test_layered_registry_ingests_unified_static_review_manifest(
    tmp_path: Path,
) -> None:
    image = tmp_path / "crop.png"
    mask = tmp_path / "mask.png"
    image.write_bytes(b"reviewed crop")
    mask.write_bytes(b"reviewed mask")
    reviewed_manifest = tmp_path / "static_reviewed.json"
    reviewed_manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "review_PMC1_figure_2",
                        "image_path": str(image),
                        "mask_path": str(mask),
                        "source_record_id": "PMC1_figure_2",
                        "source_group_id": "PMC1",
                        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
                        "review_state": "accepted",
                        "sample_weight": 4.0,
                        "sampling_weight": 0.25,
                        "license": "CC BY 4.0",
                        "usage_policy": "weak_label_training_seed_with_attribution",
                        "training_eligible": True,
                        "checksum": sha256_file(image),
                        "label_checksum": sha256_file(mask),
                        "label_type": "human_reviewed_mask",
                        "medical_boundary": "Near-domain project-reviewed publication crop.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    records, issues = build_records(
        video_library_path=empty_csv,
        ofdvd_manifest_path=empty_csv,
        multimask_manifest_path=empty_csv,
        static_reviewed_manifest_path=reviewed_manifest,
    )

    assert issues == []
    assert len(records) == 1
    assert records[0].record_id == "pmc_crop::review_PMC1_figure_2"
    assert records[0].group_id == "PMC1"
    assert records[0].training_eligible is True


def test_d048_preclinical_and_human_figures_map_to_separate_domain_tiers(
    tmp_path: Path,
) -> None:
    human = tmp_path / "human.jpg"
    animal = tmp_path / "animal.jpg"
    human.write_bytes(b"human")
    animal.write_bytes(b"animal")
    manifest = tmp_path / "d048.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "human_figure",
                        "pmcid": "PMC_HUMAN",
                        "source_page_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC_HUMAN/",
                        "asset_url": "https://cdn.example/human.jpg",
                        "local_path": str(human),
                        "medical_scene": "human jaw fluorescence surgery",
                        "asset_role": "human_clinical_jaw_surgery",
                        "license": "CC BY",
                        "sha256": sha256_file(human),
                        "usage_policy": "jaw_clinical_weak_label_seed_after_panel_crop_and_review",
                        "sample_weight": 0.3,
                    },
                    {
                        "record_id": "animal_figure",
                        "pmcid": "PMC_ANIMAL",
                        "source_page_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC_ANIMAL/",
                        "asset_url": "https://cdn.example/animal.jpg",
                        "local_path": str(animal),
                        "medical_scene": "minipig jaw fluorescence",
                        "asset_role": "preclinical_jaw_proxy",
                        "license": "CC BY",
                        "sha256": sha256_file(animal),
                        "usage_policy": "preclinical_proxy_seed_after_panel_crop_and_review",
                        "sample_weight": 0.1,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    records = open_clinical_figure_records(manifest)
    assert {record.source_id: record.domain_tier for record in records} == {
        "human_figure": "near_domain",
        "animal_figure": "fluorescence_proxy",
    }
    assert validate_registry(records)["passed"] is True


def test_grouped_keyframes_replace_old_hotspots_and_align_source_split(
    tmp_path: Path,
) -> None:
    source_group = str(tmp_path / "source.mp4").replace("\\", "/").lower()
    grouped_csv = tmp_path / "grouped.csv"
    grouped_rows = []
    for index in range(2):
        image = tmp_path / f"grouped_{index}.jpg"
        mask = tmp_path / f"grouped_{index}_mask.png"
        image.write_bytes(f"image-{index}".encode())
        mask.write_bytes(f"mask-{index}".encode())
        grouped_rows.append(
            {
                "case_id": f"grouped_{index}",
                "image_path": str(image),
                "mask_path": str(mask),
                "split": "val",
                "source_path": source_group,
                "source_group_id": source_group,
                "sample_weight": "1.0",
            }
        )
    with grouped_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(grouped_rows[0]))
        writer.writeheader()
        writer.writerows(grouped_rows)

    multi_image = tmp_path / "multi.jpg"
    hotspot_mask = tmp_path / "hotspot.png"
    boundary_mask = tmp_path / "boundary.png"
    multi_image.write_bytes(b"multi")
    hotspot_mask.write_bytes(b"hotspot")
    boundary_mask.write_bytes(b"boundary")
    multimask_csv = tmp_path / "multimask.csv"
    multimask_rows = [
        {
            "case_id": "old_hotspot",
            "image_path": str(multi_image),
            "mask_path": str(hotspot_mask),
            "mask_type": "fluorescence_hotspot",
            "review_state": "review_required",
            "source_video_path": source_group,
            "split": "train",
        },
        {
            "case_id": "boundary",
            "image_path": str(multi_image),
            "mask_path": str(boundary_mask),
            "mask_type": "boundary_risk",
            "review_state": "review_required",
            "source_video_path": source_group,
            "split": "train",
        },
    ]
    with multimask_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(multimask_rows[0]))
        writer.writeheader()
        writer.writerows(multimask_rows)
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")

    records, issues = build_records(
        video_library_path=empty,
        ofdvd_manifest_path=empty,
        multimask_manifest_path=multimask_csv,
        grouped_keyframe_manifest_path=grouped_csv,
    )

    assert len(records) == 3
    assert sum(record.artifact_role.endswith("fluorescence_hotspot") for record in records) == 2
    assert {record.split for record in records} == {"val"}
    assert not any(issue["severity"] == "error" for issue in issues)
    assert validate_registry(records)["passed"] is True


def test_static_automated_seed_is_registered_without_training_eligibility(
    tmp_path: Path,
) -> None:
    image = tmp_path / "crop.png"
    mask = tmp_path / "seed.png"
    image.write_bytes(b"crop")
    mask.write_bytes(b"seed")
    seed_manifest = tmp_path / "seed.json"
    seed_manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "review_PMC1_figure_2",
                        "dataset_id": "d047",
                        "source_record_id": "PMC1_figure_2",
                        "source_group_id": "PMC1",
                        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
                        "image_path": str(image),
                        "mask_path": str(mask),
                        "license": "CC BY 4.0",
                        "usage_policy": "weak_label_training_seed_with_attribution",
                        "checksum": sha256_file(image),
                        "label_checksum": sha256_file(mask),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")

    records, issues = build_records(
        video_library_path=empty,
        ofdvd_manifest_path=empty,
        multimask_manifest_path=empty,
        static_seed_manifest_path=seed_manifest,
    )

    assert issues == []
    assert len(records) == 1
    assert records[0].record_id == "static_seed::review_PMC1_figure_2"
    assert records[0].review_state == "review_required"
    assert records[0].training_eligible is False
    assert validate_registry(records)["passed"] is True
