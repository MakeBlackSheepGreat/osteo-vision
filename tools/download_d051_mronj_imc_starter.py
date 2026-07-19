from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.download_three_priority_zenodo_datasets import (
        _download,
        _md5,
        _session,
        _sha256,
    )
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_three_priority_zenodo_datasets import _download, _md5, _session, _sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/" "d051_mronj_imaging_mass_cytometry_starter_20260718"
SOURCE_PAGE_URL = "https://doi.org/10.6084/m9.figshare.30383407"
FIGSHARE_API_URL = "https://api.figshare.com/v2/articles/30383407/versions/1"
SUBJECT_PATTERN = re.compile(r"^(Patient\d{2}|CTRL\d{2})_\d{2}\.txt$")
REQUIRED_SUBJECTS = tuple(
    [f"Patient{index:02d}" for index in range(1, 7)] + [f"CTRL{index:02d}" for index in range(1, 9)]
)


def subject_id(file_name: str) -> str | None:
    match = SUBJECT_PATTERN.fullmatch(file_name)
    return match.group(1) if match else None


def select_balanced_roi_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {subject: [] for subject in REQUIRED_SUBJECTS}
    for item in files:
        subject = subject_id(str(item.get("name") or ""))
        if subject in grouped:
            grouped[subject].append(item)
    missing = [subject for subject, candidates in grouped.items() if not candidates]
    if missing:
        raise RuntimeError(f"D051 metadata is missing required subjects: {missing}")
    return [
        min(grouped[subject], key=lambda item: (int(item["size"]), str(item["name"]))) for subject in REQUIRED_SUBJECTS
    ]


def select_all_roi_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            item
            for item in files
            if subject_id(str(item.get("name") or "")) or re.fullmatch(r"Tonsil\d{2}\.txt", str(item.get("name") or ""))
        ],
        key=lambda item: str(item["name"]),
    )


def _official_md5(item: dict[str, Any]) -> str:
    value = str(item.get("computed_md5") or item.get("supplied_md5") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{32}", value):
        raise RuntimeError(f"D051 file lacks a valid official MD5: {item.get('name')}")
    return value


def verify_downloaded_file(path: Path, item: dict[str, Any]) -> dict[str, Any]:
    expected_size = int(item["size"])
    if path.stat().st_size != expected_size:
        raise RuntimeError(f"Downloaded size mismatch for {path.name}: {path.stat().st_size} != {expected_size}")
    official_md5 = _official_md5(item)
    local_md5 = _md5(path)
    if local_md5.lower() != official_md5:
        raise RuntimeError(f"MD5 mismatch for {path.name}")
    return {
        "original_file_name": str(item["name"]),
        "direct_download_url": str(item["download_url"]),
        "size_bytes": expected_size,
        "official_md5": official_md5,
        "local_md5": local_md5,
        "sha256": _sha256(path),
    }


def _load_metadata(output_dir: Path, metadata_path: Path | None) -> dict[str, Any]:
    target = metadata_path or output_dir / "metadata/figshare_30383407_v1_api.json"
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    session = _session()
    response = session.get(FIGSHARE_API_URL, timeout=60)
    response.raise_for_status()
    payload = response.json()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _metadata_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = {"panel.csv", "Supplementary Information.docx"}
    selected = [item for item in files if str(item.get("name") or "") in wanted]
    if {str(item["name"]) for item in selected} != wanted:
        raise RuntimeError("D051 metadata does not contain panel.csv and Supplementary Information.docx")
    return sorted(selected, key=lambda item: str(item["name"]))


def download_starter(
    output_dir: Path,
    *,
    metadata_path: Path | None = None,
    all_rois: bool = False,
) -> list[dict[str, Any]]:
    metadata = _load_metadata(output_dir, metadata_path)
    files = list(metadata.get("files") or [])
    roi_files = select_all_roi_files(files) if all_rois else select_balanced_roi_files(files)
    selected = [*roi_files, *_metadata_files(files)]
    session = _session()
    downloaded_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for item in selected:
        name = str(item["name"])
        destination = (
            output_dir / "metadata" / name.replace(" ", "_")
            if name in {"panel.csv", "Supplementary Information.docx"}
            else output_dir / "raw" / name
        )
        _download(session, str(item["download_url"]), destination, int(item["size"]))
        receipt = verify_downloaded_file(destination, item)
        rows.append(
            {
                "dataset_id": "D051",
                "subject_id": subject_id(name) or "metadata",
                "file_role": "imc_roi" if subject_id(name) else "study_metadata",
                "source_page_url": SOURCE_PAGE_URL,
                "license": "CC BY 4.0",
                "local_path": str(destination.resolve()),
                "downloaded_at_utc": downloaded_at,
                "selection_policy": "all_rois" if all_rois else "smallest_roi_per_subject",
                **receipt,
            }
        )
    return rows


def write_download_receipt(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": "osteo-vision-d051-download-receipt-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_page_url": SOURCE_PAGE_URL,
        "record_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "records": rows,
    }
    json_path = output_dir / "d051_download_receipt.json"
    csv_path = output_dir / "d051_download_receipt.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    parser.add_argument("--metadata-path")
    parser.add_argument(
        "--all-rois",
        action="store_true",
        help="Download every patient, control and tonsil ROI. Default is one smallest ROI per subject.",
    )
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    metadata_path = (ROOT / args.metadata_path).resolve() if args.metadata_path else None
    rows = download_starter(output_dir, metadata_path=metadata_path, all_rois=args.all_rois)
    write_download_receipt(output_dir, rows)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "record_count": len(rows),
                "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
                "all_rois": bool(args.all_rois),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
