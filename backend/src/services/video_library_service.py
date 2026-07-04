from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.io.video_io import VIDEO_EXTENSIONS
from src.core.paths import ensure_dir


class VideoLibraryService:
    def __init__(self, manifest_path: str | Path, preview_root: str | Path | None = None) -> None:
        self.manifest_path = Path(manifest_path)
        self.preview_root = Path(preview_root) if preview_root is not None else None

    def list_candidates(self, *, accepted_only: bool = True, limit: int = 100) -> dict[str, Any]:
        rows = self._read_rows()
        items = [self._candidate_payload(row) for row in rows]
        if accepted_only:
            items = [item for item in items if item["exists"] and item["system_readable"]]
        return {
            "manifest_path": str(self.manifest_path),
            "exists": self.manifest_path.exists(),
            "count": len(items[:limit]),
            "items": items[:limit],
        }

    def get_candidate(self, record_id: str) -> dict[str, Any] | None:
        for row in self._read_rows():
            if str(row.get("record_id", "")) == record_id:
                return self._candidate_payload(row)
        return None

    def ensure_preview(self, record_id: str) -> dict[str, Any]:
        candidate = self.get_candidate(record_id)
        if candidate is None:
            raise KeyError(record_id)
        if not candidate.get("system_readable"):
            return {**candidate, "preview_status": "unsupported_or_missing", "preview_error": "Candidate video is not locally readable."}
        if self.preview_root is None:
            return {**candidate, "preview_status": "disabled", "preview_error": "Preview root is not configured."}

        preview_dir = ensure_dir(self.preview_root / _safe_record_id(record_id))
        preview_path = preview_dir / "preview.jpg"
        if preview_path.exists():
            return {**candidate, **_preview_payload(preview_path, "cached")}

        try:
            payload = _write_video_preview(Path(str(candidate["local_path"])), preview_path)
        except Exception as exc:
            return {**candidate, "preview_status": "failed", "preview_error": str(exc)}
        return {**candidate, **payload}

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def _candidate_payload(self, row: dict[str, str]) -> dict[str, Any]:
        local_path = row.get("local_path", "")
        path = Path(local_path) if local_path else Path()
        suffix = path.suffix.lower() if local_path else ""
        exists = bool(local_path and path.exists() and path.is_file())
        system_readable = bool(exists and suffix in VIDEO_EXTENSIONS and row.get("download_status") == "exists")
        fluorescence = _yes_no(row.get("fluorescence"))
        return {
            "record_id": row.get("record_id", ""),
            "group": row.get("group", ""),
            "title": row.get("title", ""),
            "source_page_original_link": row.get("source_page_original_link", ""),
            "direct_download_link": row.get("direct_download_link", ""),
            "local_path": local_path,
            "fluorescence": fluorescence,
            "medical_scene": row.get("medical_scene", ""),
            "usable_for_training": row.get("usable_for_training", ""),
            "notes": row.get("notes", ""),
            "download_status": row.get("download_status", ""),
            "error_or_note": row.get("error_or_note", ""),
            "size_bytes": _int_or_none(row.get("size_bytes")),
            "sha256": row.get("sha256", ""),
            "downloaded_at_utc": row.get("downloaded_at_utc", ""),
            "exists": exists,
            "system_readable": system_readable,
            "input_type": "video_file" if system_readable else "unsupported_or_missing",
            "domain_boundary": "Public non-target-domain proxy video; not real intraoperative ICG jaw osteomyelitis data.",
            **self._cached_preview_fields(row.get("record_id", "")),
        }

    def _cached_preview_fields(self, record_id: str) -> dict[str, Any]:
        if self.preview_root is None or not record_id:
            return {"preview_path": None, "preview_status": "not_requested"}
        preview_path = self.preview_root / _safe_record_id(record_id) / "preview.jpg"
        if preview_path.exists():
            return _preview_payload(preview_path, "cached")
        return {"preview_path": None, "preview_status": "not_requested"}


def _yes_no(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    return None


def _int_or_none(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


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
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_index = max(0, frame_count // 2) if frame_count > 0 else 0
    if frame_index:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise ValueError("No readable frame was found for preview.")
    ensure_dir(preview_path.parent)
    cv2.imwrite(str(preview_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return _preview_payload(
        preview_path,
        "generated",
        preview_frame_index=frame_index,
        width=width,
        height=height,
        fps=fps,
        duration_sec=float(frame_count / fps) if fps > 0 and frame_count > 0 else None,
    )
