from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "research/datasets/public-candidates/d047_d048_static_crop_suggestion_manifest.json"
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d047_d048_static_paired_preview_manifest.json"


def materialize_static_crop_suggestions(
    input_manifest: str | Path,
    output_manifest: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_manifest).resolve()
    output_path = Path(output_manifest).resolve()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    atomic_records: list[dict[str, Any]] = []
    paired_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload.get("records", []):
        if not isinstance(row, dict):
            continue
        record = _materialize_record(row)
        atomic_records.append(record)
        pair_id = str(record.get("suggested_pair_id") or "").strip()
        if pair_id:
            paired_candidates[pair_id].append(record)

    pairs: list[dict[str, Any]] = []
    incomplete_pair_ids: list[str] = []
    for pair_id, records in sorted(paired_candidates.items()):
        white_records = [record for record in records if record["suggested_panel_role"] == "paired_white_light"]
        fluorescence_records = [record for record in records if record["suggested_panel_role"] == "paired_fluorescence"]
        if len(white_records) != 1 or len(fluorescence_records) != 1:
            incomplete_pair_ids.append(pair_id)
            continue
        white = white_records[0]
        fluorescence = fluorescence_records[0]
        alignment = str(white.get("suggested_pair_alignment") or fluorescence.get("suggested_pair_alignment") or "")
        pairs.append(
            {
                "pair_id": pair_id,
                "source_group_id": white["source_group_id"],
                "dataset_id": white["dataset_id"],
                "white_record_id": white["record_id"],
                "fluorescence_record_id": fluorescence["record_id"],
                "white_image_path": white["preview_crop_path"],
                "fluorescence_image_path": fluorescence["preview_crop_path"],
                "white_image_checksum": white["preview_crop_checksum"],
                "fluorescence_image_checksum": fluorescence["preview_crop_checksum"],
                "white_size": white["preview_crop_size"],
                "fluorescence_size": fluorescence["preview_crop_size"],
                "pair_alignment": alignment or "unverified",
                "pixel_registration_supervision_allowed": False,
                "supervised_segmentation_training_allowed": False,
                "training_eligible": False,
                "stress_evaluation_eligible": True,
                "annotation_overlay_present": True,
                "review_state": "review_required",
                "medical_boundary": (
                    "Publication-derived near-domain pair for registration and dual-channel engineering stress tests. "
                    "It is not pixel-aligned ground truth and cannot support clinical performance claims."
                ),
            }
        )

    result = {
        "schema_version": "osteo-vision-static-paired-preview-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(input_path),
        "source_manifest_checksum": _sha256_file(input_path),
        "atomic_record_count": len(atomic_records),
        "pair_count": len(pairs),
        "incomplete_pair_count": len(incomplete_pair_ids),
        "incomplete_pair_ids": incomplete_pair_ids,
        "training_eligible_count": 0,
        "stress_evaluation_eligible_count": len(pairs),
        "atomic_records": atomic_records,
        "pairs": pairs,
        "medical_boundary": (
            "Preview crops materialize automated review suggestions without accepting them. "
            "All records remain review_required and training_eligible=false."
        ),
    }
    _atomic_write_json(output_path, result)
    return result


def _materialize_record(row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_image_path") or "")).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    expected_source_checksum = str(row.get("source_checksum") or "").strip()
    source_checksum = _sha256_file(source_path)
    if expected_source_checksum and source_checksum != expected_source_checksum:
        raise ValueError(f"Source checksum mismatch for {row.get('record_id')}: {source_path}")
    bbox = row.get("suggested_crop_bbox")
    if not isinstance(bbox, dict):
        raise ValueError(f"Missing suggested_crop_bbox for {row.get('record_id')}")
    x, y, width, height = (int(bbox[key]) for key in ("x", "y", "width", "height"))
    with Image.open(source_path) as source_image:
        if x < 0 or y < 0 or width < 16 or height < 16:
            raise ValueError(f"Invalid crop dimensions for {row.get('record_id')}")
        if x + width > source_image.width or y + height > source_image.height:
            raise ValueError(f"Crop exceeds source bounds for {row.get('record_id')}")
        crop = source_image.convert("RGB").crop((x, y, x + width, y + height))
    dataset_root = _dataset_root(source_path)
    output_dir = dataset_root / "derived/suggested_panel_previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{_safe_name(str(row.get('record_id') or 'panel'))}.png"
    _atomic_save_image(output_path, crop)
    return {
        **row,
        "preview_crop_path": str(output_path),
        "preview_crop_checksum": _sha256_file(output_path),
        "preview_crop_size": {"width": crop.width, "height": crop.height},
        "preview_materialized": True,
        "crop_review_action": "pending",
        "review_state": "review_required",
        "training_eligible": False,
        "annotation_overlay_present": True,
    }


def _dataset_root(source_path: Path) -> Path:
    for parent in source_path.parents:
        if parent.name in {
            "d047_pmc_jaw_fluorescence_figures",
            "d048_open_clinical_bone_fluorescence",
        }:
            return parent
    raise ValueError(f"Unable to locate approved D047/D048 dataset root for {source_path}")


def _safe_name(value: str) -> str:
    normalized = "".join(char if char.isalnum() or char in "._-" else "_" for char in value)
    if not normalized:
        raise ValueError("Record id cannot produce an empty file name")
    return normalized


def _atomic_save_image(path: Path, image: Image.Image) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    image.save(temporary, format="PNG")
    temporary.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize review-only D047/D048 crop previews and pairs.")
    parser.add_argument("--input-manifest", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-manifest", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize_static_crop_suggestions(args.input_manifest, args.output_manifest)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "atomic_record_count",
                    "pair_count",
                    "incomplete_pair_count",
                    "training_eligible_count",
                    "stress_evaluation_eligible_count",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
