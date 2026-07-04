from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DOMAIN_BOUNDARY = (
    "OFDVDnet mock chicken-thigh fluorescence-guided surgery proxy; "
    "not jaw osteomyelitis or real intraoperative target-domain data."
)


@dataclass(frozen=True)
class OFDVDnetRecord:
    record_id: str
    video_path: Path
    split: str
    width: int
    height: int
    frame_count: int
    fps: float
    duration_sec: float | None
    overlay_xyxy: tuple[int, int, int, int]
    fluorescence_xyxy: tuple[int, int, int, int]
    reference_xyxy: tuple[int, int, int, int]
    source_page_original_link: str
    domain_boundary: str = DOMAIN_BOUNDARY


def read_ofdvdnet_manifest(path: str | Path, *, readable_only: bool = True) -> list[OFDVDnetRecord]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"OFDVDnet manifest not found: {manifest_path}")
    records: list[OFDVDnetRecord] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if readable_only and str(row.get("readable", "")).lower() != "true":
                continue
            video_path = Path(str(row.get("video_path", "")))
            if readable_only and not video_path.exists():
                continue
            records.append(_record_from_row(row))
    return records


def read_ofdvdnet_sample(
    record: OFDVDnetRecord,
    *,
    frame_index: int | None = None,
    relative_position: float = 0.5,
) -> dict[str, Any]:
    frame, actual_frame_index = read_video_frame(
        record.video_path,
        frame_count=record.frame_count,
        frame_index=frame_index,
        relative_position=relative_position,
    )
    views = {
        "overlay": crop_frame(frame, record.overlay_xyxy),
        "fluorescence": crop_frame(frame, record.fluorescence_xyxy),
        "reference": crop_frame(frame, record.reference_xyxy),
    }
    return {
        "record": record,
        "frame_index": actual_frame_index,
        "timestamp_sec": float(actual_frame_index / record.fps) if record.fps > 0 else None,
        "frame": frame,
        "views": views,
    }


def read_video_frame(
    video_path: str | Path,
    *,
    frame_count: int,
    frame_index: int | None = None,
    relative_position: float = 0.5,
) -> tuple[Any, int]:
    import cv2

    path = Path(video_path)
    if frame_index is None:
        bounded_position = max(0.0, min(1.0, float(relative_position)))
        frame_index = int(round(max(0, frame_count - 1) * bounded_position))
    target_index = max(0, int(frame_index))
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open OFDVDnet video: {path}")
        capture.set(cv2.CAP_PROP_POS_FRAMES, target_index)
        ok, frame_bgr = capture.read()
        if not ok or frame_bgr is None:
            raise ValueError(f"Could not decode frame {target_index} from {path}")
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    finally:
        capture.release()
    return frame_rgb, target_index


def crop_frame(frame: Any, xyxy: tuple[int, int, int, int]) -> Any:
    x1, y1, x2, y2 = xyxy
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid OFDVDnet crop coordinates: {xyxy}")
    return frame[y1:y2, x1:x2].copy()


def _record_from_row(row: dict[str, str]) -> OFDVDnetRecord:
    return OFDVDnetRecord(
        record_id=str(row.get("record_id", "")),
        video_path=Path(str(row.get("video_path", ""))),
        split=str(row.get("split", "")),
        width=_int(row.get("width")),
        height=_int(row.get("height")),
        frame_count=_int(row.get("frame_count")),
        fps=_float(row.get("fps")),
        duration_sec=_optional_float(row.get("duration_sec")),
        overlay_xyxy=_parse_xyxy(row.get("overlay_xyxy", "")),
        fluorescence_xyxy=_parse_xyxy(row.get("fluorescence_xyxy", "")),
        reference_xyxy=_parse_xyxy(row.get("reference_xyxy", "")),
        source_page_original_link=str(row.get("source_page_original_link", "")),
        domain_boundary=str(row.get("domain_boundary") or DOMAIN_BOUNDARY),
    )


def _parse_xyxy(value: str) -> tuple[int, int, int, int]:
    parts = [part for part in value.replace(",", "|").split("|") if part != ""]
    if len(parts) != 4:
        raise ValueError(f"Expected xyxy crop with four numbers, got: {value}")
    return tuple(int(float(part)) for part in parts)  # type: ignore[return-value]


def _int(value: str | None) -> int:
    if value is None or not str(value).strip():
        return 0
    return int(float(value))


def _float(value: str | None) -> float:
    if value is None or not str(value).strip():
        return 0.0
    return float(value)


def _optional_float(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    return float(value)
