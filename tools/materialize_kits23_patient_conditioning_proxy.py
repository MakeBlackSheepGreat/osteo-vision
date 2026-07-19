"""Materialize the bounded five-patient KiTS23 conditioning proxy dataset.

The generated slices are public abdominal CT proxies. The second image channel
is derived from the same CT and carries no fluorescence information. Outputs
are eligible only for non-target proxy pretraining and cannot promote a runtime
model or support jaw-osteomyelitis clinical claims.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import nibabel as nib
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_MANIFEST = (
    ROOT / "research/datasets/public-candidates/patient_conditioning_starter_20260717/"
    "patient_conditioning_starter_manifest.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "artifacts/patient_conditioned_kits23_proxy/data"

DATASET_ID = "D071"
DATASET_NAME = "KiTS23 patient conditioning starter"
LICENSE = "CC BY-NC-SA 4.0"
DOMAIN_TIER = "kits23_abdominal_ct_public_proxy"
TRAINING_SCOPE = "non_target_proxy_pretraining"
TRAINING_ELIGIBILITY_SCOPE = "proxy_pretraining_only"
CHANNEL_SEMANTICS = "non_fluorescence_ct_proxy"
FEATURE_NAMES = (
    "age_years",
    "sex_at_birth_female",
    "diabetes",
    "renal_disease",
    "egfr_ml_min_1_73m2",
)
CASE_SPLITS = {
    "case_00000": "train",
    "case_00001": "val",
    "case_00002": "train",
    "case_00003": "train",
    "case_00004": "test",
}
ALLOWED_LABELS = frozenset({0, 1, 2, 3})
RGB_WINDOWS: tuple[dict[str, float | str], ...] = (
    {"channel": "R", "name": "soft_tissue", "center_hu": 40.0, "width_hu": 400.0},
    {"channel": "G", "name": "renal_contrast", "center_hu": 100.0, "width_hu": 300.0},
    {"channel": "B", "name": "wide_ct", "center_hu": 300.0, "width_hu": 1800.0},
)
AUXILIARY_WINDOW: dict[str, float | str] = {
    "name": CHANNEL_SEMANTICS,
    "center_hu": 40.0,
    "width_hu": 400.0,
}
MEDICAL_SAFETY_BOUNDARY = (
    "Public non-jaw abdominal CT with kidney, tumor and cyst labels. The paired "
    "auxiliary channel is CT-derived and contains no fluorescence signal. These "
    "artifacts support proxy pretraining and data-contract validation only; they "
    "cannot validate patient-adaptive jaw-osteomyelitis segmentation, bone "
    "viability classification, intraoperative ICG performance, or clinical use."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--foreground-slices", type=int, default=8)
    parser.add_argument("--background-slices", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = materialize_kits23_patient_conditioning_proxy(
            source_manifest=args.source_manifest,
            output_dir=args.output_dir,
            foreground_slice_count=int(args.foreground_slices),
            background_slice_count=int(args.background_slices),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed_closed",
                    "dataset_id": DATASET_ID,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "target_domain": False,
                    "runtime_replacement_allowed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def materialize_kits23_patient_conditioning_proxy(
    *,
    source_manifest: str | Path,
    output_dir: str | Path,
    case_splits: Mapping[str, str] | None = None,
    foreground_slice_count: int = 8,
    background_slice_count: int = 2,
) -> dict[str, Any]:
    """Validate, join and materialize KiTS23 proxy slices and provenance."""

    manifest_path = Path(source_manifest).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    split_assignment = dict(case_splits or CASE_SPLITS)
    validate_split_assignment(split_assignment)
    if foreground_slice_count <= 0:
        raise ValueError("foreground_slice_count must be positive")
    if background_slice_count < 0:
        raise ValueError("background_slice_count cannot be negative")

    source_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_records = select_and_validate_source_records(
        manifest_path,
        source_payload,
        selected_cases=tuple(split_assignment),
    )
    clinical_path = Path(source_records["clinical_context_table"]["resolved_path"])
    clinical_by_case = load_one_to_one_clinical_records(clinical_path, selected_cases=tuple(split_assignment))

    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    orientation_evidence: list[dict[str, Any]] = []
    source_hashes = source_hash_evidence(source_records)
    derived_files: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []

    for case_id, split in split_assignment.items():
        ct_record = source_records["case_assets"][case_id]["sample_ct_image"]
        mask_record = source_records["case_assets"][case_id]["sample_pixel_mask"]
        ct_path = Path(ct_record["resolved_path"])
        mask_path = Path(mask_record["resolved_path"])
        case_result = validate_and_canonicalize_case(ct_path, mask_path)
        ct_data = case_result.pop("ct_data")
        mask_data = case_result.pop("mask_data")
        orientation_evidence.append({"case_id": case_id, **case_result})

        selected_slices = select_axial_slices(
            mask_data,
            foreground_count=foreground_slice_count,
            background_count=background_slice_count,
        )
        clinical_values, clinical_present, clinical_mapping = clinical_features(clinical_by_case[case_id])
        case_dir = output / "samples" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        case_rows: list[dict[str, str]] = []
        for selection in selected_slices:
            slice_index = int(selection["canonical_slice_index"])
            ct_slice = np.asarray(ct_data[:, :, slice_index], dtype=np.float32)
            if not np.isfinite(ct_slice).all():
                raise ValueError(f"{case_id} CT slice {slice_index} contains non-finite values")
            source_mask_slice = np.asarray(mask_data[:, :, slice_index])
            binary_mask = (source_mask_slice > 0).astype(np.uint8) * 255
            rgb = ct_multi_window_rgb(ct_slice)
            auxiliary = ct_window_uint8(
                ct_slice,
                center_hu=float(AUXILIARY_WINDOW["center_hu"]),
                width_hu=float(AUXILIARY_WINDOW["width_hu"]),
            )

            sample_id = f"{case_id}_ras_axial_{slice_index:04d}"
            white_path = case_dir / f"{sample_id}_ct_multi_window_rgb.png"
            auxiliary_path = case_dir / f"{sample_id}_{CHANNEL_SEMANTICS}.png"
            mask_output_path = case_dir / f"{sample_id}_binary_mask.png"
            Image.fromarray(rgb).save(white_path)
            Image.fromarray(auxiliary).save(auxiliary_path)
            Image.fromarray(binary_mask).save(mask_output_path)

            output_file_evidence = []
            for role, path in (
                ("ct_multi_window_rgb", white_path),
                (CHANNEL_SEMANTICS, auxiliary_path),
                ("binary_foreground_mask", mask_output_path),
            ):
                evidence = file_evidence(path, base=output, role=role)
                derived_files.append({"sample_id": sample_id, **evidence})
                output_file_evidence.append(evidence)

            row = build_csv_row(
                output=output,
                sample_id=sample_id,
                case_id=case_id,
                split=split,
                selection=selection,
                binary_mask=binary_mask,
                source_mask_slice=source_mask_slice,
                clinical_values=clinical_values,
                clinical_present=clinical_present,
                clinical_mapping=clinical_mapping,
                white_path=white_path,
                auxiliary_path=auxiliary_path,
                mask_output_path=mask_output_path,
                output_file_evidence=output_file_evidence,
                source_manifest=manifest_path,
                clinical_record=source_records["clinical_context_table"],
                ct_record=ct_record,
                mask_record=mask_record,
                orientation=case_result,
            )
            rows.append(row)
            case_rows.append(row)

        case_summaries.append(
            {
                "case_id": case_id,
                "patient_group_id": case_id,
                "split": split,
                "sample_count": len(case_rows),
                "foreground_slice_count": sum(row["slice_role"] == "foreground" for row in case_rows),
                "background_slice_count": sum(row["slice_role"] != "foreground" for row in case_rows),
                "selected_canonical_axial_indices": [int(row["canonical_slice_index"]) for row in case_rows],
                "clinical_present": clinical_present,
            }
        )
        del ct_data, mask_data
        gc.collect()

    leakage_checks = patient_leakage_checks(rows)
    csv_path = output / "patient_conditioned_kits23_proxy_samples.csv"
    write_csv(csv_path, rows)
    manifest_output_path = output / "patient_conditioned_kits23_proxy_manifest.json"
    summary = build_output_manifest(
        source_manifest=manifest_path,
        source_manifest_payload=source_payload,
        output_manifest=manifest_output_path,
        csv_path=csv_path,
        split_assignment=split_assignment,
        rows=rows,
        source_hashes=source_hashes,
        derived_files=derived_files,
        orientation_evidence=orientation_evidence,
        case_summaries=case_summaries,
        leakage_checks=leakage_checks,
        foreground_slice_count=foreground_slice_count,
        background_slice_count=background_slice_count,
    )
    manifest_output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def validate_split_assignment(case_splits: Mapping[str, str]) -> None:
    if not case_splits:
        raise ValueError("At least one KiTS23 case is required")
    invalid = {case_id: split for case_id, split in case_splits.items() if split not in {"train", "val", "test"}}
    if invalid:
        raise ValueError(f"Invalid split assignments: {invalid}")


def select_and_validate_source_records(
    manifest_path: Path,
    payload: Mapping[str, Any],
    *,
    selected_cases: Sequence[str],
) -> dict[str, Any]:
    records = [record for record in payload.get("records", []) if record.get("dataset_id") == DATASET_ID]
    clinical_records = [record for record in records if record.get("file_role") == "clinical_context_table"]
    if len(clinical_records) != 1:
        raise ValueError(f"Expected one D071 clinical context table, found {len(clinical_records)}")

    clinical = validate_source_record(manifest_path, clinical_records[0])
    case_assets: dict[str, dict[str, dict[str, Any]]] = {}
    for case_id in selected_cases:
        case_records = [record for record in records if record.get("case_id") == case_id]
        roles: dict[str, dict[str, Any]] = {}
        for role in ("sample_ct_image", "sample_pixel_mask"):
            matching = [record for record in case_records if record.get("file_role") == role]
            if len(matching) != 1:
                raise ValueError(f"Expected one {role} record for {case_id}, found {len(matching)}")
            roles[role] = validate_source_record(manifest_path, matching[0])
        case_assets[case_id] = roles
    return {"clinical_context_table": clinical, "case_assets": case_assets}


def validate_source_record(manifest_path: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("download_status") != "verified":
        raise ValueError(f"Source record is not verified: {record.get('relative_path')}")
    if record.get("license") != LICENSE:
        raise ValueError(f"Unexpected D071 license: {record.get('license')}")
    path = resolve_record_path(manifest_path, record)
    actual_size = path.stat().st_size
    for field in ("expected_size", "size_bytes"):
        if record.get(field) is None or int(record[field]) != actual_size:
            raise ValueError(f"Source size mismatch for {path}: {field}={record.get(field)}, actual={actual_size}")
    expected_hash = str(record.get("sha256") or "").lower()
    actual_hash = sha256_file(path)
    if len(expected_hash) != 64 or actual_hash != expected_hash:
        raise ValueError(f"Source SHA256 mismatch for {path}")
    validated = dict(record)
    validated["resolved_path"] = str(path)
    validated["validated_size_bytes"] = actual_size
    validated["validated_sha256"] = actual_hash
    return validated


def resolve_record_path(manifest_path: Path, record: Mapping[str, Any]) -> Path:
    candidates: list[Path] = []
    if record.get("local_path"):
        local = Path(str(record["local_path"])).expanduser()
        candidates.append(local if local.is_absolute() else manifest_path.parent / local)
    if record.get("relative_path"):
        candidates.append(manifest_path.parent / str(record["relative_path"]))
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"Registered source file is missing: {record.get('relative_path')}")


def load_one_to_one_clinical_records(path: Path, *, selected_cases: Sequence[str]) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("KiTS23 clinical JSON must contain a list")
    by_case: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for item in payload:
        if not isinstance(item, dict) or not item.get("case_id"):
            raise ValueError("Every KiTS23 clinical entry must have a case_id")
        case_id = str(item["case_id"])
        if case_id in by_case:
            duplicates.add(case_id)
        by_case[case_id] = item
    if duplicates:
        raise ValueError(f"Duplicate KiTS23 clinical case_id values: {sorted(duplicates)}")
    missing = sorted(set(selected_cases) - set(by_case))
    if missing:
        raise ValueError(f"Missing one-to-one clinical records: {missing}")
    return {case_id: by_case[case_id] for case_id in selected_cases}


def validate_and_canonicalize_case(ct_path: Path, mask_path: Path) -> dict[str, Any]:
    ct_image = cast(nib.Nifti1Image, nib.load(str(ct_path)))
    mask_image = cast(nib.Nifti1Image, nib.load(str(mask_path)))
    original_ct_axcodes = tuple(str(value) for value in nib.aff2axcodes(ct_image.affine))
    original_mask_axcodes = tuple(str(value) for value in nib.aff2axcodes(mask_image.affine))
    if ct_image.shape != mask_image.shape:
        raise ValueError(f"CT/mask shape mismatch: {ct_image.shape} != {mask_image.shape}")
    if not np.allclose(ct_image.affine, mask_image.affine, rtol=0.0, atol=1e-5):
        raise ValueError("CT/mask affine mismatch")
    if original_ct_axcodes != original_mask_axcodes:
        raise ValueError("CT/mask orientation mismatch")

    canonical_ct = cast(nib.Nifti1Image, nib.as_closest_canonical(ct_image))
    canonical_mask = cast(nib.Nifti1Image, nib.as_closest_canonical(mask_image))
    canonical_ct_axcodes = tuple(str(value) for value in nib.aff2axcodes(canonical_ct.affine))
    canonical_mask_axcodes = tuple(str(value) for value in nib.aff2axcodes(canonical_mask.affine))
    if canonical_ct_axcodes != ("R", "A", "S") or canonical_mask_axcodes != (
        "R",
        "A",
        "S",
    ):
        raise ValueError("NIfTI canonicalization did not produce RAS orientation")
    if canonical_ct.shape != canonical_mask.shape:
        raise ValueError("Canonical CT/mask shape mismatch")
    if not np.allclose(canonical_ct.affine, canonical_mask.affine, rtol=0.0, atol=1e-5):
        raise ValueError("Canonical CT/mask affine mismatch")

    ct_data = np.asanyarray(canonical_ct.dataobj)
    mask_data = np.asanyarray(canonical_mask.dataobj)
    raw_labels = np.unique(mask_data)
    if not np.isfinite(raw_labels).all() or any(float(value) != float(int(value)) for value in raw_labels):
        raise ValueError(f"KiTS23 mask contains non-integer labels: {raw_labels.tolist()}")
    labels = sorted(int(value) for value in raw_labels)
    if not set(labels).issubset(ALLOWED_LABELS) or not any(value > 0 for value in labels):
        raise ValueError(f"Unexpected KiTS23 labels: {labels}")
    return {
        "original_shape": list(ct_image.shape),
        "canonical_shape": list(canonical_ct.shape),
        "original_ct_axcodes": list(original_ct_axcodes),
        "original_mask_axcodes": list(original_mask_axcodes),
        "canonical_ct_axcodes": list(canonical_ct_axcodes),
        "canonical_mask_axcodes": list(canonical_mask_axcodes),
        "original_affines_match": True,
        "canonical_affines_match": True,
        "canonicalization_applied": original_ct_axcodes != canonical_ct_axcodes,
        "original_ct_affine": affine_to_list(ct_image.affine),
        "original_mask_affine": affine_to_list(mask_image.affine),
        "canonical_ct_affine": affine_to_list(canonical_ct.affine),
        "canonical_mask_affine": affine_to_list(canonical_mask.affine),
        "original_ct_dtype": str(ct_image.get_data_dtype()),
        "original_mask_dtype": str(mask_image.get_data_dtype()),
        "original_voxel_spacing": [float(value) for value in ct_image.header.get_zooms()[:3]],
        "voxel_spacing_ras": [float(value) for value in canonical_ct.header.get_zooms()[:3]],
        "validated_labels": labels,
        "ct_data": ct_data,
        "mask_data": mask_data,
    }


def select_axial_slices(mask_data: np.ndarray, *, foreground_count: int, background_count: int) -> list[dict[str, Any]]:
    if mask_data.ndim != 3:
        raise ValueError(f"Expected a 3D canonical mask, got shape {mask_data.shape}")
    foreground_indices = np.flatnonzero(np.any(mask_data > 0, axis=(0, 1)))
    if len(foreground_indices) < foreground_count:
        raise ValueError(f"Mask has {len(foreground_indices)} foreground axial slices; {foreground_count} required")
    foreground_groups = np.array_split(foreground_indices, foreground_count)
    selected_foreground = [int(group[len(group) // 2]) for group in foreground_groups]
    roles = {index: "foreground" for index in selected_foreground}

    if background_count:
        foreground_set = set(int(value) for value in foreground_indices)
        depth = int(mask_data.shape[2])
        lower = int(foreground_indices[0])
        upper = int(foreground_indices[-1])
        preferred = [lower - 1, upper + 1]
        background_candidates = [index for index in preferred if 0 <= index < depth and index not in foreground_set]
        remaining = [
            index for index in range(depth) if index not in foreground_set and index not in background_candidates
        ]
        remaining.sort(key=lambda index: (min(abs(index - lower), abs(index - upper)), index))
        background_candidates.extend(remaining)
        for index in background_candidates[:background_count]:
            roles[index] = "adjacent_background" if index in preferred else "background"

    return [{"canonical_slice_index": index, "slice_role": roles[index]} for index in sorted(roles)]


def clinical_features(
    record: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, bool], dict[str, str]]:
    values = {name: 0.0 for name in FEATURE_NAMES}
    present = {name: False for name in FEATURE_NAMES}
    mapping: dict[str, str] = {}

    assign_numeric(values, present, "age_years", record.get("age_at_nephrectomy"))
    mapping["age_years"] = "age_at_nephrectomy"

    gender = record.get("gender")
    if gender in {"female", "male"}:
        values["sex_at_birth_female"] = float(gender == "female")
        present["sex_at_birth_female"] = True
    mapping["sex_at_birth_female"] = (
        "KiTS23 gender field used as a public proxy; sex-at-birth equivalence is unverified"
    )

    comorbidities = record.get("comorbidities")
    if isinstance(comorbidities, dict):
        diabetes_keys = (
            "uncomplicated_diabetes_mellitus",
            "diabetes_mellitus_with_end_organ_damage",
        )
        diabetes_values = [comorbidities.get(key) for key in diabetes_keys]
        if all(isinstance(value, bool) for value in diabetes_values):
            values["diabetes"] = float(any(diabetes_values))
            present["diabetes"] = True
        renal = comorbidities.get("chronic_kidney_disease")
        if isinstance(renal, bool):
            values["renal_disease"] = float(renal)
            present["renal_disease"] = True
    mapping["diabetes"] = "OR of KiTS23 uncomplicated and end-organ-damage diabetes fields"
    mapping["renal_disease"] = "KiTS23 chronic_kidney_disease"

    egfr = record.get("last_preop_egfr")
    egfr_value = egfr.get("value") if isinstance(egfr, dict) else None
    assign_numeric(values, present, "egfr_ml_min_1_73m2", egfr_value)
    mapping["egfr_ml_min_1_73m2"] = "KiTS23 last_preop_egfr.value"
    return values, present, mapping


def assign_numeric(values: dict[str, float], present: dict[str, bool], name: str, value: Any) -> None:
    if value is None or isinstance(value, bool):
        return
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return
    if np.isfinite(numeric):
        values[name] = numeric
        present[name] = True


def ct_window_uint8(array: np.ndarray, *, center_hu: float, width_hu: float) -> np.ndarray:
    if width_hu <= 0:
        raise ValueError("CT window width must be positive")
    lower = center_hu - width_hu / 2.0
    upper = center_hu + width_hu / 2.0
    scaled = (np.clip(array, lower, upper) - lower) / (upper - lower)
    return np.rint(scaled * 255.0).astype(np.uint8)


def ct_multi_window_rgb(array: np.ndarray) -> np.ndarray:
    return np.stack(
        [
            ct_window_uint8(
                array,
                center_hu=float(window["center_hu"]),
                width_hu=float(window["width_hu"]),
            )
            for window in RGB_WINDOWS
        ],
        axis=-1,
    )


def build_csv_row(
    *,
    output: Path,
    sample_id: str,
    case_id: str,
    split: str,
    selection: Mapping[str, Any],
    binary_mask: np.ndarray,
    source_mask_slice: np.ndarray,
    clinical_values: Mapping[str, float],
    clinical_present: Mapping[str, bool],
    clinical_mapping: Mapping[str, str],
    white_path: Path,
    auxiliary_path: Path,
    mask_output_path: Path,
    output_file_evidence: Sequence[Mapping[str, Any]],
    source_manifest: Path,
    clinical_record: Mapping[str, Any],
    ct_record: Mapping[str, Any],
    mask_record: Mapping[str, Any],
    orientation: Mapping[str, Any],
) -> dict[str, str]:
    file_hashes = {str(item["role"]): str(item["sha256"]) for item in output_file_evidence}
    file_sizes = {str(item["role"]): str(item["size_bytes"]) for item in output_file_evidence}
    source_ct_affine_json = compact_json(orientation["original_ct_affine"])
    canonical_ct_affine_json = compact_json(orientation["canonical_ct_affine"])
    voxel_spacing_ras = [float(value) for value in orientation["voxel_spacing_ras"]]
    return {
        "sample_id": sample_id,
        "patient_group_id": case_id,
        "group_id": case_id,
        "split": split,
        "white_path": relative_path(white_path, output),
        "fluorescence_path": relative_path(auxiliary_path, output),
        "mask_path": relative_path(mask_output_path, output),
        "clinical_values_json": compact_json(clinical_values),
        "clinical_present_json": compact_json(clinical_present),
        "context_trusted": "true",
        "target_domain": "false",
        "target_domain_flag": "false",
        "physician_reviewed": "false",
        "training_eligible": "true",
        "training_scope": TRAINING_SCOPE,
        "training_eligibility_scope": TRAINING_ELIGIBILITY_SCOPE,
        "runtime_replacement_allowed": "false",
        "independent_test_set": "false",
        "domain_tier": DOMAIN_TIER,
        "channel_semantics": CHANNEL_SEMANTICS,
        "white_channel_semantics": "ct_multi_window_rgb",
        "auxiliary_channel_semantics": CHANNEL_SEMANTICS,
        "source_dataset_id": DATASET_ID,
        "source_dataset_name": DATASET_NAME,
        "source_case_id": case_id,
        "source_license": LICENSE,
        "source_page_url": str(ct_record.get("source_page_url") or ""),
        "source_manifest_path": str(source_manifest),
        "source_clinical_path": str(clinical_record["resolved_path"]),
        "source_ct_path": str(ct_record["resolved_path"]),
        "source_mask_path": str(mask_record["resolved_path"]),
        "source_clinical_sha256": str(clinical_record["validated_sha256"]),
        "source_ct_sha256": str(ct_record["validated_sha256"]),
        "source_mask_sha256": str(mask_record["validated_sha256"]),
        "source_clinical_size_bytes": str(clinical_record["validated_size_bytes"]),
        "source_ct_size_bytes": str(ct_record["validated_size_bytes"]),
        "source_mask_size_bytes": str(mask_record["validated_size_bytes"]),
        "original_ct_axcodes": compact_json(orientation["original_ct_axcodes"]),
        "original_mask_axcodes": compact_json(orientation["original_mask_axcodes"]),
        "canonical_ct_axcodes": compact_json(orientation["canonical_ct_axcodes"]),
        "canonical_mask_axcodes": compact_json(orientation["canonical_mask_axcodes"]),
        "source_ct_affine_json": source_ct_affine_json,
        "source_ct_affine_sha256": sha256_text(source_ct_affine_json),
        "canonical_ct_affine_json": canonical_ct_affine_json,
        "canonical_ct_affine_sha256": sha256_text(canonical_ct_affine_json),
        "canonical_axis0_spacing_mm": format(voxel_spacing_ras[0], ".17g"),
        "canonical_axis1_spacing_mm": format(voxel_spacing_ras[1], ".17g"),
        "spacing_unit": "mm",
        "spacing_axis_contract": "array_axis0_rows;array_axis1_columns",
        "canonical_slice_axis": "2",
        "canonical_slice_index": str(selection["canonical_slice_index"]),
        "slice_role": str(selection["slice_role"]),
        "source_labels_json": compact_json(sorted(int(value) for value in np.unique(source_mask_slice))),
        "binary_foreground_pixels": str(int(np.count_nonzero(binary_mask))),
        "clinical_mapping_json": compact_json(clinical_mapping),
        "white_sha256": file_hashes["ct_multi_window_rgb"],
        "fluorescence_sha256": file_hashes[CHANNEL_SEMANTICS],
        "mask_sha256": file_hashes["binary_foreground_mask"],
        "white_size_bytes": file_sizes["ct_multi_window_rgb"],
        "fluorescence_size_bytes": file_sizes[CHANNEL_SEMANTICS],
        "mask_size_bytes": file_sizes["binary_foreground_mask"],
        "medical_safety_boundary": MEDICAL_SAFETY_BOUNDARY,
    }


def patient_leakage_checks(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    group_splits: dict[str, set[str]] = {}
    sample_ids: set[str] = set()
    duplicate_sample_ids: set[str] = set()
    for row in rows:
        group_splits.setdefault(row["patient_group_id"], set()).add(row["split"])
        if row["sample_id"] in sample_ids:
            duplicate_sample_ids.add(row["sample_id"])
        sample_ids.add(row["sample_id"])
    leaking_groups = {group: sorted(splits) for group, splits in group_splits.items() if len(splits) > 1}
    if leaking_groups or duplicate_sample_ids:
        raise ValueError(
            f"Patient leakage or duplicate samples detected: groups={leaking_groups}, "
            f"samples={sorted(duplicate_sample_ids)}"
        )
    return {
        "group_field": "patient_group_id",
        "leakage_detected": False,
        "duplicate_sample_ids_detected": False,
        "groups_by_split": {
            split: sorted(group for group, splits in group_splits.items() if split in splits)
            for split in ("train", "val", "test")
        },
        "group_count": len(group_splits),
    }


def build_output_manifest(
    *,
    source_manifest: Path,
    source_manifest_payload: Mapping[str, Any],
    output_manifest: Path,
    csv_path: Path,
    split_assignment: Mapping[str, str],
    rows: Sequence[Mapping[str, str]],
    source_hashes: Sequence[Mapping[str, Any]],
    derived_files: Sequence[Mapping[str, Any]],
    orientation_evidence: Sequence[Mapping[str, Any]],
    case_summaries: Sequence[Mapping[str, Any]],
    leakage_checks: Mapping[str, Any],
    foreground_slice_count: int,
    background_slice_count: int,
) -> dict[str, Any]:
    split_sample_counts = {split: sum(row["split"] == split for row in rows) for split in ("train", "val", "test")}
    split_group_counts = {
        split: len({row["patient_group_id"] for row in rows if row["split"] == split})
        for split in ("train", "val", "test")
    }
    return {
        "schema_version": "osteo-vision-kits23-patient-conditioning-proxy-v1",
        "status": "engineering_validation_passed",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset": {
            "dataset_id": DATASET_ID,
            "dataset_name": DATASET_NAME,
            "source_page_url": "https://github.com/neheller/kits23",
            "license": LICENSE,
            "commercial_use_allowed": False,
            "share_alike_required": True,
            "domain_tier": DOMAIN_TIER,
            "target_domain": False,
        },
        "source_manifest": {
            "path": str(source_manifest),
            "schema_version": source_manifest_payload.get("schema_version"),
            "size_bytes": source_manifest.stat().st_size,
            "sha256": sha256_file(source_manifest),
        },
        "source_hashes": list(source_hashes),
        "clinical_join": {
            "join_field": "case_id",
            "one_to_one_validated": True,
            "selected_case_count": len(split_assignment),
            "feature_names": list(FEATURE_NAMES),
            "missing_values_use_present_mask": True,
            "semantic_warning": (
                "KiTS23 records gender; mapping to sex_at_birth_female is a proxy "
                "whose sex-at-birth equivalence is unverified."
            ),
        },
        "channel_contract": {
            "white_path": "Three-channel CT multi-window RGB proxy",
            "fluorescence_path": CHANNEL_SEMANTICS,
            "fluorescence_signal_present": False,
            "rgb_windows": [dict(window) for window in RGB_WINDOWS],
            "auxiliary_window": dict(AUXILIARY_WINDOW),
        },
        "label_contract": {
            "source_labels": {
                "0": "background",
                "1": "kidney",
                "2": "tumor",
                "3": "cyst",
            },
            "output_mask": "binary union of source labels 1, 2 and 3",
            "validated_allowed_labels": sorted(ALLOWED_LABELS),
            "jaw_osteomyelitis_label_present": False,
        },
        "slice_selection": {
            "orientation_before_selection": "RAS",
            "axial_axis": 2,
            "requested_foreground_slices_per_case": foreground_slice_count,
            "requested_adjacent_or_background_slices_per_case": background_slice_count,
            "deterministic": True,
            "method": "equal foreground-index groups with midpoint selection; nearest outside-mask background",
        },
        "orientation_evidence": list(orientation_evidence),
        "split_assignment": dict(split_assignment),
        "patient_leakage_checks": dict(leakage_checks),
        "case_summaries": list(case_summaries),
        "sample_count": len(rows),
        "case_count": len(split_assignment),
        "split_sample_counts": split_sample_counts,
        "split_group_counts": split_group_counts,
        "training_eligibility": {
            "training_eligible": True,
            "scope": TRAINING_ELIGIBILITY_SCOPE,
            "training_scope": TRAINING_SCOPE,
            "source_manifest_training_eligible": False,
            "admission_basis": (
                "Derived CT slices passed registered-file integrity, NIfTI alignment, "
                "label, clinical-join and patient-group leakage checks."
            ),
            "target_domain": False,
            "runtime_replacement_allowed": False,
            "independent_test_set": False,
            "physician_reviewed": False,
        },
        "independent_test_set": False,
        "runtime_replacement_allowed": False,
        "artifacts": {
            "sample_csv": str(csv_path),
            "output_manifest": str(output_manifest),
            "derived_file_count": len(derived_files),
            "derived_files": list(derived_files),
        },
        "checks": {
            "source_size_and_sha256_verified": True,
            "clinical_one_to_one_join_verified": True,
            "ct_mask_shape_affine_orientation_verified": True,
            "affine_and_in_plane_spacing_provenance_emitted": True,
            "nifti_canonicalized_to_ras_before_axial_selection": True,
            "labels_verified": True,
            "patient_leakage_absent": True,
            "target_domain_gate_closed": True,
            "runtime_replacement_gate_closed": True,
            "pass": True,
        },
        "medical_safety_boundary": MEDICAL_SAFETY_BOUNDARY,
    }


def source_hash_evidence(source_records: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = [source_records["clinical_context_table"]]
    for case_id, assets in source_records["case_assets"].items():
        for record in assets.values():
            records.append({"case_id": case_id, **record})
    return [
        {
            "case_id": record.get("case_id"),
            "file_role": record["file_role"],
            "path": record["resolved_path"],
            "relative_path": record.get("relative_path"),
            "size_bytes": record["validated_size_bytes"],
            "sha256": record["validated_sha256"],
        }
        for record in records
    ]


def write_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    if not rows:
        raise ValueError("No KiTS23 proxy rows were generated")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def file_evidence(path: Path, *, base: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": relative_path(path, base),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def relative_path(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def affine_to_list(affine: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(affine)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
