from __future__ import annotations

import hashlib
import math
import re
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, cast

from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.domains.cases.schemas import (
    CandidateRegion,
    CaseRecord,
    ThreeDRuntimeModelAsset,
    ThreeDRuntimeSafety,
    ThreeDRuntimeSnapshot,
    ThreeDRuntimeSpatialMapping,
)
from backend.osteo_vision_api.services.three_d_evidence import build_three_d_evidence

SNAPSHOT_SCHEMA_VERSION: Literal["osteo-vision-three-d-runtime-snapshot-v2"] = (
    "osteo-vision-three-d-runtime-snapshot-v2"
)
SPATIAL_MAPPING_SCHEMA_VERSION: Literal["osteo-vision-three-d-runtime-spatial-mapping-v1"] = (
    "osteo-vision-three-d-runtime-spatial-mapping-v1"
)
NAVIGATION_SAFETY_GATE_VERSION = "osteo-vision-navigation-safety-v2"
D024_REFERENCE_ID = "d024"
D024_REFERENCE_CASE_ID = "reference_d024"
# Local public-reference assets belong to the backend-controlled runtime data volume.
# Tests can patch this path with a small fixture when they need a deterministic asset.
D024_REFERENCE_MODEL_PATH: Path | None = None
D024_REFERENCE_MODEL_FILE_NAME = "mandible_d024_0001.stl"
SUPPORTED_MODEL_FORMATS = {"stl", "glb", "gltf"}
RENDERABLE_MODEL_FORMATS = {"stl", "glb"}

_PATH_KEY = re.compile(r"(?:^|_)(?:path|url)(?:$|_)", re.IGNORECASE)
_SAFE_EVIDENCE_KEYS = frozenset(
    {
        "schema_version",
        "analysis_mode",
        "model_format",
        "model_source",
        "exported_from",
        "segmentation_source",
        "segmentation_review_status",
        "registration_status",
        "registration_method",
        "registration_error_mm",
        "registration_error_threshold_mm",
        "registration_error_source",
        "camera_registration_status",
        "camera_intrinsics_id",
        "reprojection_error_px",
        "reprojection_fit_error_px",
        "reprojection_error_threshold_px",
        "fiducial_count",
        "surface_point_count",
        "coordinate_space",
        "model_coordinate_space",
        "registration_markups",
        "transform_chain",
        "transform_validation",
        "coordinate_chain_validation",
        "navigation_safety_gate_version",
        "doctor_review_status",
        "navigation_ready",
        "navigation_level",
        "degradation_state",
        "fallback_mode",
        "failure_reasons",
        "replay_mode",
        "input_domain",
        "orientation_review_status",
        "display_orientation_status",
        "view_space_mapping",
        "data_boundary",
        "surface_quality",
        "scene_manifest",
        "scene_manifest_v2",
        "boundary_note",
        "model_sha256",
        "model_expected_sha256",
    }
)
_DROP = object()


@dataclass(frozen=True)
class ResolvedThreeDModelAsset:
    path: Path
    format: str
    sha256: str
    size_bytes: int

    @property
    def file_name(self) -> str:
        return self.path.name

    @property
    def media_type(self) -> str:
        return {
            "stl": "model/stl",
            "glb": "model/gltf-binary",
            "gltf": "model/gltf+json",
        }[self.format]


def build_case_snapshot(case: CaseRecord, settings: Settings) -> ThreeDRuntimeSnapshot:
    evidence = effective_three_d_evidence(case)
    model_asset = resolve_model_asset(settings, evidence.get("model_path"))
    # Older persisted demo cases may contain the development machine's absolute
    # D024 path. Keep the packaged standard case portable by resolving the
    # controlled reference asset when the evidence explicitly identifies D024.
    if model_asset is None and _is_d024_demo_case(case, evidence):
        model_asset = resolve_model_asset(settings, str(_reference_model_path(settings)))
    latest_run = case.analysis_runs[-1] if case.analysis_runs else None
    return _build_snapshot(
        case_id=case.case_id,
        case_version=max(1, int(case.version or 1)),
        generated_at=_timestamp(case.updated_at),
        mode_label=_mode_label(evidence, latest_run.fused_outputs if latest_run is not None else {}),
        candidate_regions=[_candidate_payload(item) for item in (latest_run.candidate_regions if latest_run else [])],
        metrics=_sanitize_metrics(latest_run.quantitative_summary if latest_run else {}),
        evidence=evidence,
        model_asset=model_asset,
        asset_url=f"/three-d-runtime/v1/cases/{case.case_id}/assets/model",
    )


def _is_d024_demo_case(case: CaseRecord, evidence: Mapping[str, Any]) -> bool:
    if case.case_id == "case_standard_demo":
        return True
    source_policy = str(case.review_summary.get("three_d_source_policy", "")).lower()
    model_source = str(evidence.get("model_source", "")).lower()
    return "d024" in source_policy or "d024" in model_source


def build_public_reference_snapshot(reference_id: str, settings: Settings) -> ThreeDRuntimeSnapshot | None:
    if reference_id != D024_REFERENCE_ID:
        return None
    model_path = _reference_model_path(settings)
    evidence = build_three_d_evidence(
        parameters={
            "three_d_evidence_demo": "d024",
            "three_d_evidence": {
                "model_path": str(model_path),
                "model_format": "stl",
                "model_file_name": model_path.name,
            },
        },
        source_inputs=[],
        analysis_mode="public_reference",
        run_id=D024_REFERENCE_CASE_ID,
    )
    evidence.update(
        {
            "input_domain": "public_reference_non_target_domain",
            "registration_status": "unregistered",
            "navigation_level": "L0",
            "navigation_ready": False,
            "doctor_review_status": "not_reviewed",
            "fallback_mode": "unregistered_3d_reference",
            "failure_reasons": ["public_reference_l0_only"],
            "data_boundary": "D024 公开下颌表面参考，仅用于非目标域工程展示与医生复核，保持 L0 未配准参考。",
            "boundary_note": "D024 公开下颌表面参考，仅用于非目标域工程展示与医生复核，保持 L0 未配准参考。",
        }
    )
    model_asset = resolve_model_asset(settings, str(model_path))
    if model_asset is None:
        evidence["failure_reasons"] = ["public_reference_model_asset_unavailable"]
    return _build_snapshot(
        case_id=D024_REFERENCE_CASE_ID,
        case_version=1,
        generated_at=_reference_timestamp(model_asset),
        mode_label="公开 D024 下颌参考",
        candidate_regions=[],
        metrics={},
        evidence=evidence,
        model_asset=model_asset,
        asset_url=f"/three-d-runtime/v1/references/{D024_REFERENCE_ID}/assets/model",
    )


def resolve_case_model_asset(case: CaseRecord, settings: Settings, asset_id: str) -> ResolvedThreeDModelAsset | None:
    if asset_id != "model":
        return None
    return resolve_model_asset(settings, effective_three_d_evidence(case).get("model_path"))


def resolve_public_reference_model_asset(
    reference_id: str,
    settings: Settings,
    asset_id: str,
) -> ResolvedThreeDModelAsset | None:
    if reference_id != D024_REFERENCE_ID or asset_id != "model":
        return None
    return resolve_model_asset(settings, str(_reference_model_path(settings)))


def effective_three_d_evidence(case: CaseRecord) -> dict[str, Any]:
    latest_run = case.analysis_runs[-1] if case.analysis_runs else None
    run_evidence = {}
    if latest_run is not None and isinstance(latest_run.fused_outputs.get("three_d_evidence"), dict):
        run_evidence = dict(latest_run.fused_outputs["three_d_evidence"])
    case_evidence = dict(case.three_d_evidence) if isinstance(case.three_d_evidence, dict) else {}
    return {**run_evidence, **case_evidence}


def resolve_model_asset(settings: Settings, raw_path: object) -> ResolvedThreeDModelAsset | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    try:
        requested = Path(raw_path.strip()).expanduser()
        candidate = requested if requested.is_absolute() else settings.project_root / requested
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    model_format = resolved.suffix.lower().lstrip(".")
    if not resolved.is_file() or model_format not in SUPPORTED_MODEL_FORMATS:
        return None
    if not any(_is_relative_to(resolved, root) for root in _allowed_model_roots(settings)):
        return None
    try:
        stat = resolved.stat()
    except OSError:
        return None
    return ResolvedThreeDModelAsset(
        path=resolved,
        format=model_format,
        sha256=_cached_file_sha256(
            str(resolved),
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
            int(getattr(stat, "st_ino", 0)),
        ),
        size_bytes=stat.st_size,
    )


def _build_snapshot(
    *,
    case_id: str,
    case_version: int,
    generated_at: str,
    mode_label: str,
    candidate_regions: list[dict[str, Any]],
    metrics: dict[str, Any],
    evidence: Mapping[str, Any],
    model_asset: ResolvedThreeDModelAsset | None,
    asset_url: str,
) -> ThreeDRuntimeSnapshot:
    model_asset_payload = _model_asset_payload(model_asset, asset_url)
    spatial_mapping_payload = _spatial_mapping_payload(evidence)
    safety_payload = _safety_payload(evidence, spatial_mapping_payload)
    payload: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "case_id": case_id,
        "case_version": case_version,
        "generated_at": generated_at,
        "mode_label": mode_label,
        "candidate_regions": candidate_regions,
        "metrics": metrics,
        "three_d_evidence": _sanitize_evidence(evidence),
        "model_asset": model_asset_payload.model_dump() if model_asset_payload is not None else None,
        "spatial_mapping": spatial_mapping_payload.model_dump(),
        "safety": safety_payload.model_dump(),
    }
    payload["snapshot_sha256"] = _payload_sha256(payload)
    return ThreeDRuntimeSnapshot.model_validate(payload)


def _model_asset_payload(asset: ResolvedThreeDModelAsset | None, url: str) -> ThreeDRuntimeModelAsset | None:
    if asset is None:
        return None
    renderable = asset.format in RENDERABLE_MODEL_FORMATS
    return ThreeDRuntimeModelAsset(
        asset_id="model",
        url=url,
        format=cast(Literal["stl", "glb", "gltf"], asset.format),
        file_name=asset.file_name,
        sha256=asset.sha256,
        size_bytes=asset.size_bytes,
        rendering_status="ready" if renderable else "unsupported_format",
        rendering_failure_reason=None if renderable else "gltf_not_supported_by_isolated_renderer",
    )


def _safety_payload(
    evidence: Mapping[str, Any],
    spatial_mapping: ThreeDRuntimeSpatialMapping,
) -> ThreeDRuntimeSafety:
    navigation_level = _safe_text(evidence.get("navigation_level")) or "L0"
    registration_status = _safe_text(evidence.get("registration_status")) or "unregistered"
    doctor_review_status = _safe_text(evidence.get("doctor_review_status")) or "not_reviewed"
    requested_navigation_ready = _as_bool(evidence.get("navigation_ready"))
    navigation_prerequisites_ready = (
        requested_navigation_ready
        and navigation_level.upper() in {"L1", "L2"}
        and registration_status.lower() == "registered"
    )
    failure_reasons = _safe_string_list(evidence.get("failure_reasons"))
    runtime_gate_reasons = _runtime_navigation_gate_reasons(
        evidence,
        doctor_review_status=doctor_review_status,
        spatial_mapping=spatial_mapping,
    )
    if requested_navigation_ready and not navigation_prerequisites_ready:
        runtime_gate_reasons.append("navigation_prerequisites_incomplete")
    if requested_navigation_ready:
        failure_reasons = list(dict.fromkeys([*failure_reasons, *runtime_gate_reasons]))
    navigation_ready = requested_navigation_ready and navigation_prerequisites_ready and not failure_reasons
    if not navigation_ready and not failure_reasons:
        failure_reasons = ["navigation_not_ready"]
    fallback_mode = _safe_text(evidence.get("fallback_mode"))
    if not fallback_mode:
        fallback_mode = "none" if navigation_ready else "unregistered_3d_reference"
    boundary = _safe_text(evidence.get("boundary_note")) or _safe_text(evidence.get("data_boundary"))
    if not boundary:
        boundary = "三维运行时仅提供工程参考与医生复核证据；缺少安全前置条件时保持 L0 未配准参考。"
    return ThreeDRuntimeSafety(
        navigation_level=navigation_level if navigation_ready else "L0",
        navigation_ready=navigation_ready,
        registration_status=registration_status,
        doctor_review_status=doctor_review_status,
        fallback_mode=fallback_mode,
        failure_reasons=failure_reasons,
        boundary=boundary,
    )


def _runtime_navigation_gate_reasons(
    evidence: Mapping[str, Any],
    *,
    doctor_review_status: str,
    spatial_mapping: ThreeDRuntimeSpatialMapping,
) -> list[str]:
    reasons: list[str] = []
    if _safe_text(evidence.get("navigation_safety_gate_version")) != NAVIGATION_SAFETY_GATE_VERSION:
        reasons.append("runtime_navigation_safety_gate_version_unverified")
    if doctor_review_status.lower() not in {"accepted", "approved"}:
        reasons.append("runtime_doctor_review_not_accepted")
    if not _validation_is_valid(evidence.get("transform_validation")):
        reasons.append("runtime_transform_validation_unverified")
    if not _validation_is_valid(evidence.get("coordinate_chain_validation")):
        reasons.append("runtime_coordinate_chain_validation_unverified")
    if spatial_mapping.status != "verified":
        reasons.append("runtime_spatial_mapping_unverified")
    return reasons


def _spatial_mapping_payload(evidence: Mapping[str, Any]) -> ThreeDRuntimeSpatialMapping:
    model_coordinate_space = _safe_text(evidence.get("model_coordinate_space"))
    transform_sha256 = _safe_sha256(evidence.get("transform_sha256"))
    reasons: list[str] = []
    if not model_coordinate_space:
        reasons.append("model_coordinate_space_missing")
    if not transform_sha256:
        reasons.append("transform_sha256_missing")
    if not _validation_is_valid(evidence.get("transform_validation")):
        reasons.append("transform_validation_unverified")
    elif _safe_sha256(_mapping_value(evidence.get("transform_validation"), "sha256")) != transform_sha256:
        reasons.append("transform_sha256_binding_mismatch")
    if not _validation_is_valid(evidence.get("coordinate_chain_validation")):
        reasons.append("coordinate_chain_validation_unverified")
    elif not _transform_chain_mentions_space(evidence.get("transform_chain"), model_coordinate_space):
        reasons.append("model_coordinate_space_not_bound")
    return ThreeDRuntimeSpatialMapping(
        schema_version=SPATIAL_MAPPING_SCHEMA_VERSION,
        model_coordinate_space=model_coordinate_space or None,
        transform_sha256=transform_sha256 or None,
        status="verified" if not reasons else "unavailable",
        failure_reasons=reasons,
    )


def _validation_is_valid(value: object) -> bool:
    return isinstance(value, Mapping) and value.get("valid") is True


def _mapping_value(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, Mapping) else None


def _transform_chain_mentions_space(value: object, coordinate_space: str) -> bool:
    if not coordinate_space or not isinstance(value, (list, tuple)):
        return False
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if (
            _safe_text(item.get("from_space")) == coordinate_space
            or _safe_text(item.get("to_space")) == coordinate_space
        ):
            return True
    return False


def _safe_sha256(value: object) -> str:
    text = _safe_text(value).lower()
    return text if re.fullmatch(r"[a-f0-9]{64}", text) else ""


def _candidate_payload(candidate: CandidateRegion) -> dict[str, Any]:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    payload: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "risk_type": _safe_text(candidate.risk_type) or "candidate",
        "score": _finite_number(candidate.score),
        "confidence": _finite_number(candidate.confidence),
        "status": str(candidate.status.value),
    }
    for key in (
        "frame_key",
        "frame_index",
        "timestamp_sec",
        "bbox_normalized",
        "source_bbox_normalized",
        "source_bbox_xyxy",
        "surface_point_mm",
        "position_mm",
        "position_3d",
        "projection_point_3d",
        "coordinate_space",
        "spatial_mapping_status",
        "coordinate_transform_sha256",
        "surface_normal",
        "review_priority",
        "bone_gate_status",
        "input_domain",
        "data_boundary",
        "failure_reason",
    ):
        if key not in metadata:
            continue
        value = _sanitize_value(metadata[key], sensitive=False)
        if value is not _DROP:
            payload[key] = value
    return payload


def _sanitize_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in _SAFE_EVIDENCE_KEYS:
        if key not in evidence:
            continue
        value = _sanitize_value(evidence[key], sensitive=True)
        if value is not _DROP:
            payload[key] = value
    return payload


def _sanitize_metrics(metrics: object) -> dict[str, Any]:
    value = _sanitize_value(metrics if isinstance(metrics, Mapping) else {}, sensitive=True)
    return value if isinstance(value, dict) else {}


def _sanitize_value(value: object, *, sensitive: bool, depth: int = 0) -> Any:
    if depth > 24:
        return _DROP
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = _safe_text(value)
        return text if text else _DROP
    if isinstance(value, Mapping):
        payload: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            if _is_path_key(key) or (sensitive and _is_sensitive_key(key)):
                continue
            sanitized = _sanitize_value(child, sensitive=sensitive, depth=depth + 1)
            if sanitized is not _DROP:
                payload[key] = sanitized
        return payload
    if isinstance(value, (list, tuple)):
        items: list[Any] = []
        for child in value:
            sanitized = _sanitize_value(child, sensitive=sensitive, depth=depth + 1)
            if sanitized is not _DROP:
                items.append(sanitized)
        return items
    return _DROP


def _mode_label(evidence: Mapping[str, Any], fused_outputs: Mapping[str, Any]) -> str:
    mode = _safe_text(evidence.get("analysis_mode")) or _safe_text(fused_outputs.get("mode"))
    labels = {
        "video_file_keyframes": "MP4 候选区空间证据",
        "video_file": "MP4 候选区空间证据",
        "browser_frame_keyframes": "视频流候选区空间证据",
        "realtime_stream_keyframes": "视频流候选区空间证据",
        "image_pair": "白光/荧光融合证据",
        "public_reference": "公开三维参考",
    }
    return labels.get(mode, "三维证据参考")


def _allowed_model_roots(settings: Settings) -> list[Path]:
    return [
        settings.artifact_root.resolve(),
        (settings.project_root / "artifacts").resolve(),
    ]


def _reference_model_path(settings: Settings) -> Path:
    if D024_REFERENCE_MODEL_PATH is not None:
        return (
            D024_REFERENCE_MODEL_PATH
            if D024_REFERENCE_MODEL_PATH.is_absolute()
            else settings.project_root / D024_REFERENCE_MODEL_PATH
        )
    packaged_reference = settings.project_root / "artifacts" / "platform" / "three_d_runtime" / "references" / (
        D024_REFERENCE_ID
    ) / D024_REFERENCE_MODEL_FILE_NAME
    if packaged_reference.is_file():
        return packaged_reference
    return settings.artifact_root / "three_d_runtime" / "references" / D024_REFERENCE_ID / D024_REFERENCE_MODEL_FILE_NAME


def _reference_timestamp(asset: ResolvedThreeDModelAsset | None) -> str:
    if asset is not None:
        try:
            return _timestamp(datetime.fromtimestamp(asset.path.stat().st_mtime, tz=timezone.utc))
        except OSError:
            pass
    return "2026-01-01T00:00:00Z"


def _timestamp(value: datetime) -> str:
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=256)
def _cached_file_sha256(path: str, size_bytes: int, mtime_ns: int, ctime_ns: int, inode: int) -> str:
    del size_bytes, mtime_ns, ctime_ns, inode
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_snapshot_bytes(payload)).hexdigest()


def _canonical_snapshot_bytes(value: object) -> bytes:
    """Encode the v2 integrity payload without relying on language-specific JSON serialization."""

    output = bytearray()

    def append_text(text: str) -> None:
        output.extend(text.encode("utf-8"))

    def append_string(text: str) -> None:
        encoded = text.encode("utf-8")
        output.extend(b"s")
        append_text(str(len(encoded)))
        output.extend(b":")
        output.extend(encoded)

    def append_number(number: int | float) -> None:
        try:
            numeric = float(number)
        except OverflowError as exc:
            raise ValueError("3D runtime snapshot contains a number outside the browser range") from exc
        if not math.isfinite(numeric):
            raise ValueError("3D runtime snapshot contains a non-finite number")
        output.extend(b"d")
        output.extend(struct.pack(">d", numeric).hex().encode("ascii"))
        output.extend(b";")

    def append_value(item: object) -> None:
        if item is None:
            output.extend(b"n;")
            return
        if isinstance(item, bool):
            output.extend(b"b1;" if item else b"b0;")
            return
        if isinstance(item, (int, float)):
            append_number(item)
            return
        if isinstance(item, str):
            append_string(item)
            return
        if isinstance(item, Mapping):
            entries = sorted(
                ((str(key), child) for key, child in item.items()),
                key=lambda entry: entry[0].encode("utf-8"),
            )
            output.extend(b"o")
            append_text(str(len(entries)))
            output.extend(b"{")
            for key, child in entries:
                append_string(key)
                append_value(child)
            output.extend(b"}")
            return
        if isinstance(item, (list, tuple)):
            output.extend(b"a")
            append_text(str(len(item)))
            output.extend(b"[")
            for child in item:
                append_value(child)
            output.extend(b"]")
            return
        raise ValueError(f"3D runtime snapshot contains unsupported value type: {type(item)!r}")

    append_value(value)
    return bytes(output)


def _safe_string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    output: list[str] = []
    for item in value:
        text = _safe_text(item)
        if text and text not in output:
            output.append(text)
    return output


def _finite_number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "ready"}
    return False


def _safe_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or _looks_like_internal_path(text):
        return ""
    return text[:4000]


def _looks_like_internal_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    if normalized.startswith(("/", "~/", "./", "../", "artifacts/", "frontend/", "backend/", "research/")):
        return True
    if re.search(r"(?:^|[\s\"'=])(?:[A-Za-z]:/|/(?:users|tmp|home|var|opt|workspace)/)", normalized, re.IGNORECASE):
        return True
    return bool(re.search(r"(?:^|[\s:=])(?:artifacts|frontend|backend|research)/", normalized, re.IGNORECASE))


def _is_path_key(key: str) -> bool:
    return bool(_PATH_KEY.search(key))


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    tokens = {token for token in normalized.split("_") if token}
    sensitive_tokens = {
        "clinical",
        "patient",
        "age",
        "sex",
        "medication",
        "medications",
        "comorbidity",
        "comorbidities",
        "lab",
        "labs",
        "identity",
        "institution",
        "organization",
        "externalcase",
        "recordedby",
    }
    return bool(tokens.intersection(sensitive_tokens))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
