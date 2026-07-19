from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.download_d051_mronj_imc_starter import (
        FIGSHARE_API_URL,
        REQUIRED_SUBJECTS,
        SOURCE_PAGE_URL,
        select_balanced_roi_files,
        subject_id,
    )
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_d051_mronj_imc_starter import (
        FIGSHARE_API_URL,
        REQUIRED_SUBJECTS,
        SOURCE_PAGE_URL,
        select_balanced_roi_files,
        subject_id,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = ROOT / "research/datasets/public-candidates/" "d051_mronj_imaging_mass_cytometry_starter_20260718"
API_METADATA_NAME = "figshare_30383407_v1_api.json"
LOCAL_METADATA_NAMES = {
    "panel.csv": "panel.csv",
    "Supplementary Information.docx": "Supplementary_Information.docx",
}


def _hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _official_md5(item: dict[str, Any]) -> str:
    return str(item.get("computed_md5") or item.get("supplied_md5") or "").lower()


def _cohort(subject: str) -> str:
    return "mronj" if subject.startswith("Patient") else "control"


def inspect_imc_table(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header_line = handle.readline().rstrip(b"\r\n")
        columns = [value.decode("utf-8") for value in header_line.split(b"\t")]
        coordinate_indexes = {axis: columns.index(axis) for axis in ("X", "Y", "Z")}
        coordinate_ranges = {axis: {"min": math.inf, "max": -math.inf} for axis in coordinate_indexes}
        row_count = 0
        malformed_rows: list[int] = []
        invalid_coordinate_rows: list[int] = []
        for line_number, line in enumerate(handle, start=2):
            values = line.rstrip(b"\r\n").split(b"\t")
            if len(values) != len(columns):
                if len(malformed_rows) < 20:
                    malformed_rows.append(line_number)
                continue
            row_count += 1
            for axis, index in coordinate_indexes.items():
                try:
                    value = float(values[index])
                except ValueError:
                    if len(invalid_coordinate_rows) < 20:
                        invalid_coordinate_rows.append(line_number)
                    continue
                coordinate_ranges[axis]["min"] = min(coordinate_ranges[axis]["min"], value)
                coordinate_ranges[axis]["max"] = max(coordinate_ranges[axis]["max"], value)

    return {
        "column_count": len(columns),
        "columns": columns,
        "coordinate_columns": list(coordinate_indexes),
        "coordinate_ranges": coordinate_ranges,
        "row_count": row_count,
        "malformed_row_count": len(malformed_rows),
        "malformed_row_examples": malformed_rows,
        "invalid_coordinate_row_count": len(invalid_coordinate_rows),
        "invalid_coordinate_row_examples": invalid_coordinate_rows,
        "status": ("passed" if row_count > 0 and not malformed_rows and not invalid_coordinate_rows else "failed"),
    }


def _artifact(
    *,
    dataset_dir: Path,
    path: Path,
    original_name: str,
    download_url: str,
    file_role: str,
    expected_size: int,
    official_md5: str | None,
    subject: str | None = None,
    structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actual_size = path.stat().st_size
    local_md5 = _hash_file(path, "md5")
    sha256 = _hash_file(path, "sha256")
    md5_matches = official_md5 is None or local_md5 == official_md5
    return {
        "original_file_name": original_name,
        "relative_path": path.relative_to(dataset_dir).as_posix(),
        "direct_download_url": download_url,
        "file_role": file_role,
        "subject_id": subject,
        "cohort": _cohort(subject) if subject else None,
        "size_bytes": actual_size,
        "expected_size_bytes": expected_size,
        "size_matches": actual_size == expected_size,
        "official_md5": official_md5,
        "local_md5": local_md5,
        "md5_matches": md5_matches,
        "sha256": sha256,
        "structure_verification": structure,
        "verification_status": (
            "passed"
            if actual_size == expected_size and md5_matches and (structure is None or structure["status"] == "passed")
            else "failed"
        ),
    }


def verify_dataset(dataset_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    api_path = dataset_dir / "metadata" / API_METADATA_NAME
    api_payload = json.loads(api_path.read_text(encoding="utf-8"))
    receipt_path = dataset_dir / "d051_download_receipt.json"
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    downloaded_at = str(receipt_payload["generated_at_utc"])
    source_files = list(api_payload.get("files") or [])
    balanced = select_balanced_roi_files(source_files)
    artifacts: list[dict[str, Any]] = []

    for item in balanced:
        name = str(item["name"])
        subject = subject_id(name)
        path = dataset_dir / "raw" / name
        artifacts.append(
            _artifact(
                dataset_dir=dataset_dir,
                path=path,
                original_name=name,
                download_url=str(item["download_url"]),
                file_role="imaging_mass_cytometry_roi_table",
                expected_size=int(item["size"]),
                official_md5=_official_md5(item),
                subject=subject,
                structure=inspect_imc_table(path),
            )
        )

    source_by_name = {str(item["name"]): item for item in source_files}
    for source_name, local_name in LOCAL_METADATA_NAMES.items():
        item = source_by_name[source_name]
        path = dataset_dir / "metadata" / local_name
        artifacts.append(
            _artifact(
                dataset_dir=dataset_dir,
                path=path,
                original_name=source_name,
                download_url=str(item["download_url"]),
                file_role=("imc_antibody_panel" if source_name == "panel.csv" else "study_supplement"),
                expected_size=int(item["size"]),
                official_md5=_official_md5(item),
            )
        )

    api_artifact = _artifact(
        dataset_dir=dataset_dir,
        path=api_path,
        original_name=API_METADATA_NAME,
        download_url=FIGSHARE_API_URL,
        file_role="source_api_metadata",
        expected_size=api_path.stat().st_size,
        official_md5=None,
    )
    artifacts.append(api_artifact)

    panel_path = dataset_dir / "metadata" / "panel.csv"
    with panel_path.open("r", encoding="utf-8", newline="") as handle:
        panel_rows = list(csv.DictReader(handle))
    supplement_path = dataset_dir / "metadata" / "Supplementary_Information.docx"
    with zipfile.ZipFile(supplement_path) as archive:
        corrupt_member = archive.testzip()

    raw_artifacts = [item for item in artifacts if item["subject_id"]]
    headers = {tuple(item["structure_verification"]["columns"]) for item in raw_artifacts}
    actual_subjects = [str(item["subject_id"]) for item in raw_artifacts]
    total_size = sum(int(item["size_bytes"]) for item in artifacts)
    all_passed = (
        all(item["verification_status"] == "passed" for item in artifacts)
        and actual_subjects == list(REQUIRED_SUBJECTS)
        and len(headers) == 1
        and bool(panel_rows)
        and corrupt_member is None
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    dataset_record = {
        "dataset_id": "D051",
        "dataset_name": "Jaw osteonecrosis peri-lesional imaging mass cytometry balanced starter",
        "source_page_url": SOURCE_PAGE_URL,
        "metadata_url": FIGSHARE_API_URL,
        "license": "CC BY 4.0",
        "license_review_status": "verified_from_figshare_v1_metadata",
        "governance_state": "public_deidentified_imc_data_per_article_data_availability_statement",
        "domain_tier": "target_condition_near_pathology_scale_spatial_omics_proxy",
        "modalities": [
            "human peri-lesional imaging mass cytometry",
            "per-pixel spatial marker intensity tables",
        ],
        "labels": (
            "The source supplement describes epithelial, stromal, vascular, cell-type and functional-state "
            "annotations. The downloaded raw tables contain spatial marker intensities without operative "
            "necrotic, transition or viable-bone boundary masks."
        ),
        "patient_count": 14,
        "sample_count": 14,
        "sample_count_detail": "One smallest ROI from each of 6 MRONJ and 8 control subjects.",
        "source_file_count": len(source_files),
        "source_total_size_bytes": sum(int(item["size"]) for item in source_files),
        "clinical_variables_status": (
            "No downloadable patient-level age, sex, comorbidity, medication or blood-index table is "
            "paired with these ROI files."
        ),
        "recommended_use": (
            "Pathology-scale spatial marker preprocessing, near-condition representation learning, "
            "cohort-aware engineering and biological review of gray-zone concepts after explicit admission."
        ),
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
        "download_status": "verified_balanced_starter",
        "downloaded_at_utc": downloaded_at,
        "data_boundary": (
            "Human MRONJ peri-lesional pathology-scale proxy. It contains no intraoperative white-light/ICG "
            "frames, CBCT, operative bone-surface truth, necrotic-transition-viable surgical masks, or paired "
            "clinical variables. It cannot support patient-conditioned segmentation, surgical-boundary, "
            "navigation or clinical-performance claims."
        ),
        "local_artifacts": artifacts,
    }
    manifest = {
        "schema_version": "osteo-vision-d051-balanced-starter-v1",
        "generated_at_utc": generated_at,
        "downloaded_at_utc": downloaded_at,
        "dataset_count": 1,
        "artifact_count": len(artifacts),
        "total_size_bytes": total_size,
        "datasets": [dataset_record],
    }
    verification = {
        "schema_version": "osteo-vision-d051-balanced-starter-verification-v1",
        "generated_at_utc": generated_at,
        "status": "passed" if all_passed else "failed",
        "dataset_id": "D051",
        "selection_policy": "smallest_roi_per_subject",
        "expected_subjects": list(REQUIRED_SUBJECTS),
        "actual_subjects": actual_subjects,
        "cohort_counts": {
            "mronj": sum(subject.startswith("Patient") for subject in actual_subjects),
            "control": sum(subject.startswith("CTRL") for subject in actual_subjects),
        },
        "pairing_status": "unpaired_case_control_cohorts_one_roi_per_subject",
        "raw_roi_file_count": len(raw_artifacts),
        "metadata_file_count": len(artifacts) - len(raw_artifacts),
        "artifact_count": len(artifacts),
        "total_size_bytes": total_size,
        "consistent_imc_header": len(headers) == 1,
        "imc_column_count": len(next(iter(headers))) if headers else 0,
        "required_coordinate_columns": ["X", "Y", "Z"],
        "panel_marker_count": len(panel_rows),
        "supplement_docx_zip_valid": corrupt_member is None,
        "all_sizes_match": all(bool(item["size_matches"]) for item in artifacts),
        "all_available_official_md5_match": all(bool(item["md5_matches"]) for item in artifacts),
        "all_sha256_recorded": all(bool(item["sha256"]) for item in artifacts),
        "artifacts": artifacts,
        "training_eligible": False,
        "target_domain_flag": False,
    }
    return manifest, verification


def write_outputs(dataset_dir: Path, manifest: dict[str, Any], verification: dict[str, Any]) -> None:
    (dataset_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dataset_dir / "verification_20260718.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    artifacts = list(manifest["datasets"][0]["local_artifacts"])
    fieldnames = [
        "dataset_id",
        "subject_id",
        "cohort",
        "file_role",
        "original_file_name",
        "relative_path",
        "direct_download_url",
        "size_bytes",
        "expected_size_bytes",
        "size_matches",
        "official_md5",
        "local_md5",
        "md5_matches",
        "sha256",
        "verification_status",
    ]
    with (dataset_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for artifact in artifacts:
            writer.writerow({"dataset_id": "D051", **artifact})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR.relative_to(ROOT)))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    dataset_dir = (ROOT / args.dataset_dir).resolve()
    manifest, verification = verify_dataset(dataset_dir)
    if args.write:
        write_outputs(dataset_dir, manifest, verification)
    print(json.dumps(verification, ensure_ascii=False, indent=2))
    return 0 if verification["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
