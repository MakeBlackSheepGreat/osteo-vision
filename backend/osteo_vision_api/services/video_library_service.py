from __future__ import annotations

import csv
import math
from pathlib import Path
from threading import RLock
from typing import Any

from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.io.video_io import VIDEO_EXTENSIONS


class VideoLibraryService:
    def __init__(
        self,
        manifest_path: str | Path,
        preview_root: str | Path | None = None,
        *,
        ofdvd_manifest_path: str | Path | None = None,
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self.preview_root = Path(preview_root) if preview_root is not None else None
        self.ofdvd_manifest_path = Path(ofdvd_manifest_path) if ofdvd_manifest_path is not None else None
        self._cache_lock = RLock()
        self._manifest_cache_key: tuple[tuple[str, bool, int | None, int | None], ...] | None = None
        self._rows_cache: list[dict[str, str]] = []
        self._row_index: dict[str, dict[str, str]] = {}

    def list_candidates(self, *, accepted_only: bool = True, limit: int = 100) -> dict[str, Any]:
        limit = max(0, int(limit))
        rows = self._read_rows()
        items: list[dict[str, Any]] = []
        for row in rows if limit else ():
            item = self._candidate_payload(row)
            if accepted_only and not (item["exists"] and item["system_readable"]):
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {
            "manifest_path": str(self.manifest_path),
            "exists": _path_exists(self.manifest_path),
            "count": len(items),
            "items": items,
        }

    def get_candidate(self, record_id: str) -> dict[str, Any] | None:
        self._read_rows()
        row = self._row_index.get(record_id)
        return self._candidate_payload(row) if row is not None else None

    def ensure_preview(self, record_id: str) -> dict[str, Any]:
        candidate = self.get_candidate(record_id)
        if candidate is None:
            raise KeyError(record_id)
        if not candidate.get("system_readable"):
            return {
                **candidate,
                "preview_status": "unsupported_or_missing",
                "preview_error": "Candidate video is not locally readable.",
            }
        if self.preview_root is None:
            return {**candidate, "preview_status": "disabled", "preview_error": "Preview root is not configured."}

        try:
            preview_dir = ensure_dir(self.preview_root / _safe_record_id(record_id))
            preview_path = preview_dir / "preview.jpg"
            if _path_is_file(preview_path):
                return {**candidate, **_preview_payload(preview_path, "cached")}
            payload = _write_video_preview(Path(str(candidate["local_path"])), preview_path)
        except Exception as exc:
            return {**candidate, "preview_status": "failed", "preview_error": str(exc)}
        return {**candidate, **payload}

    def _read_rows(self) -> list[dict[str, str]]:
        cache_key = self._manifest_cache_signature()
        with self._cache_lock:
            if cache_key == self._manifest_cache_key:
                return self._rows_cache

            rows = self._read_manifest(self.manifest_path)
            merge_index = {
                str(row.get("record_id") or ""): index
                for index, row in enumerate(rows)
                if str(row.get("record_id") or "")
            }
            first_index: dict[str, int] = {}
            for index, row in enumerate(rows):
                record_id = str(row.get("record_id") or "")
                if record_id:
                    first_index.setdefault(record_id, index)

            for detailed_row in self._read_manifest(self.ofdvd_manifest_path):
                record_id = str(detailed_row.get("record_id") or "")
                if not record_id:
                    continue
                detailed_values = {
                    key: value for key, value in detailed_row.items() if value is not None and str(value).strip()
                }
                if record_id in merge_index:
                    index = merge_index[record_id]
                    rows[index] = {
                        **rows[index],
                        **detailed_values,
                        "_manifest_kind": "ofdvdnet",
                    }
                    continue
                merge_index[record_id] = len(rows)
                first_index.setdefault(record_id, len(rows))
                rows.append({**detailed_row, "_manifest_kind": "ofdvdnet"})

            self._rows_cache = rows
            self._row_index = {record_id: rows[index] for record_id, index in first_index.items()}
            self._manifest_cache_key = cache_key
            return self._rows_cache

    @staticmethod
    def _read_manifest(path: Path | None) -> list[dict[str, str]]:
        if path is None or not _path_exists(path):
            return []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except (OSError, UnicodeError, csv.Error):
            return []

    def _manifest_cache_signature(self) -> tuple[tuple[str, bool, int | None, int | None], ...]:
        return (_path_signature(self.manifest_path), _path_signature(self.ofdvd_manifest_path))

    def _candidate_payload(self, row: dict[str, str]) -> dict[str, Any]:
        is_ofdvd = row.get("_manifest_kind") == "ofdvdnet" or bool(row.get("view_layout"))
        local_path = row.get("video_path", "") if is_ofdvd else row.get("local_path", "")
        path = _safe_path(local_path)
        suffix = path.suffix.lower() if path is not None else ""
        exists = bool(path is not None and _path_exists(path) and _path_is_file(path))
        admitted = _yes_no(row.get("readable")) is True if is_ofdvd else row.get("download_status") == "exists"
        system_readable = bool(exists and suffix in VIDEO_EXTENSIONS and admitted)
        fluorescence = True if is_ofdvd else _yes_no(row.get("fluorescence"))
        return {
            "record_id": row.get("record_id", ""),
            "group": row.get("group", "") or row.get("dataset_id", ""),
            "title": row.get("title", "") or row.get("original_filename", ""),
            "source_page_original_link": row.get("source_page_original_link", ""),
            "direct_download_link": row.get("direct_download_link", ""),
            "local_path": local_path,
            "fluorescence": fluorescence,
            "medical_scene": row.get("medical_scene", "")
            or ("OFDVDnet fluorescence-guided surgery proxy" if is_ofdvd else ""),
            "usable_for_training": row.get("usable_for_training", ""),
            "notes": row.get("notes", ""),
            "download_status": row.get("download_status", "") or ("exists" if exists else "missing"),
            "error_or_note": row.get("error_or_note", "") or row.get("probe_error", ""),
            "size_bytes": _int_or_none(row.get("size_bytes")),
            "sha256": row.get("sha256", ""),
            "downloaded_at_utc": row.get("downloaded_at_utc", ""),
            "exists": exists,
            "system_readable": system_readable,
            "input_type": "video_file" if system_readable else "unsupported_or_missing",
            "domain_boundary": row.get("domain_boundary", "")
            or "Public non-target-domain proxy video; not real intraoperative ICG jaw osteomyelitis data.",
            "view_layout": row.get("view_layout", ""),
            "crop_regions": (
                {
                    "device_overlay": _xyxy(row.get("overlay_xyxy")),
                    "fluorescence": _xyxy(row.get("fluorescence_xyxy")),
                    "white_light": _xyxy(row.get("reference_xyxy")),
                }
                if is_ofdvd
                else {}
            ),
            "channel_previews": (
                {
                    "full": row.get("full_preview_path", ""),
                    "device_overlay": row.get("overlay_preview_path", ""),
                    "fluorescence": row.get("fluorescence_preview_path", ""),
                    "white_light": row.get("reference_preview_path", ""),
                }
                if is_ofdvd
                else {}
            ),
            "composite_layout_available": bool(is_ofdvd and row.get("view_layout")),
            **self._cached_preview_fields(row.get("record_id", "")),
        }

    def _cached_preview_fields(self, record_id: str) -> dict[str, Any]:
        if self.preview_root is None or not record_id:
            return {"preview_path": None, "preview_status": "not_requested"}
        preview_path = self.preview_root / _safe_record_id(record_id) / "preview.jpg"
        if _path_is_file(preview_path):
            return _preview_payload(preview_path, "cached")
        return {"preview_path": None, "preview_status": "not_requested"}


def _yes_no(value: str | None) -> bool | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    return None


def _int_or_none(value: str | None) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _xyxy(value: str | None) -> list[int] | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        coordinates = [int(part) for part in value.split("|")]
    except ValueError:
        return None
    return coordinates if len(coordinates) == 4 else None


def _safe_record_id(record_id: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in record_id).strip("._")
    return cleaned or "candidate"


def _preview_payload(preview_path: Path, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "preview_path": str(preview_path),
        "preview_status": status,
        "preview_error": "",
        **extra,
    }


def _write_video_preview(video_path: Path, preview_path: Path) -> dict[str, Any]:
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("Video could not be opened for preview.")
    try:
        frame_count = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
        fps_value = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = fps_value if math.isfinite(fps_value) and fps_value > 0 else 0.0
        width = max(0, int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0))
        height = max(0, int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
        frame_index = frame_count // 2 if frame_count > 0 else 0
        if frame_index:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise ValueError("No readable frame was found for preview.")
    ensure_dir(preview_path.parent)
    if not cv2.imwrite(str(preview_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88]):
        raise ValueError("Preview image could not be written.")
    return _preview_payload(
        preview_path,
        "generated",
        preview_frame_index=frame_index,
        width=width,
        height=height,
        fps=fps,
        duration_sec=float(frame_count / fps) if fps > 0 and frame_count > 0 else None,
    )


def _path_signature(path: Path | None) -> tuple[str, bool, int | None, int | None]:
    if path is None:
        return ("", False, None, None)
    try:
        stat = path.stat()
    except OSError:
        return (str(path), False, None, None)
    return (str(path), True, stat.st_mtime_ns, stat.st_size)


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _path_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return Path(value)
    except (OSError, TypeError, ValueError):
        return None
