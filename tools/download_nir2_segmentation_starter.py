from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d097_nir2b_vessel_masks_20260724"
REPOSITORY = "ZhongLab2020/NIR-IIb_sO2_UNet"


def session() -> requests.Session:
    client = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    client.mount("https://", HTTPAdapter(max_retries=retry))
    client.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Osteo-Vision NIR-II dataset downloader/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return client


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(client: requests.Session, url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    with client.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    partial.replace(destination)


def extract_archive(archive_path: Path, raw_dir: Path) -> Path:
    extract_dir = raw_dir / "repository"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)
    roots = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"Expected one archive root, found {len(roots)}")
    return roots[0]


def pair_records(repository_root: Path, commit_sha: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for split in ("train", "val"):
        image_dir = repository_root / f"gut (closed + opened belly)_images_{split}"
        mask_dir = repository_root / f"gut (closed + opened belly)_masks_{split}"
        images = {path.name: path for path in image_dir.glob("*.tif")}
        masks = {path.name: path for path in mask_dir.glob("*.tif")}
        if images.keys() != masks.keys():
            raise RuntimeError(f"Image/mask mismatch in {split}")
        for name in sorted(images):
            image_path = images[name]
            mask_path = masks[name]
            records.append(
                {
                    "candidate_id": "D097",
                    "sample_id": f"d097_{split}_{Path(name).stem}",
                    "split_as_published": "validation" if split == "val" else "train",
                    "image_path": str(image_path.resolve()),
                    "mask_path": str(mask_path.resolve()),
                    "image_size_bytes": image_path.stat().st_size,
                    "mask_size_bytes": mask_path.stat().st_size,
                    "image_sha256": sha256_file(image_path),
                    "mask_sha256": sha256_file(mask_path),
                    "source_page_url": f"https://github.com/{REPOSITORY}",
                    "source_commit": commit_sha,
                    "wavelength_window": "NIR-IIb 1500-1700 nm",
                    "medical_scene": "gut closed/opened-belly intestinal vasculature",
                    "label_type": "binary vessel mask",
                    "domain_tier": "animal_nir2b_vessel_segmentation_proxy",
                    "license": "no repository license declared",
                    "license_review_status": "blocked_missing_license",
                    "target_domain_flag": False,
                    "training_eligible": False,
                    "review_state": "review_required",
                    "data_boundary": (
                        "The files are a non-jaw NIR-IIb vascular proxy. They do not provide lesion, "
                        "osteomyelitis, bone-surface, RGB-paired, or clinical ground-truth labels. "
                        "Training admission remains blocked until the owner grants data-use permission "
                        "and provenance is documented."
                    ),
                }
            )
    if len(records) != 18:
        raise RuntimeError(f"Expected 18 image/mask pairs, found {len(records)}")
    return records


def write_outputs(
    output_dir: Path,
    repository_metadata: dict[str, Any],
    commit_metadata: dict[str, Any],
    tree_metadata: dict[str, Any],
    readme_text: str,
    archive_path: Path,
    records: list[dict[str, Any]],
) -> None:
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "github_repository.json").write_text(
        json.dumps(repository_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (metadata_dir / "github_commit.json").write_text(
        json.dumps(commit_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (metadata_dir / "github_tree.json").write_text(
        json.dumps(tree_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (metadata_dir / "README_source.md").write_text(readme_text, encoding="utf-8")

    payload = {
        "schema_version": "osteo-vision-nir2-starter-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "candidate_id": "D097",
        "dataset_name": "Deep Learning-Assisted NIR-IIb sO2 Imaging starter",
        "source_repository": f"https://github.com/{REPOSITORY}",
        "source_commit": commit_metadata["sha"],
        "archive_size_bytes": archive_path.stat().st_size,
        "archive_sha256": sha256_file(archive_path),
        "pair_count": len(records),
        "published_split_counts": {
            "train": sum(row["split_as_published"] == "train" for row in records),
            "validation": sum(row["split_as_published"] == "validation" for row in records),
        },
        "license": "no repository license declared",
        "license_review_status": "blocked_missing_license",
        "training_eligible": False,
        "records": records,
    }
    (output_dir / "d097_nir2b_vessel_masks_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "d097_nir2b_vessel_masks_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    client = session()
    api_root = f"https://api.github.com/repos/{REPOSITORY}"
    repository_response = client.get(api_root, timeout=60)
    repository_response.raise_for_status()
    repository_metadata = repository_response.json()
    default_branch = str(repository_metadata["default_branch"])
    commit_response = client.get(f"{api_root}/commits/{default_branch}", timeout=60)
    commit_response.raise_for_status()
    commit_metadata = commit_response.json()
    commit_sha = str(commit_metadata["sha"])
    tree_response = client.get(f"{api_root}/git/trees/{commit_sha}?recursive=1", timeout=60)
    tree_response.raise_for_status()
    tree_metadata = tree_response.json()
    readme_response = client.get(
        f"{api_root}/readme",
        headers={"Accept": "application/vnd.github.raw+json"},
        timeout=60,
    )
    readme_response.raise_for_status()

    archive_path = raw_dir / f"{REPOSITORY.split('/')[-1]}-{commit_sha}.zip"
    download(client, f"https://github.com/{REPOSITORY}/archive/{commit_sha}.zip", archive_path)
    repository_root = extract_archive(archive_path, raw_dir)
    records = pair_records(repository_root, commit_sha)
    write_outputs(
        output_dir,
        repository_metadata,
        commit_metadata,
        tree_metadata,
        readme_response.text,
        archive_path,
        records,
    )
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "source_commit": commit_sha,
                "pair_count": len(records),
                "training_eligible": False,
                "license_review_status": "blocked_missing_license",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
