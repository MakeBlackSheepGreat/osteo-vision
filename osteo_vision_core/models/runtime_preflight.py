from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from osteo_vision_core.core.executables import find_runtime_executable


def check_runtime_readiness(
    config_path: str | Path,
    *,
    require_strict: bool = False,
) -> dict[str, Any]:
    path = Path(config_path).resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not path.is_file():
        return _report(path, "unknown", True, [{"code": "config_missing", "path": str(path)}], [])
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return _report(
            path,
            "unknown",
            require_strict,
            [{"code": "config_invalid", "path": str(path), "detail": str(exc)}],
            [],
        )
    if not isinstance(payload, dict):
        return _report(
            path,
            "unknown",
            require_strict,
            [{"code": "config_root_must_be_mapping", "path": str(path)}],
            [],
        )
    runtime_value = payload.get("runtime") or {}
    if not isinstance(runtime_value, dict):
        return _report(
            path,
            "unknown",
            require_strict,
            [{"code": "runtime_config_must_be_mapping", "path": str(path)}],
            [],
        )
    runtime = dict(runtime_value)
    profile = str(runtime.get("runtime_profile") or "development")
    strict = bool(runtime.get("strict_startup"))
    models = [dict(item) for item in runtime.get("models") or [] if isinstance(item, dict)]
    required_ids = {str(value) for value in runtime.get("required_model_ids") or []}
    model_by_id = {str(model.get("model_id") or ""): model for model in models}
    tasks = runtime.get("tasks") if isinstance(runtime.get("tasks"), dict) else {}
    segmentation_task = tasks.get("segmentation") if isinstance(tasks, dict) else None
    segmentation_model_id = (
        str(segmentation_task.get("model_id") or "").strip() if isinstance(segmentation_task, dict) else ""
    )
    required_tools = {str(value).strip() for value in runtime.get("required_tools") or [] if str(value).strip()}
    recommended_tools = {str(value).strip() for value in runtime.get("recommended_tools") or [] if str(value).strip()}
    tool_status: list[dict[str, Any]] = []
    verified_models: list[dict[str, Any]] = []

    for tool_name in sorted(required_tools | recommended_tools):
        executable = find_runtime_executable(tool_name)
        tool_status.append(
            {
                "tool": tool_name,
                "available": executable is not None,
                "path": executable,
                "required": tool_name in required_tools,
            }
        )
        if executable is not None:
            continue
        issue = {"code": "required_runtime_tool_missing", "tool": tool_name}
        if tool_name in required_tools:
            errors.append(issue)
        else:
            warnings.append({"code": "recommended_runtime_tool_missing", "tool": tool_name})

    if require_strict:
        if not strict:
            errors.append({"code": "competition_launcher_requires_strict_startup"})
        if profile != "competition_strict":
            errors.append(
                {
                    "code": "competition_launcher_requires_competition_profile",
                    "configured_profile": profile,
                }
            )

    if strict:
        if bool(runtime.get("use_fixture_model")):
            errors.append({"code": "fixture_model_enabled"})
        if bool(runtime.get("allow_fixture_on_missing_checkpoint")):
            errors.append({"code": "fixture_missing_checkpoint_fallback_enabled"})
        if str(runtime.get("model_selection_policy") or "") != "explicit":
            errors.append({"code": "strict_profile_requires_explicit_model_selection"})
        if runtime.get("allow_heuristic_keyframe_fallback") is not False:
            errors.append({"code": "strict_profile_requires_heuristic_keyframe_fallback_disabled"})
        if runtime.get("allow_prompt_fallback") is not False:
            errors.append({"code": "strict_profile_requires_prompt_fallback_disabled"})
        if not required_ids:
            errors.append({"code": "strict_profile_missing_required_model_ids"})
        if not segmentation_model_id:
            errors.append({"code": "strict_profile_missing_segmentation_task_model_id"})
        else:
            if segmentation_model_id not in required_ids:
                errors.append(
                    {
                        "code": "segmentation_task_model_not_required",
                        "model_id": segmentation_model_id,
                        "required_model_ids": sorted(required_ids),
                    }
                )
            selected_model = model_by_id.get(segmentation_model_id)
            if selected_model is None:
                errors.append(
                    {
                        "code": "segmentation_task_model_missing_from_config",
                        "model_id": segmentation_model_id,
                    }
                )
            elif not bool(selected_model.get("enabled", True)):
                errors.append(
                    {
                        "code": "segmentation_task_model_disabled",
                        "model_id": segmentation_model_id,
                    }
                )
    elif bool(runtime.get("use_fixture_model")):
        warnings.append({"code": "development_fixture_model_enabled"})

    for model in models:
        model_id = str(model.get("model_id") or "")
        family = str(model.get("family") or "")
        enabled = bool(model.get("enabled", True))
        extra = dict(model.get("extra") or {})
        if enabled and family == "fixture":
            issue = {"code": "enabled_fixture_adapter", "model_id": model_id}
            (errors if strict else warnings).append(issue)
        if not enabled and model_id in required_ids:
            errors.append({"code": "required_model_disabled", "model_id": model_id})
        if model_id not in required_ids:
            continue
        if strict and extra.get("runtime_allowed") is not True:
            errors.append({"code": "required_model_runtime_not_explicitly_allowed", "model_id": model_id})
        checkpoint_value = str(model.get("checkpoint_path") or "").strip()
        if not checkpoint_value:
            errors.append({"code": "required_model_checkpoint_unspecified", "model_id": model_id})
            continue
        checkpoint = _resolve_from_config(path, checkpoint_value)
        if not checkpoint.is_file():
            errors.append({"code": "required_model_checkpoint_missing", "model_id": model_id, "path": str(checkpoint)})
            continue
        sidecar_value = str(extra.get("runtime_sidecar_path") or "").strip()
        sidecar = (
            _resolve_from_config(path, sidecar_value)
            if sidecar_value
            else checkpoint.with_name(f"{checkpoint.stem}_manifest.json")
        )
        if not sidecar.is_file():
            errors.append({"code": "runtime_sidecar_missing", "model_id": model_id, "path": str(sidecar)})
            continue
        try:
            sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(
                {
                    "code": "runtime_sidecar_invalid",
                    "model_id": model_id,
                    "path": str(sidecar),
                    "detail": str(exc),
                }
            )
            continue
        if not isinstance(sidecar_payload, dict):
            errors.append(
                {
                    "code": "runtime_sidecar_root_must_be_mapping",
                    "model_id": model_id,
                    "path": str(sidecar),
                }
            )
            continue
        expected_sha = str(sidecar_payload.get("checkpoint_sha256") or "")
        actual_sha = _sha256_file(checkpoint)
        verified_models.append(
            {
                "model_id": model_id,
                "family": family,
                "checkpoint_path": str(checkpoint),
                "checkpoint_sha256": actual_sha,
                "sidecar_path": str(sidecar),
                "runtime_allowed": sidecar_payload.get("runtime_allowed") is True,
            }
        )
        if not expected_sha or expected_sha != actual_sha:
            errors.append(
                {
                    "code": "checkpoint_sha256_mismatch",
                    "model_id": model_id,
                    "expected": expected_sha,
                    "actual": actual_sha,
                }
            )
        if strict and sidecar_payload.get("runtime_allowed") is not True:
            errors.append({"code": "sidecar_runtime_not_allowed", "model_id": model_id})
        sidecar_family = str(sidecar_payload.get("model_family") or "")
        if sidecar_family and sidecar_family != family:
            errors.append(
                {
                    "code": "sidecar_family_mismatch",
                    "model_id": model_id,
                    "configured": family,
                    "sidecar": sidecar_family,
                }
            )
        checkpoint_model_id = str(extra.get("checkpoint_model_id") or model_id)
        sidecar_model_id = str(sidecar_payload.get("model_id") or "")
        if sidecar_model_id and sidecar_model_id != checkpoint_model_id:
            errors.append(
                {
                    "code": "sidecar_model_id_mismatch",
                    "model_id": model_id,
                    "configured_checkpoint_model_id": checkpoint_model_id,
                    "sidecar": sidecar_model_id,
                }
            )
        configured_threshold = extra.get("threshold")
        sidecar_threshold = sidecar_payload.get("threshold")
        if sidecar_threshold is None:
            sidecar_threshold = dict(sidecar_payload.get("metrics") or {}).get("threshold")
        if configured_threshold is not None and sidecar_threshold is not None:
            if abs(float(configured_threshold) - float(sidecar_threshold)) > 1e-9:
                errors.append(
                    {
                        "code": "runtime_threshold_mismatch",
                        "model_id": model_id,
                        "configured": float(configured_threshold),
                        "sidecar": float(sidecar_threshold),
                    }
                )

    for required_id in sorted(required_ids - set(model_by_id)):
        errors.append({"code": "required_model_missing_from_config", "model_id": required_id})
    return _report(
        path,
        profile,
        strict,
        errors,
        warnings,
        required_model_ids=sorted(required_ids),
        verified_models=verified_models,
        runtime_tools=tool_status,
    )


def _report(
    path: Path,
    profile: str,
    strict: bool,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    *,
    required_model_ids: list[str] | None = None,
    verified_models: list[dict[str, Any]] | None = None,
    runtime_tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "passed": not errors,
        "runtime_profile": profile,
        "strict_startup": strict,
        "config_path": str(path),
        "config_sha256": _sha256_file(path) if path.is_file() else None,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "required_model_ids": required_model_ids or [],
        "verified_models": verified_models or [],
        "runtime_tools": runtime_tools or [],
    }


def _resolve_from_config(config_path: Path, value: str) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        return requested.resolve()
    project_root = config_path.parents[2] if len(config_path.parents) >= 3 else Path.cwd()
    return (project_root / requested).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
