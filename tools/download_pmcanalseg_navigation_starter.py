from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np

try:
    from tools.download_three_priority_zenodo_datasets import _download, _md5, _session, _sha256
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_three_priority_zenodo_datasets import _download, _md5, _session, _sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/pmcanalseg_navigation_starter_20260719"

DATASET_ID = "D092"
PERSISTENT_ID = "doi:10.7910/DVN/RTIGTP"
SOURCE_PAGE_URL = "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/RTIGTP"
METADATA_URL = "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=" "doi%3A10.7910%2FDVN%2FRTIGTP"
EXPECTED_VERSION = 2
EXPECTED_LICENSE = "CC0 1.0"
SELECTED_PATIENTS = ("Patient_001", "Patient_044", "Patient_096", "Patient_159", "Patient_180")


PINNED_FILES: tuple[dict[str, Any], ...] = (
    {
        "patient": "Patient_001",
        "region": "lower",
        "role": "image",
        "id": 13090101,
        "size": 1_675_823,
        "md5": "e30c9871ee6565f2f4bd00a25b043cb0",
    },
    {
        "patient": "Patient_001",
        "region": "lower",
        "role": "label",
        "id": 13089500,
        "size": 488_271,
        "md5": "10b54bf2e3a1d5b44b87ae6777aa8c3c",
    },
    {
        "patient": "Patient_001",
        "region": "upper",
        "role": "image",
        "id": 13089564,
        "size": 9_028_001,
        "md5": "74d8310861943e73982fb1b630e900ea",
    },
    {
        "patient": "Patient_001",
        "region": "upper",
        "role": "label",
        "id": 13089995,
        "size": 484_822,
        "md5": "97ce3b8cb6fd0dcfe744ce4dc463522a",
    },
    {
        "patient": "Patient_044",
        "region": "lower",
        "role": "image",
        "id": 13089533,
        "size": 1_631_694,
        "md5": "26001e3eb2933ec519e714fbdae14056",
    },
    {
        "patient": "Patient_044",
        "region": "lower",
        "role": "label",
        "id": 13089426,
        "size": 384_629,
        "md5": "c18916e092e8bce618a317884a10d5f3",
    },
    {
        "patient": "Patient_044",
        "region": "upper",
        "role": "image",
        "id": 13089918,
        "size": 10_622_492,
        "md5": "cacd4eebac9fabcfe83df1ab3d8f542e",
    },
    {
        "patient": "Patient_044",
        "region": "upper",
        "role": "label",
        "id": 13090061,
        "size": 382_659,
        "md5": "2af7646723aacd409d7b5b3eba018039",
    },
    {
        "patient": "Patient_096",
        "region": "lower",
        "role": "image",
        "id": 13089679,
        "size": 2_272_589,
        "md5": "ba7cb94f84c8923b2b645c75bd8c51af",
    },
    {
        "patient": "Patient_096",
        "region": "lower",
        "role": "label",
        "id": 13089730,
        "size": 419_578,
        "md5": "1884b5f89483dced1775fd515f466882",
    },
    {
        "patient": "Patient_096",
        "region": "upper",
        "role": "image",
        "id": 13089487,
        "size": 14_134_533,
        "md5": "c777096f8a8c21a467138c2be1fd8584",
    },
    {
        "patient": "Patient_096",
        "region": "upper",
        "role": "label",
        "id": 13090105,
        "size": 416_933,
        "md5": "4a3565c17d29cf9cc8081412d506b519",
    },
    {
        "patient": "Patient_159",
        "region": "lower",
        "role": "image",
        "id": 13090075,
        "size": 1_804_712,
        "md5": "17202845f8889e811f2473b4b1c271ce",
    },
    {
        "patient": "Patient_159",
        "region": "lower",
        "role": "label",
        "id": 13089326,
        "size": 448_053,
        "md5": "49473ea6786acb726146ff264fb8407d",
    },
    {
        "patient": "Patient_159",
        "region": "upper",
        "role": "image",
        "id": 13089344,
        "size": 9_895_232,
        "md5": "72b5a61967d4cbe0a2a7c864329f8890",
    },
    {
        "patient": "Patient_159",
        "region": "upper",
        "role": "label",
        "id": 13089601,
        "size": 446_044,
        "md5": "930b5a8cd19bca29418c289fee328bf7",
    },
    {
        "patient": "Patient_180",
        "region": "lower",
        "role": "image",
        "id": 13089490,
        "size": 3_539_964,
        "md5": "4a81879c1afd5fc502076a3da5971475",
    },
    {
        "patient": "Patient_180",
        "region": "lower",
        "role": "label",
        "id": 13089339,
        "size": 656_237,
        "md5": "f644160a9831057b338c2572ea45251f",
    },
    {
        "patient": "Patient_180",
        "region": "upper",
        "role": "image",
        "id": 13089759,
        "size": 15_293_497,
        "md5": "691eaec4ca4dadfff4c01a72a6203cf8",
    },
    {
        "patient": "Patient_180",
        "region": "upper",
        "role": "label",
        "id": 13089688,
        "size": 654_110,
        "md5": "9e5b0d31af14957eef1d3757e03cc99b",
    },
    {
        "patient": None,
        "region": "metadata",
        "role": "information",
        "id": 13091480,
        "size": 14_449,
        "md5": "c05c4fe3510bba58d9ffc9c418d4b787",
    },
)


def _access_url(file_id: int) -> str:
    return f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"


def _expected_directory(spec: dict[str, Any]) -> str:
    if spec["role"] == "information":
        return ""
    return f"{spec['region']}/{spec['patient']}"


def _expected_label(spec: dict[str, Any]) -> str:
    if spec["role"] == "information":
        return "Information.xlsx"
    return "image.nii.gz" if spec["role"] == "image" else "label.nii.gz"


def _validate_dataset_metadata(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if str(payload.get("status") or "OK").upper() not in {"OK", "200"}:
        raise RuntimeError("Harvard Dataverse metadata status is not OK")
    data = payload.get("data") or {}
    if str(data.get("protocol") or "doi").lower() != "doi":
        raise RuntimeError("PMCanalSeg persistent identifier protocol changed")
    authority = str(data.get("authority") or "10.7910")
    identifier = str(data.get("identifier") or "DVN/RTIGTP")
    if f"doi:{authority}/{identifier}".lower() != PERSISTENT_ID.lower():
        raise RuntimeError("PMCanalSeg persistent identifier mismatch")

    version = data.get("latestVersion") or {}
    if int(version.get("versionNumber") or 0) != EXPECTED_VERSION:
        raise RuntimeError("PMCanalSeg dataset version changed")
    if str(version.get("versionState") or "").upper() != "RELEASED":
        raise RuntimeError("PMCanalSeg dataset version is not released")
    license_value = version.get("license") or {}
    if str(license_value.get("name") or "") != EXPECTED_LICENSE:
        raise RuntimeError("PMCanalSeg dataset license changed")

    remote_files = {int((entry.get("dataFile") or {}).get("id") or 0): entry for entry in version.get("files") or []}
    validated: list[dict[str, Any]] = []
    for pinned in PINNED_FILES:
        entry = remote_files.get(int(pinned["id"]))
        if entry is None:
            raise RuntimeError(f"PMCanalSeg pinned file is missing: {pinned['id']}")
        data_file = entry.get("dataFile") or {}
        if entry.get("restricted") is True:
            raise RuntimeError(f"PMCanalSeg pinned file became restricted: {pinned['id']}")
        if str(entry.get("directoryLabel") or "") != _expected_directory(pinned):
            raise RuntimeError(f"PMCanalSeg pinned file directory changed: {pinned['id']}")
        if str(entry.get("label") or "") != _expected_label(pinned):
            raise RuntimeError(f"PMCanalSeg pinned file label changed: {pinned['id']}")
        if int(data_file.get("filesize") or 0) != int(pinned["size"]):
            raise RuntimeError(f"PMCanalSeg pinned file size changed: {pinned['id']}")
        if str(data_file.get("md5") or "").lower() != str(pinned["md5"]).lower():
            raise RuntimeError(f"PMCanalSeg pinned file MD5 changed: {pinned['id']}")
        validated.append({**pinned, "download_url": _access_url(int(pinned["id"]))})

    selected = [item for item in validated if item["patient"] is not None]
    for patient in SELECTED_PATIENTS:
        patient_files = [item for item in selected if item["patient"] == patient]
        roles = {(item["region"], item["role"]) for item in patient_files}
        if roles != {("upper", "image"), ("upper", "label"), ("lower", "image"), ("lower", "label")}:
            raise RuntimeError(f"PMCanalSeg patient pair is incomplete: {patient}")
    return validated


def _relative_path(spec: dict[str, Any]) -> Path:
    if spec["role"] == "information":
        return Path("metadata/Information.xlsx")
    return Path("raw") / str(spec["patient"]) / str(spec["region"]) / f"{spec['role']}.nii.gz"


def _nifti_header(path: Path) -> dict[str, Any]:
    image = nib.load(str(path))
    affine = np.asarray(image.affine, dtype=np.float64)
    spacing = tuple(float(value) for value in image.header.get_zooms()[:3])
    determinant = float(np.linalg.det(affine[:3, :3]))
    if len(image.shape) != 3 or any(int(value) <= 0 for value in image.shape):
        raise RuntimeError(f"Invalid PMCanalSeg NIfTI shape: {path}")
    if any(not math.isfinite(value) or value <= 0.0 for value in spacing):
        raise RuntimeError(f"Invalid PMCanalSeg voxel spacing: {path}")
    if not np.isfinite(affine).all() or not math.isfinite(determinant) or abs(determinant) < 1e-12:
        raise RuntimeError(f"Invalid PMCanalSeg physical affine: {path}")
    return {
        "shape": [int(value) for value in image.shape],
        "spacing_mm": list(spacing),
        "orientation": list(nib.aff2axcodes(affine)),
        "affine": affine.round(9).tolist(),
        "affine_determinant": determinant,
        "dtype": str(image.get_data_dtype()),
    }


def _verify_nifti_pairs(output_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for patient in SELECTED_PATIENTS:
        for region in ("upper", "lower"):
            image_path = output_dir / "raw" / patient / region / "image.nii.gz"
            label_path = output_dir / "raw" / patient / region / "label.nii.gz"
            image_header = _nifti_header(image_path)
            label_header = _nifti_header(label_path)
            affine_matches = bool(
                np.allclose(
                    np.asarray(image_header["affine"]),
                    np.asarray(label_header["affine"]),
                    rtol=0.0,
                    atol=1e-6,
                )
            )
            shape_matches = image_header["shape"] == label_header["shape"]
            if not affine_matches or not shape_matches:
                raise RuntimeError(f"PMCanalSeg image/label geometry mismatch: {patient}/{region}")
            label_image = nib.load(str(label_path))
            label_data = np.asanyarray(label_image.dataobj)
            finite = bool(np.isfinite(label_data).all())
            nonzero_voxels = int(np.count_nonzero(label_data))
            unique_values = [float(value) for value in np.unique(label_data)]
            if not finite or nonzero_voxels <= 0 or any(value not in {0.0, 1.0} for value in unique_values):
                raise RuntimeError(f"PMCanalSeg label content is invalid: {patient}/{region}")
            checks.append(
                {
                    "patient_id": patient,
                    "region": region,
                    "image": image_header,
                    "label": label_header,
                    "shape_matches": shape_matches,
                    "affine_matches": affine_matches,
                    "label_values": unique_values,
                    "label_nonzero_voxels": nonzero_voxels,
                    "orientation_review_required": True,
                }
            )
    return checks


def _file_entry(output_dir: Path, path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "file_role": spec["role"],
        "patient_id": spec["patient"],
        "region": spec["region"],
        "dataverse_file_id": spec["id"],
        "direct_download_url": spec["download_url"],
        "size_bytes": path.stat().st_size,
        "source_md5": spec["md5"],
        "md5_verified": True,
        "sha256": _sha256(path),
    }


def _write_csv(output_dir: Path, entries: list[dict[str, Any]]) -> None:
    with (output_dir / "pmcanalseg_navigation_starter_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "patient_id",
            "region",
            "file_role",
            "dataverse_file_id",
            "path",
            "size_bytes",
            "source_md5",
            "sha256",
            "direct_download_url",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: entry.get(key) for key in fieldnames} for entry in entries)


def download_pmcanalseg_starter(output_dir: Path) -> dict[str, Any]:
    session = _session()
    metadata_response = session.get(METADATA_URL, timeout=120)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    specs = _validate_dataset_metadata(metadata)

    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for spec in specs:
        destination = output_dir / _relative_path(spec)
        _download(session, str(spec["download_url"]), destination, int(spec["size"]))
        if _md5(destination).lower() != str(spec["md5"]).lower():
            raise RuntimeError(f"PMCanalSeg downloaded MD5 mismatch: {spec['id']}")
        entries.append(_file_entry(output_dir, destination, spec))

    metadata_path = output_dir / "metadata/dataverse_dataset_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata_entry = {
        "path": metadata_path.relative_to(output_dir).as_posix(),
        "file_role": "official_api_metadata",
        "direct_download_url": METADATA_URL,
        "size_bytes": metadata_path.stat().st_size,
        "sha256": _sha256(metadata_path),
    }
    entries.append(metadata_entry)

    geometry_checks = _verify_nifti_pairs(output_dir)
    downloaded_at = datetime.now(timezone.utc).isoformat()
    record = {
        "dataset_id": DATASET_ID,
        "dataset_name": "PMCanalSeg five-patient paired CBCT navigation starter",
        "source_page_url": SOURCE_PAGE_URL,
        "metadata_url": METADATA_URL,
        "direct_download_urls": [entry["direct_download_url"] for entry in entries],
        "license": EXPECTED_LICENSE,
        "license_review_status": "verified_from_harvard_dataverse_api",
        "domain_tier": "cross_domain_maxillofacial_cbct_navigation_proxy",
        "modality": "cropped maxillofacial CBCT volumes with paired 3D canal masks",
        "labels": "upper pterygopalatine canal and lower mandibular canal binary masks",
        "patient_count": len(SELECTED_PATIENTS),
        "source_patient_count": 191,
        "clinical_variables_unavailable_reason": (
            "The public release does not provide patient-level clinical variables for the selected CBCT volumes."
        ),
        "recommended_use": (
            "Multi-patient NIfTI geometry, physical-coordinate, CBCT import, label alignment and registration "
            "robustness engineering."
        ),
        "selected_patients": list(SELECTED_PATIENTS),
        "geometry_checks": geometry_checks,
        "local_files": entries,
        "download_status": "verified_selected_patient_pairs_downloaded",
        "downloaded_at_utc": downloaded_at,
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
        "navigation_claim_allowed": False,
        "orientation_review_required": True,
        "data_boundary": (
            "Public maxillofacial CBCT anatomy proxy. It contains canal masks rather than osteomyelitis, "
            "necrotic-bone, jaw-surface or intraoperative fluorescence labels. It cannot support clinical "
            "segmentation, physical navigation accuracy or patient-adaptive spatial-effect claims."
        ),
    }
    manifest = {
        "schema_version": "osteo-vision-pmcanalseg-navigation-starter-v1",
        "generated_at_utc": downloaded_at,
        "record_count": 1,
        "file_count": len(entries),
        "total_size_bytes": sum(int(entry["size_bytes"]) for entry in entries),
        "records": [record],
    }
    manifest_path = output_dir / "pmcanalseg_navigation_starter_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir, entries)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    manifest = download_pmcanalseg_starter(output_dir)
    record = manifest["records"][0]
    print(
        json.dumps(
            {
                "dataset_id": record["dataset_id"],
                "patient_count": record["patient_count"],
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
