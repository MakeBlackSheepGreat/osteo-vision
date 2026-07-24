"""Materialize traceable D083 ICG video engineering evidence.

D083 is a public human bone-graft ICG video proxy. It has no jaw
osteomyelitis labels or physician-reviewed pixel ground truth. Every generated
artifact therefore remains outside target-domain training and clinical claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile, ZipInfo

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.osteo_vision_api.services.keyframe_segmentation import (  # noqa: E402
    analyze_keyframe_segmentations,
    keyframe_segmentation_warnings,
)
from backend.osteo_vision_api.services.video_analysis_details import build_video_frame_details  # noqa: E402
from backend.osteo_vision_api.services.video_keyframe_metrics import (  # noqa: E402
    video_fluorescence_dynamics_summary,
    video_inference_performance_summary,
    video_temporal_summary,
)
from backend.osteo_vision_api.services.video_segmentation_manifest import (  # noqa: E402
    write_video_frame_details_manifest,
    write_video_segmentation_outputs,
)
from osteo_vision_core.core.config import load_yaml  # noqa: E402
from osteo_vision_core.core.executables import find_runtime_executable  # noqa: E402
from osteo_vision_core.core.paths import resolve_path  # noqa: E402
from osteo_vision_core.preprocess.video import extract_keyframes  # noqa: E402

DEFAULT_SOURCE_MANIFEST = (
    ROOT / "research/datasets/public-candidates/bone_activity_gap_20260718/" "bone_activity_gap_manifest.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "artifacts/data_review/d083_icg_video_evidence_20260718"
DEFAULT_CONFIG = ROOT / "configs/inference/osteo_vision_competition_strict.yml"
DEFAULT_MODEL_ID = "keyframe_residual_attention_unet_s20260715_20260715"
DEFAULT_MEMBER_NAME = "Video1.mpeg"
DATASET_ID = "D083"
CASE_ID = "D083_PUBLIC_BONE_GRAFT_ICG_PROXY"
RUN_ID = "d083_icg_video_evidence_20260718"
DOMAIN_TIER = "human_bone_graft_icg_video_proxy"
DATA_BOUNDARY = (
    "Public human vascularized bone-graft ICG video proxy. It contains no jaw "
    "osteomyelitis target-domain labels, physician-reviewed bone-surface masks, "
    "necrotic-transition-viable pixel ground truth, or pathology mapping."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--member-name", default=DEFAULT_MEMBER_NAME)
    parser.add_argument("--keyframes", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = materialize_d083_evidence(
            source_manifest=args.source_manifest,
            archive_path=args.archive,
            output_dir=args.output_dir,
            config_path=args.config,
            model_id=str(args.model_id),
            member_name=str(args.member_name),
            keyframe_count=max(2, int(args.keyframes)),
            threshold=min(1.0, max(0.0, float(args.threshold))),
            ffmpeg_path=args.ffmpeg,
            ffprobe_path=args.ffprobe,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed_closed",
                    "dataset_id": DATASET_ID,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "target_domain_flag": False,
                    "training_eligible": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["checks"]["pass"] else 1


def materialize_d083_evidence(
    *,
    source_manifest: str | Path,
    archive_path: str | Path | None,
    output_dir: str | Path,
    config_path: str | Path,
    model_id: str,
    member_name: str,
    keyframe_count: int,
    threshold: float,
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
) -> dict[str, Any]:
    manifest_path = Path(source_manifest).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    record = load_dataset_record(manifest_path, candidate_id=DATASET_ID)
    asset = dataset_archive_asset(record, member_name=member_name)
    archive = (
        Path(archive_path).resolve()
        if archive_path
        else resolve_dataset_asset_path(manifest_path, str(asset["local_path"]))
    )
    verify_file(
        archive,
        expected_size=asset.get("size_bytes"),
        expected_sha256=asset.get("sha256"),
    )

    extracted_path = output / "source" / member_name
    archive_evidence = extract_validated_member(
        archive,
        member_name=member_name,
        output_path=extracted_path,
        expected_archive_sha256=str(asset["sha256"]),
    )

    ffmpeg = require_executable(ffmpeg_path, "ffmpeg")
    ffprobe = require_executable(ffprobe_path, "ffprobe")
    mp4_path = output / "derived" / "D083_Video1_h264.mp4"
    transcode = transcode_to_mp4(extracted_path, mp4_path, ffmpeg=ffmpeg)
    source_probe = probe_media(extracted_path, ffprobe=ffprobe)
    mp4_probe = probe_media(mp4_path, ffprobe=ffprobe)

    requested_timestamps = uniform_timestamps(
        media_duration_seconds(mp4_probe),
        count=keyframe_count,
        fps=media_video_fps(mp4_probe),
    )
    keyframe_report = extract_keyframes(
        mp4_path,
        output / "keyframes_uniform",
        max_frames=keyframe_count,
        sampling_strategy="uniform",
        requested_timestamps_sec=requested_timestamps,
        max_preview_side=1280,
    )
    keyframes = list(keyframe_report.get("keyframes") or [])
    hotspot_outputs = analyze_keyframe_segmentations(
        keyframes,
        output / "keyframe_segmentations_uniform",
        case_id=CASE_ID,
        config_path=str(Path(config_path).resolve()),
        model_id=model_id,
        threshold=threshold,
        colormap="green",
        roi_hints=[],
        allow_heuristic_fallback=False,
    )
    warnings = keyframe_segmentation_warnings(hotspot_outputs)
    frame_details = build_video_frame_details(
        keyframes,
        hotspot_outputs,
        keyframe_report=keyframe_report,
    )
    apply_d083_domain_boundary(frame_details, hotspot_outputs)
    engineering_qc = build_engineering_qc(frame_details)
    if engineering_qc["dark_baseline_nonempty_mask"]:
        warnings.append(
            {
                "code": "d083_dark_baseline_nonempty_mask",
                "message": (
                    "The proxy segmenter produced a non-empty candidate mask on one or more dark baseline frames. "
                    "Spatial masks remain physician-review candidates and cannot be interpreted as bone viability."
                ),
                "blocking": False,
                "details": {
                    "dark_baseline_frame_count": engineering_qc["dark_baseline_frame_count"],
                    "dark_baseline_nonempty_frame_count": engineering_qc["dark_baseline_nonempty_frame_count"],
                    "mean_dark_baseline_positive_area_fraction": engineering_qc[
                        "mean_dark_baseline_positive_area_fraction"
                    ],
                },
            }
        )
    three_d_evidence = {
        "navigation_ready": False,
        "navigation_level": "L0",
        "registration_status": "not_recorded",
        "fallback_mode": "unregistered_3d_reference",
        "medical_boundary": "D083 carries no validated camera-to-patient transform or navigation truth.",
    }
    segmentation_outputs = write_video_segmentation_outputs(
        output / "video_segmentation_uniform",
        case_id=CASE_ID,
        run_id=RUN_ID,
        source_path=str(mp4_path),
        keyframe_report=keyframe_report,
        frame_details=frame_details,
        hotspot_outputs=hotspot_outputs,
        three_d_evidence=three_d_evidence,
        analysis_mode="public_proxy_video_keyframes",
    )
    frame_details_manifest_path = write_video_frame_details_manifest(
        output / "frame_details_uniform",
        case_id=CASE_ID,
        run_id=RUN_ID,
        source_path=str(mp4_path),
        keyframe_report=keyframe_report,
        frame_details=frame_details,
        three_d_evidence=three_d_evidence,
        analysis_mode="public_proxy_video_keyframes",
    )
    contact_sheet_path = write_contact_sheet(keyframes, output / "d083_keyframe_contact_sheet.jpg")
    dynamics = video_fluorescence_dynamics_summary(frame_details)
    temporal = video_temporal_summary(frame_details)
    performance = video_inference_performance_summary(frame_details)
    model = model_provenance(config_path, model_id=model_id)

    checks = {
        "source_archive_integrity_verified": archive_evidence["archive_sha256"] == str(asset["sha256"]).lower(),
        "zip_crc_verified": archive_evidence["zip_test_status"] == "passed",
        "mpeg_extracted": extracted_path.is_file() and extracted_path.stat().st_size > 0,
        "official_mp4_derivative_decodable": media_has_video(mp4_probe),
        "keyframes_extracted": len(keyframes) >= 2,
        "strict_model_executed": bool(hotspot_outputs)
        and all(item.get("analysis_method") == "trainable_keyframe_segmenter" for item in hotspot_outputs),
        "heuristic_fallback_absent": not any(
            "fallback" in str(item.get("analysis_method")) for item in hotspot_outputs
        ),
        "blocking_warning_absent": not any(bool(item.get("blocking")) for item in warnings),
        "frame_details_complete": len(frame_details) == len(keyframes) == len(hotspot_outputs),
        "fluorescence_dynamics_available": dynamics.get("available") is True,
        "dark_baseline_sampled": engineering_qc["dark_baseline_frame_count"] >= 1,
        "dark_baseline_safety_warning_emitted": (
            not engineering_qc["dark_baseline_nonempty_mask"]
            or any(item.get("code") == "d083_dark_baseline_nonempty_mask" for item in warnings)
        ),
        "contact_sheet_written": contact_sheet_path.is_file(),
        "video_segmentation_manifest_written": Path(
            str(segmentation_outputs.get("video_segmentation_manifest_path") or "")
        ).is_file(),
        "target_domain_claim_blocked": all(item.get("target_domain_flag") is False for item in frame_details),
        "training_admission_blocked": True,
        "navigation_claim_blocked": three_d_evidence["navigation_ready"] is False,
    }
    checks["pass"] = all(checks.values())

    summary_path = output / "d083_icg_video_evidence_manifest.json"
    report_path = output / "d083_icg_video_evidence_report_zh.md"
    summary: dict[str, Any] = {
        "schema_version": "osteo-vision-d083-icg-video-evidence-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "engineering_validation_passed" if checks["pass"] else "failed_closed",
        "dataset": {
            "dataset_id": DATASET_ID,
            "dataset_name": record.get("dataset_name"),
            "source_page_url": record.get("source_page_url"),
            "direct_download_url": record.get("direct_download_url"),
            "doi": record.get("doi"),
            "license": record.get("license"),
            "license_review_status": record.get("license_review_status"),
            "sample_count": record.get("sample_count"),
            "clinical_variables": record.get("clinical_variables"),
            "domain_tier": DOMAIN_TIER,
            "target_domain_flag": False,
            "training_eligible": False,
            "review_state": "review_required",
            "data_boundary": DATA_BOUNDARY,
        },
        "source_archive": {
            "path": str(archive),
            "size_bytes": archive.stat().st_size,
            **archive_evidence,
        },
        "extracted_mpeg": file_evidence(extracted_path) | {"ffprobe": source_probe},
        "derived_mp4": file_evidence(mp4_path)
        | {
            "relationship": "lossy H.264/AAC MP4 derivative of the CRC-verified Video1.mpeg member",
            "transcode": transcode,
            "ffprobe": mp4_probe,
            "official_input_compatibility": "MP4 upload engineering path",
        },
        "analysis": {
            "mode": "selected_keyframe_video_signal_segmentation",
            "full_frame_realtime_claim_allowed": False,
            "pixel_ground_truth_available": False,
            "disease_final_mask_allowed": False,
            "model": model,
            "keyframe_manifest_path": keyframe_report.get("keyframe_manifest_path"),
            "frame_details_manifest_path": frame_details_manifest_path,
            "video_segmentation_manifest_path": segmentation_outputs.get("video_segmentation_manifest_path"),
            "segmentation_review_video_path": segmentation_outputs.get("segmentation_review_video_path"),
            "mask_review_video_path": segmentation_outputs.get("mask_review_video_path"),
            "contact_sheet_path": str(contact_sheet_path),
            "selected_keyframe_count": len(keyframes),
            "requested_timestamps_sec": requested_timestamps,
            "warnings": warnings,
            "engineering_qc": engineering_qc,
            "fluorescence_dynamics": dynamics,
            "temporal_stability": temporal,
            "inference_performance": performance,
        },
        "safety": {
            "patient_safety_priority": True,
            "physician_review_required": True,
            "spatial_effect_applied": False,
            "navigation_ready": False,
            "runtime_replacement_allowed": False,
            "patient_video_linkage_available": False,
            "medical_claim": (
                "Engineering evidence for video ingestion, signal segmentation and temporal quantification only. "
                "It cannot support jaw-osteomyelitis diagnosis, resection boundaries or clinical performance."
            ),
        },
        "checks": checks,
        "manifest_path": str(summary_path),
        "report_path": str(report_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(summary), encoding="utf-8")
    return summary


def load_dataset_record(manifest_path: Path, *, candidate_id: str) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValueError("Dataset manifest records must be a list.")
    matches = [record for record in records if isinstance(record, dict) and record.get("candidate_id") == candidate_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {candidate_id} record, found {len(matches)}.")
    return matches[0]


def dataset_archive_asset(record: dict[str, Any], *, member_name: str) -> dict[str, Any]:
    assets = record.get("assets")
    if not isinstance(assets, list):
        raise ValueError("D083 assets must be a list.")
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and member_name.lower() in str(asset.get("content") or "").lower()
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one archive asset containing {member_name}, found {len(matches)}.")
    asset = matches[0]
    for key in ("local_path", "size_bytes", "sha256"):
        if not asset.get(key):
            raise ValueError(f"D083 archive asset is missing {key}.")
    return asset


def resolve_dataset_asset_path(manifest_path: Path, local_path: str) -> Path:
    candidate = Path(local_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (manifest_path.parent / candidate).resolve()


def verify_file(path: Path, *, expected_size: Any, expected_sha256: Any) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if int(expected_size) != path.stat().st_size:
        raise ValueError(f"Size mismatch for {path}.")
    if str(expected_sha256).lower() != sha256_file(path):
        raise ValueError(f"SHA256 mismatch for {path}.")


def extract_validated_member(
    archive_path: Path,
    *,
    member_name: str,
    output_path: Path,
    expected_archive_sha256: str,
) -> dict[str, Any]:
    archive_hash = sha256_file(archive_path)
    if archive_hash != expected_archive_sha256.lower():
        raise ValueError("D083 source archive SHA256 does not match the registered manifest.")
    try:
        with ZipFile(archive_path) as archive:
            infos = archive.infolist()
            validate_zip_members(infos)
            bad_member = archive.testzip()
            if bad_member is not None:
                raise BadZipFile(f"CRC verification failed for {bad_member}.")
            matches = [info for info in infos if PurePosixPath(info.filename.replace("\\", "/")).name == member_name]
            if len(matches) != 1:
                raise ValueError(f"Expected one {member_name} member, found {len(matches)}.")
            member = matches[0]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
            temp_path.unlink(missing_ok=True)
            try:
                with (
                    archive.open(member, "r") as source,
                    temp_path.open("wb") as target,
                ):
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                temp_path.replace(output_path)
            finally:
                temp_path.unlink(missing_ok=True)
    except BadZipFile as exc:
        raise ValueError(f"D083 source archive failed ZIP integrity validation: {exc}") from exc
    return {
        "archive_sha256": archive_hash,
        "zip_test_status": "passed",
        "member_name": member.filename,
        "member_size_bytes": member.file_size,
        "member_compressed_size_bytes": member.compress_size,
        "member_crc32": f"{member.CRC:08x}",
        "extracted_sha256": sha256_file(output_path),
    }


def validate_zip_members(infos: list[ZipInfo]) -> None:
    normalized_names: set[str] = set()
    for info in infos:
        normalized = info.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
            raise ValueError(f"Unsafe ZIP member path: {info.filename}")
        if normalized in normalized_names:
            raise ValueError(f"Duplicate ZIP member path: {info.filename}")
        normalized_names.add(normalized)
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise ValueError(f"ZIP symlink members are prohibited: {info.filename}")
        if info.flag_bits & 0x1:
            raise ValueError(f"Encrypted ZIP members are prohibited: {info.filename}")


def require_executable(value: str | None, name: str) -> str:
    candidate = value or find_runtime_executable(name)
    if not candidate or not Path(candidate).is_file():
        raise FileNotFoundError(f"Required executable is unavailable: {name}")
    return str(Path(candidate).resolve())


def transcode_to_mp4(source_path: Path, output_path: Path, *, ffmpeg: str) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    temp_path.unlink(missing_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(temp_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if result.returncode != 0 or not temp_path.is_file() or temp_path.stat().st_size <= 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg transcode failed: {result.stderr.strip()}")
    temp_path.replace(output_path)
    return {
        "status": "completed",
        "ffmpeg_path": ffmpeg,
        "video_codec": "libx264",
        "audio_codec": "aac_when_present",
        "crf": 18,
        "pixel_format": "yuv420p",
        "source_sha256": sha256_file(source_path),
        "output_sha256": sha256_file(output_path),
    }


def probe_media(path: Path, *, ffprobe: str) -> dict[str, Any]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        str(path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed for {path}: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"FFprobe returned an invalid payload for {path}.")
    return payload


def media_has_video(probe: dict[str, Any]) -> bool:
    streams = probe.get("streams")
    return isinstance(streams, list) and any(
        isinstance(stream, dict)
        and stream.get("codec_type") == "video"
        and int(stream.get("width") or 0) > 0
        and int(stream.get("height") or 0) > 0
        for stream in streams
    )


def media_duration_seconds(probe: dict[str, Any]) -> float:
    format_payload = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration = _finite_nonnegative_float(format_payload.get("duration"))
    if duration > 0:
        return duration
    streams = probe.get("streams") if isinstance(probe.get("streams"), list) else []
    durations = [
        _finite_nonnegative_float(stream.get("duration"))
        for stream in streams
        if isinstance(stream, dict) and stream.get("codec_type") == "video"
    ]
    duration = max(durations, default=0.0)
    if duration <= 0:
        raise ValueError("Video duration is unavailable.")
    return duration


def media_video_fps(probe: dict[str, Any]) -> float:
    streams = probe.get("streams") if isinstance(probe.get("streams"), list) else []
    video = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        None,
    )
    if not isinstance(video, dict):
        raise ValueError("Video stream is unavailable.")
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = str(video.get(key) or "")
        numerator, separator, denominator = value.partition("/")
        if separator:
            denominator_value = _finite_nonnegative_float(denominator)
            if denominator_value > 0:
                fps = _finite_nonnegative_float(numerator) / denominator_value
                if fps > 0:
                    return fps
        else:
            fps = _finite_nonnegative_float(value)
            if fps > 0:
                return fps
    raise ValueError("Video frame rate is unavailable.")


def uniform_timestamps(duration_sec: float, *, count: int, fps: float) -> list[float]:
    if duration_sec <= 0 or count < 2 or fps <= 0:
        raise ValueError("Uniform keyframe sampling requires positive duration, FPS and at least two frames.")
    last_timestamp = max(0.0, duration_sec - (1.0 / fps))
    step = last_timestamp / float(count - 1)
    return [round(step * index, 6) for index in range(count)]


def build_engineering_qc(frame_details: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for detail in frame_details:
        p95 = _finite_nonnegative_float(detail.get("p95_intensity"))
        positive_fraction = _finite_nonnegative_float(detail.get("positive_area_fraction"))
        dark_baseline = p95 <= 0.05
        nonempty_mask = positive_fraction >= 0.001
        item = {
            "frame_index": detail.get("frame_index"),
            "timestamp_sec": detail.get("timestamp_sec"),
            "p95_intensity": p95,
            "positive_area_fraction": positive_fraction,
            "dark_baseline": dark_baseline,
            "nonempty_mask": nonempty_mask,
            "large_candidate_mask": positive_fraction > 0.6,
        }
        detail["engineering_qc"] = item
        items.append(item)
    dark_items = [item for item in items if item["dark_baseline"]]
    dark_nonempty = [item for item in dark_items if item["nonempty_mask"]]
    empty_items = [item for item in items if not item["nonempty_mask"]]
    large_items = [item for item in items if item["large_candidate_mask"]]
    mean_dark_fraction = (
        sum(float(item["positive_area_fraction"]) for item in dark_items) / len(dark_items) if dark_items else None
    )
    return {
        "schema_version": "osteo-vision-d083-engineering-qc-v1",
        "frame_count": len(items),
        "dark_baseline_threshold_p95": 0.05,
        "nonempty_mask_threshold_fraction": 0.001,
        "large_candidate_mask_threshold_fraction": 0.6,
        "dark_baseline_frame_count": len(dark_items),
        "dark_baseline_nonempty_frame_count": len(dark_nonempty),
        "dark_baseline_nonempty_mask": bool(dark_nonempty),
        "mean_dark_baseline_positive_area_fraction": (
            round(float(mean_dark_fraction), 8) if mean_dark_fraction is not None else None
        ),
        "empty_mask_frame_count": len(empty_items),
        "empty_mask_rate": round(len(empty_items) / len(items), 8) if items else None,
        "large_candidate_mask_frame_count": len(large_items),
        "patient_video_linkage_available": False,
        "fixed_roi_available": False,
        "injection_timestamp_available": False,
        "exposure_gain_metadata_available": False,
        "spatial_mask_interpretation": "review_candidate_only",
        "frames": items,
    }


def _finite_nonnegative_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return 0.0
    return max(0.0, parsed)


def apply_d083_domain_boundary(
    frame_details: list[dict[str, Any]],
    hotspot_outputs: list[dict[str, Any]],
) -> None:
    for output in hotspot_outputs:
        output["target_domain_flag"] = False
        output["input_domain"] = DOMAIN_TIER
        output["data_boundary"] = DATA_BOUNDARY
        output["domain_boundary"] = DATA_BOUNDARY
    for detail in frame_details:
        detail["target_domain_flag"] = False
        detail["input_domain"] = DOMAIN_TIER
        detail["data_boundary"] = DATA_BOUNDARY
        detail["domain_boundary"] = DATA_BOUNDARY
        detail["review_required"] = True


def model_provenance(config_path: str | Path, *, model_id: str) -> dict[str, Any]:
    config = load_yaml(config_path)
    runtime = config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
    models = runtime.get("models") if isinstance(runtime, dict) else []
    mappings = [item for item in models if isinstance(item, dict) and item.get("model_id") == model_id]
    if len(mappings) != 1:
        raise ValueError(f"Expected one configured model {model_id}, found {len(mappings)}.")
    mapping = mappings[0]
    checkpoint_value = mapping.get("checkpoint_path")
    if not checkpoint_value:
        raise ValueError(f"Configured model {model_id} has no checkpoint path.")
    checkpoint = resolve_path(str(checkpoint_value))
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    extra = mapping.get("extra") if isinstance(mapping.get("extra"), dict) else {}
    sidecar_value = extra.get("runtime_sidecar_path")
    sidecar = resolve_path(str(sidecar_value)) if sidecar_value else None
    return {
        "model_id": model_id,
        "family": mapping.get("family"),
        "config_path": str(Path(config_path).resolve()),
        "config_sha256": sha256_file(Path(config_path).resolve()),
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "runtime_sidecar_path": str(sidecar) if sidecar else None,
        "runtime_sidecar_sha256": sha256_file(sidecar) if sidecar and sidecar.is_file() else None,
        "runtime_allowed": bool(extra.get("runtime_allowed")),
        "clinical_claim_allowed": bool(mapping.get("clinical_claim_allowed", False)),
        "input_domain": extra.get("input_domain"),
        "target_domain": bool(extra.get("target_domain", False)),
    }


def write_contact_sheet(keyframes: list[dict[str, Any]], output_path: Path) -> Path:
    if not keyframes:
        raise ValueError("Cannot write a contact sheet without keyframes.")
    columns = min(4, len(keyframes))
    rows = (len(keyframes) + columns - 1) // columns
    tile_width, tile_height, label_height = 360, 240, 34
    sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), (26, 30, 34))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(keyframes):
        image_path = Path(str(frame.get("preview_path") or frame.get("path") or ""))
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as image:
            tile = ImageOps.contain(image.convert("RGB"), (tile_width, tile_height))
        x = (index % columns) * tile_width
        y = (index // columns) * (tile_height + label_height)
        paste_x = x + (tile_width - tile.width) // 2
        paste_y = y + (tile_height - tile.height) // 2
        sheet.paste(tile, (paste_x, paste_y))
        timestamp = frame.get("timestamp_sec")
        label = f"#{index + 1:02d} frame={frame.get('frame_index')} time={float(timestamp or 0.0):.3f}s"
        draw.text((x + 8, y + tile_height + 9), label, fill=(236, 240, 242))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92, optimize=True)
    return output_path


def render_report(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    analysis = summary["analysis"]
    dynamics = analysis["fluorescence_dynamics"]
    engineering_qc = analysis["engineering_qc"]
    checks = summary["checks"]
    check_lines = "\n".join(f"- [{'x' if value else ' '}] `{key}`" for key, value in checks.items() if key != "pass")
    return f"""# D083 公开骨移植 ICG 视频工程证据

## 结论

- 状态：`{summary["status"]}`
- 数据域：`{dataset["domain_tier"]}`
- 关键帧数量：`{analysis["selected_keyframe_count"]}`
- 时序曲线可用：`{dynamics.get("available")}`
- 暗场帧数量：`{engineering_qc["dark_baseline_frame_count"]}`
- 暗场非空候选 mask：`{engineering_qc["dark_baseline_nonempty_mask"]}`
- 模型：`{analysis["model"]["model_id"]}`
- 训练准入：`false`
- 目标域标记：`false`

## 来源与边界

- 来源：[PMC9478374]({dataset["source_page_url"]})
- DOI：`{dataset["doi"]}`
- 许可：`{dataset["license"]}`
- 视频内容：血管化骨移植物 ICG 灌注
- 边界：{dataset["data_boundary"]}

当前结果只支持 MP4 接入、关键帧信号分割、荧光时序量化和证据输出的工程验证。所有候选区需医生复核，禁止用于颌骨骨髓炎诊断、切除边界、切净率或临床性能声明。

暗场仍产生非空候选 mask 时，平台会写入 `d083_dark_baseline_nonempty_mask` 安全警告。该现象说明代理模型存在域偏移，空间候选不能直接解释为骨活性。

## 完整性检查

{check_lines}

## 证据文件

- 原始归档：`{summary["source_archive"]["path"]}`
- CRC 校验提取 MPEG：`{summary["extracted_mpeg"]["path"]}`
- H.264 MP4：`{summary["derived_mp4"]["path"]}`
- 关键帧清单：`{analysis["keyframe_manifest_path"]}`
- 分割清单：`{analysis["video_segmentation_manifest_path"]}`
- 时序明细：`{analysis["frame_details_manifest_path"]}`
- 联系表：`{analysis["contact_sheet_path"]}`
"""


def file_evidence(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
