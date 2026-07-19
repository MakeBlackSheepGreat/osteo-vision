from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from PIL import Image

try:
    _shared_downloads = cast(Any, import_module("tools.download_three_priority_zenodo_datasets"))
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    _shared_downloads = cast(Any, import_module("download_three_priority_zenodo_datasets"))

_download = _shared_downloads._download
_session = _shared_downloads._session
_sha256 = _shared_downloads._sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d093_mronj_spect_ct_figures_20260719"

DATASET_ID = "D093"
MENDELEY_ID = "7x7dxvg8cc"
VERSION = 1
EXPECTED_DOI = "10.17632/7x7dxvg8cc.1"
EXPECTED_LICENSE = "CC BY 4.0"
EXPECTED_TITLE = (
    "The added diagnostic value of SPECT/CT in detecting periapical and periodontal inflammation "
    "in medication-related osteonecrosis of the jaw patients"
)
VISUAL_REVIEWED_AT_UTC = "2026-07-19T01:29:25+00:00"
SOURCE_PAGE_URL = f"https://data.mendeley.com/datasets/{MENDELEY_ID}/{VERSION}"
SNAPSHOT_URL = f"https://data.mendeley.com/public-api/datasets/{MENDELEY_ID}/snapshot/{VERSION}"
FILES_URL = f"https://data.mendeley.com/public-api/datasets/{MENDELEY_ID}/files?folder_id=root&version={VERSION}"

PINNED_FILES: tuple[dict[str, Any], ...] = (
    {
        "id": "0ad800a1-e90a-4c55-8c12-b8197985ae8d",
        "filename": "Fig 1.JPG",
        "local_name": "Fig_1.jpg",
        "size": 41_990,
        "sha256": "d0b04d4992e63f42a20f82c4f46297e242cee1391a2767c2171f32a8ad764ee8",
        "content_type": "image/jpeg",
        "file_role": "published_roc_curve_figure",
        "visual_classification": "diagnostic_roc_curve_without_anatomical_imaging",
        "visual_observation": (
            "A 1280x720 ROC plot with two colored step curves and a diagonal reference line; "
            "no anatomical image or pixel-level lesion annotation is present."
        ),
        "contains_patient_imaging": False,
    },
    {
        "id": "4096fa99-ee1d-41ad-9372-6b108a8766ff",
        "filename": "Fig 2.TIF",
        "local_name": "Fig_2.tif",
        "size": 478_074,
        "sha256": "b8934e5abaa9477284b6471e0e3180c157814005c02a3bfefa3809198dafb6fb",
        "content_type": "image/tiff",
        "file_role": "published_spect_ct_composite_figure",
        "visual_classification": "mronj_spect_ct_multiplanar_composite_with_roi_table",
        "visual_observation": (
            "A 1280x720 multi-panel figure with coronal, sagittal and transaxial CT, SPECT and "
            "hybrid views, colored jaw/lesion ROI contours, and an SUV quantification table."
        ),
        "contains_patient_imaging": True,
    },
)


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if str(snapshot.get("id") or "") != MENDELEY_ID:
        raise RuntimeError("Mendeley dataset identifier mismatch")
    if int(snapshot.get("version") or 0) != VERSION:
        raise RuntimeError("Mendeley dataset version changed")
    if str(snapshot.get("doi") or "").lower() != EXPECTED_DOI.lower():
        raise RuntimeError("Mendeley dataset DOI changed")
    if str(snapshot.get("name") or "") != EXPECTED_TITLE:
        raise RuntimeError("Mendeley dataset title changed")
    if snapshot.get("is_confidential") is not False or snapshot.get("is_metadata_only") is not False:
        raise RuntimeError("Mendeley dataset access state is unsuitable")
    licence = snapshot.get("licence") or {}
    if str(licence.get("short_name") or "") != EXPECTED_LICENSE:
        raise RuntimeError("Mendeley dataset license changed")


def _validate_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("id") or ""): item for item in files}
    validated: list[dict[str, Any]] = []
    for pinned in PINNED_FILES:
        item = by_id.get(str(pinned["id"]))
        if item is None:
            raise RuntimeError(f"Mendeley pinned file is missing: {pinned['id']}")
        details = item.get("content_details") or {}
        if str(item.get("filename") or "") != pinned["filename"]:
            raise RuntimeError(f"Mendeley pinned filename changed: {pinned['id']}")
        if int(details.get("size") or item.get("size") or 0) != int(pinned["size"]):
            raise RuntimeError(f"Mendeley pinned file size changed: {pinned['id']}")
        if str(details.get("sha256_hash") or "").lower() != str(pinned["sha256"]).lower():
            raise RuntimeError(f"Mendeley pinned file SHA256 changed: {pinned['id']}")
        if str(details.get("content_type") or "").lower() != str(pinned["content_type"]).lower():
            raise RuntimeError(f"Mendeley pinned content type changed: {pinned['id']}")
        download_url = str(details.get("download_url") or "")
        expected_prefix = f"https://data.mendeley.com/public-files/datasets/{MENDELEY_ID}/files/"
        if not download_url.startswith(expected_prefix):
            raise RuntimeError(f"Mendeley pinned download URL is invalid: {pinned['id']}")
        validated.append({**pinned, "download_url": download_url})
    if len(files) != len(PINNED_FILES):
        raise RuntimeError("Mendeley dataset file inventory changed")
    return validated


def _image_metadata(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return {
            "format": str(image.format or ""),
            "width": int(image.width),
            "height": int(image.height),
            "mode": str(image.mode),
            "frame_count": int(getattr(image, "n_frames", 1)),
        }


def _metadata_entry(output_dir: Path, path: Path, *, role: str, url: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "file_role": role,
        "direct_download_url": url,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _download_pinned(
    session: Any,
    url: str,
    destination: Path,
    *,
    expected_size: int,
    expected_sha256: str,
) -> None:
    if destination.is_file():
        if destination.stat().st_size == expected_size and _sha256(destination) == expected_sha256:
            return
        destination.unlink()
    _download(session, url, destination, expected_size)
    actual_size = destination.stat().st_size if destination.is_file() else 0
    actual_sha256 = _sha256(destination) if destination.is_file() else ""
    if actual_size != expected_size or actual_sha256 != expected_sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"Mendeley downloaded integrity mismatch for {destination.name}: "
            f"size={actual_size}, sha256={actual_sha256}"
        )


def download_d093(output_dir: Path) -> dict[str, Any]:
    session = _session()
    headers = {"Accept": "application/vnd.mendeley-public-dataset.1+json"}
    snapshot_response = session.get(SNAPSHOT_URL, headers=headers, timeout=60)
    snapshot_response.raise_for_status()
    snapshot = snapshot_response.json()
    _validate_snapshot(snapshot)

    files_response = session.get(FILES_URL, headers=headers, timeout=60)
    files_response.raise_for_status()
    files = files_response.json()
    if not isinstance(files, list):
        raise RuntimeError("Mendeley file inventory is not a list")
    specs = _validate_files(files)

    output_dir.mkdir(parents=True, exist_ok=True)
    local_files: list[dict[str, Any]] = []
    image_checks: list[dict[str, Any]] = []
    for spec in specs:
        destination = output_dir / "raw" / str(spec["local_name"])
        _download_pinned(
            session,
            str(spec["download_url"]),
            destination,
            expected_size=int(spec["size"]),
            expected_sha256=str(spec["sha256"]),
        )
        digest = _sha256(destination)
        metadata = _image_metadata(destination)
        image_checks.append(
            {
                "source_filename": spec["filename"],
                **metadata,
                "visual_classification": spec["visual_classification"],
                "visual_observation": spec["visual_observation"],
                "contains_patient_imaging": spec["contains_patient_imaging"],
            }
        )
        local_files.append(
            {
                "path": destination.relative_to(output_dir).as_posix(),
                "file_role": spec["file_role"],
                "source_filename": spec["filename"],
                "mendeley_file_id": spec["id"],
                "direct_download_url": spec["download_url"],
                "content_type": spec["content_type"],
                "size_bytes": destination.stat().st_size,
                "sha256": digest,
            }
        )

    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = metadata_dir / "mendeley_snapshot.json"
    files_path = metadata_dir / "mendeley_files.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files_path.write_text(json.dumps(files, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    local_files.extend(
        [
            _metadata_entry(output_dir, snapshot_path, role="official_snapshot_metadata", url=SNAPSHOT_URL),
            _metadata_entry(output_dir, files_path, role="official_file_inventory", url=FILES_URL),
        ]
    )

    downloaded_at = datetime.now(timezone.utc).isoformat()
    record = {
        "candidate_id": DATASET_ID,
        "dataset_name": EXPECTED_TITLE,
        "source_page_url": SOURCE_PAGE_URL,
        "metadata_urls": [SNAPSHOT_URL, FILES_URL],
        "direct_download_urls": [spec["download_url"] for spec in specs],
        "license": EXPECTED_LICENSE,
        "license_identifier": "cc-by-4.0",
        "license_review_status": "verified_from_mendeley_public_api",
        "domain_tier": "target_condition_near_published_figure_proxy",
        "modality": "published MRONJ diagnostic ROC plot and SPECT/CT composite figure",
        "labels": "visual ROI contours in one figure; no machine-readable lesion, bone or inflammation mask",
        "sample_count": len(specs),
        "sample_count_unit": "released_figure_files",
        "patient_count_unavailable_reason": "The two released figures do not expose a patient-level inventory.",
        "clinical_variables_unavailable_reason": (
            "The public figure release does not include patient-level demographics, laboratory values or medications."
        ),
        "recommended_use": (
            "Target-condition-near SPECT/CT layout review, ROI-table extraction checks and "
            "evidence-boundary validation."
        ),
        "image_checks": image_checks,
        "visual_review": {
            "status": "completed",
            "reviewed_at_utc": VISUAL_REVIEWED_AT_UTC,
            "method": "local_original_pixel_visual_inspection",
            "finding_count": len(image_checks),
            "findings": [
                {
                    "source_filename": item["source_filename"],
                    "visual_classification": item["visual_classification"],
                    "visual_observation": item["visual_observation"],
                    "contains_patient_imaging": item["contains_patient_imaging"],
                }
                for item in image_checks
            ],
            "summary": (
                "The release contains one ROC plot and one SPECT/CT composite imaging figure. "
                "Only the TIFF contains anatomical imaging and visual ROI contours."
            ),
        },
        "local_files": local_files,
        "download_status": "verified_complete_public_figure_release",
        "downloaded_at_utc": downloaded_at,
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
        "data_boundary": (
            "A published ROC plot and a published SPECT/CT composite figure from an MRONJ study. "
            "The release has no raw DICOM, paired white-light/ICG frames, patient-level inventory or "
            "pixel ground truth and cannot support model training, clinical performance or spatial "
            "navigation claims."
        ),
    }
    manifest = {
        "schema_version": "osteo-vision-d093-mronj-spect-ct-figures-v1",
        "generated_at_utc": downloaded_at,
        "record_count": 1,
        "file_count": len(local_files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in local_files),
        "records": [record],
    }
    manifest_path = output_dir / "d093_mronj_spect_ct_figures_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    manifest = download_d093(output_dir)
    record = manifest["records"][0]
    print(
        json.dumps(
            {
                "candidate_id": record["candidate_id"],
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
