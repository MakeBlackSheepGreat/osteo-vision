from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.src.services.video_keyframe_metrics import positive_float
from src.core.config import load_yaml
from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapter, model_spec_from_mapping
from src.models.hotspot_segmenter import segment_2d_fluorescence_hotspots


def analyze_keyframe_segmentations(
    keyframes: list[dict[str, Any]],
    output_dir: Any,
    *,
    case_id: str,
    config_path: str,
    model_id: str,
    threshold: float,
    colormap: str,
    roi_hints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    model_adapter, model_warnings = _keyframe_model_adapter(
        config_path,
        model_id=model_id,
        output_dir=output_dir,
    )
    for frame in keyframes:
        source_path = frame.get("evidence_path") or frame.get("path")
        if not source_path:
            continue
        frame_case_id = f"{case_id}_frame_{int(frame.get('order', len(outputs) + 1)):02d}"
        frame_warnings = list(model_warnings)
        payload, analysis_method, model_frame_warnings = _trainable_keyframe_payload(
            model_adapter,
            frame_case_id=frame_case_id,
            source_path=str(source_path),
            roi_hints=roi_hints,
        )
        frame_warnings.extend(model_frame_warnings)
        if payload is None:
            payload = _hotspot_keyframe_fallback(
                source_path=str(source_path),
                output_dir=Path(output_dir) / "hotspot_fallback",
                frame_case_id=frame_case_id,
                threshold=threshold,
                colormap=colormap,
                roi_hints=roi_hints,
            )
            frame_warnings.append(_keyframe_fallback_warning())
        outputs.append(
            _keyframe_segmentation_output(
                frame,
                source_path=str(source_path),
                payload=payload,
                analysis_method=analysis_method,
                warnings=frame_warnings,
            )
        )
    return outputs


def keyframe_segmentation_warnings(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for output in outputs:
        for item in output.get("warnings", []):
            if not isinstance(item, dict):
                continue
            key = (str(item.get("code")), str(item.get("message")))
            if key in seen:
                continue
            seen.add(key)
            warnings.append(item)
    return warnings


def _trainable_keyframe_payload(
    model_adapter: Any | None,
    *,
    frame_case_id: str,
    source_path: str,
    roi_hints: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    if model_adapter is None:
        return None, "heuristic_hotspot_fallback", []

    result = model_adapter.predict(
        AdapterRequest(
            case_id=frame_case_id,
            input_path=source_path,
            input_type="2d_image",
            task_type="segmentation",
            modality="surgical_keyframe",
            metadata={"roi_hints": roi_hints},
        )
    )
    model_payload = result.to_dict()
    warnings = list(model_payload.get("warnings", []))
    if not _dict_field(model_payload, "segmentation_mask").get("path"):
        return None, "heuristic_hotspot_fallback", warnings
    if _segmentation_payload_has_positive_mask(model_payload):
        return model_payload, "trainable_keyframe_segmenter", warnings
    warnings.append(_empty_keyframe_mask_warning())
    return None, "heuristic_hotspot_fallback", warnings


def _hotspot_keyframe_fallback(
    *,
    source_path: str,
    output_dir: Path,
    frame_case_id: str,
    threshold: float,
    colormap: str,
    roi_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    # 真实目标域数据不足时，fallback 仍要产出可复核 mask/overlay，保证 MP4 闭环不中断。
    return segment_2d_fluorescence_hotspots(
        source_path,
        output_dir=output_dir,
        case_id=frame_case_id,
        threshold=threshold,
        min_component_area=25,
        colormap=colormap,
        model_id="video_keyframe_hotspot_segmenter",
        roi_hints=roi_hints,
    )


def _keyframe_segmentation_output(
    frame: dict[str, Any],
    *,
    source_path: str,
    payload: dict[str, Any],
    analysis_method: str,
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    lesion_evidence = _dict_field(payload, "lesion_evidence")
    prediction = _dict_field(payload, "prediction")
    return {
        "frame_order": frame.get("order"),
        "frame_index": frame.get("frame_index"),
        "timestamp_sec": frame.get("timestamp_sec"),
        "source_path": source_path,
        "model_id": payload.get("model_id") or lesion_evidence.get("source") or "video_keyframe_hotspot_segmenter",
        "model_family": payload.get("model_family"),
        "analysis_method": analysis_method,
        "prediction": payload["prediction"],
        "segmentation_mask": payload["segmentation_mask"],
        "lesion_evidence": payload["lesion_evidence"],
        "quantification": payload["quantification"],
        "review_priority": lesion_evidence.get("review_priority") or prediction.get("review_priority"),
        "failure_reason": lesion_evidence.get("failure_reason") or prediction.get("failure_reason"),
        "target_domain_flag": bool(lesion_evidence.get("target_domain_flag") or prediction.get("target_domain_flag")),
        "warnings": warnings,
        "domain_boundary": _keyframe_domain_boundary(analysis_method),
    }


def _keyframe_domain_boundary(analysis_method: str) -> str:
    if analysis_method == "trainable_keyframe_segmenter":
        return (
            "Trainable 2D keyframe segmentation proxy on synthetic or pseudo-labeled data; "
            "requires physician review and is not a diagnosis."
        )
    return "Heuristic keyframe hotspot fallback; requires physician review and is not a diagnosis."


def _empty_keyframe_mask_warning() -> dict[str, Any]:
    return {
        "code": "keyframe_segmenter_empty_mask_fallback",
        "message": (
            "Trainable keyframe segmenter produced an empty mask for this frame; "
            "hotspot fallback was used to keep candidate review available."
        ),
        "blocking": False,
    }


def _keyframe_fallback_warning() -> dict[str, Any]:
    return {
        "code": "keyframe_segmenter_fell_back_to_hotspot",
        "message": "Trainable keyframe segmenter was unavailable for this frame; hotspot fallback was used.",
        "blocking": False,
    }


def _segmentation_payload_has_positive_mask(payload: dict[str, Any]) -> bool:
    quantification = payload.get("quantification") if isinstance(payload.get("quantification"), dict) else {}
    segmentation_mask = payload.get("segmentation_mask") if isinstance(payload.get("segmentation_mask"), dict) else {}
    for key in ("positive_area_px", "component_count"):
        value = quantification.get(key)
        if positive_float(value) > 0:
            return True
    return positive_float(segmentation_mask.get("positive_area_px")) > 0


def _keyframe_model_adapter(
    config_path: str, *, model_id: str, output_dir: Any
) -> tuple[Any | None, list[dict[str, Any]]]:
    model_mapping = _keyframe_model_mapping(config_path, model_id=model_id)
    if not model_mapping:
        return None, [
            {
                "code": "keyframe_segmenter_model_not_configured",
                "message": f"Keyframe segmentation model {model_id} is not configured; hotspot fallback will be used.",
                "blocking": False,
            }
        ]
    extra = dict(model_mapping.get("extra") or {})
    extra["output_dir"] = str(output_dir)
    model_mapping["extra"] = extra
    adapter = build_adapter(model_spec_from_mapping(model_mapping))
    status = adapter.warmup()
    if not status.available:
        return None, [
            *status.warnings,
            {
                "code": "keyframe_segmenter_model_unavailable",
                "message": (
                    f"Keyframe segmentation model {model_id} is unavailable: "
                    f"{'; '.join(status.reasons) or 'unknown reason'}; hotspot fallback will be used."
                ),
                "blocking": False,
            },
        ]
    return adapter, list(status.warnings)


def _keyframe_model_mapping(config_path: str, *, model_id: str) -> dict[str, Any] | None:
    runtime = dict(load_yaml(config_path).get("runtime") or {})
    for model in runtime.get("models") or []:
        if str(model.get("model_id")) == model_id:
            return dict(model)
    return None


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}
