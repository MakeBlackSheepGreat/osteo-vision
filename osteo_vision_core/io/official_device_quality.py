from __future__ import annotations

from typing import Any

from osteo_vision_core.core.warnings import warning

OFFICIAL_WIDTH = 3840
OFFICIAL_HEIGHT = 2160
OFFICIAL_IMAGE_MIME = "image/jpeg"
OFFICIAL_VIDEO_MIME = "video/mp4"
OFFICIAL_VIDEO_CONTAINER = "mp4"
SUPPORTED_VIDEO_CODECS = {"h264", "hevc", "h265", "mpeg4"}


def assess_official_image_profile(metadata: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    width = _int_or_none(metadata.get("width"))
    height = _int_or_none(metadata.get("height"))
    extension = str(metadata.get("extension") or "").lower()
    content_probe = _dict_or_empty(metadata.get("content_probe"))
    detected_mime = content_probe.get("detected_mime")
    format_match = extension in {".jpg", ".jpeg"} and detected_mime in {None, OFFICIAL_IMAGE_MIME}
    resolution_match = width == OFFICIAL_WIDTH and height == OFFICIAL_HEIGHT
    aspect_ratio_match = _aspect_ratio_match(width, height)
    profile = {
        "schema_version": "official-device-image-profile-v1",
        "source": "official technical document",
        "target_format": "jpeg",
        "target_mime": OFFICIAL_IMAGE_MIME,
        "target_resolution": [OFFICIAL_WIDTH, OFFICIAL_HEIGHT],
        "observed_resolution": [width, height] if width and height else [],
        "observed_extension": extension,
        "observed_mime": detected_mime,
        "format_match": format_match,
        "resolution_match": resolution_match,
        "aspect_ratio_match": aspect_ratio_match,
        "status": _profile_status(format_match and resolution_match),
    }
    warnings = []
    if not format_match:
        warnings.append(
            warning(
                "official_image_format_mismatch",
                "Image is readable, but it does not match the configured JPEG device profile.",
                False,
                expected_format="jpeg",
                observed_extension=extension,
                observed_mime=detected_mime,
            )
        )
    if width and height and not resolution_match:
        warnings.append(
            warning(
                "official_image_resolution_mismatch",
                "Image is readable, but it does not match the official 3840x2160 device resolution.",
                False,
                expected_resolution=[OFFICIAL_WIDTH, OFFICIAL_HEIGHT],
                observed_resolution=[width, height],
            )
        )
    return profile, warnings


def assess_official_video_profile(metadata: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    width = _int_or_none(metadata.get("width"))
    height = _int_or_none(metadata.get("height"))
    fps = _float_or_none(metadata.get("fps"))
    frame_count = _int_or_none(metadata.get("frame_count"))
    duration_sec = _float_or_none(metadata.get("duration_sec"))
    extension = str(metadata.get("extension") or "").lower()
    content_probe = _dict_or_empty(metadata.get("content_probe"))
    ffprobe = _dict_or_empty(metadata.get("ffprobe"))
    stream = _dict_or_empty(ffprobe.get("stream"))
    fmt = _dict_or_empty(ffprobe.get("format"))
    codec_name = _codec_name(stream)
    bit_rate_bps = _int_or_none(stream.get("bit_rate")) or _int_or_none(fmt.get("bit_rate"))
    rotation_degrees = _rotation_degrees(stream)
    container_names = _container_names(fmt.get("format_name"))
    container_match = extension == ".mp4" and bool(content_probe.get("mp4_ftyp_present"))
    resolution_match = width == OFFICIAL_WIDTH and height == OFFICIAL_HEIGHT
    aspect_ratio_match = _aspect_ratio_match(width, height)
    codec_supported = codec_name in SUPPORTED_VIDEO_CODECS if codec_name else None
    ffprobe_available = bool(ffprobe.get("available"))
    profile = {
        "schema_version": "official-device-video-profile-v1",
        "source": "official technical document",
        "target_container": OFFICIAL_VIDEO_CONTAINER,
        "target_mime": OFFICIAL_VIDEO_MIME,
        "target_resolution": [OFFICIAL_WIDTH, OFFICIAL_HEIGHT],
        "observed_resolution": [width, height] if width and height else [],
        "observed_extension": extension,
        "container_match": container_match,
        "format_names": sorted(container_names),
        "resolution_match": resolution_match,
        "aspect_ratio_match": aspect_ratio_match,
        "fps": fps,
        "frame_count": frame_count,
        "duration_sec": duration_sec,
        "codec_name": codec_name,
        "codec_supported": codec_supported,
        "pixel_format": stream.get("pix_fmt"),
        "bit_rate_bps": bit_rate_bps,
        "rotation_degrees": rotation_degrees,
        "ffprobe_available": ffprobe_available,
        "status": _profile_status(container_match and resolution_match),
    }
    warnings = []
    if not resolution_match and width and height:
        warnings.append(
            warning(
                "official_video_resolution_mismatch",
                "Video is readable, but it does not match the official 3840x2160 device resolution.",
                False,
                expected_resolution=[OFFICIAL_WIDTH, OFFICIAL_HEIGHT],
                observed_resolution=[width, height],
            )
        )
    if rotation_degrees not in {None, 0}:
        warnings.append(
            warning(
                "official_video_rotation_present",
                "Video has rotation metadata; downstream 4K framing should normalize orientation before analysis.",
                False,
                rotation_degrees=rotation_degrees,
            )
        )
    if codec_supported is False:
        warnings.append(
            warning(
                "official_video_codec_unverified",
                "Video codec is readable locally but is outside the currently verified platform codec set.",
                False,
                codec_name=codec_name,
                verified_codecs=sorted(SUPPORTED_VIDEO_CODECS),
            )
        )
    if not ffprobe_available:
        warnings.append(
            warning(
                "ffprobe_unavailable",
                "ffprobe is unavailable; codec, bit-rate and rotation checks are limited to OpenCV metadata.",
                False,
            )
        )
    return profile, warnings


def _profile_status(full_match: bool) -> str:
    return "official_profile_match" if full_match else "accepted_with_profile_warnings"


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _aspect_ratio_match(width: int | None, height: int | None) -> bool | None:
    if not width or not height:
        return None
    observed = width / height
    official = OFFICIAL_WIDTH / OFFICIAL_HEIGHT
    return abs(observed - official) <= 0.01


def _codec_name(stream: dict[str, Any]) -> str | None:
    value = stream.get("codec_name")
    return str(value).lower() if value else None


def _container_names(format_name: Any) -> set[str]:
    if not format_name:
        return set()
    return {item.strip().lower() for item in str(format_name).split(",") if item.strip()}


def _rotation_degrees(stream: dict[str, Any]) -> int | None:
    tags = _dict_or_empty(stream.get("tags"))
    rotation = _int_or_none(tags.get("rotate"))
    if rotation is not None:
        return rotation
    side_data = stream.get("side_data_list")
    if isinstance(side_data, list):
        for item in side_data:
            if not isinstance(item, dict):
                continue
            rotation = _int_or_none(item.get("rotation"))
            if rotation is not None:
                return rotation
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
