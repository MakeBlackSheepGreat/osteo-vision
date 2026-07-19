from __future__ import annotations

import argparse
import configparser
import csv
import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.download_three_priority_zenodo_datasets import _download, _session, _sha256
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    from download_three_priority_zenodo_datasets import _download, _session, _sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/c3vd_l2_proxy_20260719"

C3VD_SAMPLE: dict[str, Any] = {
    "candidate_id": "D087",
    "dataset_name": "C3VD official sample video sequence",
    "google_drive_file_id": "1Ddeq5Dm4tx7cMRTZBu3CN3otsGu2_kY1",
    "file_name": "sampledata.zip",
    "size_bytes": 1_515_094_074,
    "source_page_url": "https://durrlab.github.io/C3VD/",
    "code_repository_url": "https://github.com/DurrLab/C3VD",
    "license_evidence_url": "https://github.com/DurrLab/C3VD/blob/main/README.md#license",
    "license": "CC BY-NC-SA 4.0",
}

REQUIRED_ARCHIVE_FILES = {
    "sampledata/config.ini",
    "sampledata/mask.png",
    "sampledata/model.mtl",
    "sampledata/model.obj",
    "sampledata/pose.txt",
}
_FRAME_PATTERN = re.compile(r"^sampledata/(?P<channel>rgb|depth)/(?P<index>\d{4})\.png$")


def direct_download_url(file_id: str) -> str:
    return "https://drive.usercontent.google.com/download" f"?id={file_id}&export=download&confirm=t"


def inspect_c3vd_archive(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise RuntimeError(f"C3VD ZIP CRC failed for {corrupt_member}")
        names = archive.namelist()
        name_set = set(names)
        missing = sorted(REQUIRED_ARCHIVE_FILES - name_set)
        if missing:
            raise RuntimeError(f"C3VD archive is missing required files: {missing}")

        channel_indices: dict[str, set[int]] = {"rgb": set(), "depth": set()}
        for name in names:
            match = _FRAME_PATTERN.fullmatch(name)
            if match is not None:
                channel_indices[match.group("channel")].add(int(match.group("index")))
        rgb_indices = channel_indices["rgb"]
        depth_indices = channel_indices["depth"]
        if not rgb_indices or rgb_indices != depth_indices:
            raise RuntimeError("C3VD RGB and depth frame indexes must be non-empty and paired")
        first_index = min(rgb_indices)
        last_index = max(rgb_indices)
        contiguous = rgb_indices == set(range(first_index, last_index + 1))
        if not contiguous:
            raise RuntimeError("C3VD RGB/depth frame indexes are not contiguous")

        config_text = archive.read("sampledata/config.ini").decode("utf-8")
        parser = configparser.ConfigParser()
        parser.read_string("[c3vd]\n" + config_text)
        config = parser["c3vd"]
        width = config.getint("width")
        height = config.getint("height")
        camera_parameters = {
            field: config.getfloat(field) for field in ("cx", "cy", "a0", "a1", "a2", "a3", "a4", "c", "d", "e")
        }
        pose_start_time = config.getfloat("poseStartTime")

        pose_count = 0
        pose_start: float | None = None
        pose_end: float | None = None
        previous_timestamp: float | None = None
        duplicate_pose_timestamp_count = 0
        with archive.open("sampledata/pose.txt") as raw_pose_file:
            reader = csv.reader(io.TextIOWrapper(raw_pose_file, encoding="utf-8", newline=""))
            for row in reader:
                if not row:
                    continue
                if len(row) != 17:
                    raise RuntimeError("Each C3VD pose row must contain a timestamp and 16 matrix values")
                try:
                    values = [float(value) for value in row]
                except ValueError as exc:
                    raise RuntimeError("C3VD pose values must be numeric") from exc
                if not all(math.isfinite(value) for value in values):
                    raise RuntimeError("C3VD pose values must be finite")
                timestamp = values[0]
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    raise RuntimeError("C3VD pose timestamps must be monotonic")
                if previous_timestamp is not None and timestamp == previous_timestamp:
                    duplicate_pose_timestamp_count += 1
                pose_start = timestamp if pose_start is None else pose_start
                pose_end = timestamp
                previous_timestamp = timestamp
                pose_count += 1
        if pose_count < len(rgb_indices):
            raise RuntimeError("C3VD pose log is shorter than the RGB/depth frame sequence")

    return {
        "zip_crc_verified": True,
        "archive_entry_count": len(names),
        "required_files_present": True,
        "rgb_frame_count": len(rgb_indices),
        "depth_frame_count": len(depth_indices),
        "paired_frame_count": len(rgb_indices),
        "first_frame_index": first_index,
        "last_frame_index": last_index,
        "frame_indices_contiguous": contiguous,
        "image_width": width,
        "image_height": height,
        "camera_model": "scaramuzza_ocamcalib_polynomial_v1",
        "camera_parameters": camera_parameters,
        "runtime_projection_supported": True,
        "pose_record_count": pose_count,
        "pose_timestamp_start_s": pose_start,
        "pose_timestamp_end_s": pose_end,
        "pose_timestamps_monotonic_non_decreasing": True,
        "pose_timestamps_strictly_increasing": duplicate_pose_timestamp_count == 0,
        "duplicate_pose_timestamp_count": duplicate_pose_timestamp_count,
        "runtime_pose_use_requires_deduplication": duplicate_pose_timestamp_count > 0,
        "pose_start_time_s": pose_start_time,
    }


def download_c3vd_sample(output_dir: Path) -> list[dict[str, Any]]:
    session = _session()
    destination = output_dir / "d087" / "raw" / str(C3VD_SAMPLE["file_name"])
    download_url = direct_download_url(str(C3VD_SAMPLE["google_drive_file_id"]))
    expected_size = int(C3VD_SAMPLE["size_bytes"])

    response = session.head(download_url, allow_redirects=True, timeout=(30, 120))
    response.raise_for_status()
    remote_size = int(response.headers.get("Content-Length") or 0)
    if remote_size != expected_size:
        raise RuntimeError(
            f"C3VD remote size changed: {remote_size} != {expected_size}. "
            "Review the official source before downloading."
        )

    _download(session, download_url, destination, expected_size)
    actual_size = destination.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(f"C3VD downloaded size mismatch: {actual_size} != {expected_size}")

    inventory = inspect_c3vd_archive(destination)
    return [
        {
            "candidate_id": C3VD_SAMPLE["candidate_id"],
            "dataset_name": C3VD_SAMPLE["dataset_name"],
            "source_page_url": C3VD_SAMPLE["source_page_url"],
            "code_repository_url": C3VD_SAMPLE["code_repository_url"],
            "license_evidence_url": C3VD_SAMPLE["license_evidence_url"],
            "direct_download_url": download_url,
            "google_drive_file_id": C3VD_SAMPLE["google_drive_file_id"],
            "file_name": destination.name,
            "local_path": str(destination.resolve()),
            "size_bytes": actual_size,
            "remote_content_length": remote_size,
            "sha256": _sha256(destination),
            "source_checksum": "not_published",
            "integrity_basis": "official_content_length_and_local_sha256",
            "license": C3VD_SAMPLE["license"],
            "license_review_status": "verified_from_official_repository_readme",
            "medical_scene": "high_fidelity_colon_phantom_endoscopy",
            "modalities": "rgb;3d_model;robot_pose;camera_pose;depth;calibration",
            "recommended_use": (
                "L2 offline pose synchronization, transform-chain, projection, drift, "
                "tracking-loss and fail-closed engineering validation"
            ),
            "priority_target": "l2_offline_dynamic_ar_proxy",
            "target_domain_flag": False,
            "training_eligible": False,
            "navigation_claim_allowed": False,
            "review_state": "review_required",
            "download_status": "verified",
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            **inventory,
            "data_boundary": (
                "Public colon-phantom proxy without jaw anatomy, osteomyelitis, fluorescence, "
                "microscope zoom or working-distance ground truth. It supports software engineering "
                "validation only and cannot support physical jaw-navigation or clinical claims. "
                "The raw pose log contains duplicate timestamps and requires deterministic "
                "deduplication before strict replay admission."
            ),
        }
    ]


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "osteo-vision-c3vd-l2-proxy-download-v3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "records": rows,
        "medical_boundary": (
            "C3VD is an external non-target-domain colon-phantom proxy. All derived navigation "
            "evidence remains L2 software engineering evidence and requires independent jaw-phantom "
            "validation before any physical-navigation claim."
        ),
    }
    (output_dir / "c3vd_l2_proxy_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "c3vd_l2_proxy_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0]) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    rows = download_c3vd_sample(output_dir)
    write_manifest(output_dir, rows)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "record_count": len(rows),
                "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
                "sha256": rows[0]["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
