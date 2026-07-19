"""Materialize D074 microscope-fluorescence images as a bone-activity proxy.

The source is a public 5-ALA/PpIX brain-surgery dataset. Its logical masks and
image intensities are converted into rule-derived review-gate, continuous-score,
and three-band targets strictly for non-target engineering pretraining.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, NamedTuple
from zipfile import BadZipFile, ZipFile

import numpy as np
from PIL import Image
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_MANIFEST = (
    ROOT / "research/datasets/public-candidates/three_priority_zenodo_20260717/three_priority_zenodo_manifest.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "artifacts/bone_activity_d074_proxy/data"

DATASET_ID = "D074"
LICENSE = "cc-by-4.0"
DOMAIN_TIER = "clinical_microscope_fluorescence_non_jaw_proxy"
TRAINING_SCOPE = "non_target_proxy_pretraining"
CHANNEL_SEMANTICS = "single_ppix_rgb_view_with_red_channel_proxy"
IMAGE_ARCHIVE_NAME = "Fluorescence Guided GBM Resection.zip"
MASK_ARCHIVE_NAME = "Annotation Masks.zip"
IMAGE_PATTERN = re.compile(r"P(?P<patient>\d{3}) \((?P<frame>\d+)\)\.png$", re.IGNORECASE)
MASK_PATTERN = re.compile(r"P(?P<patient>\d{3})_(?P<frame>\d+)_mask\.mat$", re.IGNORECASE)
PATIENT_SPLITS = {"P001": "train", "P002": "val", "P003": "test"}
IGNORE_VALUE = 255
LOW_THRESHOLD = 1.0 / 3.0
HIGH_THRESHOLD = 2.0 / 3.0
MEDICAL_BOUNDARY = (
    "Public human brain 5-ALA/PpIX microscope-fluorescence proxy. The supplied logical mask is used as an "
    "engineering review-gate proxy, while continuous activity and low/transition/high targets are derived from "
    "red-channel intensity rules. These outputs are not bone, ICG, jaw osteomyelitis, physician bone-viability "
    "labels, pathology ground truth, or clinical evidence. Runtime replacement and clinical claims remain prohibited."
)


class ArchiveArray(NamedTuple):
    data: np.ndarray
    member_path: str
    member_sha256: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = materialize_d074_bone_activity_proxy(
            source_manifest=args.source_manifest,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed_closed",
                    "dataset_id": DATASET_ID,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "target_domain": False,
                    "runtime_replacement_allowed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def materialize_d074_bone_activity_proxy(
    *,
    source_manifest: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    manifest_path = Path(source_manifest).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    image_record = _source_record(payload, IMAGE_ARCHIVE_NAME)
    mask_record = _source_record(payload, MASK_ARCHIVE_NAME)
    image_archive = _validate_source_record(image_record)
    mask_archive = _validate_source_record(mask_record)

    images = _read_image_members(image_archive)
    masks = _read_mask_members(mask_archive)
    paired_keys = sorted(set(images).intersection(masks))
    if not paired_keys:
        raise ValueError("D074 contains no matched fluorescence image and logical-mask pairs")
    if set(masks) - set(images):
        raise ValueError(f"D074 masks have no matching image: {sorted(set(masks) - set(images))}")

    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    derived_files: list[dict[str, Any]] = []
    for patient_id, frame_index in paired_keys:
        patient_key = f"P{patient_id}"
        split = PATIENT_SPLITS.get(patient_key)
        if split is None:
            continue
        image_member = images[(patient_id, frame_index)]
        mask_member = masks[(patient_id, frame_index)]
        rgb = image_member.data
        gate = mask_member.data
        if rgb.shape[:2] != gate.shape:
            raise ValueError(
                f"D074 image/mask shape mismatch for {patient_key}_{frame_index}: {rgb.shape[:2]} != {gate.shape}"
            )
        score, class_target, uncertainty = _derive_targets(rgb, gate)
        sample_id = f"d074_{patient_key.lower()}_{frame_index:02d}"
        sample_dir = output / "samples" / patient_key
        sample_dir.mkdir(parents=True, exist_ok=True)
        white_path = sample_dir / f"{sample_id}_source_rgb.png"
        fluorescence_path = sample_dir / f"{sample_id}_red_channel_proxy.png"
        gate_path = sample_dir / f"{sample_id}_review_gate_proxy.png"
        score_path = sample_dir / f"{sample_id}_activity_score_proxy.png"
        class_path = sample_dir / f"{sample_id}_activity_classes_proxy.png"
        uncertainty_path = sample_dir / f"{sample_id}_uncertainty_proxy.png"
        Image.fromarray(rgb).save(white_path)
        Image.fromarray(rgb[:, :, 0]).save(fluorescence_path)
        Image.fromarray(gate.astype(np.uint8) * 255).save(gate_path)
        Image.fromarray(np.rint(score * 255.0).astype(np.uint8)).save(score_path)
        Image.fromarray(class_target.astype(np.uint8)).save(class_path)
        Image.fromarray(np.rint(uncertainty * 255.0).astype(np.uint8)).save(uncertainty_path)

        files = {
            "white": white_path,
            "fluorescence": fluorescence_path,
            "bone_gate": gate_path,
            "activity_score": score_path,
            "class_target": class_path,
            "uncertainty": uncertainty_path,
        }
        evidence = {role: _file_evidence(path, base=output) for role, path in files.items()}
        derived_files.extend({"sample_id": sample_id, "role": role, **item} for role, item in evidence.items())
        class_counts = {str(value): int(np.count_nonzero(class_target == value)) for value in (0, 1, 2)}
        rows.append(
            {
                "sample_id": sample_id,
                "patient_group_id": patient_key,
                "case_id": patient_key,
                "split": split,
                "white_path": evidence["white"]["relative_path"],
                "white_sha256": evidence["white"]["sha256"],
                "fluorescence_path": evidence["fluorescence"]["relative_path"],
                "fluorescence_sha256": evidence["fluorescence"]["sha256"],
                "bone_gate_path": evidence["bone_gate"]["relative_path"],
                "bone_gate_sha256": evidence["bone_gate"]["sha256"],
                "activity_score_path": evidence["activity_score"]["relative_path"],
                "activity_score_sha256": evidence["activity_score"]["sha256"],
                "class_target_path": evidence["class_target"]["relative_path"],
                "class_target_sha256": evidence["class_target"]["sha256"],
                "uncertainty_path": evidence["uncertainty"]["relative_path"],
                "uncertainty_sha256": evidence["uncertainty"]["sha256"],
                "image_width": str(rgb.shape[1]),
                "image_height": str(rgb.shape[0]),
                "gate_positive_pixels": str(int(np.count_nonzero(gate))),
                "class_counts_json": json.dumps(class_counts, separators=(",", ":")),
                "dataset_id": DATASET_ID,
                "source_record_id": str(image_record.get("record_id") or ""),
                "source_case_id": patient_key,
                "source_sequence_id": f"{DATASET_ID}:{patient_key}",
                "source_frame_id": f"{DATASET_ID}:{patient_key}:{frame_index}",
                "source_image_member": image_member.member_path,
                "source_mask_member": mask_member.member_path,
                "source_asset_sha256": image_member.member_sha256,
                "source_mask_asset_sha256": mask_member.member_sha256,
                "source_image_archive_sha256": str(image_record["sha256"]),
                "source_mask_archive_sha256": str(mask_record["sha256"]),
                "license": LICENSE,
                "domain_tier": DOMAIN_TIER,
                "training_scope": TRAINING_SCOPE,
                "channel_semantics": CHANNEL_SEMANTICS,
                "label_semantics": "rule_derived_from_ppix_red_intensity_inside_public_logic_mask",
                "target_domain": "false",
                "training_eligible": "true",
                "physician_reviewed_bone_gate": "false",
                "independent_test_set": "false",
                "runtime_replacement_allowed": "false",
                "clinical_claim_allowed": "false",
                "medical_boundary": MEDICAL_BOUNDARY,
            }
        )

    _validate_rows(rows)
    csv_path = output / "d074_bone_activity_proxy_samples.csv"
    _write_csv(csv_path, rows)
    result = {
        "schema_version": "osteo-vision-d074-bone-activity-proxy-v1",
        "status": "engineering_validation_passed",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset_id": DATASET_ID,
        "source_manifest_path": str(manifest_path),
        "source_manifest_sha256": _sha256(manifest_path),
        "source_archives": [
            _source_evidence(image_record, image_archive),
            _source_evidence(mask_record, mask_archive),
        ],
        "csv_path": str(csv_path),
        "csv_sha256": _sha256(csv_path),
        "sample_count": len(rows),
        "patient_group_count": len({row["patient_group_id"] for row in rows}),
        "split_sample_counts": _counts(rows, "split"),
        "split_group_counts": {
            split: len({row["patient_group_id"] for row in rows if row["split"] == split})
            for split in ("train", "val", "test")
        },
        "patient_group_leakage_detected": False,
        "derived_files": derived_files,
        "target_derivation": {
            "review_gate": "public D074 logical fluorescence mask used only as a non-bone review-gate proxy",
            "activity_score": "red-channel intensity robustly normalized inside the proxy gate",
            "class_thresholds": {"low_upper": LOW_THRESHOLD, "transition_upper": HIGH_THRESHOLD},
            "ignore_value": IGNORE_VALUE,
            "uncertainty": "distance to fixed class thresholds plus outside-gate abstention",
        },
        "training_eligibility": {
            "training_eligible": True,
            "scope": "proxy_pretraining_only",
            "training_scope": TRAINING_SCOPE,
            "source_manifest_training_eligible": False,
            "target_domain": False,
            "physician_reviewed_bone_gate": False,
            "runtime_replacement_allowed": False,
            "clinical_claim_allowed": False,
        },
        "medical_boundary": MEDICAL_BOUNDARY,
    }
    output_manifest = output / "d074_bone_activity_proxy_manifest.json"
    output_manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _source_record(payload: Mapping[str, Any], file_name: str) -> dict[str, Any]:
    matches = [
        dict(record)
        for record in payload.get("records", [])
        if isinstance(record, Mapping)
        and record.get("candidate_id") == DATASET_ID
        and record.get("original_file_name") == file_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one D074 source record for {file_name}, found {len(matches)}")
    return matches[0]


def _validate_source_record(record: Mapping[str, Any]) -> Path:
    if record.get("download_status") != "verified":
        raise ValueError("D074 source record is not verified")
    if str(record.get("license") or "").lower() != LICENSE:
        raise ValueError(f"Unexpected D074 license: {record.get('license')}")
    path = Path(str(record.get("local_path") or "")).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if int(record.get("size_bytes") or -1) != path.stat().st_size:
        raise ValueError(f"D074 source size mismatch: {path}")
    expected = str(record.get("sha256") or "").lower()
    if len(expected) != 64 or _sha256(path) != expected:
        raise ValueError(f"D074 source SHA256 mismatch: {path}")
    return path


def _read_image_members(path: Path) -> dict[tuple[str, int], ArchiveArray]:
    result: dict[tuple[str, int], ArchiveArray] = {}
    try:
        with ZipFile(path) as archive:
            for info in archive.infolist():
                _safe_member(info.filename)
                match = IMAGE_PATTERN.search(PurePosixPath(info.filename).name)
                if not match:
                    continue
                key = (match.group("patient"), int(match.group("frame")))
                if key in result:
                    raise ValueError(f"Duplicate D074 image member for {key}")
                raw = archive.read(info)
                with Image.open(BytesIO(raw)) as image:
                    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
                if rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.size:
                    raise ValueError(f"Invalid D074 image member: {info.filename}")
                result[key] = ArchiveArray(
                    data=rgb,
                    member_path=info.filename,
                    member_sha256=hashlib.sha256(raw).hexdigest(),
                )
    except BadZipFile as exc:
        raise ValueError(f"Unreadable D074 image archive: {path}") from exc
    return result


def _read_mask_members(path: Path) -> dict[tuple[str, int], ArchiveArray]:
    result: dict[tuple[str, int], ArchiveArray] = {}
    try:
        with ZipFile(path) as archive:
            for info in archive.infolist():
                _safe_member(info.filename)
                if "masks ala/" not in info.filename.lower():
                    continue
                match = MASK_PATTERN.search(PurePosixPath(info.filename).name)
                if not match:
                    continue
                key = (match.group("patient"), int(match.group("frame")))
                if key in result:
                    raise ValueError(f"Duplicate D074 mask member for {key}")
                raw = archive.read(info)
                payload = loadmat(BytesIO(raw))
                arrays = [value for name, value in payload.items() if not name.startswith("__")]
                if len(arrays) != 1:
                    raise ValueError(f"D074 mask must contain one array: {info.filename}")
                array = np.asarray(arrays[0])
                if array.ndim != 2 or not np.isfinite(array).all() or not set(np.unique(array)).issubset({0, 1}):
                    raise ValueError(f"D074 mask must be finite binary 2D data: {info.filename}")
                gate = array.astype(bool)
                if not gate.any() or gate.all():
                    raise ValueError(f"D074 mask must contain foreground and background: {info.filename}")
                result[key] = ArchiveArray(
                    data=gate,
                    member_path=info.filename,
                    member_sha256=hashlib.sha256(raw).hexdigest(),
                )
    except BadZipFile as exc:
        raise ValueError(f"Unreadable D074 mask archive: {path}") from exc
    return result


def _derive_targets(rgb: np.ndarray, gate: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    red = rgb[:, :, 0].astype(np.float32) / 255.0
    inside = red[gate]
    lower, upper = np.quantile(inside, [0.01, 0.99])
    if not np.isfinite(lower) or not np.isfinite(upper) or upper <= lower:
        raise ValueError("D074 proxy-gate red-channel intensity has no usable dynamic range")
    score = np.clip((red - float(lower)) / float(upper - lower), 0.0, 1.0)
    score[~gate] = 0.0
    classes = np.full(gate.shape, IGNORE_VALUE, dtype=np.uint8)
    classes[gate & (score < LOW_THRESHOLD)] = 0
    classes[gate & (score >= LOW_THRESHOLD) & (score < HIGH_THRESHOLD)] = 1
    classes[gate & (score >= HIGH_THRESHOLD)] = 2
    uncertainty = np.ones(gate.shape, dtype=np.float32)
    threshold_distance = np.minimum(np.abs(score - LOW_THRESHOLD), np.abs(score - HIGH_THRESHOLD))
    uncertainty[gate] = np.exp(-np.square(threshold_distance[gate]) / 0.01)
    return score.astype(np.float32), classes, uncertainty


def _safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\x00" in name:
        raise ValueError(f"Unsafe D074 ZIP member: {name}")


def _validate_rows(rows: list[dict[str, str]]) -> None:
    if len(rows) != 5:
        raise ValueError(f"Expected five matched D074 ALA samples, found {len(rows)}")
    if {row["split"] for row in rows} != {"train", "val", "test"}:
        raise ValueError("D074 proxy requires non-empty train, val, and test splits")
    groups_by_split = {
        split: {row["patient_group_id"] for row in rows if row["split"] == split} for split in ("train", "val", "test")
    }
    if (
        groups_by_split["train"] & groups_by_split["val"]
        or groups_by_split["train"] & groups_by_split["test"]
        or groups_by_split["val"] & groups_by_split["test"]
    ):
        raise ValueError("D074 patient-group leakage detected")


def _file_evidence(path: Path, *, base: Path) -> dict[str, Any]:
    return {
        "relative_path": path.resolve().relative_to(base.resolve()).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _source_evidence(record: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "file_name": path.name,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "source_page_url": record.get("source_page_url"),
        "direct_download_url": record.get("direct_download_url"),
        "license": record.get("license"),
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return {value: sum(row[field] == value for row in rows) for value in sorted({row[field] for row in rows})}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
