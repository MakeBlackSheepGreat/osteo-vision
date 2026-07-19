from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d094_clinrad_orn_context_20260719"

DATASET_ID = "D094"
ARTICLE_ID = 28_292_186
ARTICLE_VERSION = 2
FILE_ID = 51_987_479
EXPECTED_DOI = "10.6084/m9.figshare.28292186.v2"
EXPECTED_LICENSE = "CC BY 4.0"
EXPECTED_TITLE = (
    "Available Data for Early Imaging Identification of Osteoradionecrosis and Classification "
    "Using the Novel ClinRad System: Results from A Retrospective Observational Cohort."
)
EXPECTED_FILENAME = "FINAL_Anon_Pts Included_for_Analysis.xlsx"
EXPECTED_SIZE = 19_198
EXPECTED_MD5 = "5768c25d72c4480d0b2d0af19d485e35"
EXPECTED_SHA256 = "022075cfc73b13f7b7e6bcfbeacd6f30bb1eb506525333f83214742bc12c268e"
EXPECTED_PATIENT_COUNT = 53
EXPECTED_HEADERS = (
    "Anonymization_ORN_X",
    "Sex",
    "Age at ORNinitial",
    "Age at Death",
    "M27.2 or M87.9 In Problem List? (Y/N)",
    "HPV/p16 Status",
    "Primary Tumor Location",
    "Total Dose to Primary; Fx",
    "Chemotherapy/Immunotherapy",
    "RTend to initial ORN (months)",
    "Watson S/G",
    "Findings at initial ORN diagnosis",
)
EXPECTED_SEX_COUNTS = {"F": 3, "M": 50}
EXPECTED_STAGE_COUNTS = {"S0/G1": 14, "S1/G2": 28, "S2/G3": 9, "S3/G4": 2}

API_URL = f"https://api.figshare.com/v2/articles/{ARTICLE_ID}"
DATACITE_URL = f"https://api.datacite.org/dois/{EXPECTED_DOI}"
DOWNLOAD_URL = f"https://ndownloader.figshare.com/files/{FILE_ID}"
SOURCE_PAGE_URL = (
    "https://figshare.com/articles/dataset/"
    "Available_Data_for_Early_Imaging_Identification_of_Osteoradionecrosis_and_Classification_"
    "Using_the_Novel_ClinRad_System_Results_from_A_Retrospective_Observational_Cohort_"
    f"/{ARTICLE_ID}/{ARTICLE_VERSION}"
)

_SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


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
    sizes = {str(item) for item in (attributes.get("sizes") or [])}
    if f"{EXPECTED_SIZE} Bytes" not in sizes:
        raise RuntimeError("DataCite file size mismatch")


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(payload)
    return ["".join(node.itertext()) for node in root.findall(f"{{{_SHEET_NS}}}si")]


def _read_workbook_rows(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    row_nodes = sheet.findall(f".//{{{_SHEET_NS}}}sheetData/{{{_SHEET_NS}}}row")
    raw_rows: list[dict[str, str]] = []
    for row in row_nodes:
        values: dict[str, str] = {}
        for cell in row.findall(f"{{{_SHEET_NS}}}c"):
            reference = str(cell.attrib.get("r") or "")
            match = re.match(r"[A-Z]+", reference)
            if match is None:
                continue
            column = match.group(0)
            value_node = cell.find(f"{{{_SHEET_NS}}}v")
            if cell.attrib.get("t") == "inlineStr":
                inline = cell.find(f"{{{_SHEET_NS}}}is")
                value = "" if inline is None else "".join(inline.itertext())
            elif value_node is None:
                value = ""
            elif cell.attrib.get("t") == "s":
                index = int(value_node.text or "0")
                if index >= len(shared):
                    raise RuntimeError("Workbook shared-string index is invalid")
                value = shared[index]
            else:
                value = str(value_node.text or "")
            values[column] = value.strip()
        raw_rows.append(values)
    if not raw_rows:
        raise RuntimeError("Workbook has no rows")
    header_by_column = raw_rows[0]
    columns = tuple(chr(ord("A") + index) for index in range(len(EXPECTED_HEADERS)))
    headers = tuple(header_by_column.get(column, "") for column in columns)
    if headers != EXPECTED_HEADERS:
        raise RuntimeError("Workbook headers changed")
    rows: list[dict[str, str]] = []
    for raw in raw_rows[1:]:
        patient_id = raw.get("A", "")
        if not patient_id:
            continue
        rows.append({header: raw.get(column, "") for column, header in zip(columns, headers, strict=True)})
    return rows


def _audit_workbook(path: Path) -> dict[str, Any]:
    rows = _read_workbook_rows(path)
    patient_ids = [row[EXPECTED_HEADERS[0]] for row in rows]
    if len(rows) != EXPECTED_PATIENT_COUNT or len(set(patient_ids)) != EXPECTED_PATIENT_COUNT:
        raise RuntimeError("ClinRad patient count or uniqueness changed")
    ages = [float(row["Age at ORNinitial"]) for row in rows]
    sex_counts = dict(sorted(Counter(row["Sex"] for row in rows).items()))
    stage_counts = dict(sorted(Counter(row["Watson S/G"].split(maxsplit=1)[0] for row in rows).items()))
    if sex_counts != EXPECTED_SEX_COUNTS:
        raise RuntimeError("ClinRad sex distribution changed")
    if stage_counts != EXPECTED_STAGE_COUNTS:
        raise RuntimeError("ClinRad Watson stage distribution changed")
    if min(ages) != 43.0 or max(ages) != 81.0:
        raise RuntimeError("ClinRad age range changed")
    findings = [row["Findings at initial ORN diagnosis"] for row in rows]
    return {
        "patient_count": len(rows),
        "unique_anonymized_patient_ids": len(set(patient_ids)),
        "column_count": len(EXPECTED_HEADERS),
        "columns": list(EXPECTED_HEADERS),
        "age_min_years": min(ages),
        "age_max_years": max(ages),
        "sex_counts": sex_counts,
        "watson_stage_grade_counts": stage_counts,
        "records_mentioning_ct": sum(bool(re.search(r"\bCT\b", value, flags=re.IGNORECASE)) for value in findings),
        "records_mentioning_cbct": sum("cbct" in value.lower() for value in findings),
        "records_mentioning_panoramic_or_panorex": sum(
            bool(re.search(r"panoramic|panorex", value, flags=re.IGNORECASE)) for value in findings
        ),
        "records_mentioning_exposed_bone": sum(
            bool(re.search(r"exposed bone|bone exposure", value, flags=re.IGNORECASE)) for value in findings
        ),
    }


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
        raise RuntimeError("ClinRad download size mismatch")
    if _md5(partial) != EXPECTED_MD5 or _sha256(partial) != EXPECTED_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError("ClinRad download digest mismatch")
    partial.replace(destination)


def _metadata_entry(output_dir: Path, path: Path, *, role: str, url: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "file_role": role,
        "direct_download_url": url,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def download_d094(output_dir: Path) -> dict[str, Any]:
    article_metadata = json.loads(_curl_bytes(API_URL).decode("utf-8"))
    datacite_metadata = json.loads(_curl_bytes(DATACITE_URL).decode("utf-8"))
    if not isinstance(article_metadata, dict) or not isinstance(datacite_metadata, dict):
        raise RuntimeError("Dataset metadata payload is invalid")
    file_info = _validate_article_metadata(article_metadata)
    _validate_datacite_metadata(datacite_metadata)

    workbook_path = output_dir / "raw" / "clinrad_orn_anonymized_cohort_v2.xlsx"
    _write_pinned_file(workbook_path, _curl_bytes(DOWNLOAD_URL))
    audit = _audit_workbook(workbook_path)

    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    article_path = metadata_dir / "figshare_article_28292186_v2.json"
    datacite_path = metadata_dir / "datacite_10.6084_m9.figshare.28292186.v2.json"
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
            "path": workbook_path.relative_to(output_dir).as_posix(),
            "file_role": "anonymized_patient_level_clinical_and_radiographic_interpretation_table",
            "source_filename": EXPECTED_FILENAME,
            "figshare_file_id": FILE_ID,
            "direct_download_url": DOWNLOAD_URL,
            "content_type": str(file_info.get("mimetype") or ""),
            "size_bytes": workbook_path.stat().st_size,
            "official_md5": EXPECTED_MD5,
            "local_md5": _md5(workbook_path),
            "sha256": _sha256(workbook_path),
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
        "domain_tier": "human_ornj_target_condition_near_clinical_and_imaging_derived_labels",
        "modality": "patient-level clinical table with CT, CBCT, panoramic and examination interpretation text",
        "labels": (
            "Watson S/G severity class plus patient-level free-text radiographic and exposed-bone findings; "
            "no source images, ROI coordinates or pixel masks"
        ),
        "patient_count": EXPECTED_PATIENT_COUNT,
        "patient_count_unit": "anonymized_human_ornj_records",
        "clinical_variables": [
            "age at initial ORNJ",
            "sex",
            "problem-list code status",
            "HPV/p16 status",
            "primary tumor location",
            "radiotherapy dose and fractions",
            "chemotherapy or immunotherapy",
            "radiotherapy-to-ORN interval",
            "Watson stage and grade",
            "initial CT, CBCT, panoramic and examination findings",
        ],
        "recommended_use": (
            "Target-condition-near clinical feature dictionary, patient-level grouped protocol, weak severity-label "
            "engineering and audit of patient-conditioning safety boundaries."
        ),
        "content_audit": audit,
        "cross_verification": {
            "figshare_api": "public, non-confidential, download enabled, one pinned XLSX, CC BY 4.0",
            "datacite": "matching DOI, title, 19198-byte size and SPDX cc-by-4.0 rights",
            "local_workbook": "53 unique anonymized records with fixed columns and checked label distributions",
        },
        "local_files": local_files,
        "download_status": "verified_complete_public_release",
        "downloaded_at_utc": downloaded_at,
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
        "data_boundary": (
            "Real anonymized human osteoradionecrosis-of-the-jaw patient context and image-derived interpretation "
            "labels. The release contains no raw CT or CBCT, operative white-light or fluorescence frames, pixel "
            "annotations, pathology mapping, patient-specific surface model or navigation coordinates. It cannot "
            "validate spatial patient-conditioned segmentation, bone-activity classes, fluorescence performance or "
            "navigation accuracy."
        ),
    }
    manifest = {
        "schema_version": "osteo-vision-d094-clinrad-orn-context-v1",
        "generated_at_utc": downloaded_at,
        "record_count": 1,
        "file_count": len(local_files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in local_files),
        "records": [record],
    }
    manifest_path = output_dir / "d094_clinrad_orn_context_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    manifest = download_d094(output_dir)
    audit = manifest["records"][0]["content_audit"]
    print(
        json.dumps(
            {
                "candidate_id": DATASET_ID,
                "patient_count": audit["patient_count"],
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
