from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.download_three_priority_zenodo_datasets import (
        _download,
        _session,
        _sha256,
    )
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_three_priority_zenodo_datasets import _download, _session, _sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/patient_conditioning_starter_20260717"

KITS23_CASE_FILES: tuple[tuple[str, int, int], ...] = (
    ("case_00000", 225_959_569, 776_578),
    ("case_00001", 276_387_358, 851_533),
    ("case_00002", 101_967_812, 373_942),
    ("case_00003", 118_681_596, 379_266),
    ("case_00004", 25_269_467, 101_172),
)


def _kits23_case_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for case_id, image_size, mask_size in KITS23_CASE_FILES:
        sources.extend(
            [
                {
                    "dataset_id": "D071",
                    "dataset_name": "KiTS23 patient conditioning starter",
                    "file_role": "sample_ct_image",
                    "case_id": case_id,
                    "url": (
                        "https://huggingface.co/datasets/neheller/KiTS-Challenge-Imaging/resolve/main/"
                        f"images/{case_id}.nii.gz?download=true"
                    ),
                    "relative_path": f"d071_kits23/raw/{case_id}/imaging.nii.gz",
                    "expected_size": image_size,
                    "license": "CC BY-NC-SA 4.0",
                    "modalities": "abdominal CT",
                    "labels": "paired with kidney, tumor and cyst segmentation",
                },
                {
                    "dataset_id": "D071",
                    "dataset_name": "KiTS23 patient conditioning starter",
                    "file_role": "sample_pixel_mask",
                    "case_id": case_id,
                    "url": (
                        "https://raw.githubusercontent.com/neheller/kits23/main/dataset/"
                        f"{case_id}/segmentation.nii.gz"
                    ),
                    "relative_path": f"d071_kits23/raw/{case_id}/segmentation.nii.gz",
                    "expected_size": mask_size,
                    "license": "CC BY-NC-SA 4.0",
                    "modalities": "3D segmentation mask",
                    "labels": "kidney, tumor and cyst",
                },
            ]
        )
    return sources


SOURCES: list[dict[str, Any]] = [
    {
        "dataset_id": "D071",
        "dataset_name": "KiTS23 patient conditioning starter",
        "file_role": "clinical_context_table",
        "url": "https://raw.githubusercontent.com/neheller/kits23/main/dataset/kits23.json",
        "relative_path": "d071_kits23/metadata/kits23.json",
        "expected_size": 1_310_350,
        "license": "CC BY-NC-SA 4.0",
        "modalities": "structured clinical context",
        "labels": "age, gender, BMI, comorbidities, smoking, alcohol, eGFR, stage and outcomes",
    },
    *_kits23_case_sources(),
    {
        "dataset_id": "D072",
        "dataset_name": "HCC-TACE-Seg clinical context",
        "file_role": "clinical_context_table",
        "url": ("https://www.cancerimagingarchive.net/wp-content/uploads/" "HCC-TACE-Seg_clinical_data-V2.xlsx"),
        "relative_path": "d072_hcc_tace_seg/metadata/HCC-TACE-Seg_clinical_data-V2.xlsx",
        "expected_size": 128_507,
        "license": "CC BY 4.0",
        "modalities": "structured clinical context",
        "labels": "age, sex, diabetes, smoking, alcohol, hepatitis, cirrhosis, AFP and outcomes",
    },
    {
        "dataset_id": "D072",
        "dataset_name": "HCC-TACE-Seg clinical context",
        "file_role": "tcia_download_manifest",
        "url": ("https://www.cancerimagingarchive.net/wp-content/uploads/" "HCC-TACE-Seg_v1_202201.tcia"),
        "relative_path": "d072_hcc_tace_seg/metadata/HCC-TACE-Seg_v1_202201.tcia",
        "expected_size": None,
        "license": "CC BY 4.0",
        "modalities": "TCIA download manifest",
        "labels": "105 multiphase CT cases with DICOM SEG",
    },
    {
        "dataset_id": "D073",
        "dataset_name": "NSCLC-Radiomics clinical context",
        "file_role": "clinical_context_table",
        "url": (
            "https://www.cancerimagingarchive.net/wp-content/uploads/"
            "NSCLC-Radiomics-Lung1.clinical-version3-Oct-2019.csv"
        ),
        "relative_path": "d073_nsclc_radiomics/metadata/NSCLC-Radiomics-Lung1.clinical.csv",
        "expected_size": None,
        "license": "CC BY-NC 3.0",
        "modalities": "structured clinical context",
        "labels": "age, gender, TNM stage, histology and survival",
    },
    {
        "dataset_id": "D075",
        "dataset_name": "MRONJ clinical and laboratory context",
        "file_role": "target_condition_near_clinical_context_table",
        "url": (
            "https://data.mendeley.com/public-files/datasets/f6yxfvkr4c/files/"
            "e04bda1f-34c2-4b71-a45e-1da6de4dfcac/file_downloaded"
        ),
        "relative_path": "d075_mronj_clinical_context/metadata/MRONJ_clinical_laboratory_data.xlsx",
        "expected_size": 261_512,
        "license": "CC BY 4.0",
        "modalities": "structured MRONJ clinical and perioperative laboratory context",
        "labels": "demographics, medication, lesion distribution, surgery and routine laboratory values",
        "recommended_use_override": (
            "MRONJ clinical feature dictionary, missing-data handling and statistical-prior engineering."
        ),
        "data_boundary_override": (
            "Target-condition-near clinical table without paired images or pixel masks. It cannot prove "
            "that clinical variables improve or alter spatial segmentation."
        ),
    },
]


def download_starter(output_dir: Path) -> list[dict[str, Any]]:
    session = _session()
    rows: list[dict[str, Any]] = []
    for source in SOURCES:
        destination = output_dir / source["relative_path"]
        expected_size = source["expected_size"]
        if expected_size is None:
            if destination.exists() and destination.stat().st_size > 0:
                expected_size = destination.stat().st_size
            else:
                head = session.head(source["url"], allow_redirects=True, timeout=60)
                head.raise_for_status()
                expected_size = int(head.headers["Content-Length"])
        _download(session, source["url"], destination, int(expected_size))
        rows.append(
            {
                **{key: value for key, value in source.items() if not key.endswith("_override")},
                "expected_size": int(expected_size),
                "source_page_url": _source_page(str(source["dataset_id"])),
                "local_path": str(destination.resolve()),
                "size_bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
                "download_status": "verified",
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "target_domain_flag": False,
                "training_eligible": False,
                "review_state": "review_required",
                "recommended_use": source.get(
                    "recommended_use_override",
                    "Patient-conditioning data contract, grouped split, multimodal fusion and safety-fallback "
                    "engineering validation.",
                ),
                "data_boundary": source.get(
                    "data_boundary_override",
                    "Public non-jaw, non-fluorescence proxy data. It cannot validate patient-adaptive "
                    "jaw-osteomyelitis or intraoperative ICG segmentation performance.",
                ),
            }
        )
    return rows


def _source_page(dataset_id: str) -> str:
    return {
        "D071": "https://github.com/neheller/kits23",
        "D072": "https://www.cancerimagingarchive.net/collection/hcc-tace-seg/",
        "D073": "https://www.cancerimagingarchive.net/collection/nsclc-radiomics/",
        "D075": "https://data.mendeley.com/datasets/f6yxfvkr4c/1",
    }[dataset_id]


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "osteo-vision-patient-conditioning-starter-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "records": rows,
        "medical_boundary": (
            "These datasets support engineering of patient-conditioned segmentation and clinical-table "
            "handling. They remain non-target-domain and cannot enable clinical spatial effects."
        ),
    }
    (output_dir / "patient_conditioning_starter_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "patient_conditioning_starter_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    rows = download_starter(output_dir)
    write_manifest(output_dir, rows)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "record_count": len(rows),
                "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
