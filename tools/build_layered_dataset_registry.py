from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from osteo_vision_core.datasets.registry import (  # noqa: E402
    DatasetRecord,
    sha256_file,
    validate_registry,
    write_registry,
)

DEFAULT_VIDEO_LIBRARY = ROOT / "research/literature/inventory/video_library_manifest_20260704.csv"
DEFAULT_OFDVD = ROOT / "research/literature/inventory/ofdvdnet_video_manifest_20260704.csv"
DEFAULT_MULTIMASK = (
    ROOT / "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/"
    "video_signal_multimask_20260707/video_signal_multimask_training_manifest.csv"
)
DEFAULT_GROUPED_KEYFRAMES = (
    ROOT / "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/"
    "mp4_keyframe_segmentation_proxy_20260710_grouped/keyframe_segmentation_proxy_manifest.csv"
)
DEFAULT_PMC_FIGURES = (
    ROOT / "research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/"
    "pmc_jaw_fluorescence_figure_manifest.json"
)
DEFAULT_PMC_REVIEWED = (
    ROOT / "research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/derived/figure_review/"
    "pmc_figure_training_candidates.json"
)
DEFAULT_OPEN_CLINICAL_FIGURES = (
    ROOT / "research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/"
    "open_clinical_bone_fluorescence_manifest.json"
)
DEFAULT_OPEN_CLINICAL_REVIEWED = (
    ROOT / "research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/derived/figure_review/"
    "pmc_figure_training_candidates.json"
)
DEFAULT_STATIC_REVIEWED = ROOT / "research/datasets/public-candidates/d047_d048_static_figure_reviewed_manifest.json"
DEFAULT_STATIC_SEEDS = ROOT / "research/datasets/public-candidates/d047_d048_static_figure_seed_manifest.json"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/layered_registry_20260711"
)
DRYAD_URL = "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w"
DRYAD_DOWNLOAD_URL = "https://datadryad.org/downloads/file_stream/3078626"
OFDVD_BOUNDARY = "Mock chicken-thigh fluorescence-guided surgery proxy; no jaw osteomyelitis clinical labels."
OSTEOMYELITIS_BOUNDARY = "Public non-fluorescence osteomyelitis surgery video; no target-domain jaw ICG labels."
MULTIMASK_BOUNDARY = (
    "Proxy or prompt-assisted mask for engineering training; clinical ground-truth status is unavailable."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the layered dataset registry and run quality gates.")
    parser.add_argument("--video-library", type=Path, default=DEFAULT_VIDEO_LIBRARY)
    parser.add_argument("--ofdvd-manifest", type=Path, default=DEFAULT_OFDVD)
    parser.add_argument("--multimask-manifest", type=Path, default=DEFAULT_MULTIMASK)
    parser.add_argument("--grouped-keyframe-manifest", type=Path, default=DEFAULT_GROUPED_KEYFRAMES)
    parser.add_argument("--pmc-figure-manifest", type=Path, default=DEFAULT_PMC_FIGURES)
    parser.add_argument("--pmc-reviewed-manifest", type=Path, default=DEFAULT_PMC_REVIEWED)
    parser.add_argument(
        "--open-clinical-figure-manifest",
        type=Path,
        default=DEFAULT_OPEN_CLINICAL_FIGURES,
    )
    parser.add_argument(
        "--open-clinical-reviewed-manifest",
        type=Path,
        default=DEFAULT_OPEN_CLINICAL_REVIEWED,
    )
    parser.add_argument("--static-reviewed-manifest", type=Path, default=DEFAULT_STATIC_REVIEWED)
    parser.add_argument("--static-seed-manifest", type=Path, default=DEFAULT_STATIC_SEEDS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reuse-checksum-cache", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_records(
    *,
    video_library_path: Path,
    ofdvd_manifest_path: Path,
    multimask_manifest_path: Path,
    grouped_keyframe_manifest_path: Path | None = None,
    pmc_figure_manifest_path: Path | None = None,
    pmc_reviewed_manifest_path: Path | None = None,
    open_clinical_figure_manifest_path: Path | None = None,
    open_clinical_reviewed_manifest_path: Path | None = None,
    static_reviewed_manifest_path: Path | None = None,
    static_seed_manifest_path: Path | None = None,
    checksum_cache: dict[str, str] | None = None,
) -> tuple[list[DatasetRecord], list[dict[str, str]]]:
    cache = checksum_cache if checksum_cache is not None else {}
    videos = read_csv(video_library_path)
    ofdvd_by_path = {normalize_path(row.get("video_path")): row for row in read_csv(ofdvd_manifest_path)}
    grouped_splits = grouped_source_splits(grouped_keyframe_manifest_path)
    records: list[DatasetRecord] = []
    ingestion_issues: list[dict[str, str]] = []
    for row in videos:
        local_path = Path(str(row.get("local_path") or ""))
        if not local_path.is_file():
            ingestion_issues.append(
                {
                    "severity": "error",
                    "code": "quarantined_missing_source_file",
                    "record_id": f"video::{row.get('record_id')}",
                    "field": "local_path",
                    "message": str(local_path),
                }
            )
            continue
        records.append(
            video_record(
                row,
                ofdvd_by_path=ofdvd_by_path,
                checksum_cache=cache,
                preferred_splits=grouped_splits,
            )
        )
    mask_records, mask_issues = multimask_records(
        multimask_manifest_path,
        checksum_cache=cache,
        ofdvd_by_path=ofdvd_by_path,
        preferred_splits=grouped_splits,
        excluded_mask_types={"fluorescence_hotspot"} if grouped_splits else set(),
    )
    records.extend(mask_records)
    ingestion_issues.extend(mask_issues)
    grouped_records, grouped_issues = grouped_keyframe_records(
        grouped_keyframe_manifest_path,
        checksum_cache=cache,
    )
    records.extend(grouped_records)
    ingestion_issues.extend(grouped_issues)
    records.extend(pmc_figure_records(pmc_figure_manifest_path))
    records.extend(open_clinical_figure_records(open_clinical_figure_manifest_path))
    reviewed_records, reviewed_issues = pmc_reviewed_training_records(pmc_reviewed_manifest_path)
    records.extend(reviewed_records)
    ingestion_issues.extend(reviewed_issues)
    open_reviewed_records, open_reviewed_issues = pmc_reviewed_training_records(open_clinical_reviewed_manifest_path)
    records.extend(open_reviewed_records)
    ingestion_issues.extend(open_reviewed_issues)
    static_reviewed_records, static_reviewed_issues = pmc_reviewed_training_records(static_reviewed_manifest_path)
    existing_record_ids = {record.record_id for record in records}
    records.extend(record for record in static_reviewed_records if record.record_id not in existing_record_ids)
    ingestion_issues.extend(static_reviewed_issues)
    static_seed_records, static_seed_issues = static_review_seed_records(static_seed_manifest_path)
    reviewed_source_ids = {record.record_id.removeprefix("pmc_crop::") for record in static_reviewed_records}
    records.extend(
        record
        for record in static_seed_records
        if record.record_id.removeprefix("static_seed::") not in reviewed_source_ids
    )
    ingestion_issues.extend(static_seed_issues)
    return records, ingestion_issues


def video_record(
    row: dict[str, str],
    *,
    ofdvd_by_path: dict[str, dict[str, str]],
    checksum_cache: dict[str, str],
    preferred_splits: dict[str, str] | None = None,
) -> DatasetRecord:
    local_path = Path(str(row.get("local_path") or ""))
    group = str(row.get("group") or "")
    is_ofdvd = group in {"fluorescence_proxy", "fluorescence_proxy_ofdvdnet"}
    detailed = ofdvd_by_path.get(normalize_path(local_path), {})
    source_id = "D046_OFDVDNET" if is_ofdvd else str(row.get("record_id") or group)
    source_url = str(row.get("source_page_original_link") or (DRYAD_URL if is_ofdvd else ""))
    checksum = checksum_for(local_path, supplied=str(row.get("sha256") or ""), cache=checksum_cache)
    split = (
        str((preferred_splits or {}).get(normalize_path(local_path)) or detailed.get("split") or "") if is_ofdvd else ""
    )
    return DatasetRecord(
        record_id=f"video::{row.get('record_id')}",
        source_id=source_id,
        source_url=source_url,
        direct_download_url=str(row.get("direct_download_link") or (DRYAD_DOWNLOAD_URL if is_ofdvd else "")),
        local_path=str(local_path),
        label_path="",
        medical_scene=str(row.get("medical_scene") or "unknown surgical video"),
        fluorescence=normalize_fluorescence(row.get("fluorescence")),
        domain_tier="fluorescence_proxy" if is_ofdvd else "near_domain",
        label_type="none",
        review_state="unlabeled",
        sample_weight=1.0,
        target_domain_flag=False,
        license=(
            "CC0-1.0 (Dryad record; redistribution terms should be rechecked)"
            if is_ofdvd
            else "source terms require verification"
        ),
        checksum=checksum,
        split=split,
        group_id=normalize_path(local_path) if is_ofdvd else str(row.get("record_id") or source_id),
        artifact_role="source_video",
        medical_boundary=OFDVD_BOUNDARY if is_ofdvd else OSTEOMYELITIS_BOUNDARY,
        usage_policy="engineering_source_reference",
        training_eligible=False,
        sampling_weight=1.0,
    )


def multimask_records(
    manifest_path: Path,
    *,
    checksum_cache: dict[str, str],
    ofdvd_by_path: dict[str, dict[str, str]],
    preferred_splits: dict[str, str] | None = None,
    excluded_mask_types: set[str] | None = None,
) -> tuple[list[DatasetRecord], list[dict[str, str]]]:
    records: list[DatasetRecord] = []
    ingestion_issues: list[dict[str, str]] = []
    split_preferences = preferred_splits or {}
    excluded = excluded_mask_types or set()
    for row in read_csv(manifest_path):
        if str(row.get("mask_type") or "") in excluded:
            continue
        local_path = Path(str(row.get("image_path") or ""))
        label_path = Path(str(row.get("mask_path") or ""))
        record_id = f"mask::{row.get('case_id')}"
        if not local_path.is_file() or not label_path.is_file():
            ingestion_issues.append(
                {
                    "severity": "error",
                    "code": "quarantined_missing_training_artifact",
                    "record_id": record_id,
                    "field": "local_path" if not local_path.is_file() else "label_path",
                    "message": str(local_path if not local_path.is_file() else label_path),
                }
            )
            continue
        source_video = normalize_path(row.get("source_video_path"))
        is_ofdvd = "ofdvdnet" in source_video
        review_state = str(row.get("review_state") or "review_required").lower()
        label_source = str(row.get("label_source") or "")
        label_type = (
            "prompt_assisted_mask"
            if "review" in label_source or review_state in {"accepted", "modified", "rejected"}
            else "proxy_mask"
        )
        source_id = "D046_OFDVDNET_DERIVED" if is_ofdvd else "D046_PROMPT_ASSISTED_DERIVED"
        return_url = DRYAD_URL if is_ofdvd else source_url_from_manifest(row.get("source_manifest_path"))
        original_split = str(row.get("split") or "")
        canonical_split = canonical_split_for_group(
            source_video,
            preferred=str(
                split_preferences.get(source_video) or ofdvd_by_path.get(source_video, {}).get("split") or ""
            ),
        )
        if original_split and original_split != canonical_split:
            ingestion_issues.append(
                {
                    "severity": "warning",
                    "code": "source_split_reassigned_by_group",
                    "record_id": record_id,
                    "field": "split",
                    "message": f"original={original_split}; canonical={canonical_split}; group={source_video}",
                }
            )
        records.append(
            DatasetRecord(
                record_id=record_id,
                source_id=source_id,
                source_url=return_url,
                direct_download_url=DRYAD_DOWNLOAD_URL if is_ofdvd else "",
                local_path=str(local_path),
                label_path=str(label_path),
                medical_scene=(
                    "mock chicken-thigh fluorescence-guided surgery derived keyframe"
                    if is_ofdvd
                    else "prompt-assisted non-target-domain surgical keyframe"
                ),
                fluorescence="yes" if is_ofdvd else "unknown",
                domain_tier="derived_proxy",
                label_type=label_type,
                review_state=review_state,
                sample_weight=float(row.get("sample_weight") or 1.0),
                target_domain_flag=False,
                license=(
                    "CC0-1.0 Dryad source; derived proxy mask retains attribution and medical boundary"
                    if is_ofdvd
                    else "derived artifact; upstream source terms require verification"
                ),
                checksum=checksum_for(local_path, supplied="", cache=checksum_cache),
                label_checksum=checksum_for(label_path, supplied="", cache=checksum_cache),
                split=canonical_split,
                group_id=str(
                    row.get("source_group_id") or row.get("source_video_path") or row.get("source_case_id") or ""
                ),
                artifact_role=f"training_keyframe::{row.get('mask_type')}",
                medical_boundary=str(row.get("medical_boundary") or MULTIMASK_BOUNDARY),
                usage_policy="proxy_training_allowed_with_boundary",
                training_eligible=review_state != "rejected",
                sampling_weight=1.0,
            )
        )
    return records, ingestion_issues


def grouped_source_splits(manifest_path: Path | None) -> dict[str, str]:
    if manifest_path is None or not manifest_path.is_file():
        return {}
    grouped: dict[str, set[str]] = {}
    for row in read_csv(manifest_path):
        group_id = normalize_path(row.get("source_group_id") or row.get("source_path"))
        split = str(row.get("split") or "")
        if group_id and split in {"train", "val", "test"}:
            grouped.setdefault(group_id, set()).add(split)
    return {group_id: next(iter(splits)) for group_id, splits in grouped.items() if len(splits) == 1}


def grouped_keyframe_records(
    manifest_path: Path | None,
    *,
    checksum_cache: dict[str, str],
) -> tuple[list[DatasetRecord], list[dict[str, str]]]:
    if manifest_path is None or not manifest_path.is_file():
        return [], []
    records: list[DatasetRecord] = []
    issues: list[dict[str, str]] = []
    for row in read_csv(manifest_path):
        image_path = Path(str(row.get("image_path") or ""))
        label_path = Path(str(row.get("mask_path") or ""))
        record_id = str(row.get("case_id") or image_path.stem)
        if not image_path.is_file() or not label_path.is_file():
            issues.append(
                {
                    "severity": "error",
                    "code": "quarantined_missing_grouped_keyframe_artifact",
                    "record_id": record_id,
                    "field": ("local_path" if not image_path.is_file() else "label_path"),
                    "message": str(image_path if not image_path.is_file() else label_path),
                }
            )
            continue
        group_id = normalize_path(row.get("source_group_id") or row.get("source_path"))
        records.append(
            DatasetRecord(
                record_id=f"grouped_hotspot::{record_id}",
                source_id="D046_OFDVDNET_GROUPED",
                source_url=DRYAD_URL,
                direct_download_url=DRYAD_DOWNLOAD_URL,
                local_path=str(image_path),
                label_path=str(label_path),
                medical_scene="mock chicken-thigh fluorescence-guided surgery grouped keyframe",
                fluorescence="yes",
                domain_tier="derived_proxy",
                label_type="proxy_mask",
                review_state="review_required",
                sample_weight=float(row.get("sample_weight") or 1.0),
                target_domain_flag=False,
                license="CC0-1.0 Dryad source; derived proxy mask retains attribution and medical boundary",
                checksum=checksum_for(image_path, supplied="", cache=checksum_cache),
                label_checksum=checksum_for(label_path, supplied="", cache=checksum_cache),
                split=str(row.get("split") or ""),
                group_id=group_id,
                artifact_role="training_keyframe::fluorescence_hotspot",
                medical_boundary=str(
                    row.get("medical_boundary")
                    or "Grouped fluorescence-intensity proxy mask; no target-domain clinical label."
                ),
                usage_policy="proxy_pretrain_only_with_boundary",
                training_eligible=True,
                sampling_weight=float(row.get("sample_weight") or 1.0),
            )
        )
    return records, issues


def static_review_seed_records(
    manifest_path: Path | None,
) -> tuple[list[DatasetRecord], list[dict[str, str]]]:
    if manifest_path is None or not manifest_path.is_file():
        return [], []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[DatasetRecord] = []
    issues: list[dict[str, str]] = []
    for row in payload.get("records") or []:
        if not isinstance(row, dict):
            continue
        image_path = Path(str(row.get("image_path") or row.get("local_path") or ""))
        label_path = Path(str(row.get("mask_path") or row.get("label_path") or ""))
        record_id = str(row.get("record_id") or row.get("source_record_id") or "")
        if not image_path.is_file() or not label_path.is_file():
            issues.append(
                {
                    "severity": "error",
                    "code": "quarantined_missing_static_seed_artifact",
                    "record_id": record_id,
                    "field": ("local_path" if not image_path.is_file() else "label_path"),
                    "message": str(image_path if not image_path.is_file() else label_path),
                }
            )
            continue
        dataset_id = str(row.get("dataset_id") or "static")
        scene = (
            "jaw fluorescence publication crop pending review"
            if dataset_id == "d047"
            else "clinical bone fluorescence publication crop pending review"
        )
        records.append(
            DatasetRecord(
                record_id=f"static_seed::{record_id}",
                source_id=str(row.get("source_id") or row.get("source_record_id") or record_id),
                source_url=str(row.get("source_url") or ""),
                direct_download_url=str(row.get("direct_download_url") or ""),
                local_path=str(image_path),
                label_path=str(label_path),
                medical_scene=scene,
                fluorescence="yes",
                domain_tier="near_domain",
                label_type=str(row.get("label_type") or "automated_seed_mask"),
                review_state="review_required",
                sample_weight=1.0,
                target_domain_flag=False,
                license=str(row.get("license") or "unknown"),
                checksum=str(row.get("checksum") or row.get("image_checksum") or sha256_file(image_path)).lower(),
                label_checksum=str(row.get("label_checksum") or sha256_file(label_path)).lower(),
                split="",
                group_id=str(row.get("source_group_id") or row.get("source_record_id") or record_id),
                artifact_role="review_seed::fluorescence_hotspot",
                medical_boundary=str(
                    row.get("medical_boundary")
                    or payload.get("medical_boundary")
                    or "Automated near-domain seed pending authorized review."
                ),
                usage_policy=str(row.get("usage_policy") or "review_required_no_training"),
                training_eligible=False,
                sampling_weight=float(row.get("sampling_weight") or 0.25),
            )
        )
    return records, issues


def pmc_figure_records(manifest_path: Path | None) -> list[DatasetRecord]:
    if manifest_path is None or not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[DatasetRecord] = []
    for row in payload.get("records") or []:
        if not isinstance(row, dict):
            continue
        local_path = Path(str(row.get("local_path") or ""))
        if not local_path.is_file():
            continue
        records.append(
            DatasetRecord(
                record_id=f"figure::{row.get('record_id')}",
                source_id=str(row.get("record_id") or row.get("pmcid") or "D047_PMC_FIGURE"),
                source_url=str(row.get("source_page_url") or ""),
                direct_download_url=str(row.get("asset_url") or row.get("package_url") or ""),
                local_path=str(local_path),
                label_path="",
                medical_scene=str(row.get("medical_scene") or "jaw fluorescence article figure"),
                fluorescence="yes",
                domain_tier="near_domain",
                label_type="none",
                review_state="unlabeled",
                sample_weight=1.0,
                target_domain_flag=False,
                license=str(row.get("license") or "unknown"),
                checksum=str(row.get("sha256") or sha256_file(local_path)).lower(),
                split="",
                group_id=str(row.get("pmcid") or row.get("record_id") or local_path),
                artifact_role="source_article_figure",
                medical_boundary=str(
                    row.get("data_boundary") or payload.get("medical_boundary") or "Near-domain figure."
                ),
                usage_policy=str(row.get("usage_policy") or "literature_reference_only"),
                training_eligible=False,
                sampling_weight=float(row.get("sample_weight") or 0.0),
            )
        )
    return records


def pmc_reviewed_training_records(
    manifest_path: Path | None,
) -> tuple[list[DatasetRecord], list[dict[str, str]]]:
    if manifest_path is None or not manifest_path.is_file():
        return [], []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[DatasetRecord] = []
    issues: list[dict[str, str]] = []
    for row in payload.get("records") or []:
        if not isinstance(row, dict) or not bool(row.get("training_eligible")):
            continue
        image_path = Path(str(row.get("local_path") or row.get("image_path") or ""))
        label_path = Path(str(row.get("label_path") or row.get("mask_path") or ""))
        record_id = str(row.get("record_id") or row.get("case_id") or "")
        if not image_path.is_file() or not label_path.is_file():
            issues.append(
                {
                    "severity": "error",
                    "code": "quarantined_missing_pmc_review_artifact",
                    "record_id": record_id,
                    "field": "local_path" if not image_path.is_file() else "label_path",
                    "message": str(image_path if not image_path.is_file() else label_path),
                }
            )
            continue
        records.append(
            DatasetRecord(
                record_id=f"pmc_crop::{record_id}",
                source_id=str(row.get("source_id") or record_id),
                source_url=str(row.get("source_url") or ""),
                direct_download_url=str(row.get("direct_download_url") or ""),
                local_path=str(image_path),
                label_path=str(label_path),
                medical_scene=str(row.get("medical_scene") or "jaw fluorescence reviewed publication crop"),
                fluorescence="yes",
                domain_tier="near_domain",
                label_type=str(row.get("label_type") or "prompt_assisted_mask"),
                review_state=str(row.get("review_state") or "review_required"),
                sample_weight=float(row.get("sample_weight") or 1.0),
                target_domain_flag=False,
                license=str(row.get("license") or "unknown"),
                checksum=str(row.get("checksum") or sha256_file(image_path)).lower(),
                label_checksum=str(row.get("label_checksum") or sha256_file(label_path)).lower(),
                split=str(row.get("split") or ""),
                group_id=str(row.get("group_id") or row.get("source_group_id") or row.get("source_id") or record_id),
                artifact_role="training_keyframe::fluorescence_hotspot",
                medical_boundary=str(
                    row.get("medical_boundary") or payload.get("data_boundary") or "Near-domain crop."
                ),
                usage_policy=str(row.get("usage_policy") or "training_allowed_by_license_with_attribution"),
                training_eligible=True,
                sampling_weight=float(row.get("sampling_weight") or 0.25),
            )
        )
    return records, issues


def open_clinical_figure_records(manifest_path: Path | None) -> list[DatasetRecord]:
    if manifest_path is None or not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[DatasetRecord] = []
    for row in payload.get("records") or []:
        if not isinstance(row, dict):
            continue
        local_path = Path(str(row.get("local_path") or ""))
        if not local_path.is_file():
            continue
        asset_role = str(row.get("asset_role") or "")
        domain_tier = "fluorescence_proxy" if "preclinical" in asset_role else "near_domain"
        records.append(
            DatasetRecord(
                record_id=f"d048_figure::{row.get('record_id')}",
                source_id=str(row.get("record_id") or row.get("pmcid") or "D048_FIGURE"),
                source_url=str(row.get("source_page_url") or ""),
                direct_download_url=str(row.get("asset_url") or row.get("package_url") or ""),
                local_path=str(local_path),
                label_path="",
                medical_scene=str(row.get("medical_scene") or "open clinical bone fluorescence article figure"),
                fluorescence="yes",
                domain_tier=domain_tier,
                label_type="none",
                review_state="unlabeled",
                sample_weight=1.0,
                target_domain_flag=False,
                license=str(row.get("license") or "unknown"),
                checksum=str(row.get("sha256") or sha256_file(local_path)).lower(),
                split="",
                group_id=str(row.get("pmcid") or row.get("record_id") or local_path),
                artifact_role="source_article_figure",
                medical_boundary=str(
                    row.get("data_boundary") or payload.get("medical_boundary") or "Near-domain figure."
                ),
                usage_policy=str(row.get("usage_policy") or "literature_reference_only"),
                training_eligible=False,
                sampling_weight=float(row.get("sample_weight") or 0.0),
            )
        )
    return records


def source_url_from_manifest(value: Any) -> str:
    normalized = str(value or "").lower()
    if "ofdvd" in normalized:
        return DRYAD_URL
    return "https://github.com/openmedlab/MedSAM2"


def checksum_for(path: Path, *, supplied: str, cache: dict[str, str]) -> str:
    normalized = normalize_path(path)
    supplied = supplied.strip().lower()
    if len(supplied) == 64:
        cache[normalized] = supplied
        return supplied
    cached = cache.get(normalized, "")
    if len(cached) == 64:
        return cached
    if not path.is_file():
        return ""
    checksum = sha256_file(path)
    cache[normalized] = checksum
    return checksum


def normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower()


def normalize_fluorescence(value: Any) -> str:
    normalized = str(value or "unknown").lower()
    return normalized if normalized in {"yes", "no"} else "unknown"


def canonical_split_for_group(group_id: str, *, preferred: str = "") -> str:
    if preferred in {"train", "val", "test"}:
        return preferred
    bucket = int(hashlib.sha256(group_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "val" if bucket == 0 else "train"


def load_checksum_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload.items()}


def write_outputs(
    output_dir: Path,
    records: list[DatasetRecord],
    quality: dict[str, Any],
    cache: dict[str, str],
    ingestion_issues: list[dict[str, str]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    registry_path = output_dir / "layered_dataset_registry.csv"
    quality_path = output_dir / "layered_dataset_quality_report.json"
    issue_path = output_dir / "layered_dataset_quality_issues.csv"
    write_registry(registry_path, records)
    payload = {
        "schema_version": "osteo-vision-layered-dataset-registry-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "registry_path": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "input_issue_count": len(ingestion_issues),
        "quarantined_count": sum(issue["code"].startswith("quarantined_") for issue in ingestion_issues),
        "split_reassignment_count": sum(
            issue["code"] == "source_split_reassigned_by_group" for issue in ingestion_issues
        ),
        "input_issues": ingestion_issues,
        **quality,
    }
    quality_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with issue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["severity", "code", "record_id", "field", "message"])
        writer.writeheader()
        writer.writerows([*ingestion_issues, *quality["issues"]])
    (output_dir / "checksum_cache.json").write_text(json.dumps(cache, indent=2), encoding="utf-8")
    report_dir = ROOT / "research/reports/modeling"
    (report_dir / "layered_dataset_registry_quality_20260711_zh.md").write_text(
        render_report(payload, language="zh"), encoding="utf-8"
    )
    (report_dir / "layered_dataset_registry_quality_20260711_en.md").write_text(
        render_report(payload, language="en"), encoding="utf-8"
    )


def render_report(payload: dict[str, Any], *, language: str) -> str:
    if language == "zh":
        lines = [
            "# 分层数据注册与质量门控报告",
            "",
            "## 结果",
            "",
            f"- 注册记录：{payload['record_count']}",
            f"- 质量门：{'通过' if payload['passed'] else '未通过'}",
            f"- 错误：{payload['error_count']}",
            f"- 警告：{payload['warning_count']}",
            f"- 目标域记录：{payload['target_domain_count']}",
            f"- 可进入训练准入检查的记录：{payload['training_eligible_count']}",
            f"- 隔离的缺失文件记录：{payload['quarantined_count']}",
            f"- 按 source group 重分配的泄漏风险行：{payload['split_reassignment_count']}",
            f"- 分层统计：`{json.dumps(payload['domain_tier_counts'], ensure_ascii=False)}`",
            f"- 标签统计：`{json.dumps(payload['label_type_counts'], ensure_ascii=False)}`",
            f"- 使用策略统计：`{json.dumps(payload['usage_policy_counts'], ensure_ascii=False)}`",
            "",
            "## 质量门范围",
            "",
            "来源链接与本地文件、SHA256、分组切分泄漏、重复内容、标签与复核状态、目标域标记、样本权重契约均纳入自动检查。",
            "缺失本地文件的源记录进入隔离清单。多 mask 原始 manifest 中跨组切分不一致的行已按原始视频组统一切分，并保留逐行修正记录。",
            "",
            "## 数据边界",
            "",
            "当前注册表包含 OFDVDnet 鸡腿模拟荧光手术视频、公开骨髓炎清创视频、颌骨荧光论文图及代理/半自动多 mask 样本。目标域记录数为 0。论文多面板原图只作为近域来源资产注册，不直接进入分割训练。所有训练指标均属于非目标域工程证据。",
            "",
            "## 后续使用",
            "",
            "训练候选应先通过本质量门。医生复核产生的 accepted/modified/rejected 状态需继续沿用 4.0/4.0/0.5 权重契约；review_required 保持 1.0。",
        ]
    else:
        lines = [
            "# Layered Dataset Registry and Quality Gate Report",
            "",
            "## Result",
            "",
            f"- Registered records: {payload['record_count']}",
            f"- Quality gate: {'passed' if payload['passed'] else 'failed'}",
            f"- Errors: {payload['error_count']}",
            f"- Warnings: {payload['warning_count']}",
            f"- Target-domain records: {payload['target_domain_count']}",
            f"- Records eligible for training admission checks: {payload['training_eligible_count']}",
            f"- Quarantined missing-file records: {payload['quarantined_count']}",
            f"- Rows reassigned by source group: {payload['split_reassignment_count']}",
            f"- Domain tiers: `{json.dumps(payload['domain_tier_counts'])}`",
            f"- Label types: `{json.dumps(payload['label_type_counts'])}`",
            f"- Usage policies: `{json.dumps(payload['usage_policy_counts'])}`",
            "",
            "## Gate Coverage",
            "",
            "The automated checks cover provenance URLs, local files, SHA256, group split leakage, duplicate content, label-review consistency, target-domain flags, and sample-weight contracts.",
            "Source rows with missing local files are quarantined. Multi-mask rows with inconsistent source-group splits are assigned a canonical video-level split, with every correction retained in the issue log.",
            "",
            "## Data Boundary",
            "",
            "The registry contains OFDVDnet mock chicken-thigh fluorescence videos, public osteomyelitis debridement videos, jaw-fluorescence article figures, and proxy or semi-automatic multi-mask samples. The target-domain count is zero. Raw multi-panel article figures are registered as near-domain source assets and do not directly enter segmentation training. Training metrics remain non-target-domain engineering evidence.",
            "",
            "## Operational Use",
            "",
            "Training candidates should pass this gate first. Doctor-reviewed accepted, modified, and rejected samples retain weights 4.0, 4.0, and 0.5; review_required remains 1.0.",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    cache_path = output_dir / "checksum_cache.json"
    cache = load_checksum_cache(cache_path) if args.reuse_checksum_cache else {}
    records, ingestion_issues = build_records(
        video_library_path=args.video_library.resolve(),
        ofdvd_manifest_path=args.ofdvd_manifest.resolve(),
        multimask_manifest_path=args.multimask_manifest.resolve(),
        grouped_keyframe_manifest_path=args.grouped_keyframe_manifest.resolve(),
        pmc_figure_manifest_path=args.pmc_figure_manifest.resolve(),
        pmc_reviewed_manifest_path=args.pmc_reviewed_manifest.resolve(),
        open_clinical_figure_manifest_path=args.open_clinical_figure_manifest.resolve(),
        open_clinical_reviewed_manifest_path=args.open_clinical_reviewed_manifest.resolve(),
        static_reviewed_manifest_path=args.static_reviewed_manifest.resolve(),
        static_seed_manifest_path=args.static_seed_manifest.resolve(),
        checksum_cache=cache,
    )
    quality = validate_registry(records)
    write_outputs(output_dir, records, quality, cache, ingestion_issues)
    print(
        json.dumps(
            {key: value for key, value in quality.items() if key != "issues"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if quality["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
