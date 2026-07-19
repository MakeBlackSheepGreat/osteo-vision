"""Build and promote human-reviewed crops from the D047 PMC figure manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.datasets.group_splits import assign_group_split  # noqa: E402
from src.datasets.registry import sha256_file  # noqa: E402

DEFAULT_DATASET_DIR = ROOT / "research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures"
TRAINING_FIELDS = [
    "case_id",
    "record_id",
    "image_path",
    "mask_path",
    "local_path",
    "label_path",
    "split",
    "source_id",
    "source_url",
    "direct_download_url",
    "source_group_id",
    "group_id",
    "domain_tier",
    "target_domain_flag",
    "medical_scene",
    "fluorescence",
    "fluorescence_attribute",
    "panel_role",
    "label_source",
    "label_type",
    "review_state",
    "sample_weight",
    "sampling_weight",
    "license",
    "usage_policy",
    "checksum",
    "label_checksum",
    "artifact_role",
    "training_eligible",
    "crop_bbox",
    "positive_area_fraction",
    "review_update_path",
    "medical_boundary",
]
PROMOTION_BOUNDARY = (
    "Human-reviewed crop from an open-access jaw fluorescence publication figure. "
    "It remains near-domain, non-ICG and non-target-domain evidence and does not establish clinical ground truth."
)
TRAINING_PANEL_ROLES = {"fluorescence_signal", "fluorescence_guided_surgical_field", "bone_autofluorescence"}


def _eligible_source(record: dict[str, Any]) -> bool:
    policy = str(record.get("usage_policy") or "").lower()
    license_name = str(record.get("license") or "").lower()
    blocked = any(marker in policy for marker in ("reference_only", "no_derivatives", "no_derivative"))
    blocked = blocked or "cc by-nc-nd" in license_name or "cc-by-nc-nd" in license_name
    return bool(record.get("training_seed_allowed")) and not blocked


def build_review_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert licensable weak figure seeds into non-trainable review items."""
    review_records: list[dict[str, Any]] = []
    for source in records:
        if not _eligible_source(source):
            continue
        pmcid = str(source.get("pmcid") or "").strip()
        source_record_id = str(source.get("record_id") or "").strip()
        if not pmcid or not source_record_id:
            continue
        review_records.append(
            {
                "record_id": f"review_{source_record_id}",
                "source_record_id": source_record_id,
                "pmcid": pmcid,
                "source_group_id": pmcid,
                "caption": str(source.get("caption") or ""),
                "license": str(source.get("license") or "unknown"),
                "usage_policy": str(source.get("usage_policy") or ""),
                "source_url": str(source.get("source_page_url") or ""),
                "direct_download_url": str(source.get("asset_url") or ""),
                "local_path": str(source.get("local_path") or ""),
                "source_checksum": str(source.get("sha256") or ""),
                "medical_scene": str(source.get("medical_scene") or "jaw_fluorescence_publication_figure"),
                "fluorescence_attribute": str(source.get("fluorescence") or "unknown"),
                "panel_role": "unclassified",
                "domain_tier": "near_domain",
                "target_domain_flag": False,
                "review_state": "review_required",
                "sample_weight": 1.0,
                "sampling_weight": float(source.get("sample_weight") or 0.25),
                "crop_bbox": None,
                "cropped_image_path": None,
                "mask_path": None,
                "mask_source": None,
                "positive_area_fraction": None,
                "review_update_path": None,
                "training_eligible": False,
                "review_notes": "",
            }
        )
    return review_records


def load_review_updates(path: str | Path) -> list[dict[str, Any]]:
    """Load reviewer-authored updates from JSON or CSV without inferring review decisions."""
    source = Path(path).resolve()
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(row) for row in payload]
        return [dict(row) for row in payload.get("records", payload.get("updates", []))]
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"Unsupported review update format: {source}")


def apply_review_updates(
    records: list[dict[str, Any]],
    updates: list[dict[str, Any]],
    *,
    output_dir: Path,
    review_update_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    """Materialize permitted crops and promote only complete reviewed image-mask pairs."""
    by_id: dict[str, dict[str, Any]] = {}
    for queue_record in records:
        by_id[str(queue_record["record_id"])] = queue_record
        by_id[str(queue_record["source_record_id"])] = queue_record
    training_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()
    for update in updates:
        requested_id = str(update.get("record_id") or update.get("source_record_id") or "").strip()
        record = by_id.get(requested_id)
        if record is None:
            skipped.append({"record_id": requested_id, "reason": "record_not_in_licensable_review_queue"})
            continue
        canonical_id = str(record["record_id"])
        if canonical_id in seen:
            skipped.append({"record_id": requested_id, "reason": "duplicate_review_update"})
            continue
        seen.add(canonical_id)
        state = _review_state(update.get("review_state") or update.get("status"))
        record["review_state"] = state
        record["sample_weight"] = 4.0 if state in {"accepted", "modified"} else (0.5 if state == "rejected" else 1.0)
        record["review_notes"] = str(update.get("review_notes") or update.get("notes") or "")
        record["panel_role"] = str(update.get("panel_role") or "unclassified").strip().lower()
        record["review_update_path"] = str(review_update_path.resolve())

        source_path = Path(str(record["local_path"])).resolve()
        if not source_path.is_file():
            skipped.append({"record_id": requested_id, "reason": "missing_source_image"})
            continue
        try:
            with Image.open(source_path) as source:
                source_rgb = source.convert("RGB")
                bbox = _crop_bbox(update.get("crop_bbox"), source_rgb.size)
                if bbox is None:
                    skipped.append({"record_id": requested_id, "reason": "missing_or_invalid_crop_bbox"})
                    continue
                crop = source_rgb.crop(bbox)
        except (OSError, ValueError, TypeError) as exc:
            skipped.append({"record_id": requested_id, "reason": f"invalid_source_or_crop:{exc}"})
            continue

        crop_dir = output_dir / "crops"
        crop_dir.mkdir(parents=True, exist_ok=True)
        crop_path = crop_dir / f"{record['source_record_id']}_crop.png"
        crop.save(crop_path)
        record["crop_bbox"] = list(bbox)
        record["cropped_image_path"] = str(crop_path.resolve())

        mask, mask_source, mask_reason = _review_mask(update, source_size=source_rgb.size, crop_bbox=bbox)
        if mask is None:
            skipped.append({"record_id": requested_id, "reason": mask_reason})
            continue
        mask_dir = output_dir / "masks"
        mask_dir.mkdir(parents=True, exist_ok=True)
        mask_path = mask_dir / f"{record['source_record_id']}_mask.png"
        Image.fromarray(mask * 255).save(mask_path)
        positive_fraction = float(mask.mean())
        record["mask_path"] = str(mask_path.resolve())
        record["mask_source"] = mask_source
        record["positive_area_fraction"] = round(positive_fraction, 8)
        if state not in {"accepted", "modified"}:
            skipped.append({"record_id": requested_id, "reason": f"review_state_not_promotable:{state}"})
            continue
        if record["panel_role"] not in TRAINING_PANEL_ROLES:
            skipped.append({"record_id": requested_id, "reason": f"panel_role_not_trainable:{record['panel_role']}"})
            continue
        record["training_eligible"] = True
        training_rows.append(_training_row(record, crop_path=crop_path, mask_path=mask_path, mask_source=mask_source))
    return records, training_rows, skipped


def _review_state(value: Any) -> str:
    state = str(value or "review_required").strip().lower().replace("-", "_").replace(" ", "_")
    if state not in {"review_required", "accepted", "modified", "rejected"}:
        raise ValueError(f"Unsupported review_state: {state}")
    return state


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _crop_bbox(value: Any, image_size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    parsed = _json_value(value)
    width, height = image_size
    if isinstance(parsed, dict):
        if {"x", "y", "width", "height"} <= set(parsed):
            x0, y0 = float(parsed["x"]), float(parsed["y"])
            x1, y1 = x0 + float(parsed["width"]), y0 + float(parsed["height"])
        elif {"x0", "y0", "x1", "y1"} <= set(parsed):
            x0, y0, x1, y1 = (float(parsed[key]) for key in ("x0", "y0", "x1", "y1"))
        else:
            return None
        if str(parsed.get("coordinate_space") or "pixels").lower() in {"normalized", "normalized_source"}:
            x0, x1, y0, y1 = x0 * width, x1 * width, y0 * height, y1 * height
    elif isinstance(parsed, (list, tuple)) and len(parsed) == 4:
        x0, y0, x1, y1 = (float(item) for item in parsed)
    else:
        return None
    bbox = (max(0, round(x0)), max(0, round(y0)), min(width, round(x1)), min(height, round(y1)))
    return bbox if bbox[2] > bbox[0] and bbox[3] > bbox[1] else None


def _review_mask(
    update: dict[str, Any],
    *,
    source_size: tuple[int, int],
    crop_bbox: tuple[int, int, int, int],
) -> tuple[np.ndarray | None, str, str]:
    crop_size = (crop_bbox[2] - crop_bbox[0], crop_bbox[3] - crop_bbox[1])
    requested_mask = str(update.get("mask_path") or "").strip()
    if requested_mask:
        path = Path(requested_mask).resolve()
        if not path.is_file():
            return None, "", "missing_mask_path"
        try:
            with Image.open(path) as image:
                mask = np.asarray(image.convert("L")) > 0
        except OSError:
            return None, "", "invalid_mask_file"
        if (mask.shape[1], mask.shape[0]) == source_size:
            x0, y0, x1, y1 = crop_bbox
            mask = mask[y0:y1, x0:x1]
        elif (mask.shape[1], mask.shape[0]) != crop_size:
            return None, "", "mask_dimensions_do_not_match_source_or_crop"
        if not bool(mask.any()):
            return None, "", "empty_mask"
        return mask.astype(np.uint8), "reviewer_supplied_mask", ""

    prompt = _json_value(update.get("prompt_info") or update.get("prompt"))
    prompt_mask = _mask_from_prompt(prompt, crop_size=crop_size, crop_bbox=crop_bbox, source_size=source_size)
    if prompt_mask is None:
        return None, "", "missing_mask_or_rasterizable_prompt"
    if not bool(prompt_mask.any()):
        return None, "", "empty_prompt_mask"
    return prompt_mask, "reviewer_prompt_geometry", ""


def _mask_from_prompt(
    prompt: Any,
    *,
    crop_size: tuple[int, int],
    crop_bbox: tuple[int, int, int, int],
    source_size: tuple[int, int],
) -> np.ndarray | None:
    if not isinstance(prompt, dict):
        return None
    width, height = crop_size
    canvas = Image.new("L", crop_size, 0)
    draw = ImageDraw.Draw(canvas)
    coordinate_space = str(prompt.get("coordinate_space") or "crop_pixels").lower()

    def point(value: Any) -> tuple[float, float]:
        x, y = float(value[0]), float(value[1])
        if coordinate_space in {"normalized", "normalized_crop"}:
            return x * width, y * height
        if coordinate_space in {"source_pixels", "source"}:
            return x - crop_bbox[0], y - crop_bbox[1]
        if coordinate_space == "normalized_source":
            return x * source_size[0] - crop_bbox[0], y * source_size[1] - crop_bbox[1]
        return x, y

    polygon = prompt.get("polygon") or prompt.get("mask_polygon")
    if isinstance(polygon, list) and len(polygon) >= 3:
        draw.polygon([point(item) for item in polygon], fill=1)
    else:
        bbox = prompt.get("bbox") or prompt.get("box")
        if isinstance(bbox, dict):
            parsed = _crop_bbox(bbox, crop_size if "source" not in coordinate_space else source_size)
            if parsed is None:
                return None
            if "source" in coordinate_space:
                parsed = (
                    parsed[0] - crop_bbox[0],
                    parsed[1] - crop_bbox[1],
                    parsed[2] - crop_bbox[0],
                    parsed[3] - crop_bbox[1],
                )
            draw.rectangle(parsed, fill=1)
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            p0 = point(bbox[:2])
            p1 = point(bbox[2:])
            draw.rectangle((p0[0], p0[1], p1[0], p1[1]), fill=1)
        else:
            return None
    return (np.asarray(canvas) > 0).astype(np.uint8)


def _training_row(
    record: dict[str, Any],
    *,
    crop_path: Path,
    mask_path: Path,
    mask_source: str,
) -> dict[str, Any]:
    record_id = f"d047_{record['source_record_id']}_crop"
    group_id = str(record["pmcid"])
    label_type = "prompt_assisted_mask" if mask_source == "reviewer_prompt_geometry" else "human_reviewed_mask"
    row = {
        "case_id": record_id,
        "record_id": record_id,
        "image_path": str(crop_path.resolve()),
        "mask_path": str(mask_path.resolve()),
        "local_path": str(crop_path.resolve()),
        "label_path": str(mask_path.resolve()),
        "split": assign_group_split(group_id, val_fraction=0.2, test_fraction=0.0, seed=20260711),
        "source_id": str(record["source_record_id"]),
        "source_url": str(record["source_url"]),
        "direct_download_url": str(record["direct_download_url"]),
        "source_group_id": group_id,
        "group_id": group_id,
        "domain_tier": "near_domain",
        "target_domain_flag": False,
        "medical_scene": str(record["medical_scene"]),
        "fluorescence": "yes",
        "fluorescence_attribute": str(record["fluorescence_attribute"]),
        "panel_role": str(record["panel_role"]),
        "label_source": label_type,
        "label_type": label_type,
        "review_state": str(record["review_state"]),
        "sample_weight": 4.0,
        "sampling_weight": 0.25,
        "license": str(record["license"]),
        "usage_policy": "training_allowed_by_license_with_attribution",
        "checksum": sha256_file(crop_path),
        "label_checksum": sha256_file(mask_path),
        "artifact_role": "training_keyframe::fluorescence_hotspot",
        "training_eligible": True,
        "crop_bbox": json.dumps(record["crop_bbox"], separators=(",", ":")),
        "positive_area_fraction": record["positive_area_fraction"],
        "review_update_path": str(record["review_update_path"]),
        "medical_boundary": PROMOTION_BOUNDARY,
    }
    return row


def write_contact_sheet(records: list[dict[str, Any]], destination: Path) -> Path | None:
    """Write an inspection aid without modifying source figures."""
    available = [record for record in records if Path(record["local_path"]).is_file()]
    if not available:
        return None
    thumb_size = (360, 240)
    label_height = 42
    columns = 2
    rows = (len(available) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_size[0], rows * (thumb_size[1] + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(available):
        with Image.open(record["local_path"]) as source:
            thumbnail = ImageOps.contain(source.convert("RGB"), thumb_size)
        x = (index % columns) * thumb_size[0]
        y = (index // columns) * (thumb_size[1] + label_height)
        sheet.paste(thumbnail, (x + (thumb_size[0] - thumbnail.width) // 2, y))
        draw.text((x + 6, y + thumb_size[1] + 5), record["source_record_id"], fill="black")
        draw.text((x + 6, y + thumb_size[1] + 21), "review_required | no crop | no mask", fill="black")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=90)
    return destination


def write_crop_contact_sheet(records: list[dict[str, Any]], destination: Path) -> Path | None:
    """Write the reviewer-selected crop seeds without promoting them to training."""
    available = [record for record in records if Path(str(record.get("cropped_image_path") or "")).is_file()]
    if not available:
        return None
    thumb_size = (360, 240)
    label_height = 58
    columns = 2
    rows = (len(available) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_size[0], rows * (thumb_size[1] + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(available):
        with Image.open(record["cropped_image_path"]) as source:
            thumbnail = ImageOps.contain(source.convert("RGB"), thumb_size)
        x = (index % columns) * thumb_size[0]
        y = (index // columns) * (thumb_size[1] + label_height)
        sheet.paste(thumbnail, (x + (thumb_size[0] - thumbnail.width) // 2, y))
        draw.text((x + 6, y + thumb_size[1] + 5), str(record["source_record_id"]), fill="black")
        draw.text(
            (x + 6, y + thumb_size[1] + 21),
            f"state={record['review_state']} | mask={bool(record['mask_path'])}",
            fill="black",
        )
        draw.text((x + 6, y + thumb_size[1] + 37), "engineering crop seed | physician review pending", fill="black")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=90)
    return destination


def _write_csv(path: Path, records: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    fields = fieldnames or (list(records[0]) if records else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(records)


def write_outputs(
    output_dir: Path,
    records: list[dict[str, Any]],
    source_manifest: Path,
    *,
    training_rows: list[dict[str, Any]] | None = None,
    skipped: list[dict[str, str]] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    training_rows = training_rows or []
    skipped = skipped or []
    json_path = output_dir / "pmc_figure_review_queue.json"
    payload = {
        "schema_version": "osteo-vision-pmc-figure-review-queue-v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_manifest.resolve()),
        "record_count": len(records),
        "training_eligible_count": sum(bool(row["training_eligible"]) for row in records),
        "records": records,
        "skipped_updates": skipped,
        "data_boundary": (
            "Publication figures remain review-required until a reviewer supplies a valid crop and supervision. "
            "Promotion preserves near-domain and non-clinical-ground-truth boundaries."
        ),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir / "pmc_figure_review_queue.csv", records)

    training_payload = {
        "schema_version": "osteo-vision-pmc-figure-training-candidates-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_manifest.resolve()),
        "record_count": len(training_rows),
        "records": training_rows,
        "data_boundary": PROMOTION_BOUNDARY,
    }
    (output_dir / "pmc_figure_training_candidates.json").write_text(
        json.dumps(training_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "pmc_figure_training_candidates.csv", training_rows, TRAINING_FIELDS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and promote the D047 PMC figure human-review queue.")
    parser.add_argument("--manifest", default=str(DEFAULT_DATASET_DIR / "pmc_jaw_fluorescence_figure_manifest.json"))
    parser.add_argument("--output-dir", default=str(DEFAULT_DATASET_DIR / "derived" / "figure_review"))
    parser.add_argument("--review-updates", help="Reviewer-authored JSON/CSV with crop, state, and mask/prompt fields")
    parser.add_argument("--contact-sheet", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = build_review_records(list(payload.get("records") or []))
    output_dir = Path(args.output_dir).resolve()
    training_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    if args.review_updates:
        review_update_path = Path(args.review_updates).resolve()
        records, training_rows, skipped = apply_review_updates(
            records,
            load_review_updates(review_update_path),
            output_dir=output_dir,
            review_update_path=review_update_path,
        )
    write_outputs(output_dir, records, manifest_path, training_rows=training_rows, skipped=skipped)
    if args.contact_sheet:
        write_contact_sheet(records, output_dir / "pmc_figure_review_contact_sheet.jpg")
        write_crop_contact_sheet(records, output_dir / "pmc_figure_crop_contact_sheet.jpg")
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "record_count": len(records),
                "training_candidate_count": len(training_rows),
                "skipped_update_count": len(skipped),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
