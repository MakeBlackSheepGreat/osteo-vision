from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.download_three_priority_zenodo_datasets import _download, _md5, _session, _sha256
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_three_priority_zenodo_datasets import _download, _md5, _session, _sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/navigation_cbct_stl_audit_20260718"
RECORD_ID = "13231287"
EXPECTED_FILE_NAME = "Head-Neck-CBCT-CT.rar"
EXPECTED_SIZE = 406_022_191
EXPECTED_MD5 = "f81a695252a7ac9e2bf92104c8b8cac1"
EXPECTED_LICENSE = "cc-by-4.0"


def _validated_download_spec(record: dict[str, Any]) -> dict[str, Any]:
    if str(record.get("id")) != RECORD_ID:
        raise RuntimeError("Zenodo record identifier mismatch")

    metadata = record.get("metadata") or {}
    license_value = metadata.get("license") or {}
    license_id = str(license_value.get("id") or "").lower()
    if license_id != EXPECTED_LICENSE:
        raise RuntimeError(f"Unexpected Zenodo license: {license_id or 'missing'}")
    if str(metadata.get("access_right") or "").lower() != "open":
        raise RuntimeError("Zenodo record is not open access")

    matches = [item for item in record.get("files") or [] if str(item.get("key")) == EXPECTED_FILE_NAME]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {EXPECTED_FILE_NAME} file")
    item = matches[0]
    if int(item.get("size") or 0) != EXPECTED_SIZE:
        raise RuntimeError("Zenodo file size changed")
    checksum = str(item.get("checksum") or "")
    if checksum.lower() != f"md5:{EXPECTED_MD5}":
        raise RuntimeError("Zenodo MD5 changed")
    download_url = str((item.get("links") or {}).get("self") or "")
    if not download_url.startswith("https://zenodo.org/"):
        raise RuntimeError("Zenodo content URL is missing or unexpected")
    return {
        "download_url": download_url,
        "size_bytes": EXPECTED_SIZE,
        "md5": EXPECTED_MD5,
        "license_id": license_id,
    }


def _relative_file_entry(output_dir: Path, path: Path, *, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "file_role": role,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _upsert_local_file(record: dict[str, Any], entry: dict[str, Any]) -> None:
    files = [dict(item) for item in record.get("local_files") or []]
    files = [item for item in files if str(item.get("path")) != str(entry["path"])]
    files.append(entry)
    record["local_files"] = sorted(files, key=lambda item: str(item.get("path") or ""))


def _update_manifest_record(
    record: dict[str, Any],
    *,
    spec: dict[str, Any],
    archive_entry: dict[str, Any],
    metadata_entry: dict[str, Any],
    downloaded_at_utc: str,
) -> dict[str, Any]:
    updated = dict(record)
    updated.update(
        {
            "direct_download_url": spec["download_url"],
            "remote_size_bytes": spec["size_bytes"],
            "zenodo_checksum": f"md5:{spec['md5']}",
            "license_identifier": spec["license_id"],
            "license_review_status": "verified_from_zenodo_api",
            "download_status": "verified_archive_downloaded",
            "downloaded_at_utc": downloaded_at_utc,
            "clinical_variables_unavailable_reason": (
                "The Zenodo record does not publish patient-level clinical variables."
            ),
            "navigation_claim_allowed": False,
        }
    )
    metadata_urls = [str(item) for item in updated.get("metadata_urls") or []]
    api_url = f"https://zenodo.org/api/records/{RECORD_ID}"
    if api_url not in metadata_urls:
        metadata_urls.append(api_url)
    updated["metadata_urls"] = metadata_urls
    _upsert_local_file(updated, metadata_entry)
    _upsert_local_file(updated, archive_entry)
    return updated


def _write_summary_csv(output_dir: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "candidate_id",
        "dataset_name",
        "source_page_url",
        "license",
        "sample_count",
        "modality",
        "labels_or_coordinates",
        "download_status",
        "priority_target",
        "target_domain_flag",
        "training_eligible",
        "review_state",
        "data_boundary",
    ]
    path = output_dir / "navigation_cbct_stl_manifest.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    field: (
                        record.get(field) if record.get(field) is not None else record.get(f"{field}_status", "unknown")
                    )
                    for field in fieldnames
                }
            )


def _write_verification_csv(output_dir: Path, records: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for record in records:
        for entry in record.get("local_files") or []:
            relative_path = str(entry.get("path") or "")
            path = output_dir / relative_path
            exists = path.is_file()
            expected_size = int(entry.get("size_bytes") or 0)
            expected_sha256 = str(entry.get("sha256") or "")
            rows.append(
                {
                    "relative_path": relative_path,
                    "size_bytes": expected_size,
                    "sha256": expected_sha256,
                    "exists": str(exists).lower(),
                    "size_verified": str(exists and path.stat().st_size == expected_size).lower(),
                    "sha256_verified": str(exists and _sha256(path) == expected_sha256).lower(),
                }
            )
    path = output_dir / "downloaded_file_verification.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "relative_path",
            "size_bytes",
            "sha256",
            "exists",
            "size_verified",
            "sha256_verified",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: str(row["relative_path"])))


def download_d085(output_dir: Path) -> dict[str, Any]:
    session = _session()
    metadata_url = f"https://zenodo.org/api/records/{RECORD_ID}"
    response = session.get(metadata_url, timeout=60)
    response.raise_for_status()
    record = response.json()
    spec = _validated_download_spec(record)

    archive_path = output_dir / "head_neck_cbct_ct/raw" / EXPECTED_FILE_NAME
    _download(session, str(spec["download_url"]), archive_path, int(spec["size_bytes"]))
    if _md5(archive_path).lower() != EXPECTED_MD5:
        raise RuntimeError("Downloaded D085 archive MD5 mismatch")

    metadata_path = output_dir / "head_neck_cbct_ct/metadata" / f"zenodo_record_{RECORD_ID}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = output_dir / "navigation_cbct_stl_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = [dict(item) for item in payload.get("records") or []]
    matches = [index for index, item in enumerate(records) if item.get("candidate_id") == "D085"]
    if len(matches) != 1:
        raise RuntimeError("Navigation audit manifest must contain exactly one D085 record")
    downloaded_at_utc = datetime.now(timezone.utc).isoformat()
    archive_entry = _relative_file_entry(output_dir, archive_path, role="source_archive")
    archive_entry.update(
        {
            "direct_download_url": spec["download_url"],
            "zenodo_checksum": f"md5:{EXPECTED_MD5}",
            "md5_verified": True,
        }
    )
    metadata_entry = _relative_file_entry(output_dir, metadata_path, role="official_api_metadata")
    index = matches[0]
    records[index] = _update_manifest_record(
        records[index],
        spec=spec,
        archive_entry=archive_entry,
        metadata_entry=metadata_entry,
        downloaded_at_utc=downloaded_at_utc,
    )
    payload["generated_at_utc"] = downloaded_at_utc
    payload["records"] = records
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_summary_csv(output_dir, records)
    _write_verification_csv(output_dir, records)
    return records[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    record = download_d085(output_dir)
    archive = next(item for item in record["local_files"] if item.get("file_role") == "source_archive")
    print(
        json.dumps(
            {
                "candidate_id": record["candidate_id"],
                "download_status": record["download_status"],
                "local_path": str((output_dir / archive["path"]).resolve()),
                "size_bytes": archive["size_bytes"],
                "sha256": archive["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
