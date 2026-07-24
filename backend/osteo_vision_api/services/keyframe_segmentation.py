from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from backend.osteo_vision_api.services.video_keyframe_metrics import positive_float
from osteo_vision_core.core.config import load_yaml
from osteo_vision_core.core.schemas import AdapterRequest
from osteo_vision_core.models.adapters import build_adapter, model_spec_from_mapping
from osteo_vision_core.models.hotspot_segmenter import segment_2d_fluorescence_hotspots
from osteo_vision_core.preprocess.fluorescence import decoded_frame_fluorescence_quantification


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
    allow_heuristic_fallback: bool = True,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    model_adapter, model_warnings = _keyframe_model_adapter(
        config_path,
        model_id=model_id,
        output_dir=output_dir,
        allow_heuristic_fallback=allow_heuristic_fallback,
    )
    for frame in keyframes:
        source_path = frame.get("evidence_path") or frame.get("path")
        if not source_path:
            continue
        rgb = _load_rgb_image(str(source_path))
        frame_case_id = f"{case_id}_frame_{int(frame.get('order', len(outputs) + 1)):02d}"
        frame_warnings = list(model_warnings)
        payload, analysis_method, model_frame_warnings = _trainable_keyframe_payload(
            model_adapter,
            frame_case_id=frame_case_id,
            source_path=str(source_path),
            roi_hints=roi_hints,
            rgb=rgb,
        )
        frame_warnings.extend(model_frame_warnings)
        if payload is None:
            if not allow_heuristic_fallback:
                frame_warnings.append(_keyframe_fallback_disallowed_warning(model_id))
                outputs.append(
                    _unavailable_keyframe_output(
                        frame,
                        source_path=str(source_path),
                        model_id=model_id,
                        warnings=frame_warnings,
                    )
                )
                continue
            payload = _hotspot_keyframe_fallback(
                source_path=str(source_path),
                output_dir=Path(output_dir) / "hotspot_fallback",
                frame_case_id=frame_case_id,
                threshold=threshold,
                colormap=colormap,
                roi_hints=roi_hints,
                rgb=rgb,
            )
            frame_warnings.append(_keyframe_fallback_warning())
        outputs.append(
            _keyframe_segmentation_output(
                frame,
                source_path=str(source_path),
                payload=payload,
                analysis_method=analysis_method,
                warnings=frame_warnings,
                roi_hints=roi_hints,
                rgb=rgb,
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
    rgb: np.ndarray,
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
            metadata={"roi_hints": roi_hints, "predecoded_rgb": rgb},
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
    rgb: np.ndarray,
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
        rgb=rgb,
    )


def _keyframe_segmentation_output(
    frame: dict[str, Any],
    *,
    source_path: str,
    payload: dict[str, Any],
    analysis_method: str,
    warnings: list[dict[str, Any]],
    roi_hints: list[dict[str, Any]],
    rgb: np.ndarray,
) -> dict[str, Any]:
    lesion_evidence = _dict_field(payload, "lesion_evidence")
    prediction = _dict_field(payload, "prediction")
    model_quantification = _dict_field(payload, "quantification")
    decoded_intensity = decoded_frame_fluorescence_quantification(rgb, roi_hints=roi_hints)
    decoded_intensity["source_path"] = source_path
    quantification = {
        **model_quantification,
        "model_probability_summary": {
            key: model_quantification.get(key)
            for key in ("mean_probability", "max_probability")
            if model_quantification.get(key) is not None
        },
        "decoded_frame_intensity": decoded_intensity,
    }
    if decoded_intensity.get("available"):
        quantification.update(
            {
                "p95_intensity": decoded_intensity.get("p95_intensity"),
                "background_intensity": decoded_intensity.get("background_intensity"),
                "intensity_source": decoded_intensity.get("source"),
                "intensity_domain": decoded_intensity.get("intensity_domain"),
            }
        )
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
        "quantification": quantification,
        "signal_masks": payload.get("signal_masks") or lesion_evidence.get("signal_masks") or {},
        "video_signal_segmentation": payload.get("video_signal_segmentation")
        or lesion_evidence.get("video_signal_segmentation")
        or {},
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
            "Trainable keyframe segmenter produced an empty mask for this frame and no usable "
            "trainable candidate mask is available."
        ),
        "blocking": False,
    }


def _keyframe_fallback_warning() -> dict[str, Any]:
    return {
        "code": "keyframe_segmenter_fell_back_to_hotspot",
        "message": "Trainable keyframe segmenter was unavailable for this frame; hotspot fallback was used.",
        "blocking": False,
    }


def _keyframe_fallback_disallowed_warning(model_id: str) -> dict[str, Any]:
    return {
        "code": "keyframe_heuristic_fallback_disallowed",
        "message": (
            f"Trainable keyframe segmenter {model_id} did not produce a usable mask and "
            "the active runtime prohibits heuristic hotspot fallback."
        ),
        "blocking": True,
        "model_id": model_id,
        "failure_stage": "keyframe_segmentation",
    }


def _unavailable_keyframe_output(
    frame: dict[str, Any],
    *,
    source_path: str,
    model_id: str,
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    failure_reason = "heuristic_keyframe_fallback_disallowed"
    return {
        "frame_order": frame.get("order"),
        "frame_index": frame.get("frame_index"),
        "timestamp_sec": frame.get("timestamp_sec"),
        "source_path": source_path,
        "model_id": model_id,
        "model_family": None,
        "analysis_method": "trainable_keyframe_segmenter_unavailable",
        "analysis_available": False,
        "display_allowed": False,
        "prediction": {
            "label": "unavailable",
            "confidence": 0.0,
            "review_required": True,
            "failure_reason": failure_reason,
            "target_domain_flag": False,
        },
        "segmentation_mask": {
            "available": False,
            "path": None,
            "positive_area_px": 0,
        },
        "lesion_evidence": {
            "available": False,
            "source": model_id,
            "failure_reason": failure_reason,
            "target_domain_flag": False,
        },
        "quantification": {"available": False},
        "signal_masks": {},
        "video_signal_segmentation": {},
        "review_priority": "high",
        "failure_reason": failure_reason,
        "target_domain_flag": False,
        "warnings": warnings,
        "domain_boundary": (
            "Trainable keyframe segmentation is unavailable and the active runtime prohibits "
            "heuristic fallback; no decision-support mask is available."
        ),
    }


def _segmentation_payload_has_positive_mask(payload: dict[str, Any]) -> bool:
    quantification = _dict_field(payload, "quantification")
    segmentation_mask = _dict_field(payload, "segmentation_mask")
    for key in ("positive_area_px", "component_count"):
        value = quantification.get(key)
        if positive_float(value) > 0:
            return True
    return positive_float(segmentation_mask.get("positive_area_px")) > 0


def _keyframe_model_adapter(
    config_path: str,
    *,
    model_id: str,
    output_dir: Any,
    allow_heuristic_fallback: bool,
) -> tuple[Any | None, list[dict[str, Any]]]:
    unavailable_action = (
        "hotspot fallback will be used"
        if allow_heuristic_fallback
        else "heuristic hotspot fallback is prohibited by the active runtime"
    )
    model_mapping = _keyframe_model_mapping(config_path, model_id=model_id)
    if not model_mapping:
        return None, [
            {
                "code": "keyframe_segmenter_model_not_configured",
                "message": f"Keyframe segmentation model {model_id} is not configured; {unavailable_action}.",
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
                    f"{'; '.join(status.reasons) or 'unknown reason'}; {unavailable_action}."
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


def _load_rgb_image(source_path: str) -> np.ndarray:
    with Image.open(source_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
