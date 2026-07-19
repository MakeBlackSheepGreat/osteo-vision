from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/three_priority_zenodo_20260717"

DATASETS: dict[str, dict[str, Any]] = {
    "D074": {
        "record_id": "15260349",
        "name": "Fluorescence Guided Surgery computational assessment dataset",
        "files": None,
        "license_expected": "CC BY 4.0",
        "medical_scene": "human_brain_5ala_ppix_fluorescence_guided_surgery",
        "fluorescence": "5ala_ppix_microscope_fluorescence_and_non_fluorescence_controls",
        "domain_tier": "clinical_microscope_fluorescence_non_jaw_proxy",
        "recommended_use": "weak-fluorescence, surgeon-disagreement, mask and abstention engineering",
        "priority_target": "bone_activity_gray_zone_and_review_proxy",
    },
    "D064": {
        "record_id": "11479346",
        "name": "Fluorescence-guided surgery denoising data and models",
        "files": None,
        "license_expected": "MIT",
        "medical_scene": "fluorescence_guided_surgery_video_denoising",
        "fluorescence": "low_photon_and_excitation_leakage_fluorescence_video",
        "domain_tier": "fluorescence_engineering_proxy",
        "recommended_use": "fluorescence restoration and quality-control validation",
        "priority_target": "bone_activity_signal_quality",
    },
    "D065": {
        "record_id": "14942607",
        "name": "Public ICG surgical supplementary videos",
        "files": None,
        "license_expected": "CC BY 4.0",
        "medical_scene": "human_liver_icg_perfusion_surgery",
        "fluorescence": "dynamic_icg_fluorescence",
        "domain_tier": "clinical_icg_non_jaw_proxy",
        "recommended_use": "MP4 ingestion, temporal ICG quantification and playback validation",
        "priority_target": "bone_activity_temporal_pipeline",
    },
    "D049": {
        "record_id": "8411792",
        "name": "Fluorescence labelled infected mouse bone tissues",
        "files": ["Mandal_etal_ijms_2023_Figure_1_(bacteria channel Lime).czi"],
        "license_expected": "CC BY 4.0",
        "medical_scene": "infected_mouse_bone_multiphoton_microscopy",
        "fluorescence": "labelled_staphylococcus_aureus_and_bone_microstructure",
        "domain_tier": "animal_bone_infection_microscopy_proxy",
        "recommended_use": "infection-bone fluorescence preprocessing and representation learning",
        "priority_target": "bone_activity_and_infection_signal_proxy",
    },
}


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
    session.headers.update({"User-Agent": "Osteo-Vision research dataset downloader/1.0"})
    return session


def _safe_name(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _license_label(metadata: dict[str, Any]) -> str:
    license_value = metadata.get("license")
    if isinstance(license_value, dict):
        return str(license_value.get("title") or license_value.get("id") or "unknown")
    return str(license_value or "unknown")


def _selected_files(files: list[dict[str, Any]], names: list[str] | None) -> list[dict[str, Any]]:
    if names is None:
        return files
    by_name = {str(item.get("key")): item for item in files}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise RuntimeError(f"Zenodo record is missing selected files: {missing}")
    return [by_name[name] for name in names]


def _download(session: requests.Session, url: str, destination: Path, expected_size: int) -> None:
    if destination.exists() and destination.stat().st_size == expected_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, 8):
        current_size = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={current_size}-"} if current_size else {}
        try:
            with session.get(url, headers=headers, stream=True, timeout=(30, 300)) as response:
                response.raise_for_status()
                if current_size and response.status_code != 206:
                    partial.unlink(missing_ok=True)
                    current_size = 0
                mode = "ab" if current_size and response.status_code == 206 else "wb"
                with partial.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                        if chunk:
                            handle.write(chunk)
        except RequestException:
            if attempt == 7:
                raise
            continue
        actual_size = partial.stat().st_size
        if actual_size == expected_size:
            break
        if actual_size > expected_size:
            partial.unlink(missing_ok=True)
        if attempt == 7:
            raise RuntimeError(f"Downloaded size mismatch for {destination.name}: {actual_size} != {expected_size}")
    if partial.stat().st_size != expected_size:
        raise RuntimeError(
            f"Downloaded size mismatch for {destination.name}: " f"{partial.stat().st_size} != {expected_size}"
        )
    partial.replace(destination)


def download_datasets(output_dir: Path, dataset_ids: list[str]) -> list[dict[str, Any]]:
    session = _session()
    rows: list[dict[str, Any]] = []
    for dataset_id in dataset_ids:
        spec = DATASETS[dataset_id]
        record_id = str(spec["record_id"])
        metadata_url = f"https://zenodo.org/api/records/{record_id}"
        response = session.get(metadata_url, timeout=60)
        response.raise_for_status()
        record = response.json()
        license_label = _license_label(record.get("metadata") or {})
        files = _selected_files(list(record.get("files") or []), spec["files"])
        for item in files:
            original_name = str(item["key"])
            local_path = output_dir / dataset_id.lower() / "raw" / _safe_name(original_name)
            content_url = str((item.get("links") or {}).get("self") or "")
            expected_size = int(item["size"])
            _download(session, content_url, local_path, expected_size)
            checksum = str(item.get("checksum") or "")
            expected_md5 = checksum.removeprefix("md5:") if checksum.startswith("md5:") else ""
            actual_md5 = _md5(local_path)
            if expected_md5 and actual_md5.lower() != expected_md5.lower():
                raise RuntimeError(f"MD5 mismatch for {original_name}")
            rows.append(
                {
                    "candidate_id": dataset_id,
                    "dataset_name": spec["name"],
                    "record_id": record_id,
                    "source_page_url": f"https://zenodo.org/records/{record_id}",
                    "metadata_url": metadata_url,
                    "direct_download_url": content_url,
                    "original_file_name": original_name,
                    "local_path": str(local_path.resolve()),
                    "size_bytes": local_path.stat().st_size,
                    "zenodo_checksum": checksum,
                    "sha256": _sha256(local_path),
                    "license": license_label,
                    "license_expected": spec["license_expected"],
                    "license_review_status": "verified_from_zenodo_metadata",
                    "medical_scene": spec["medical_scene"],
                    "fluorescence": spec["fluorescence"],
                    "domain_tier": spec["domain_tier"],
                    "recommended_use": spec["recommended_use"],
                    "priority_target": spec["priority_target"],
                    "target_domain_flag": False,
                    "training_eligible": False,
                    "review_state": "review_required",
                    "download_status": "verified",
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "data_boundary": (
                        "Public proxy data for engineering or representation validation. It does not provide "
                        "real intraoperative jaw-osteomyelitis ICG ground truth, physician pixel masks, or "
                        "clinical performance evidence."
                    ),
                }
            )
    return rows


def _merge_existing_rows(output_dir: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest_path = output_dir / "three_priority_zenodo_manifest.json"
    existing_rows: list[dict[str, Any]] = []
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_rows = [dict(item) for item in payload.get("records", [])]

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in [*existing_rows, *rows]:
        key = (str(row["candidate_id"]), str(row["original_file_name"]))
        merged[key] = row
    return [merged[key] for key in sorted(merged)]


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _merge_existing_rows(output_dir, rows)
    payload = {
        "schema_version": "osteo-vision-three-priority-public-datasets-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "records": rows,
        "medical_boundary": (
            "All downloaded files are public non-target-domain resources. Training admission remains false "
            "until license, content, quality and physician-review gates are completed."
        ),
    }
    (output_dir / "three_priority_zenodo_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "three_priority_zenodo_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0]) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    parser.add_argument(
        "--dataset-id",
        action="append",
        choices=sorted(DATASETS),
        dest="dataset_ids",
        help="Dataset ID to download. Repeat to select multiple datasets; defaults to all starter datasets.",
    )
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    dataset_ids = args.dataset_ids or list(DATASETS)
    rows = download_datasets(output_dir, dataset_ids)
    write_manifest(output_dir, rows)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "dataset_ids": dataset_ids,
                "record_count": len(rows),
                "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
