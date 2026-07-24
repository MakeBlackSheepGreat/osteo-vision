from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
from PIL import Image, UnidentifiedImageError

from osteo_vision_core.datasets.static_panel_detection import crop_quality_warnings
from osteo_vision_core.models.hotspot_segmenter import segment_2d_fluorescence_hotspots

DATASET_RELATIVE_ROOTS = {
    "d047": Path("research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures"),
    "d048": Path("research/datasets/public-candidates/d048_open_clinical_bone_fluorescence"),
}
QUEUE_RELATIVE_PATH = Path("derived/figure_review/pmc_figure_review_queue.json")
REVIEWED_MANIFEST_NAME = "d047_d048_static_figure_reviewed_manifest.json"
SEED_MANIFEST_NAME = "d047_d048_static_figure_seed_manifest.json"
ALLOWED_REVIEW_STATES = {"accepted", "modified", "rejected"}
ALLOWED_REVIEWER_ROLES = {"project_reviewer", "physician"}
ALLOWED_PANEL_ROLES = {
    "fluorescence_signal",
    "white_light",
    "paired_fluorescence",
    "paired_white_light",
    "histopathology",
    "unclassified",
}
ALLOWED_CROP_REVIEW_ACTIONS = {"accepted", "modified"}
MIN_MASK_AREA_FRACTION = 0.0001
MAX_MASK_AREA_FRACTION = 0.95
MAX_MASK_BYTES = 32 * 1024 * 1024
MEDICAL_BOUNDARY = (
    "Publication-figure masks are authorized-reviewer supervision for non-target-domain engineering validation. "
    "They require physician review and cannot support clinical diagnosis claims."
)


class StaticDatasetReviewError(ValueError):
    """Base error raised by the static publication-figure review service."""


class StaticDatasetReviewNotFoundError(StaticDatasetReviewError):
    """Raised when a requested queue record or reviewed mask does not exist."""


class StaticDatasetReviewSecurityError(StaticDatasetReviewError):
    """Raised when a manifest path escapes an approved dataset root."""


class StaticDatasetReviewService:
    """Serve and persist reviewed masks for the D047/D048 figure crops."""

    def __init__(self, project_root: str | Path) -> None:
        configured_root = os.environ.get("OSTEO_DATASET_REVIEW_PROJECT_ROOT", "").strip()
        self.project_root = Path(configured_root or project_root).resolve()
        self.dataset_roots = {
            dataset_id: (self.project_root / relative_root).resolve()
            for dataset_id, relative_root in DATASET_RELATIVE_ROOTS.items()
        }
        common_root = self.project_root / "research/datasets/public-candidates"
        self.reviewed_manifest_path = (common_root / REVIEWED_MANIFEST_NAME).resolve()
        self.seed_manifest_path = (common_root / SEED_MANIFEST_NAME).resolve()
        self._write_lock = threading.RLock()

    def list_queue(self) -> dict[str, Any]:
        reviewed_by_id = self._reviewed_records_by_id()
        seed_by_id = self._seed_records_by_id()
        items: list[dict[str, Any]] = []
        skipped_count = 0
        for dataset_id, source_record, dataset_root in self._queue_records():
            try:
                item = self._queue_item(
                    dataset_id,
                    source_record,
                    dataset_root,
                    reviewed_by_id.get(str(source_record.get("record_id") or ""))
                    or seed_by_id.get(str(source_record.get("record_id") or "")),
                )
            except (OSError, StaticDatasetReviewSecurityError, UnidentifiedImageError):
                skipped_count += 1
                continue
            if item is None:
                continue
            items.append(item)
        items.sort(key=lambda item: (str(item["dataset_id"]), str(item["record_id"])))
        return {
            "schema_version": "osteo-vision-static-dataset-review-queue-v1",
            "record_count": len(items),
            "reviewed_count": sum(bool(item["physician_reviewed"]) for item in items),
            "seed_count": sum(item.get("record_kind") == "automated_seed" for item in items),
            "training_eligible_count": sum(bool(item["training_eligible"]) for item in items),
            "skipped_invalid_record_count": skipped_count,
            "items": items,
            "records": items,
            "medical_boundary": MEDICAL_BOUNDARY,
        }

    def save_mask(
        self,
        record_id: str,
        *,
        mask_png_base64: str,
        review_state: str,
        reviewer_notes: str | None,
        reviewer_role: str = "project_reviewer",
    ) -> dict[str, Any]:
        state = _normalized_review_state(review_state)
        role = _normalized_reviewer_role(reviewer_role)
        dataset_id, source_record, dataset_root = self._find_source_record(record_id)
        image_path = self._source_image_path(source_record, dataset_root)
        with Image.open(image_path) as source_image:
            width, height = int(source_image.width), int(source_image.height)
        mask = _decode_and_validate_mask(mask_png_base64, expected_size=(width, height))
        positive_area_fraction = float(np.mean(mask > 0))

        safe_stem = _safe_record_stem(str(source_record["source_record_id"]), str(source_record["record_id"]))
        mask_dir = self._resolve_within(dataset_root, dataset_root / "derived/reviewed_masks", must_exist=False)
        mask_dir.mkdir(parents=True, exist_ok=True)
        mask_path = self._resolve_within(dataset_root, mask_dir / f"{safe_stem}_mask.png", must_exist=False)

        with self._write_lock:
            _atomic_save_mask(mask_path, mask)
            image_checksum = _sha256_file(image_path)
            label_checksum = _sha256_file(mask_path)
            training_eligible = state in {"accepted", "modified"} and _source_allows_training(source_record)
            reviewed_record = {
                "record_id": str(source_record["record_id"]),
                "dataset_id": dataset_id,
                "source_record_id": str(source_record["source_record_id"]),
                "source_group_id": str(source_record.get("source_group_id") or ""),
                "source_url": str(source_record.get("source_url") or ""),
                "image_path": str(image_path),
                "local_path": str(image_path),
                "mask_path": str(mask_path),
                "label_path": str(mask_path),
                "review_state": state,
                "reviewer_notes": str(reviewer_notes or ""),
                "reviewer_role": role,
                "review_authority": role,
                "physician_reviewed": role == "physician",
                "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
                "panel_role": str(source_record.get("panel_role") or ""),
                "license": str(source_record.get("license") or ""),
                "usage_policy": str(source_record.get("usage_policy") or ""),
                "sample_weight": _sample_weight(state),
                "sampling_weight": _positive_float(source_record.get("sampling_weight"), default=1.0),
                "training_eligible": training_eligible,
                "label_source": _label_source(state, reviewer_role=role),
                "mask_source": _label_source(state, reviewer_role=role),
                "label_type": "human_reviewed_mask",
                "record_kind": "human_review",
                "checksum": image_checksum,
                "image_checksum": image_checksum,
                "label_checksum": label_checksum,
                "positive_area_fraction": round(positive_area_fraction, 8),
                "quality_status": "accepted_for_review_feedback",
                "quality_warnings": [],
                "width": width,
                "height": height,
                "medical_boundary": MEDICAL_BOUNDARY,
            }
            self._upsert_reviewed_record(reviewed_record)

        item = self._queue_item(dataset_id, source_record, dataset_root, reviewed_record)
        if item is None:  # pragma: no cover - the source record was resolved immediately above.
            raise StaticDatasetReviewNotFoundError(f"Review record has no crop image: {record_id}")
        return item

    def generate_seed(
        self,
        record_id: str,
        *,
        threshold: float = 0.6,
        colormap: str = "green",
    ) -> dict[str, Any]:
        normalized_threshold = _normalized_threshold(threshold)
        normalized_colormap = _normalized_colormap(colormap)
        dataset_id, source_record, dataset_root = self._find_source_record(record_id)
        image_path = self._source_image_path(source_record, dataset_root)
        with Image.open(image_path) as source_image:
            width, height = int(source_image.width), int(source_image.height)

        safe_stem = _safe_record_stem(str(source_record["source_record_id"]), str(source_record["record_id"]))
        output_dir = self._resolve_within(
            dataset_root,
            dataset_root / "derived/review_seeds" / safe_stem,
            must_exist=False,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = segment_2d_fluorescence_hotspots(
                image_path,
                output_dir=output_dir,
                case_id=safe_stem,
                threshold=normalized_threshold,
                colormap=normalized_colormap,
                model_id="dataset_review_fluorescence_hotspot_seed",
            )
        except (OSError, ValueError) as exc:
            raise StaticDatasetReviewError(f"Unable to generate fluorescence hotspot seed: {exc}") from exc

        raw_mask_path = Path(str(result.get("segmentation_mask", {}).get("path") or ""))
        try:
            mask_path = self._resolve_within(dataset_root, raw_mask_path, must_exist=True)
        except FileNotFoundError as exc:
            raise StaticDatasetReviewError("Fluorescence hotspot seed did not produce a mask") from exc
        with Image.open(mask_path) as mask_image:
            mask_values = np.asarray(mask_image.convert("L"), dtype=np.uint8)
        if (int(mask_values.shape[1]), int(mask_values.shape[0])) != (width, height):
            raise StaticDatasetReviewError("Generated seed mask dimensions do not match the source crop")
        positive_area_fraction = float(np.mean(mask_values > 0)) if mask_values.size else 0.0
        quality_warnings = _seed_quality_warnings(
            positive_area_fraction,
            component_count=int(result.get("prediction", {}).get("candidate_count") or 0),
        )
        image_checksum = _sha256_file(image_path)
        label_checksum = _sha256_file(mask_path)
        seed_record = {
            "record_id": str(source_record["record_id"]),
            "dataset_id": dataset_id,
            "source_record_id": str(source_record["source_record_id"]),
            "source_group_id": str(source_record.get("source_group_id") or ""),
            "source_url": str(source_record.get("source_url") or ""),
            "image_path": str(image_path),
            "local_path": str(image_path),
            "mask_path": str(mask_path),
            "label_path": str(mask_path),
            "review_state": "review_required",
            "reviewer_notes": "Automated fluorescence hotspot seed pending authorized review.",
            "reviewer_role": "automated_seed",
            "review_authority": "automated_heuristic",
            "physician_reviewed": False,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "panel_role": str(source_record.get("panel_role") or ""),
            "license": str(source_record.get("license") or ""),
            "usage_policy": str(source_record.get("usage_policy") or ""),
            "sample_weight": 1.0,
            "sampling_weight": _positive_float(source_record.get("sampling_weight"), default=1.0),
            "training_eligible": False,
            "label_source": "heuristic_fluorescence_hotspot_seed",
            "mask_source": "heuristic_fluorescence_hotspot_seed",
            "label_type": "automated_seed_mask",
            "record_kind": "automated_seed",
            "checksum": image_checksum,
            "image_checksum": image_checksum,
            "label_checksum": label_checksum,
            "positive_area_fraction": round(positive_area_fraction, 8),
            "threshold": normalized_threshold,
            "colormap": normalized_colormap,
            "quality_status": "warning" if quality_warnings else "ready_for_review",
            "quality_warnings": quality_warnings,
            "width": width,
            "height": height,
            "medical_boundary": MEDICAL_BOUNDARY,
        }
        with self._write_lock:
            self._upsert_seed_record(seed_record)

        item = self._queue_item(dataset_id, source_record, dataset_root, seed_record)
        if item is None:  # pragma: no cover - the source record was resolved immediately above.
            raise StaticDatasetReviewNotFoundError(f"Review record has no crop image: {record_id}")
        return item

    def save_crop(
        self,
        record_id: str,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        panel_role: str = "unclassified",
        pair_id: str | None = None,
        crop_notes: str | None = None,
        suggestion_id: str | None = None,
        crop_review_action: str = "modified",
    ) -> dict[str, Any]:
        dataset_id, source_record, dataset_root = self._find_source_record(record_id)
        if str(source_record["record_id"]) in self._reviewed_records_by_id():
            raise StaticDatasetReviewError(
                "A reviewed mask already exists; remove or supersede that review before changing the crop."
            )
        original_path = self._source_original_image_path(source_record, dataset_root)
        with Image.open(original_path) as source_image:
            image_width, image_height = int(source_image.width), int(source_image.height)
            bbox = _normalized_crop_bbox(
                x=x,
                y=y,
                width=width,
                height=height,
                image_width=image_width,
                image_height=image_height,
            )
            cropped = source_image.convert("RGB").crop(
                (
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                )
            )
            quality_warnings = crop_quality_warnings(source_image, bbox)
        role = _normalized_panel_role(panel_role)
        review_action = _normalized_crop_review_action(crop_review_action)
        expected_suggestion_id = str(source_record.get("suggestion_id") or "").strip()
        requested_suggestion_id = str(suggestion_id or expected_suggestion_id).strip()
        suggested_bbox = source_record.get("suggested_crop_bbox")
        suggestion_quality_status = str(source_record.get("suggestion_quality_status") or "").strip()
        if expected_suggestion_id and requested_suggestion_id != expected_suggestion_id:
            raise StaticDatasetReviewError("suggestion_id does not match the queue record")
        if review_action == "accepted":
            if not isinstance(suggested_bbox, dict):
                raise StaticDatasetReviewError("Accepted crop requires an existing suggested_crop_bbox")
            if bbox != {key: int(suggested_bbox[key]) for key in ("x", "y", "width", "height")}:
                raise StaticDatasetReviewError("Accepted crop coordinates must match suggested_crop_bbox")
            if suggestion_quality_status == "blocked":
                raise StaticDatasetReviewError("Blocked crop suggestions require manual modification")
        safe_stem = _safe_record_stem(str(source_record["source_record_id"]), str(source_record["record_id"]))
        crop_dir = self._resolve_within(
            dataset_root,
            dataset_root / "derived/figure_review/crops",
            must_exist=False,
        )
        crop_dir.mkdir(parents=True, exist_ok=True)
        crop_path = self._resolve_within(
            dataset_root,
            crop_dir / f"{safe_stem}_crop.png",
            must_exist=False,
        )
        queue_path = dataset_root / QUEUE_RELATIVE_PATH
        updated_fields = {
            "crop_bbox": bbox,
            "cropped_image_path": str(crop_path),
            "panel_role": role,
            "pair_id": str(pair_id or "").strip(),
            "crop_notes": str(crop_notes or "").strip(),
            "crop_review_action": review_action,
            "crop_quality_status": "warning" if quality_warnings else "pass",
            "crop_quality_warnings": quality_warnings,
            "accepted_suggestion_id": requested_suggestion_id,
            "crop_reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "crop_source_image_path": str(original_path),
            "crop_source_checksum": _sha256_file(original_path),
            "review_state": "review_required",
            "training_eligible": False,
        }
        with self._write_lock:
            _atomic_save_image(crop_path, cropped)
            self._update_queue_record(queue_path, str(source_record["record_id"]), updated_fields)
            self._remove_seed_record(str(source_record["record_id"]))

        refreshed_dataset_id, refreshed_record, refreshed_root = self._find_source_record(record_id)
        item = self._queue_item(
            refreshed_dataset_id,
            refreshed_record,
            refreshed_root,
            None,
        )
        if item is None:  # pragma: no cover - refreshed source was validated above.
            raise StaticDatasetReviewNotFoundError(f"Dataset review record not found after crop save: {record_id}")
        return item

    def image_path_for(self, record_id: str) -> Path:
        _dataset_id, source_record, dataset_root = self._find_source_record(record_id)
        return self._effective_image_path(source_record, dataset_root)

    def mask_path_for(self, record_id: str) -> Path:
        dataset_id, source_record, dataset_root = self._find_source_record(record_id)
        reviewed = self._reviewed_records_by_id().get(str(source_record["record_id"]))
        seed = self._seed_records_by_id().get(str(source_record["record_id"]))
        effective_record = reviewed or seed
        if effective_record is None or str(effective_record.get("dataset_id") or dataset_id) != dataset_id:
            raise StaticDatasetReviewNotFoundError(f"Reviewed mask not found: {record_id}")
        raw_path = str(effective_record.get("mask_path") or "").strip()
        if not raw_path:
            raise StaticDatasetReviewNotFoundError(f"Reviewed mask not found: {record_id}")
        try:
            return self._resolve_within(dataset_root, Path(raw_path), must_exist=True)
        except FileNotFoundError as exc:
            raise StaticDatasetReviewNotFoundError(f"Reviewed mask not found: {record_id}") from exc

    def _queue_records(self) -> list[tuple[str, dict[str, Any], Path]]:
        records: list[tuple[str, dict[str, Any], Path]] = []
        for dataset_id, dataset_root in self.dataset_roots.items():
            queue_path = dataset_root / QUEUE_RELATIVE_PATH
            if not queue_path.is_file():
                continue
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            for raw_record in payload.get("records", []):
                if not isinstance(raw_record, dict) or not str(raw_record.get("record_id") or "").strip():
                    continue
                records.append((dataset_id, dict(raw_record), dataset_root))
        return records

    def _find_source_record(self, record_id: str) -> tuple[str, dict[str, Any], Path]:
        requested = str(record_id or "").strip()
        for dataset_id, source_record, dataset_root in self._queue_records():
            if str(source_record.get("record_id") or "") == requested:
                self._source_original_image_path(source_record, dataset_root)
                return dataset_id, source_record, dataset_root
        raise StaticDatasetReviewNotFoundError(f"Dataset review record not found: {requested}")

    def _source_image_path(self, source_record: dict[str, Any], dataset_root: Path) -> Path:
        raw_value = str(source_record.get("cropped_image_path") or "").strip()
        if not raw_value:
            raise StaticDatasetReviewNotFoundError(
                f"Crop is required before mask review for record {source_record.get('record_id')}"
            )
        raw_path = Path(raw_value)
        if not raw_path.is_absolute():
            raw_path = dataset_root / raw_path
        try:
            image_path = self._resolve_within(dataset_root, raw_path, must_exist=True)
        except FileNotFoundError as exc:
            raise StaticDatasetReviewNotFoundError(
                f"Crop image not found for record {source_record.get('record_id')}"
            ) from exc
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            raise StaticDatasetReviewSecurityError("Unsupported dataset review image type")
        return image_path

    def _source_original_image_path(self, source_record: dict[str, Any], dataset_root: Path) -> Path:
        raw_value = str(source_record.get("local_path") or "").strip()
        if not raw_value:
            raw_value = str(source_record.get("cropped_image_path") or "").strip()
        if not raw_value:
            raise StaticDatasetReviewNotFoundError(
                f"Source image not found for record {source_record.get('record_id')}"
            )
        raw_path = Path(raw_value)
        if not raw_path.is_absolute():
            raw_path = dataset_root / raw_path
        try:
            image_path = self._resolve_within(dataset_root, raw_path, must_exist=True)
        except FileNotFoundError as exc:
            raise StaticDatasetReviewNotFoundError(
                f"Source image not found for record {source_record.get('record_id')}"
            ) from exc
        if image_path.suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
            ".bmp",
        }:
            raise StaticDatasetReviewSecurityError("Unsupported dataset review image type")
        return image_path

    def _effective_image_path(self, source_record: dict[str, Any], dataset_root: Path) -> Path:
        if str(source_record.get("cropped_image_path") or "").strip():
            return self._source_image_path(source_record, dataset_root)
        return self._source_original_image_path(source_record, dataset_root)

    def _queue_item(
        self,
        dataset_id: str,
        source_record: dict[str, Any],
        dataset_root: Path,
        reviewed_record: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if (
            str(source_record.get("record_kind") or "") == "source_figure"
            and int(source_record.get("crop_suggestion_child_count") or 0) > 0
        ):
            return None
        crop_required = not bool(str(source_record.get("cropped_image_path") or "").strip())
        image_path = self._effective_image_path(source_record, dataset_root)
        with Image.open(image_path) as image:
            width, height = int(image.width), int(image.height)
        record_id = str(source_record["record_id"])
        reviewed = dict(reviewed_record or {})
        mask_path: Path | None = None
        raw_mask_path = str(reviewed.get("mask_path") or "").strip()
        if raw_mask_path:
            try:
                mask_path = self._resolve_within(dataset_root, Path(raw_mask_path), must_exist=True)
            except (FileNotFoundError, StaticDatasetReviewSecurityError):
                mask_path = None
        review_state = str(reviewed.get("review_state") or source_record.get("review_state") or "review_required")
        training_eligible = bool(reviewed.get("training_eligible")) and mask_path is not None
        image_checksum = str(reviewed.get("image_checksum") or reviewed.get("checksum") or "")
        if not image_checksum:
            image_checksum = _sha256_file(image_path)
        label_checksum = str(reviewed.get("label_checksum") or "") if mask_path is not None else ""
        encoded_id = quote(record_id, safe="")
        return {
            "record_id": record_id,
            "dataset_id": dataset_id,
            "source_record_id": str(source_record.get("source_record_id") or ""),
            "source_group_id": str(source_record.get("source_group_id") or ""),
            "image_path": str(image_path),
            "image_href": f"/dataset-review/{encoded_id}/image",
            "crop_required": crop_required,
            "crop_bbox": source_record.get("crop_bbox"),
            "parent_record_id": str(source_record.get("parent_record_id") or ""),
            "panel_label": str(source_record.get("panel_label") or ""),
            "suggestion_id": str(source_record.get("suggestion_id") or ""),
            "suggested_crop_bbox": source_record.get("suggested_crop_bbox"),
            "suggested_panel_role": str(source_record.get("suggested_panel_role") or ""),
            "suggested_pair_id": str(source_record.get("suggested_pair_id") or ""),
            "suggested_pair_alignment": str(source_record.get("suggested_pair_alignment") or ""),
            "suggestion_method": str(source_record.get("suggestion_method") or ""),
            "suggestion_score": source_record.get("suggestion_score"),
            "suggestion_quality_status": str(source_record.get("suggestion_quality_status") or ""),
            "suggestion_quality_warnings": list(source_record.get("suggestion_quality_warnings") or []),
            "crop_review_action": str(source_record.get("crop_review_action") or ""),
            "crop_quality_status": str(source_record.get("crop_quality_status") or ""),
            "crop_quality_warnings": list(source_record.get("crop_quality_warnings") or []),
            "pair_id": str(source_record.get("pair_id") or ""),
            "crop_notes": str(source_record.get("crop_notes") or ""),
            "mask_path": str(mask_path) if mask_path is not None else None,
            "mask_href": f"/dataset-review/{encoded_id}/mask" if mask_path is not None else None,
            "review_state": review_state,
            "reviewer_notes": str(reviewed.get("reviewer_notes") or source_record.get("review_notes") or ""),
            "license": str(source_record.get("license") or ""),
            "usage_policy": str(source_record.get("usage_policy") or ""),
            "sampling_weight": _positive_float(source_record.get("sampling_weight"), default=1.0),
            "sample_weight": float(reviewed.get("sample_weight") or source_record.get("sample_weight") or 1.0),
            "physician_reviewed": bool(reviewed.get("physician_reviewed")),
            "reviewer_role": str(reviewed.get("reviewer_role") or ""),
            "review_authority": str(reviewed.get("review_authority") or ""),
            "mask_source": str(reviewed.get("mask_source") or reviewed.get("label_source") or ""),
            "record_kind": str(reviewed.get("record_kind") or source_record.get("record_kind") or "queue_record"),
            "training_eligible": training_eligible,
            "width": width,
            "height": height,
            "source_url": str(source_record.get("source_url") or ""),
            "panel_role": str(source_record.get("panel_role") or ""),
            "image_checksum": image_checksum,
            "checksum": image_checksum,
            "label_checksum": label_checksum,
            "positive_area_fraction": reviewed.get("positive_area_fraction"),
            "threshold": reviewed.get("threshold"),
            "colormap": reviewed.get("colormap"),
            "quality_status": str(reviewed.get("quality_status") or "pending_review"),
            "quality_warnings": list(reviewed.get("quality_warnings") or []),
            "medical_boundary": MEDICAL_BOUNDARY,
        }

    def _update_queue_record(self, queue_path: Path, record_id: str, fields: dict[str, Any]) -> None:
        payload = json.loads(queue_path.read_text(encoding="utf-8"))
        records = payload.get("records") or []
        matched = False
        for record in records:
            if isinstance(record, dict) and str(record.get("record_id") or "") == record_id:
                record.update(fields)
                matched = True
                break
        if not matched:
            raise StaticDatasetReviewNotFoundError(f"Dataset review record not found: {record_id}")
        payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_json(queue_path, payload)

    def _reviewed_records_by_id(self) -> dict[str, dict[str, Any]]:
        if not self.reviewed_manifest_path.is_file():
            return {}
        payload = json.loads(self.reviewed_manifest_path.read_text(encoding="utf-8"))
        return {
            str(record["record_id"]): dict(record)
            for record in payload.get("records", [])
            if isinstance(record, dict) and str(record.get("record_id") or "").strip()
        }

    def _upsert_reviewed_record(self, record: dict[str, Any]) -> None:
        records_by_id = self._reviewed_records_by_id()
        records_by_id[str(record["record_id"])] = record
        records = sorted(
            records_by_id.values(),
            key=lambda item: (str(item.get("dataset_id") or ""), str(item.get("record_id") or "")),
        )
        payload = {
            "schema_version": "osteo-vision-static-figure-reviewed-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "training_eligible_count": sum(bool(item.get("training_eligible")) for item in records),
            "records": records,
            "medical_boundary": MEDICAL_BOUNDARY,
        }
        self.reviewed_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.reviewed_manifest_path, payload)

    def _seed_records_by_id(self) -> dict[str, dict[str, Any]]:
        if not self.seed_manifest_path.is_file():
            return {}
        payload = json.loads(self.seed_manifest_path.read_text(encoding="utf-8"))
        return {
            str(record["record_id"]): dict(record)
            for record in payload.get("records", [])
            if isinstance(record, dict) and str(record.get("record_id") or "").strip()
        }

    def _upsert_seed_record(self, record: dict[str, Any]) -> None:
        records_by_id = self._seed_records_by_id()
        records_by_id[str(record["record_id"])] = record
        records = sorted(
            records_by_id.values(),
            key=lambda item: (str(item.get("dataset_id") or ""), str(item.get("record_id") or "")),
        )
        payload = {
            "schema_version": "osteo-vision-static-figure-seed-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "training_eligible_count": 0,
            "records": records,
            "medical_boundary": MEDICAL_BOUNDARY,
        }
        self.seed_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.seed_manifest_path, payload)

    def _remove_seed_record(self, record_id: str) -> None:
        records_by_id = self._seed_records_by_id()
        if record_id not in records_by_id:
            return
        records_by_id.pop(record_id, None)
        records = sorted(
            records_by_id.values(),
            key=lambda item: (
                str(item.get("dataset_id") or ""),
                str(item.get("record_id") or ""),
            ),
        )
        payload = {
            "schema_version": "osteo-vision-static-figure-seed-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "training_eligible_count": 0,
            "records": records,
            "medical_boundary": MEDICAL_BOUNDARY,
        }
        _atomic_write_json(self.seed_manifest_path, payload)

    @staticmethod
    def _resolve_within(root: Path, requested: Path, *, must_exist: bool) -> Path:
        root = root.resolve()
        candidate = requested if requested.is_absolute() else root / requested
        if must_exist:
            resolved = candidate.resolve(strict=True)
        else:
            resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise StaticDatasetReviewSecurityError("Path is outside the approved dataset root") from exc
        return resolved


def _normalized_review_state(value: str) -> str:
    state = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if state not in ALLOWED_REVIEW_STATES:
        raise StaticDatasetReviewError(f"review_state must be one of: {', '.join(sorted(ALLOWED_REVIEW_STATES))}")
    return state


def _normalized_reviewer_role(value: str) -> str:
    role = str(value or "project_reviewer").strip().lower().replace("-", "_").replace(" ", "_")
    if role not in ALLOWED_REVIEWER_ROLES:
        raise StaticDatasetReviewError(f"reviewer_role must be one of: {', '.join(sorted(ALLOWED_REVIEWER_ROLES))}")
    return role


def _normalized_threshold(value: float) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError) as exc:
        raise StaticDatasetReviewError("threshold must be a number between 0 and 1") from exc
    if not np.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise StaticDatasetReviewError("threshold must be a number between 0 and 1")
    return threshold


def _normalized_colormap(value: str) -> str:
    colormap = str(value or "green").strip().lower()
    if colormap not in {"green", "amber", "magenta"}:
        raise StaticDatasetReviewError("colormap must be one of: amber, green, magenta")
    return colormap


def _normalized_panel_role(value: str) -> str:
    role = str(value or "unclassified").strip().lower().replace("-", "_")
    if role not in ALLOWED_PANEL_ROLES:
        raise StaticDatasetReviewError(f"panel_role must be one of: {', '.join(sorted(ALLOWED_PANEL_ROLES))}")
    return role


def _normalized_crop_review_action(value: str) -> str:
    action = str(value or "modified").strip().lower()
    if action not in ALLOWED_CROP_REVIEW_ACTIONS:
        raise StaticDatasetReviewError(
            f"crop_review_action must be one of: {', '.join(sorted(ALLOWED_CROP_REVIEW_ACTIONS))}"
        )
    return action


def _normalized_crop_bbox(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> dict[str, int]:
    values = {"x": x, "y": y, "width": width, "height": height}
    try:
        normalized = {key: int(value) for key, value in values.items()}
    except (TypeError, ValueError) as exc:
        raise StaticDatasetReviewError("Crop coordinates must be integers") from exc
    if normalized["x"] < 0 or normalized["y"] < 0:
        raise StaticDatasetReviewError("Crop coordinates must be non-negative")
    if normalized["width"] < 16 or normalized["height"] < 16:
        raise StaticDatasetReviewError("Crop width and height must each be at least 16 pixels")
    if normalized["x"] + normalized["width"] > image_width:
        raise StaticDatasetReviewError("Crop exceeds the source image width")
    if normalized["y"] + normalized["height"] > image_height:
        raise StaticDatasetReviewError("Crop exceeds the source image height")
    return normalized


def _seed_quality_warnings(positive_area_fraction: float, *, component_count: int) -> list[str]:
    warnings: list[str] = []
    if positive_area_fraction <= 0.0:
        warnings.append("empty_seed_mask")
    elif positive_area_fraction < MIN_MASK_AREA_FRACTION:
        warnings.append("seed_mask_area_below_review_threshold")
    elif positive_area_fraction > MAX_MASK_AREA_FRACTION:
        warnings.append("seed_mask_area_above_review_threshold")
    if component_count <= 0:
        warnings.append("no_connected_hotspot_candidates")
    return warnings


def _decode_and_validate_mask(encoded_value: str, *, expected_size: tuple[int, int]) -> np.ndarray:
    encoded = str(encoded_value or "").strip()
    if encoded.lower().startswith("data:"):
        header, separator, payload = encoded.partition(",")
        if not separator or "image/png" not in header.lower() or ";base64" not in header.lower():
            raise StaticDatasetReviewError("mask_png_base64 data URI must contain a base64 PNG")
        encoded = payload
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise StaticDatasetReviewError("mask_png_base64 is not valid base64") from exc
    if not raw or len(raw) > MAX_MASK_BYTES:
        raise StaticDatasetReviewError("mask_png_base64 payload is empty or too large")
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format != "PNG":
                raise StaticDatasetReviewError("mask_png_base64 must encode a PNG image")
            image.load()
            if (int(image.width), int(image.height)) != expected_size:
                raise StaticDatasetReviewError(
                    f"Mask dimensions {image.width}x{image.height} do not match crop {expected_size[0]}x{expected_size[1]}"
                )
            values = _mask_values(image)
    except StaticDatasetReviewError:
        raise
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise StaticDatasetReviewError("mask_png_base64 is not a readable PNG image") from exc
    unique_values = set(int(value) for value in np.unique(values))
    if not unique_values <= {0, 1, 255}:
        raise StaticDatasetReviewError(f"Mask must be binary; values={sorted(unique_values)[:12]}")
    binary = (values > 0).astype(np.uint8)
    if not bool(binary.any()):
        raise StaticDatasetReviewError("Mask must contain a non-empty positive region")
    positive_fraction = float(binary.mean())
    if not MIN_MASK_AREA_FRACTION <= positive_fraction <= MAX_MASK_AREA_FRACTION:
        raise StaticDatasetReviewError(
            f"Mask positive area fraction {positive_fraction:.8f} is outside "
            f"[{MIN_MASK_AREA_FRACTION}, {MAX_MASK_AREA_FRACTION}]"
        )
    return binary


def _mask_values(image: Image.Image) -> np.ndarray:
    if image.mode in {"1", "L", "P"}:
        return np.asarray(image.convert("L"), dtype=np.uint8)
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    if not bool(np.all(rgba[..., 3] == 255)):
        raise StaticDatasetReviewError("Mask alpha channel must be fully opaque")
    if not bool(np.array_equal(rgba[..., 0], rgba[..., 1])) or not bool(np.array_equal(rgba[..., 1], rgba[..., 2])):
        raise StaticDatasetReviewError("Mask RGB channels must contain identical binary values")
    return rgba[..., 0]


def _source_allows_training(source_record: dict[str, Any]) -> bool:
    license_name = str(source_record.get("license") or "").strip().lower()
    usage_policy = str(source_record.get("usage_policy") or "").strip().lower()
    blocked_policy = any(
        marker in usage_policy for marker in ("reference_only", "no_training", "no_derivatives", "training_forbidden")
    )
    blocked_license = any(marker in license_name for marker in ("all rights reserved", "cc by-nd", "cc-by-nd"))
    allows_derivatives = license_name.startswith("cc by") or license_name in {"cc0", "public domain"}
    return bool(allows_derivatives and not blocked_policy and not blocked_license)


def _safe_record_stem(source_record_id: str, record_id: str) -> str:
    safe_source = "".join(char if char.isalnum() or char in "._-" else "_" for char in source_record_id)[:96]
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe_source or 'review_record'}_{digest}"


def _atomic_save_mask(path: Path, mask: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    Image.fromarray(mask.astype(np.uint8) * 255).save(temporary, format="PNG")
    os.replace(temporary, path)


def _atomic_save_image(path: Path, image: Image.Image) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG")
    os.replace(temporary, path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_weight(review_state: str) -> float:
    return 4.0 if review_state in {"accepted", "modified"} else 0.5


def _label_source(review_state: str, *, reviewer_role: str) -> str:
    if reviewer_role == "physician":
        return f"physician_{review_state}_mask"
    if review_state == "modified":
        return "engineer_modified_mask"
    if review_state == "accepted":
        return "engineer_reviewed_mask"
    return "engineer_rejected_mask"


def _positive_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
