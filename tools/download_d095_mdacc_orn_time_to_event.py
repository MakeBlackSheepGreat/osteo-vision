from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d095_mdacc_orn_time_to_event_20260719"

DATASET_ID = "D095"
ARTICLE_ID = 26_240_435
ARTICLE_VERSION = 1
FILE_ID = 47_559_242
EXPECTED_DOI = "10.6084/m9.figshare.26240435.v1"
EXPECTED_LICENSE = "CC BY 4.0"
EXPECTED_TITLE = "MDACC ORN Time-to-event anonymized clinical dataset"
EXPECTED_FILENAME = "TTE_ORN_data_Figshare.csv"
EXPECTED_SIZE = 403_524
EXPECTED_MD5 = "9935bb4bc167f9f393de912edb99652d"
EXPECTED_SHA256 = "1aa85466fa34c3444908f89a03b4cfeff0fa80a668828f576eb146bde3fa25fb"
EXPECTED_PATIENT_COUNT = 1_129
EXPECTED_HEADERS = (
    (
        "Study ID",
        "Gender",
        "Age",
        "Overall survival",
        "Overall survival time",
        "ORN status",
        "Time to event",
        "ORN Grade (Tsai)",
        "Smoking status",
        "Smoking Pack-Years",
        "Pre-RT dental extractions",
        "T Stage",
        "N Stage",
        "Chemotherapy",
        "Postop RT vs. Definitive RT",
        "HPV/P16 +Ve",
        "Tumor site group",
        "Mandible volume (cc)",
    )
    + tuple(f"V{dose}Gy" for dose in range(5, 85, 5))
    + (
        "D0.5%",
        "D1%",
        "D2%",
        "D3%",
        "D5%",
        "D10%",
        "D15%",
        "D20%",
        "D25%",
        "D30%",
        "D35%",
        "D40%",
        "D45%",
        "D50%",
        "D55%",
        "D60%",
        "D65%",
        "D70%",
        "D75%",
        "D80%",
        "D85%",
        "D90%",
        "D95%",
        "D97%",
        "D98%",
        "D99%",
        "D99.5%",
    )
)
EXPECTED_GENDER_COUNTS = {"Female": 191, "Male": 938}
EXPECTED_ORN_COUNTS = {"0": 931, "1": 198}
EXPECTED_GRADE_COUNTS = {"0": 931, "1": 36, "2": 39, "3": 54, "4": 69}

API_URL = f"https://api.figshare.com/v2/articles/{ARTICLE_ID}"
DATACITE_URL = f"https://api.datacite.org/dois/{EXPECTED_DOI}"
DOWNLOAD_URL = f"https://ndownloader.figshare.com/files/{FILE_ID}"
SOURCE_PAGE_URL = f"https://figshare.com/articles/dataset/MDACC_ORN_Time-to-event_anonymized_clinical_dataset/{ARTICLE_ID}/{ARTICLE_VERSION}"


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm, usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return _digest(path, "sha256")


def _md5(path: Path) -> str:
    return _digest(path, "md5")


def _curl_bytes(url: str) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl executable is required for the Figshare download")
    completed = subprocess.run(
        [
            curl,
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "5",
            "--retry-delay",
            "1",
            "--connect-timeout",
            "30",
            "--max-time",
            "300",
            "-A",
            "Mozilla/5.0",
            url,
        ],
        check=True,
        capture_output=True,
    )
    if not completed.stdout:
        raise RuntimeError(f"Empty response from {url}")
    return completed.stdout


def _validate_article_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    if int(metadata.get("id") or 0) != ARTICLE_ID:
        raise RuntimeError("Figshare article identifier changed")
    if int(metadata.get("version") or 0) != ARTICLE_VERSION:
        raise RuntimeError("Figshare article version changed")
    if str(metadata.get("doi") or "").lower() != EXPECTED_DOI.lower():
        raise RuntimeError("Figshare DOI changed")
    if str(metadata.get("title") or "") != EXPECTED_TITLE:
        raise RuntimeError("Figshare title changed")
    if metadata.get("is_public") is not True or metadata.get("is_confidential") is not False:
        raise RuntimeError("Figshare public access state changed")
    if metadata.get("download_disabled") is not False:
        raise RuntimeError("Figshare download access is disabled")
    license_payload = metadata.get("license") or {}
    if str(license_payload.get("name") or "") != EXPECTED_LICENSE:
        raise RuntimeError("Figshare license changed")
    files = metadata.get("files")
    if not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict):
        raise RuntimeError("Figshare file inventory changed")
    file_info = files[0]
    checks = {
        "id": int(file_info.get("id") or 0) == FILE_ID,
        "name": str(file_info.get("name") or "") == EXPECTED_FILENAME,
        "size": int(file_info.get("size") or 0) == EXPECTED_SIZE,
        "md5": str(file_info.get("computed_md5") or "").lower() == EXPECTED_MD5,
        "download_url": str(file_info.get("download_url") or "") == DOWNLOAD_URL,
        "link_only": file_info.get("is_link_only") is False,
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"Figshare pinned file metadata changed: {failed}")
    return file_info


def _validate_datacite_metadata(metadata: dict[str, Any]) -> None:
    data = metadata.get("data") or {}
    attributes = data.get("attributes") or {}
    if str(data.get("id") or "").lower() != EXPECTED_DOI.lower():
        raise RuntimeError("DataCite DOI mismatch")
    titles = attributes.get("titles") or []
    if not titles or str(titles[0].get("title") or "") != EXPECTED_TITLE:
        raise RuntimeError("DataCite title mismatch")
    rights = attributes.get("rightsList") or []
    identifiers = {str(item.get("rightsIdentifier") or "").lower() for item in rights if isinstance(item, dict)}
    if "cc-by-4.0" not in identifiers:
        raise RuntimeError("DataCite license mismatch")
    if f"{EXPECTED_SIZE} Bytes" not in {str(item) for item in (attributes.get("sizes") or [])}:
        raise RuntimeError("DataCite file size mismatch")


def _write_pinned_file(destination: Path, payload: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (
        destination.is_file()
        and destination.stat().st_size == EXPECTED_SIZE
        and _sha256(destination) == EXPECTED_SHA256
    ):
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.write_bytes(payload)
    if partial.stat().st_size != EXPECTED_SIZE:
        partial.unlink(missing_ok=True)
        raise RuntimeError("MDACC ORN download size mismatch")
    if _md5(partial) != EXPECTED_MD5 or _sha256(partial) != EXPECTED_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError("MDACC ORN download digest mismatch")
    partial.replace(destination)


def _audit_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = tuple(reader.fieldnames or [])
        if headers != EXPECTED_HEADERS:
            raise RuntimeError("MDACC ORN CSV headers changed")
        rows = list(reader)
    patient_ids = [str(row["Study ID"]) for row in rows]
    if len(rows) != EXPECTED_PATIENT_COUNT or len(set(patient_ids)) != EXPECTED_PATIENT_COUNT:
        raise RuntimeError("MDACC ORN patient count or uniqueness changed")
    missing_cells = sum(value is None or not str(value).strip() for row in rows for value in row.values())
    if missing_cells:
        raise RuntimeError("MDACC ORN CSV now contains missing cells")
    ages = [float(row["Age"]) for row in rows]
    gender_counts = dict(sorted(Counter(row["Gender"] for row in rows).items()))
    orn_counts = dict(sorted(Counter(row["ORN status"] for row in rows).items()))
    grade_counts = dict(sorted(Counter(row["ORN Grade (Tsai)"] for row in rows).items()))
    if gender_counts != EXPECTED_GENDER_COUNTS:
        raise RuntimeError("MDACC ORN gender distribution changed")
    if orn_counts != EXPECTED_ORN_COUNTS or grade_counts != EXPECTED_GRADE_COUNTS:
        raise RuntimeError("MDACC ORN outcome distribution changed")
    if min(ages) != 23.0 or max(ages) != 89.0:
        raise RuntimeError("MDACC ORN age range changed")
    return {
        "patient_count": len(rows),
        "unique_anonymized_study_ids": len(set(patient_ids)),
        "column_count": len(EXPECTED_HEADERS),
        "columns": list(EXPECTED_HEADERS),
        "missing_cell_count": missing_cells,
        "age_min_years": min(ages),
        "age_max_years": max(ages),
        "gender_counts": gender_counts,
        "orn_status_counts": orn_counts,
        "tsai_grade_counts": grade_counts,
        "orn_positive_count": orn_counts["1"],
        "mandible_dose_volume_feature_count": len(
            [header for header in EXPECTED_HEADERS if header.startswith(("V", "D")) and header not in {"Definitive RT"}]
        ),
    }


def _metadata_entry(output_dir: Path, path: Path, *, role: str, url: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "file_role": role,
        "direct_download_url": url,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def download_d095(output_dir: Path) -> dict[str, Any]:
    article_metadata = json.loads(_curl_bytes(API_URL).decode("utf-8"))
    datacite_metadata = json.loads(_curl_bytes(DATACITE_URL).decode("utf-8"))
    if not isinstance(article_metadata, dict) or not isinstance(datacite_metadata, dict):
        raise RuntimeError("Dataset metadata payload is invalid")
    file_info = _validate_article_metadata(article_metadata)
    _validate_datacite_metadata(datacite_metadata)

    csv_path = output_dir / "raw" / "mdacc_orn_time_to_event_v1.csv"
    _write_pinned_file(csv_path, _curl_bytes(DOWNLOAD_URL))
    audit = _audit_csv(csv_path)

    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    article_path = metadata_dir / "figshare_article_26240435_v1.json"
    datacite_path = metadata_dir / "datacite_10.6084_m9.figshare.26240435.v1.json"
    article_path.write_text(
        json.dumps(article_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    datacite_path.write_text(
        json.dumps(datacite_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    local_files = [
        {
            "path": csv_path.relative_to(output_dir).as_posix(),
            "file_role": "anonymized_patient_level_orn_time_to_event_and_mandible_dosimetry_table",
            "source_filename": EXPECTED_FILENAME,
            "figshare_file_id": FILE_ID,
            "direct_download_url": DOWNLOAD_URL,
            "content_type": str(file_info.get("mimetype") or ""),
            "size_bytes": csv_path.stat().st_size,
            "official_md5": EXPECTED_MD5,
            "local_md5": _md5(csv_path),
            "sha256": _sha256(csv_path),
        },
        _metadata_entry(output_dir, article_path, role="official_figshare_api_metadata", url=API_URL),
        _metadata_entry(output_dir, datacite_path, role="official_datacite_metadata", url=DATACITE_URL),
    ]
    downloaded_at = datetime.now(timezone.utc).isoformat()
    record = {
        "candidate_id": DATASET_ID,
        "dataset_name": EXPECTED_TITLE,
        "doi": EXPECTED_DOI,
        "source_page_url": SOURCE_PAGE_URL,
        "metadata_urls": [API_URL, DATACITE_URL],
        "direct_download_url": DOWNLOAD_URL,
        "license": EXPECTED_LICENSE,
        "license_identifier": "cc-by-4.0",
        "license_review_status": "verified_from_figshare_api_and_datacite",
        "governance_state": "public_author_declared_anonymized_dataset",
        "domain_tier": "human_ornj_target_condition_near_clinical_and_mandible_dosimetry_labels",
        "modality": "patient-level clinical, outcome and mandible dose-volume feature table",
        "labels": "ORN status, time to event and Tsai grade 0-4; no source images, ROI coordinates or pixel masks",
        "patient_count": EXPECTED_PATIENT_COUNT,
        "patient_count_unit": "unique_anonymized_head_and_neck_radiotherapy_records",
        "clinical_variables": [
            "age",
            "sex",
            "smoking and pack-years",
            "pre-radiotherapy dental extraction",
            "T and N stage",
            "chemotherapy",
            "radiotherapy setting",
            "HPV/p16 status",
            "tumor site",
            "survival and time",
            "ORN status, event time and Tsai grade",
            "mandible volume and dose-volume features",
        ],
        "recommended_use": (
            "Target-condition-near patient-context schema, patient-level grouped evaluation, weak ordinal outcome "
            "engineering, subgroup audit and no-harm gate design."
        ),
        "content_audit": audit,
        "cross_verification": {
            "figshare_api": "public, non-confidential, author-declared anonymized, download enabled, CC BY 4.0",
            "datacite": "matching DOI, title, 403524-byte size and SPDX cc-by-4.0 rights",
            "local_csv": "1129 unique records, 61 columns, zero missing cells and checked ORN outcome distributions",
        },
        "local_files": local_files,
        "download_status": "verified_complete_public_release",
        "downloaded_at_utc": downloaded_at,
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
        "data_boundary": (
            "Real anonymized human head-and-neck radiotherapy cohort with mandibular ORNJ outcomes and derived "
            "dose-volume features. The release contains no raw CT, mandible masks, operative white-light or "
            "fluorescence frames, bone-activity labels, pathology mapping or navigation coordinates. It cannot "
            "validate spatial patient-conditioned segmentation, intraoperative bone-activity classes or navigation "
            "accuracy. Author-declared anonymization and the public license support controlled engineering use while "
            "training admission remains disabled pending project governance review."
        ),
    }
    manifest = {
        "schema_version": "osteo-vision-d095-mdacc-orn-time-to-event-v1",
        "generated_at_utc": downloaded_at,
        "record_count": 1,
        "file_count": len(local_files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in local_files),
        "records": [record],
    }
    manifest_path = output_dir / "d095_mdacc_orn_time_to_event_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    manifest = download_d095(output_dir)
    audit = manifest["records"][0]["content_audit"]
    print(
        json.dumps(
            {
                "candidate_id": DATASET_ID,
                "patient_count": audit["patient_count"],
                "column_count": audit["column_count"],
                "file_count": manifest["file_count"],
                "total_size_bytes": manifest["total_size_bytes"],
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
