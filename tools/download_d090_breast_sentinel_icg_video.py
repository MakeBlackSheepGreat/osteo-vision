from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import stat
import zlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile, ZipInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d090_breast_sentinel_icg_video_20260719"
CANDIDATE_ID = "D090"
RECORD_ID = "17745489"
DOI = "10.5281/zenodo.17745489"
SOURCE_PAGE_URL = f"https://zenodo.org/records/{RECORD_ID}"
METADATA_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
EXPECTED_LICENSE_ID = "cc-by-4.0"
EXPECTED_VIDEO_COUNT = 3
VIDEO_SUFFIXES = {".avi", ".m4v", ".mov", ".mp4"}
_MD5_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "Osteo-Vision D090 dataset downloader/1.0"})
    return session


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise RuntimeError(f"D090 download URL must use HTTPS: {url}")
    return url


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        raise RuntimeError(f"D090 has an unsafe empty file name: {value!r}")
    return cleaned


def _contained_path(root: Path, relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise RuntimeError(f"D090 output path escapes the dataset directory: {relative_path}")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"D090 output path escapes the dataset directory: {relative_path}") from exc
    return candidate


def _expected_md5(checksum: str) -> str:
    value = checksum.removeprefix("md5:").lower()
    if not _MD5_PATTERN.fullmatch(value):
        raise RuntimeError(f"D090 Zenodo file has no valid MD5 checksum: {checksum!r}")
    return value


def _select_archive(files: list[dict[str, Any]]) -> dict[str, Any]:
    safe_names: set[str] = set()
    for item in files:
        original_name = str(item.get("key") or "")
        safe_name = _safe_name(original_name).casefold()
        if safe_name in safe_names:
            raise RuntimeError(f"D090 Zenodo metadata has duplicate file names: {original_name}")
        safe_names.add(safe_name)
    archives = [item for item in files if Path(str(item.get("key") or "")).suffix.lower() == ".zip"]
    if len(archives) != 1:
        raise RuntimeError(f"D090 requires exactly one Zenodo ZIP archive; found {len(archives)}")
    archive = archives[0]
    _expected_md5(str(archive.get("checksum") or ""))
    if int(archive.get("size") or 0) <= 0:
        raise RuntimeError("D090 Zenodo archive has an invalid declared size")
    _validate_https_url(str((archive.get("links") or {}).get("self") or ""))
    return archive


def _verify_file(path: Path, expected_size: int, expected_md5: str) -> dict[str, Any]:
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(f"D090 size mismatch for {path.name}: {actual_size} != {expected_size}")
    actual_md5 = _md5(path)
    if actual_md5.lower() != expected_md5.lower():
        raise RuntimeError(f"D090 MD5 mismatch for {path.name}: {actual_md5} != {expected_md5}")
    return {
        "size_bytes": actual_size,
        "md5": actual_md5,
        "sha256": _sha256(path),
    }


def _download_verified(
    session: requests.Session,
    url: str,
    destination: Path,
    *,
    expected_size: int,
    expected_md5: str,
) -> dict[str, Any]:
    _validate_https_url(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        try:
            return _verify_file(destination, expected_size, expected_md5)
        except RuntimeError:
            destination.unlink()

    partial = destination.with_name(destination.name + ".part")
    partial.unlink(missing_ok=True)
    try:
        with session.get(url, stream=True, timeout=(30, 300)) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                    if chunk:
                        handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        receipt = _verify_file(partial, expected_size, expected_md5)
        partial.replace(destination)
        return receipt
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _is_symlink(info: ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def _video_members(archive_path: Path) -> list[ZipInfo]:
    try:
        with ZipFile(archive_path) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir() and PurePosixPath(info.filename).suffix.lower() in VIDEO_SUFFIXES
            ]
    except BadZipFile as exc:
        raise RuntimeError("D090 downloaded archive is not a valid ZIP file") from exc

    safe_names: set[str] = set()
    for info in members:
        member_path = PurePosixPath(info.filename)
        if member_path.is_absolute() or ".." in member_path.parts or _is_symlink(info):
            raise RuntimeError(f"D090 archive contains an unsafe video member: {info.filename}")
        safe_name = _safe_name(member_path.name).casefold()
        if safe_name in safe_names:
            raise RuntimeError(f"D090 archive contains duplicate video names: {info.filename}")
        safe_names.add(safe_name)
    if len(members) != EXPECTED_VIDEO_COUNT:
        raise RuntimeError(f"D090 requires {EXPECTED_VIDEO_COUNT} supplementary videos; found {len(members)}")
    return sorted(members, key=lambda info: info.filename.casefold())


def _extract_videos(archive_path: Path, output_dir: Path) -> list[dict[str, Any]]:
    members = _video_members(archive_path)
    receipts: list[dict[str, Any]] = []
    with ZipFile(archive_path) as archive:
        for info in members:
            local_name = _safe_name(PurePosixPath(info.filename).name)
            destination = _contained_path(output_dir, Path("raw/videos") / local_name)
            partial = destination.with_name(destination.name + ".part")
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial.unlink(missing_ok=True)
            digest = hashlib.sha256()
            crc32 = 0
            actual_size = 0
            try:
                with archive.open(info, "r") as source, partial.open("wb") as target:
                    for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                        target.write(chunk)
                        digest.update(chunk)
                        crc32 = zlib.crc32(chunk, crc32)
                        actual_size += len(chunk)
                    target.flush()
                    os.fsync(target.fileno())
                if actual_size != int(info.file_size):
                    raise RuntimeError(
                        f"D090 extracted size mismatch for {info.filename}: " f"{actual_size} != {info.file_size}"
                    )
                actual_crc32 = f"{crc32 & 0xFFFFFFFF:08x}"
                expected_crc32 = f"{info.CRC:08x}"
                if actual_crc32 != expected_crc32:
                    raise RuntimeError(
                        f"D090 ZIP CRC mismatch for {info.filename}: " f"{actual_crc32} != {expected_crc32}"
                    )
                partial.replace(destination)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            receipts.append(
                {
                    "artifact_role": "extracted_supplementary_video",
                    "source_archive_member": info.filename,
                    "local_path": str(destination.relative_to(output_dir)),
                    "original_file_name": PurePosixPath(info.filename).name,
                    "size_bytes": actual_size,
                    "sha256": digest.hexdigest(),
                    "zip_crc32": expected_crc32,
                    "zip_crc_verified": True,
                }
            )
    return receipts


def _write_metadata_snapshot(output_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    destination = _contained_path(output_dir, "metadata/zenodo_record_17745489.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    partial = destination.with_name(destination.name + ".part")
    partial.write_bytes(payload)
    partial.replace(destination)
    return {
        "artifact_role": "zenodo_metadata_snapshot",
        "direct_download_url": METADATA_URL,
        "local_path": str(destination.relative_to(output_dir)),
        "original_file_name": destination.name,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def _license_id(metadata: dict[str, Any]) -> str:
    value = metadata.get("license")
    if isinstance(value, dict):
        return str(value.get("id") or "").lower()
    return str(value or "").lower()


def download_d090(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session = _session()
    response = session.get(METADATA_URL, timeout=60)
    response.raise_for_status()
    record = response.json()
    if str(record.get("id")) != RECORD_ID:
        raise RuntimeError(f"D090 Zenodo record ID mismatch: {record.get('id')} != {RECORD_ID}")
    metadata = dict(record.get("metadata") or {})
    license_id = _license_id(metadata)
    if license_id != EXPECTED_LICENSE_ID:
        raise RuntimeError(f"D090 license mismatch: {license_id!r} != {EXPECTED_LICENSE_ID!r}")

    archive = _select_archive(list(record.get("files") or []))
    archive_name = _safe_name(str(archive["key"]))
    archive_path = _contained_path(output_dir, Path("raw/archive") / archive_name)
    content_url = str((archive.get("links") or {})["self"])
    zenodo_checksum = str(archive["checksum"])
    expected_md5 = _expected_md5(zenodo_checksum)
    archive_receipt = _download_verified(
        session,
        content_url,
        archive_path,
        expected_size=int(archive["size"]),
        expected_md5=expected_md5,
    )
    videos = _extract_videos(archive_path, output_dir)
    metadata_receipt = _write_metadata_snapshot(output_dir, record)
    downloaded_at = datetime.now(timezone.utc).isoformat()
    local_artifacts = [
        metadata_receipt,
        {
            "artifact_role": "zenodo_source_archive",
            "direct_download_url": content_url,
            "local_path": str(archive_path.relative_to(output_dir)),
            "original_file_name": str(archive["key"]),
            "size_bytes": archive_receipt["size_bytes"],
            "zenodo_checksum": zenodo_checksum,
            "zenodo_declared_md5": expected_md5,
            "local_md5": archive_receipt["md5"],
            "sha256": archive_receipt["sha256"],
        },
        *videos,
    ]
    creators = [str(item.get("name")) for item in metadata.get("creators") or [] if item.get("name")]
    dataset_record = {
        "candidate_id": CANDIDATE_ID,
        "dataset_name": str(metadata.get("title") or ""),
        "record_id": RECORD_ID,
        "doi": str(metadata.get("doi") or DOI),
        "source_page_url": SOURCE_PAGE_URL,
        "metadata_url": METADATA_URL,
        "direct_download_url": content_url,
        "publication_date": metadata.get("publication_date"),
        "creators": creators,
        "license": "CC BY 4.0",
        "license_identifier": license_id,
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_review_status": "verified_from_zenodo_metadata",
        "domain_tier": "clinical_human_icg_non_jaw_non_bone_non_target_domain_video_proxy",
        "medical_scene": "human_breast_cancer_sentinel_lymph_node_biopsy",
        "anatomy_scope": "breast_and_axillary_sentinel_lymph_node; no jaw or bone target",
        "modality": "human intraoperative ICG fluorescence supplementary videos",
        "fluorescence_agent": "indocyanine_green_icg",
        "channel_availability": "requires per-video visual review; source metadata does not define channel layout",
        "labels": (
            "Supplementary video identities S1-S3 only; no pixel segmentation masks, bone labels, "
            "necrotic-transition-viable labels, or frame-level quality labels"
        ),
        "sample_count": EXPECTED_VIDEO_COUNT,
        "video_count": len(videos),
        "patient_count_unavailable_reason": (
            "The Zenodo record does not publish a patient-to-video mapping or an independent patient count."
        ),
        "clinical_variables_unavailable_reason": (
            "No patient-level age, sex, comorbidity, medication, laboratory, or blood-index table is published."
        ),
        "recommended_use": (
            "MP4/video decoding, ICG temporal signal quality anomalies, playback, ignore/abstention, "
            "and non-target-domain robustness engineering validation after manual content review."
        ),
        "prohibited_use": (
            "No jaw-osteomyelitis, bone-viability, patient-conditioned segmentation, diagnostic, "
            "resection-boundary, navigation, or clinical-performance claim."
        ),
        "target_domain_flag": False,
        "non_target_domain": True,
        "non_jaw": True,
        "non_bone": True,
        "training_eligible": False,
        "review_state": "review_required",
        "download_status": "verified",
        "downloaded_at_utc": downloaded_at,
        "zenodo_archive_size_bytes": int(archive["size"]),
        "zenodo_archive_checksum": zenodo_checksum,
        "archive_integrity_verified": True,
        "extracted_video_crc_verified": all(bool(item["zip_crc_verified"]) for item in videos),
        "local_artifacts": local_artifacts,
        "data_boundary": (
            "Public CC BY 4.0 human breast-cancer sentinel-lymph-node ICG supplementary videos. "
            "They are non-jaw, non-bone, and non-target-domain proxy data. They provide no "
            "jaw-osteomyelitis ground truth, bone-surface mask, bone-activity class, patient clinical "
            "variables, or physician segmentation. Training admission remains false."
        ),
    }
    manifest = {
        "schema_version": "osteo-vision-d090-breast-sentinel-icg-video-v1",
        "generated_at_utc": downloaded_at,
        "record_count": 1,
        "dataset_count": 1,
        "video_count": len(videos),
        "artifact_count": len(local_artifacts),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in local_artifacts),
        "records": [dataset_record],
        "medical_boundary": (
            "D090 is restricted to public non-target-domain ICG video engineering validation. "
            "It remains excluded from target-domain training and all clinical performance claims."
        ),
    }
    return manifest


def write_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    output_dir = output_dir.resolve()
    manifest_path = _contained_path(output_dir, "d090_breast_sentinel_icg_video_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = list(manifest["records"][0]["local_artifacts"])
    csv_path = _contained_path(output_dir, "d090_breast_sentinel_icg_video_files.csv")
    fieldnames = sorted({key for row in rows for key in row})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    manifest = download_d090(output_dir)
    write_manifest(output_dir, manifest)
    print(
        json.dumps(
            {
                "candidate_id": CANDIDATE_ID,
                "output_dir": str(output_dir),
                "video_count": manifest["video_count"],
                "artifact_count": manifest["artifact_count"],
                "total_size_bytes": manifest["total_size_bytes"],
                "status": "verified",
                "training_eligible": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
