from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from src.models.runtime_preflight import check_runtime_readiness


def _strict_config(checkpoint: Path, sidecar: Path) -> dict:
    return {
        "runtime": {
            "runtime_profile": "competition_strict",
            "strict_startup": True,
            "use_fixture_model": False,
            "allow_fixture_on_missing_checkpoint": False,
            "allow_heuristic_keyframe_fallback": False,
            "allow_prompt_fallback": False,
            "model_selection_policy": "explicit",
            "required_model_ids": ["required_segmenter"],
            "tasks": {
                "segmentation": {
                    "pipeline": "segmentation",
                    "model_id": "required_segmenter",
                }
            },
            "models": [
                {
                    "model_id": "required_segmenter",
                    "family": "convnext2d_keyframe_segmenter",
                    "checkpoint_path": str(checkpoint),
                    "enabled": True,
                    "extra": {
                        "runtime_allowed": True,
                        "runtime_sidecar_path": str(sidecar),
                        "checkpoint_model_id": "checkpoint_segmenter",
                        "threshold": 0.5,
                    },
                }
            ],
        }
    }


def test_strict_runtime_preflight_accepts_matching_promoted_sidecar(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": True,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(_strict_config(checkpoint, sidecar)), encoding="utf-8")

    report = check_runtime_readiness(config)

    assert report["passed"] is True
    assert report["runtime_profile"] == "competition_strict"
    assert report["error_count"] == 0
    assert report["required_model_ids"] == ["required_segmenter"]
    assert report["verified_models"] == [
        {
            "model_id": "required_segmenter",
            "family": "convnext2d_keyframe_segmenter",
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "sidecar_path": str(sidecar),
            "runtime_allowed": True,
        }
    ]


def test_strict_runtime_preflight_rejects_sidecar_without_runtime_promotion(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": False,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(_strict_config(checkpoint, sidecar)), encoding="utf-8")

    report = check_runtime_readiness(config)

    assert report["passed"] is False
    assert {error["code"] for error in report["errors"]} == {"sidecar_runtime_not_allowed"}


def test_strict_runtime_preflight_requires_segmentation_task_model_id(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": True,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    payload = _strict_config(checkpoint, sidecar)
    payload["runtime"]["tasks"] = {}
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = check_runtime_readiness(config)

    assert report["passed"] is False
    assert "strict_profile_missing_segmentation_task_model_id" in {error["code"] for error in report["errors"]}


def test_strict_runtime_preflight_requires_heuristic_fallback_disabled(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": True,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    payload = _strict_config(checkpoint, sidecar)
    payload["runtime"].pop("allow_heuristic_keyframe_fallback")
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = check_runtime_readiness(config)

    assert report["passed"] is False
    assert "strict_profile_requires_heuristic_keyframe_fallback_disabled" in {
        error["code"] for error in report["errors"]
    }


def test_strict_runtime_preflight_requires_prompt_fallback_disabled(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": True,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    payload = _strict_config(checkpoint, sidecar)
    payload["runtime"].pop("allow_prompt_fallback")
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = check_runtime_readiness(config)

    assert report["passed"] is False
    assert "strict_profile_requires_prompt_fallback_disabled" in {error["code"] for error in report["errors"]}


def test_strict_runtime_preflight_rejects_segmentation_task_model_mismatch(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": True,
                "metrics": {"threshold": 0.5},
            }
        ),
        encoding="utf-8",
    )
    payload = _strict_config(checkpoint, sidecar)
    payload["runtime"]["tasks"]["segmentation"]["model_id"] = "unconfigured_segmenter"
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = check_runtime_readiness(config)
    codes = {error["code"] for error in report["errors"]}

    assert report["passed"] is False
    assert "segmentation_task_model_not_required" in codes
    assert "segmentation_task_model_missing_from_config" in codes


def test_development_profile_reports_fixture_as_warning(tmp_path: Path) -> None:
    config = tmp_path / "configs/inference/dev.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "development",
                    "use_fixture_model": True,
                    "models": [
                        {
                            "model_id": "fixture_default",
                            "family": "fixture",
                            "enabled": True,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    report = check_runtime_readiness(config)

    assert report["passed"] is True
    assert report["warning_count"] == 2


def test_competition_launcher_rejects_development_profile(tmp_path: Path) -> None:
    config = tmp_path / "configs/inference/dev.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "development",
                    "strict_startup": False,
                    "use_fixture_model": False,
                    "models": [],
                }
            }
        ),
        encoding="utf-8",
    )

    report = check_runtime_readiness(config, require_strict=True)
    codes = {error["code"] for error in report["errors"]}

    assert report["passed"] is False
    assert "competition_launcher_requires_strict_startup" in codes
    assert "competition_launcher_requires_competition_profile" in codes


def test_runtime_preflight_reports_invalid_sidecar(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text("{invalid json", encoding="utf-8")
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(_strict_config(checkpoint, sidecar)), encoding="utf-8")

    report = check_runtime_readiness(config, require_strict=True)

    assert report["passed"] is False
    assert {error["code"] for error in report["errors"]} == {"runtime_sidecar_invalid"}


def test_runtime_preflight_checks_configured_external_tools(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "configs/inference/dev.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "development",
                    "required_tools": ["required_codec"],
                    "recommended_tools": ["optional_probe"],
                    "models": [],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.models.runtime_preflight.find_runtime_executable",
        lambda name: "/tools/required_codec" if name == "required_codec" else None,
    )

    report = check_runtime_readiness(config)

    assert report["passed"] is True
    assert {warning["code"] for warning in report["warnings"]} == {"recommended_runtime_tool_missing"}
    assert report["runtime_tools"] == [
        {"tool": "optional_probe", "available": False, "path": None, "required": False},
        {
            "tool": "required_codec",
            "available": True,
            "path": "/tools/required_codec",
            "required": True,
        },
    ]


def test_runtime_preflight_fails_when_required_external_tool_is_missing(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "development",
                    "required_tools": ["required_missing_codec"],
                    "models": [],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.models.runtime_preflight.find_runtime_executable", lambda _name: None)

    report = check_runtime_readiness(config)

    assert report["passed"] is False
    assert report["errors"] == [{"code": "required_runtime_tool_missing", "tool": "required_missing_codec"}]


def test_strict_runtime_preflight_rejects_fixture_and_threshold_mismatch(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    sidecar = tmp_path / "model_manifest.json"
    sidecar.write_text(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "model_id": "checkpoint_segmenter",
                "model_family": "convnext2d_keyframe_segmenter",
                "runtime_allowed": True,
                "metrics": {"threshold": 0.45},
            }
        ),
        encoding="utf-8",
    )
    payload = _strict_config(checkpoint, sidecar)
    payload["runtime"]["use_fixture_model"] = True
    config = tmp_path / "configs/inference/strict.yml"
    config.parent.mkdir(parents=True)
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")

    report = check_runtime_readiness(config)
    codes = {error["code"] for error in report["errors"]}

    assert "fixture_model_enabled" in codes
    assert "runtime_threshold_mismatch" in codes
