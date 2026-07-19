from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.download_three_priority_zenodo_datasets import _download, _session, _sha256
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_three_priority_zenodo_datasets import _download, _session, _sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/navigation_starter_20260717"

DATASETS: dict[str, dict[str, Any]] = {
    "D076": {
        "name": "SERV-CT simplified validation dataset",
        "article_id": "26352199",
        "selected_file": "SERV-CT.zip",
        "download_url": "https://ndownloader.figshare.com/files/47857471",
        "size": 36_823_665,
        "md5": "911048d7f15833db6fc0603051a67c9c",
        "source_page_url": (
            "https://rdr.ucl.ac.uk/articles/dataset/"
            "SERV-CT_A_disparity_dataset_from_cone-beam_CT_for_validation_of_endoscopic_3D_reconstruction/"
            "26352199"
        ),
        "license_expected": "CC BY 4.0",
        "medical_scene": "ex_vivo_porcine_stereo_endoscopy_with_cone_beam_ct",
        "recommended_use": (
            "L1 static camera calibration, CT-surface correspondence, depth, reprojection and transform-chain validation"
        ),
    }
}


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_navigation_starter(output_dir: Path) -> list[dict[str, Any]]:
    session = _session()
    rows: list[dict[str, Any]] = []
    for dataset_id, spec in DATASETS.items():
        metadata_url = f"https://api.figshare.com/v2/articles/{spec['article_id']}"
        selected_name = str(spec["selected_file"])
        destination = output_dir / dataset_id.lower() / "raw" / selected_name
        _download(session, str(spec["download_url"]), destination, int(spec["size"]))
        expected_md5 = str(spec["md5"])
        actual_md5 = _md5(destination)
        if expected_md5 and actual_md5.lower() != expected_md5.lower():
            raise RuntimeError(f"MD5 mismatch for {selected_name}")
        rows.append(
            {
                "candidate_id": dataset_id,
                "dataset_name": spec["name"],
                "source_page_url": spec["source_page_url"],
                "metadata_url": metadata_url,
                "direct_download_url": spec["download_url"],
                "file_name": selected_name,
                "local_path": str(destination.resolve()),
                "size_bytes": destination.stat().st_size,
                "figshare_md5": expected_md5,
                "sha256": _sha256(destination),
                "license": spec["license_expected"],
                "license_expected": spec["license_expected"],
                "medical_scene": spec["medical_scene"],
                "recommended_use": spec["recommended_use"],
                "priority_target": "l1_static_registration",
                "target_domain_flag": False,
                "training_eligible": False,
                "review_state": "review_required",
                "download_status": "verified",
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "data_boundary": (
                    "Ex vivo non-jaw surgical-vision proxy. It validates geometry and software behavior only; "
                    "it cannot support jaw-navigation accuracy or clinical readiness claims."
                ),
            }
        )
    return rows


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "osteo-vision-navigation-starter-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "records": rows,
    }
    (output_dir / "navigation_starter_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "navigation_starter_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0]) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    rows = download_navigation_starter(output_dir)
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
