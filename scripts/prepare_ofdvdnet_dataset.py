from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from osteo_vision_core.core.paths import ensure_dir, resolve_path

DATASET_ID = "D046_OFDVDNET"
DEFAULT_ZIP_PATH = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/raw/fluorescence_proxy/"
    "ofdvdnet_dryad_v6wwpzh3w/data.zip"
)
DEFAULT_EXTRACT_DIR = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/raw/fluorescence_proxy/"
    "ofdvdnet_dryad_v6wwpzh3w/extracted"
)
DEFAULT_PREVIEW_DIR = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/ofdvdnet/previews"
)
DEFAULT_DETAILED_MANIFEST = "research/literature/inventory/ofdvdnet_video_manifest_20260704.csv"
DEFAULT_VIDEO_LIBRARY_MANIFEST = "research/literature/inventory/video_library_manifest_20260704.csv"
DEFAULT_SOURCE_MANIFEST = "research/literature/inventory/video_download_manifest_20260703.csv"
DEFAULT_REPORT_DIR = "research/reports/modeling"
VIDEO_LIBRARY_FIELDS = [
    "record_id",
    "group",
    "title",
    "source_page_original_link",
    "direct_download_link",
    "local_path",
    "fluorescence",
    "medical_scene",
    "usable_for_training",
    "notes",
    "download_status",
    "error_or_note",
    "size_bytes",
    "sha256",
    "downloaded_at_utc",
]
DETAILED_FIELDS = [
    "record_id",
    "dataset_id",
    "video_path",
    "source_zip",
    "original_filename",
    "split",
    "width",
    "height",
    "fps",
    "frame_count",
    "duration_sec",
    "view_layout",
    "overlay_xyxy",
    "fluorescence_xyxy",
    "reference_xyxy",
    "full_preview_path",
    "overlay_preview_path",
    "fluorescence_preview_path",
    "reference_preview_path",
    "source_page_original_link",
    "domain_boundary",
    "readable",
    "probe_error",
]
DOMAIN_BOUNDARY = (
    "OFDVDnet mock chicken-thigh FGS proxy; not jaw osteomyelitis or real intraoperative target-domain data."
)


def prepare_ofdvdnet_dataset(
    *,
    zip_path: str | Path = DEFAULT_ZIP_PATH,
    extract_dir: str | Path = DEFAULT_EXTRACT_DIR,
    detailed_manifest_path: str | Path = DEFAULT_DETAILED_MANIFEST,
    video_library_manifest_path: str | Path = DEFAULT_VIDEO_LIBRARY_MANIFEST,
    source_manifest_path: str | Path = DEFAULT_SOURCE_MANIFEST,
    preview_dir: str | Path = DEFAULT_PREVIEW_DIR,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
    max_videos: int | None = None,
    skip_extract: bool = False,
    skip_previews: bool = False,
) -> dict[str, Any]:
    zip_file = resolve_path(zip_path)
    if not zip_file.exists():
        raise FileNotFoundError(f"Missing OFDVDnet zip: {zip_file}")
    extraction_root = resolve_path(extract_dir)
    ensure_dir(extraction_root)
    if not skip_extract:
        safe_extract(zip_file, extraction_root)
    videos = sorted(extraction_root.glob("*.mp4"))
    if max_videos is not None:
        videos = videos[:max_videos]
    rows = []
    preview_root = ensure_dir(resolve_path(preview_dir))
    for index, video_path in enumerate(videos):
        rows.append(
            video_manifest_row(
                video_path,
                zip_file=zip_file,
                index=index,
                total=len(videos),
                preview_dir=preview_root,
                create_preview=not skip_previews,
            )
        )
    detailed_manifest = resolve_path(detailed_manifest_path)
    video_library_manifest = resolve_path(video_library_manifest_path)
    source_manifest = resolve_path(source_manifest_path)
    write_csv(detailed_manifest, rows, DETAILED_FIELDS)
    combined_rows = read_video_library_rows(source_manifest)
    readable_rows = video_library_rows(rows)
    combined_rows.extend(readable_rows)
    write_csv(video_library_manifest, combined_rows, VIDEO_LIBRARY_FIELDS)
    report_paths = write_reports(
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "zip_path": str(zip_file),
            "extract_dir": str(extraction_root),
            "detailed_manifest_path": str(detailed_manifest),
            "video_library_manifest_path": str(video_library_manifest),
            "source_manifest_path": str(source_manifest),
            "video_count": len(rows),
            "readable_video_count": len(readable_rows),
            "combined_video_library_count": len(combined_rows),
            "domain_boundary": DOMAIN_BOUNDARY,
        },
        report_dir=resolve_path(report_dir),
    )
    return {
        "zip_path": str(zip_file),
        "extract_dir": str(extraction_root),
        "video_count": len(rows),
        "readable_video_count": len(readable_rows),
        "detailed_manifest_path": str(detailed_manifest),
        "video_library_manifest_path": str(video_library_manifest),
        "combined_video_library_count": len(combined_rows),
        "report_paths": report_paths,
    }


def safe_extract(zip_path: Path, target_dir: Path) -> None:
    target_root = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = target_root / member.filename
            resolved = member_path.resolve()
            if target_root not in resolved.parents and resolved != target_root:
                raise ValueError(f"Unsafe zip member path: {member.filename}")
            ensure_dir(resolved.parent)
            if resolved.exists() and resolved.stat().st_size == member.file_size:
                continue
            with archive.open(member) as source, resolved.open("wb") as target:
                target.write(source.read())


def video_manifest_row(
    video_path: Path,
    *,
    zip_file: Path,
    index: int,
    total: int,
    preview_dir: Path,
    create_preview: bool,
) -> dict[str, Any]:
    probe_error = ""
    try:
        metadata = probe_video(video_path)
    except Exception as exc:
        probe_error = str(exc)
        metadata = {"width": 0, "height": 0, "fps": 0.0, "frame_count": 0, "duration_sec": ""}
    record_id = f"OFDVDNET_{index + 1:03d}"
    crops = quadrant_crops(int(metadata["width"]), int(metadata["height"]))
    preview_paths = (
        write_preview_images(video_path, record_id=record_id, preview_dir=preview_dir, crops=crops)
        if create_preview and not probe_error
        else {}
    )
    readable = not probe_error and int(metadata["width"]) > 0 and int(metadata["height"]) > 0
    return {
        "record_id": record_id,
        "dataset_id": DATASET_ID,
        "video_path": str(video_path),
        "source_zip": str(zip_file),
        "original_filename": video_path.name,
        "split": split_for_index(index, total),
        "width": metadata["width"],
        "height": metadata["height"],
        "fps": metadata["fps"],
        "frame_count": metadata["frame_count"],
        "duration_sec": metadata["duration_sec"],
        "view_layout": "top_left_overlay__top_right_fluorescence__bottom_left_reference",
        "overlay_xyxy": xyxy(crops["overlay"]),
        "fluorescence_xyxy": xyxy(crops["fluorescence"]),
        "reference_xyxy": xyxy(crops["reference"]),
        "full_preview_path": preview_paths.get("full", ""),
        "overlay_preview_path": preview_paths.get("overlay", ""),
        "fluorescence_preview_path": preview_paths.get("fluorescence", ""),
        "reference_preview_path": preview_paths.get("reference", ""),
        "source_page_original_link": "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w",
        "domain_boundary": DOMAIN_BOUNDARY,
        "readable": readable,
        "probe_error": probe_error,
    }


def probe_video(video_path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        capture.release()
    return {
        "width": width,
        "height": height,
        "fps": round(fps, 6),
        "frame_count": frame_count,
        "duration_sec": round(frame_count / fps, 6) if fps > 0 and frame_count > 0 else "",
    }


def quadrant_crops(width: int, height: int) -> dict[str, tuple[int, int, int, int]]:
    mid_x = width // 2
    mid_y = height // 2
    return {
        "overlay": (0, 0, mid_x, mid_y),
        "fluorescence": (mid_x, 0, width, mid_y),
        "reference": (0, mid_y, mid_x, height),
    }


def write_preview_images(
    video_path: Path,
    *,
    record_id: str,
    preview_dir: Path,
    crops: dict[str, tuple[int, int, int, int]],
) -> dict[str, str]:
    capture = cv2.VideoCapture(str(video_path))
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        return {}
    paths = {"full": preview_dir / f"{record_id}_full.jpg"}
    cv2.imwrite(str(paths["full"]), frame)
    for view, (x1, y1, x2, y2) in crops.items():
        path = preview_dir / f"{record_id}_{view}.jpg"
        cv2.imwrite(str(path), frame[y1:y2, x1:x2])
        paths[view] = path
    return {key: str(path) for key, path in paths.items()}


def split_for_index(index: int, total: int) -> str:
    train_cutoff = int(total * 0.8)
    val_cutoff = int(total * 0.9)
    if index < train_cutoff:
        return "train"
    if index < val_cutoff:
        return "val"
    return "test"


def video_library_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "record_id": row["record_id"],
            "group": "fluorescence_proxy_ofdvdnet",
            "title": "OFDVDnet fluorescence-guided surgery proxy video",
            "source_page_original_link": row["source_page_original_link"],
            "direct_download_link": "https://datadryad.org/downloads/file_stream/3078626",
            "local_path": row["video_path"],
            "fluorescence": "yes",
            "medical_scene": "mock chicken-thigh fluorescence-guided surgery",
            "usable_for_training": "enhancement_or_self_supervised_only",
            "notes": DOMAIN_BOUNDARY,
            "download_status": "exists",
            "error_or_note": "",
            "size_bytes": str(Path(row["video_path"]).stat().st_size),
            "sha256": "",
            "downloaded_at_utc": "",
        }
        for row in rows
        if row.get("readable") is True or str(row.get("readable")).lower() == "true"
    ]


def read_video_library_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_reports(payload: dict[str, Any], *, report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh_path = report_dir / "ofdvdnet_manifest_20260704_zh.md"
    en_path = report_dir / "ofdvdnet_manifest_20260704_en.md"
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def render_report(payload: dict[str, Any], *, language: str) -> str:
    if language == "zh":
        lines = [
            "# OFDVDnet 荧光代理视频 Manifest 报告",
            "",
            "## 处理结果",
            "",
            f"- 视频数：{payload['video_count']}",
            f"- 可读视频数：{payload['readable_video_count']}",
            f"- 详细 manifest：`{payload['detailed_manifest_path']}`",
            f"- 前端视频库 manifest：`{payload['video_library_manifest_path']}`",
            f"- 解压目录：`{payload['extract_dir']}`",
            f"- 合并视频库条目数：{payload['combined_video_library_count']}",
            "",
            "## 医学边界",
            "",
            payload["domain_boundary"],
            "",
            "这些视频可用于多模态荧光处理中的视频增强、伪彩稳定性和三视图拆分工程验证；禁止作为颌骨骨髓炎诊断或真实术中 ICG 目标域数据。",
        ]
    else:
        lines = [
            "# OFDVDnet Fluorescence Proxy Video Manifest Report",
            "",
            "## Result",
            "",
            f"- Video count: {payload['video_count']}",
            f"- Readable videos: {payload['readable_video_count']}",
            f"- Detailed manifest: `{payload['detailed_manifest_path']}`",
            f"- Frontend video-library manifest: `{payload['video_library_manifest_path']}`",
            f"- Extraction directory: `{payload['extract_dir']}`",
            f"- Combined video-library rows: {payload['combined_video_library_count']}",
            "",
            "## Medical Boundary",
            "",
            payload["domain_boundary"],
            "",
            "These videos support track-1 fluorescence enhancement, pseudo-color stability, and triple-view demos. They must not be presented as jaw-osteomyelitis diagnosis or real intraoperative ICG target-domain data.",
        ]
    return "\n".join(lines) + "\n"


def xyxy(value: tuple[int, int, int, int]) -> str:
    return "|".join(str(item) for item in value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare OFDVDnet proxy videos and manifests.")
    parser.add_argument("--zip-path", default=DEFAULT_ZIP_PATH)
    parser.add_argument("--extract-dir", default=DEFAULT_EXTRACT_DIR)
    parser.add_argument("--detailed-manifest-path", default=DEFAULT_DETAILED_MANIFEST)
    parser.add_argument("--video-library-manifest-path", default=DEFAULT_VIDEO_LIBRARY_MANIFEST)
    parser.add_argument("--source-manifest-path", default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--preview-dir", default=DEFAULT_PREVIEW_DIR)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--max-videos", type=int, default=None)
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-previews", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = prepare_ofdvdnet_dataset(
        zip_path=args.zip_path,
        extract_dir=args.extract_dir,
        detailed_manifest_path=args.detailed_manifest_path,
        video_library_manifest_path=args.video_library_manifest_path,
        source_manifest_path=args.source_manifest_path,
        preview_dir=args.preview_dir,
        report_dir=args.report_dir,
        max_videos=args.max_videos,
        skip_extract=args.skip_extract,
        skip_previews=args.skip_previews,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
