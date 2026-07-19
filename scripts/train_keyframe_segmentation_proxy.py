from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections.abc import Iterator, Sequence, Sized
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, Sampler

from src.core.paths import ensure_dir, resolve_path
from src.datasets.domain_adaptation import (
    augment_microscope_image,
    augmentation_report,
    load_domain_adaptation_config,
    sampled_indices,
    sampling_report,
)
from src.datasets.group_splits import assert_no_group_leakage
from src.datasets.training_admission import admit_keyframe_training_rows
from src.metrics.calibration import fit_binary_temperature
from src.models.keyframe_segmenter import (
    build_keyframe_segmenter,
    checkpoint_sha256,
    select_torch_device,
)
from src.reports.writers import write_json

DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/keyframe_convnext2d_proxy.pt"
DEFAULT_REPORT_DIR = "research/reports/modeling"
DEFAULT_SEED = 20260704


class SyntheticFluorescenceKeyframeDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]):
    def __init__(self, *, size: int, image_shape: tuple[int, int], seed: int) -> None:
        self.size = size
        self.image_shape = image_shape
        self.seed = seed

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        image, mask = synthetic_keyframe(index, image_shape=self.image_shape, seed=self.seed)
        return (
            torch.from_numpy(image.transpose(2, 0, 1).astype(np.float32) / 255.0),
            torch.from_numpy(mask),
            torch.tensor(1.0, dtype=torch.float32),
        )


class ManifestKeyframeDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        rows: list[dict[str, str]],
        *,
        image_shape: tuple[int, int],
        domain_config: dict[str, Any] | None = None,
        seed: int = DEFAULT_SEED,
    ) -> None:
        self.rows = rows
        self.image_shape = image_shape
        self.domain_config = domain_config or {"enabled": False}
        self.seed = seed
        self.access_counts: dict[int, int] = {}

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        row = self.rows[index]
        image_path = resolve_path(row["image_path"])
        mask_path = resolve_path(row["mask_path"])
        sample_weight = _positive_float(row.get("sample_weight"), default=1.0)
        height, width = self.image_shape
        with Image.open(image_path) as image_obj:
            image = np.asarray(image_obj.convert("RGB").resize((width, height)), dtype=np.uint8)
        with Image.open(mask_path) as mask_obj:
            mask = np.asarray(mask_obj.convert("L").resize((width, height), Image.Resampling.NEAREST), dtype=np.uint8)
        access = self.access_counts.get(index, 0)
        self.access_counts[index] = access + 1
        image = augment_microscope_image(
            image,
            config=self.domain_config,
            rng=np.random.default_rng(self.seed + index * 1009 + access * 9176),
        )
        target = (mask > 0).astype(np.int64)
        return (
            torch.from_numpy(image.transpose(2, 0, 1).astype(np.float32) / 255.0),
            torch.from_numpy(target),
            torch.tensor(sample_weight, dtype=torch.float32),
        )


def synthetic_keyframe(index: int, *, image_shape: tuple[int, int], seed: int) -> tuple[np.ndarray, np.ndarray]:
    height, width = image_shape
    rng = np.random.default_rng(seed + index * 1009)
    base = rng.normal(loc=22.0, scale=7.0, size=(height, width, 3)).clip(0, 80).astype(np.float32)
    yy, xx = np.mgrid[:height, :width]
    mask = np.zeros((height, width), dtype=np.int64)
    component_count = int(rng.integers(1, 4))
    for _ in range(component_count):
        center_y = float(rng.uniform(0.2, 0.8) * height)
        center_x = float(rng.uniform(0.2, 0.8) * width)
        radius_y = float(rng.uniform(0.06, 0.18) * height)
        radius_x = float(rng.uniform(0.06, 0.18) * width)
        ellipse = ((yy - center_y) / radius_y) ** 2 + ((xx - center_x) / radius_x) ** 2 <= 1.0
        mask[ellipse] = 1
    base[..., 1] += mask.astype(np.float32) * float(rng.uniform(145.0, 220.0))
    base[..., 0] += mask.astype(np.float32) * float(rng.uniform(5.0, 25.0))
    distractor_count = int(rng.integers(0, 3))
    for _ in range(distractor_count):
        y0 = int(rng.integers(0, max(1, height - 8)))
        x0 = int(rng.integers(0, max(1, width - 8)))
        y1 = min(height, y0 + int(rng.integers(3, 10)))
        x1 = min(width, x0 + int(rng.integers(3, 10)))
        base[y0:y1, x0:x1, :] += rng.uniform(35.0, 70.0)
    image = np.clip(base, 0, 255).astype(np.uint8)
    return image, mask


def train_keyframe_proxy(args: argparse.Namespace) -> dict[str, Any]:
    _set_seed(args.seed)
    device = select_torch_device(args.device)
    image_shape = _parse_shape(args.image_shape)
    train_dataset, val_dataset, data_summary = build_datasets(args, image_shape=image_shape)
    data_summary["image_shape"] = [int(image_shape[0]), int(image_shape[1])]
    initialization = load_training_initialization(args, device=device)
    model_config = model_config_for_initialization(args, initialization)
    model = build_keyframe_segmenter(model_config).to(device)
    if initialization is not None:
        model.load_state_dict(initialization["state_dict"])
    freeze_summary = configure_encoder_freeze(
        model,
        enabled=bool(getattr(args, "freeze_encoder", False)),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    optimizer_restore_requested = bool(getattr(args, "restore_optimizer", False))
    optimizer_restored = False
    if optimizer_restore_requested:
        if initialization is None:
            raise ValueError("--restore-optimizer requires --resume-checkpoint")
        if initialization["mode"] != "resume":
            raise ValueError("--restore-optimizer is only valid with --resume-checkpoint")
        optimizer_state = initialization.get("optimizer_state_dict")
        if not isinstance(optimizer_state, dict):
            raise ValueError(f"Resume checkpoint has no optimizer_state_dict: {initialization['checkpoint_path']}")
        optimizer.load_state_dict(optimizer_state)
        for parameter_group in optimizer.param_groups:
            parameter_group["lr"] = float(args.learning_rate)
        optimizer_restored = True
    previous_completed_batches = (
        int(initialization.get("previous_completed_train_batches") or 0)
        if initialization is not None and initialization["mode"] == "resume"
        else 0
    )
    fine_tuning = {
        "mode": initialization["mode"] if initialization is not None else "fresh",
        "source_checkpoint": initialization["checkpoint_path"] if initialization is not None else None,
        "source_checkpoint_sha256": (initialization["checkpoint_sha256"] if initialization is not None else None),
        "source_model_id": initialization.get("model_id") if initialization is not None else None,
        "source_optimizer_state": (initialization.get("optimizer_state_path") if initialization is not None else None),
        "source_optimizer_state_sha256": (
            initialization.get("optimizer_state_sha256") if initialization is not None else None
        ),
        "model_weights_loaded": initialization is not None,
        "optimizer_restore_requested": optimizer_restore_requested,
        "optimizer_restored": optimizer_restored,
        **freeze_summary,
    }
    sample_plan = data_summary.pop("_sample_plan", None)
    loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=sample_plan is None,
        sampler=FixedIndexSampler(sample_plan) if sample_plan is not None else None,
        num_workers=0,
        generator=torch.Generator().manual_seed(args.seed),
    )
    started = time.perf_counter()
    completed_batches = 0
    losses: list[float] = []
    model.train()
    while completed_batches < args.max_train_batches:
        for image, target, sample_weight in loader:
            image = image.to(device=device, dtype=torch.float32)
            target = target.to(device=device, dtype=torch.long)
            sample_weight = sample_weight.to(device=device, dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            logits = model(image)
            loss = weighted_segmentation_loss(logits, target, sample_weight)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            completed_batches += 1
            if completed_batches >= args.max_train_batches:
                break
    calibration = fit_model_temperature(model, val_dataset, device=device)
    metrics = evaluate_model(
        model,
        val_dataset,
        device=device,
        threshold=args.threshold,
        temperature=float(calibration["temperature"]),
    )
    elapsed = round(time.perf_counter() - started, 3)
    checkpoint_path = resolve_path(args.output_checkpoint)
    ensure_dir(checkpoint_path.parent)
    optimizer_state_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_optimizer.pt")
    torch.save(
        {
            "model_id": args.model_id,
            "optimizer_state_dict": optimizer.state_dict(),
            "generated_at_utc": datetime.now(UTC).isoformat(),
        },
        optimizer_state_path,
    )
    optimizer_state_sha256 = checkpoint_sha256(optimizer_state_path)
    model_family = model_family_for_architecture(str(model_config["architecture"]))
    parameter_summary = model_parameter_summary(model)
    checkpoint_payload = {
        "model_id": args.model_id,
        "model_family": model_family,
        "model_config": model_config,
        "parameter_summary": parameter_summary,
        "threshold": float(args.threshold),
        "calibration": calibration,
        "state_dict": model.state_dict(),
        "optimizer_state": {
            "path": str(optimizer_state_path),
            "sha256": optimizer_state_sha256,
        },
        "training": {
            **data_summary,
            "completed_train_batches": completed_batches,
            "previous_completed_train_batches": previous_completed_batches,
            "total_completed_train_batches": previous_completed_batches + completed_batches,
            "batch_size": int(args.batch_size),
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            "requested_learning_rate": float(args.learning_rate),
            "seed": int(args.seed),
            "elapsed_seconds": elapsed,
            "mean_train_loss": float(np.mean(losses)) if losses else None,
            "fine_tuning": fine_tuning,
        },
        "metrics": metrics,
        "medical_boundary": (
            "2D keyframe segmentation proxy trained on synthetic or pseudo-labeled fluorescence-like frames; "
            "clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured."
        ),
        "clinical_claim_allowed": False,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    torch.save(checkpoint_payload, checkpoint_path)
    digest = checkpoint_sha256(checkpoint_path)
    sidecar = {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "model_id": args.model_id,
        "model_family": model_family,
        "model_config": model_config,
        "parameter_summary": parameter_summary,
        "runtime_allowed": bool(getattr(args, "runtime_allowed", False)),
        "clinical_claim_allowed": False,
        "optimizer_state_path": str(optimizer_state_path),
        "optimizer_state_sha256": optimizer_state_sha256,
        "training": checkpoint_payload["training"],
        "fine_tuning": fine_tuning,
        "metrics": metrics,
        "warnings": [
            "This checkpoint is a trainable platform-software model on proxy keyframe data.",
            "Target-domain intraoperative ICG jaw osteomyelitis performance remains unmeasured.",
        ],
    }
    manifest_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_manifest.json")
    model_card_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_model_card.json")
    write_json(manifest_path, sidecar)
    write_json(
        model_card_path,
        {
            "model_id": args.model_id,
            "model_family": model_family,
            "model_config": model_config,
            "parameter_summary": parameter_summary,
            "intended_use": "Trainable 2D JPEG/MP4 keyframe signal segmentation for engineering validation.",
            "training_data": data_summary,
            "fine_tuning": fine_tuning,
            "metrics": metrics,
            "limitations": sidecar["warnings"],
            "clinical_claim_allowed": False,
        },
    )
    report_paths = write_reports(
        {
            "checkpoint_path": str(checkpoint_path),
            "manifest_path": str(manifest_path),
            "model_card_path": str(model_card_path),
            "checkpoint_sha256": digest,
            "model_id": args.model_id,
            "model_family": model_family,
            "model_config": model_config,
            "parameter_summary": parameter_summary,
            "training": checkpoint_payload["training"],
            "metrics": metrics,
            "environment": {
                "device": str(device),
                "torch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
            },
            "medical_boundary": checkpoint_payload["medical_boundary"],
        },
        report_dir=args.report_dir,
        report_stamp=str(args.report_stamp),
    )
    return {
        "checkpoint_path": str(checkpoint_path),
        "optimizer_state_path": str(optimizer_state_path),
        "manifest_path": str(manifest_path),
        "model_card_path": str(model_card_path),
        "report_paths": report_paths,
        "metrics": metrics,
    }


def load_training_initialization(
    args: argparse.Namespace,
    *,
    device: torch.device,
) -> dict[str, Any] | None:
    resume_checkpoint = str(getattr(args, "resume_checkpoint", "") or "").strip()
    pretrained_checkpoint = str(getattr(args, "pretrained_checkpoint", "") or "").strip()
    if resume_checkpoint and pretrained_checkpoint:
        raise ValueError("Use only one of --resume-checkpoint and --pretrained-checkpoint")
    selected = resume_checkpoint or pretrained_checkpoint
    if not selected:
        return None
    checkpoint_path = resolve_path(selected)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Missing training checkpoint: {checkpoint_path}")
    try:
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location=device)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unsupported training checkpoint payload: {checkpoint_path}")
    state_dict = checkpoint.get("state_dict")
    if not isinstance(state_dict, dict):
        raise ValueError(f"Training checkpoint missing state_dict: {checkpoint_path}")
    model_family = str(checkpoint.get("model_family") or "")
    if model_family and model_family != "convnext2d_keyframe_segmenter":
        raise ValueError(f"Incompatible training checkpoint model_family={model_family!r}: {checkpoint_path}")
    model_config = dict(checkpoint.get("model_config") or {})
    training_payload = checkpoint.get("training")
    training: dict[str, Any] = training_payload if isinstance(training_payload, dict) else {}
    optimizer_record = checkpoint.get("optimizer_state")
    optimizer_state_path: str | None = None
    optimizer_state_sha256: str | None = None
    optimizer_state_dict = checkpoint.get("optimizer_state_dict")
    if isinstance(optimizer_record, dict):
        optimizer_state_path = str(optimizer_record.get("path") or "").strip() or None
        optimizer_state_sha256 = str(optimizer_record.get("sha256") or "").strip() or None
    if bool(getattr(args, "restore_optimizer", False)) and not isinstance(optimizer_state_dict, dict):
        optimizer_state_path, optimizer_state_sha256, optimizer_state_dict = load_optimizer_state_artifact(
            checkpoint_path,
            optimizer_state_path=optimizer_state_path,
            expected_sha256=optimizer_state_sha256,
            device=device,
        )
    return {
        "mode": "resume" if resume_checkpoint else "pretrained",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256(checkpoint_path),
        "model_id": checkpoint.get("model_id"),
        "model_config": model_config,
        "state_dict": state_dict,
        "optimizer_state_path": optimizer_state_path,
        "optimizer_state_sha256": optimizer_state_sha256,
        "optimizer_state_dict": optimizer_state_dict,
        "previous_completed_train_batches": int(
            training.get("total_completed_train_batches") or training.get("completed_train_batches") or 0
        ),
    }


def load_optimizer_state_artifact(
    checkpoint_path: Path,
    *,
    optimizer_state_path: str | None,
    expected_sha256: str | None,
    device: torch.device,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    if not optimizer_state_path:
        return None, expected_sha256, None
    candidate = Path(optimizer_state_path)
    if not candidate.is_absolute():
        candidate = resolve_path(candidate)
    if not candidate.exists():
        candidate = checkpoint_path.with_name(Path(optimizer_state_path).name)
    if not candidate.exists():
        return str(candidate), expected_sha256, None
    actual_sha256 = checkpoint_sha256(candidate)
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise ValueError(f"Optimizer state SHA256 mismatch: {candidate}")
    try:
        payload = torch.load(candidate, map_location=device, weights_only=False)
    except TypeError:
        payload = torch.load(candidate, map_location=device)
    if not isinstance(payload, dict) or not isinstance(payload.get("optimizer_state_dict"), dict):
        raise ValueError(f"Unsupported optimizer state payload: {candidate}")
    return str(candidate), actual_sha256, payload["optimizer_state_dict"]


def model_config_for_initialization(
    args: argparse.Namespace,
    initialization: dict[str, Any] | None,
) -> dict[str, Any]:
    if initialization is None:
        return {
            "architecture": str(getattr(args, "architecture", "convnext_unet")),
            "in_channels": 3,
            "out_channels": 2,
            "base_channels": int(args.base_channels),
        }
    source = initialization.get("model_config")
    if not isinstance(source, dict):
        source = {}
    return {
        "architecture": str(source.get("architecture") or "convnext_unet"),
        "in_channels": int(source.get("in_channels", 3)),
        "out_channels": int(source.get("out_channels", 2)),
        "base_channels": int(source.get("base_channels", args.base_channels)),
    }


def model_family_for_architecture(architecture: str) -> str:
    families = {
        "convnext_unet": "convnext2d_keyframe_segmenter",
        "residual_attention_unet": "residual_attention_unet_keyframe_segmenter",
        "multiscale_depthwise_unet": "multiscale_depthwise_unet_keyframe_segmenter",
    }
    try:
        return families[architecture]
    except KeyError as exc:
        raise ValueError(f"Unsupported keyframe architecture: {architecture}") from exc


def model_parameter_summary(model: nn.Module) -> dict[str, Any]:
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    trainable_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    parameter_bytes = sum(parameter.numel() * parameter.element_size() for parameter in model.parameters())
    return {
        "parameter_count": int(parameter_count),
        "trainable_parameter_count": int(trainable_count),
        "parameter_memory_mb_fp32": round(float(parameter_bytes / (1024**2)), 6),
    }


def configure_encoder_freeze(model: nn.Module, *, enabled: bool) -> dict[str, Any]:
    encoder_prefixes = ("enc0.", "down1.", "enc1.", "down2.", "enc2.", "down3.", "bottleneck.")
    frozen_names: list[str] = []
    if enabled:
        for name, parameter in model.named_parameters():
            if name.startswith(encoder_prefixes):
                parameter.requires_grad_(False)
                frozen_names.append(name)
        if not frozen_names:
            raise ValueError("Encoder freeze requested, but no supported encoder parameters were found")
    frozen_parameter_count = sum(parameter.numel() for parameter in model.parameters() if not parameter.requires_grad)
    trainable_parameter_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return {
        "encoder_frozen": bool(enabled),
        "encoder_prefixes": list(encoder_prefixes) if enabled else [],
        "frozen_parameter_tensor_count": len(frozen_names),
        "frozen_parameter_count": int(frozen_parameter_count),
        "trainable_parameter_count": int(trainable_parameter_count),
    }


def build_datasets(
    args: argparse.Namespace,
    *,
    image_shape: tuple[int, int],
) -> tuple[
    Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    dict[str, Any],
]:
    manifest_paths = _manifest_paths(getattr(args, "manifest", []))
    registry_path = str(getattr(args, "registry", "") or "").strip()
    quality_report_path = str(getattr(args, "quality_report", "") or "").strip()
    if registry_path and manifest_paths:
        raise ValueError("Use either --registry or --manifest for one training run")
    if registry_path:
        if not quality_report_path:
            raise ValueError("--quality-report is required when --registry is used")
        admission = admit_keyframe_training_rows(
            registry_path,
            quality_report_path,
            admission_stage=str(getattr(args, "admission_stage", "proxy_pretrain")),
        )
        rows = admission.rows
        manifest_summaries: list[dict[str, Any]] = []
        source_summary: dict[str, Any] = {
            "source": "layered_registry_admission",
            "manifest_path": admission.summary["registry_path"],
            "manifest_paths": [],
            "registry_path": admission.summary["registry_path"],
            "registry_sha256": admission.summary["registry_sha256"],
            "quality_report_path": admission.summary["quality_report_path"],
            "quality_report_sha256": admission.summary["quality_report_sha256"],
            "training_admission": admission.summary,
            "quality_gates": {
                "registry_quality_gate_passed": admission.summary["quality_gate_passed"],
                "admitted_count": admission.summary["admitted_count"],
                "isolated_count": admission.summary["isolated_count"],
                "isolation_reason_counts": admission.summary["isolation_reason_counts"],
            },
            "data_boundary": admission.summary["data_boundary"],
        }
    elif manifest_paths:
        rows = []
        manifest_summaries = []
        for manifest in manifest_paths:
            rows.extend(load_manifest_rows(manifest))
            manifest_summaries.append(load_proxy_manifest_summary(manifest))
        source_summary = {
            "source": "manifest",
            "manifest_path": str(resolve_path(manifest_paths[0])),
            "manifest_paths": [str(resolve_path(item)) for item in manifest_paths],
            "manifest_summary_paths": [
                summary.get("summary_path") for summary in manifest_summaries if summary.get("summary_path")
            ],
            "review_seed_csv_path": _first_summary_value(manifest_summaries, "review_seed_csv_path"),
            "review_seed_count": _sum_summary_int(manifest_summaries, "review_seed_count"),
            "quality_gates": _first_summary_value(manifest_summaries, "quality_gates"),
            "data_boundary": "manifest rows may be pseudo-labeled or non-target-domain unless separately verified.",
        }
    else:
        return (
            SyntheticFluorescenceKeyframeDataset(
                size=args.synthetic_train_size, image_shape=image_shape, seed=args.seed
            ),
            SyntheticFluorescenceKeyframeDataset(
                size=args.synthetic_val_size,
                image_shape=image_shape,
                seed=args.seed + 50000,
            ),
            {
                "source": "synthetic_fluorescence_proxy",
                "train_samples": int(args.synthetic_train_size),
                "val_samples": int(args.synthetic_val_size),
                "image_shape": [int(image_shape[0]), int(image_shape[1])],
                "data_boundary": "synthetic proxy data; target-domain clinical validity remains unmeasured.",
            },
        )

    if rows:
        leakage_report = assert_no_group_leakage(rows, context="keyframe training manifests")
        train_rows = [row for row in rows if row.get("split", "train") == "train"]
        val_rows = [row for row in rows if row.get("split") == "val"]
        if not val_rows:
            raise ValueError(f"No validation rows in grouped keyframe manifest(s): {manifest_paths}")
        if not train_rows:
            raise ValueError(f"No training rows in keyframe manifest(s): {manifest_paths}")
        domain_config = load_domain_adaptation_config(getattr(args, "domain_adaptation_config", None))
        if bool(getattr(args, "domain_aware", False)):
            domain_config["enabled"] = True
        sample_plan = (
            sampled_indices(
                train_rows,
                config=domain_config,
                sample_count=max(1, int(getattr(args, "max_train_batches", 1)) * int(getattr(args, "batch_size", 1))),
                seed=int(getattr(args, "seed", DEFAULT_SEED)),
            )
            if domain_config.get("enabled")
            else None
        )
        return (
            ManifestKeyframeDataset(
                train_rows,
                image_shape=image_shape,
                domain_config=domain_config,
                seed=int(getattr(args, "seed", DEFAULT_SEED)),
            ),
            ManifestKeyframeDataset(val_rows, image_shape=image_shape),
            {
                **source_summary,
                "train_samples": len(train_rows),
                "val_samples": len(val_rows),
                "positive_area_fraction_stats": _numeric_stats_from_rows(rows, "positive_area_fraction"),
                "sample_weight_stats": _numeric_stats_from_rows(rows, "sample_weight"),
                "sampling_weight_stats": _numeric_stats_from_rows(rows, "sampling_weight"),
                "review_state_counts": _value_counts(rows, "review_state"),
                "domain_tier_counts": _value_counts(rows, "domain_tier"),
                "source_group_counts": _value_counts(rows, "source_group_id"),
                "domain_adaptation": augmentation_report(domain_config),
                "domain_sampling": sampling_report(train_rows, sample_plan or []),
                "_sample_plan": sample_plan,
                "label_source_counts": _value_counts(rows, "label_source"),
                "source_group_split": leakage_report,
            },
        )
    raise ValueError("No training rows were loaded")


def load_manifest_rows(manifest_path: str | Path) -> list[dict[str, str]]:
    path = resolve_path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("image_path") and row.get("mask_path"):
                rows.append({key: str(value) for key, value in row.items()})
    return rows


class FixedIndexSampler(Sampler[int]):
    def __init__(self, indices: Sequence[int]) -> None:
        self.indices = list(indices)

    def __iter__(self) -> Iterator[int]:
        return iter(self.indices)

    def __len__(self) -> int:
        return len(self.indices)


def load_proxy_manifest_summary(manifest_path: str | Path) -> dict[str, Any]:
    path = resolve_path(manifest_path)
    summary_path = path.with_name("keyframe_segmentation_proxy_summary.json")
    if not summary_path.exists():
        return {}
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(summary, dict):
        return {}
    return {"summary_path": str(summary_path), **summary}


def weighted_segmentation_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    sample_weight: torch.Tensor,
) -> torch.Tensor:
    cross_entropy = F.cross_entropy(logits, target, reduction="none").mean(dim=(1, 2))
    dice_loss = foreground_dice_loss_per_sample(logits, target)
    per_sample_loss = 0.5 * cross_entropy + 0.5 * dice_loss
    weights = torch.clamp(sample_weight, min=0.0)
    if float(weights.sum().detach().cpu()) <= 0.0:
        return per_sample_loss.mean()
    return torch.sum(per_sample_loss * weights) / torch.sum(weights)


def foreground_dice_loss_per_sample(
    logits: torch.Tensor,
    target: torch.Tensor,
    *,
    smooth: float = 1e-5,
) -> torch.Tensor:
    probability = torch.softmax(logits, dim=1)[:, 1]
    foreground = (target > 0).float()
    intersection = torch.sum(probability * foreground, dim=(1, 2))
    denominator = torch.sum(probability, dim=(1, 2)) + torch.sum(foreground, dim=(1, 2))
    return 1.0 - (2.0 * intersection + smooth) / (denominator + smooth)


def evaluate_model(
    model: nn.Module,
    dataset: Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    *,
    device: torch.device,
    threshold: float,
    temperature: float = 1.0,
) -> dict[str, Any]:
    model.eval()
    dice_scores: list[float] = []
    iou_scores: list[float] = []
    positive_fractions: list[float] = []
    with torch.no_grad():
        for image, target, _sample_weight in DataLoader(dataset, batch_size=1, shuffle=False, num_workers=0):
            image = image.to(device=device, dtype=torch.float32)
            target_np = target.numpy()[0] > 0
            logits = model(image)
            probability = torch.softmax(logits / max(1e-3, float(temperature)), dim=1)[0, 1].detach().cpu().numpy()
            prediction = probability >= threshold
            dice, iou = binary_dice_iou(prediction, target_np)
            dice_scores.append(dice)
            iou_scores.append(iou)
            positive_fractions.append(float(prediction.mean()))
    return {
        "case_count": len(cast(Sized, dataset)),
        "foreground_mean_dice": float(np.mean(dice_scores)) if dice_scores else None,
        "foreground_mean_iou": float(np.mean(iou_scores)) if iou_scores else None,
        "prediction_positive_fraction": float(np.mean(positive_fractions)) if positive_fractions else None,
        "threshold": float(threshold),
        "temperature": float(temperature),
    }


def fit_model_temperature(
    model: nn.Module,
    dataset: Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    *,
    device: torch.device,
) -> dict[str, Any]:
    logits_values: list[np.ndarray] = []
    target_values: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for image, target, _sample_weight in DataLoader(dataset, batch_size=1, shuffle=False, num_workers=0):
            image = image.to(device=device, dtype=torch.float32)
            logits = model(image)
            binary_logit = (logits[:, 1] - logits[:, 0]).detach().cpu().numpy().astype(np.float32)
            logits_values.append(binary_logit.reshape(-1))
            target_values.append((target.numpy() > 0).astype(np.float32).reshape(-1))
    return fit_binary_temperature(np.concatenate(logits_values), np.concatenate(target_values))


def binary_dice_iou(prediction: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    pred = np.asarray(prediction, dtype=bool)
    true = np.asarray(target, dtype=bool)
    intersection = float(np.logical_and(pred, true).sum())
    pred_area = float(pred.sum())
    true_area = float(true.sum())
    union = float(np.logical_or(pred, true).sum())
    dice = 1.0 if pred_area == 0 and true_area == 0 else 2.0 * intersection / max(1.0, pred_area + true_area)
    iou = 1.0 if union == 0 else intersection / union
    return float(dice), float(iou)


def write_reports(payload: dict[str, Any], *, report_dir: str | Path, report_stamp: str) -> dict[str, str]:
    out_dir = ensure_dir(resolve_path(report_dir))
    architecture = str((payload.get("model_config") or {}).get("architecture") or "convnext_unet")
    zh_path = out_dir / f"keyframe_{architecture}_segmenter_{report_stamp}_zh.md"
    en_path = out_dir / f"keyframe_{architecture}_segmenter_{report_stamp}_en.md"
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def render_report(payload: dict[str, Any], *, language: str) -> str:
    training = payload["training"]
    metrics = payload["metrics"]
    architecture = str((payload.get("model_config") or {}).get("architecture") or "convnext_unet")
    parameters = payload.get("parameter_summary") or {}
    if language == "zh":
        lines = [
            f"# 2D Keyframe {architecture} 分割模型报告",
            "",
            "## 定位",
            "",
            f"本报告记录一个可训练的 2D `{architecture}` keyframe 分割模型。它用于把官方 JPEG/MP4 keyframe 从启发式 hotspot baseline 推进到 PyTorch checkpoint 推理。当前训练数据为合成或伪标注代理数据，真实术中 ICG 颌骨骨髓炎性能仍待测量。",
            "",
            "## 训练设置",
            "",
            f"- Checkpoint：`{payload['checkpoint_path']}`",
            f"- 模型架构：`{architecture}`；参数量：{parameters.get('parameter_count')}。",
            f"- Manifest：`{payload['manifest_path']}`",
            f"- Model card：`{payload['model_card_path']}`",
            f"- 数据来源：{training.get('source')}",
            f"- 数据注册表 SHA256：`{training.get('registry_sha256') or 'N/A'}`",
            f"- 质量报告 SHA256：`{training.get('quality_report_sha256') or 'N/A'}`",
            f"- 训练准入统计：`{json.dumps(training.get('quality_gates') or {}, ensure_ascii=False)}`",
            f"- Manifest 数量：{len(training.get('manifest_paths') or []) or 1}；样本权重统计：`{json.dumps(training.get('sample_weight_stats') or {}, ensure_ascii=False)}`",
            f"- 复核状态分布：`{json.dumps(training.get('review_state_counts') or {}, ensure_ascii=False)}`",
            f"- 域层级分布：`{json.dumps(training.get('domain_tier_counts') or {}, ensure_ascii=False)}`",
            f"- 实际域采样：`{json.dumps(training.get('domain_sampling') or {}, ensure_ascii=False)}`",
            f"- 显微镜域增强：`{json.dumps(training.get('domain_adaptation') or {}, ensure_ascii=False)}`",
            f"- 训练样本：{training.get('train_samples')}；验证样本：{training.get('val_samples')}。",
            f"- 伪标注质量门控：`{json.dumps(training.get('quality_gates') or {}, ensure_ascii=False)}`",
            f"- 人工复核种子集：{training.get('review_seed_count')}；路径：`{training.get('review_seed_csv_path')}`",
            f"- 训练 batch：{training.get('completed_train_batches')}；batch size：{training.get('batch_size')}。",
            f"- 初始化与微调：`{json.dumps(training.get('fine_tuning') or {}, ensure_ascii=False)}`",
            f"- 平均训练 loss：{_fmt(training.get('mean_train_loss'))}",
            f"- 设备：{payload['environment']['device']}；PyTorch：{payload['environment']['torch_version']}。",
            "",
            "## 指标",
            "",
            f"- Foreground Dice：{_fmt(metrics.get('foreground_mean_dice'))}",
            f"- Foreground IoU：{_fmt(metrics.get('foreground_mean_iou'))}",
            f"- Prediction positive fraction：{_fmt(metrics.get('prediction_positive_fraction'))}",
            "",
            "## 医学边界",
            "",
            payload["medical_boundary"],
            "ICG 主要反映灌注、血管通透性和组织活性差异；本模型输出仅作为候选区提示和医生复核辅助，禁止用于自动诊断。",
            "",
            "## 数据缺口与下一阶段",
            "",
            "当前仍没有真实术中 ICG 颌骨骨髓炎 MP4/JPEG 像素级医生标注训练集。本轮用公开 MP4 代理数据和荧光强度伪 mask 训练可运行模型；下一阶段应把医生接受/修改后的 `review_manifest_json/csv` 样本提升为高权重训练数据，并保留 rejected 样本作为负例和错误分析。",
            "本脚本已支持多个 manifest 合并训练和 `sample_weight` 加权 loss；这些权重只表示复核可信度或错误分析优先级，不等同于真实目标域临床标注。",
        ]
    else:
        lines = [
            f"# 2D Keyframe {architecture} Segmenter Report",
            "",
            "## Scope",
            "",
            "This report records a trainable 2D keyframe segmentation model. It advances official JPEG/MP4 keyframe inference from a heuristic hotspot baseline to a PyTorch checkpoint. The current training data are synthetic or pseudo-labeled proxies; target-domain clinical performance remains unmeasured.",
            "",
            "## Training Setup",
            "",
            f"- Checkpoint: `{payload['checkpoint_path']}`",
            f"- Architecture: `{architecture}`; parameters: {parameters.get('parameter_count')}.",
            f"- Manifest: `{payload['manifest_path']}`",
            f"- Model card: `{payload['model_card_path']}`",
            f"- Data source: {training.get('source')}",
            f"- Dataset registry SHA256: `{training.get('registry_sha256') or 'N/A'}`",
            f"- Quality report SHA256: `{training.get('quality_report_sha256') or 'N/A'}`",
            f"- Training admission summary: `{json.dumps(training.get('quality_gates') or {}, ensure_ascii=False)}`",
            f"- Manifest count: {len(training.get('manifest_paths') or []) or 1}; sample-weight stats: `{json.dumps(training.get('sample_weight_stats') or {}, ensure_ascii=False)}`",
            f"- Review-state counts: `{json.dumps(training.get('review_state_counts') or {}, ensure_ascii=False)}`",
            f"- Domain-tier counts: `{json.dumps(training.get('domain_tier_counts') or {}, ensure_ascii=False)}`",
            f"- Actual domain sampling: `{json.dumps(training.get('domain_sampling') or {}, ensure_ascii=False)}`",
            f"- Microscope-domain augmentation: `{json.dumps(training.get('domain_adaptation') or {}, ensure_ascii=False)}`",
            f"- Train samples: {training.get('train_samples')}; validation samples: {training.get('val_samples')}.",
            f"- Pseudo-label quality gates: `{json.dumps(training.get('quality_gates') or {}, ensure_ascii=False)}`",
            f"- Human-review seed set: {training.get('review_seed_count')}; path: `{training.get('review_seed_csv_path')}`",
            f"- Training batches: {training.get('completed_train_batches')}; batch size: {training.get('batch_size')}.",
            f"- Initialization and fine-tuning: `{json.dumps(training.get('fine_tuning') or {}, ensure_ascii=False)}`",
            f"- Mean train loss: {_fmt(training.get('mean_train_loss'))}",
            f"- Device: {payload['environment']['device']}; PyTorch: {payload['environment']['torch_version']}.",
            "",
            "## Metrics",
            "",
            f"- Foreground Dice: {_fmt(metrics.get('foreground_mean_dice'))}",
            f"- Foreground IoU: {_fmt(metrics.get('foreground_mean_iou'))}",
            f"- Prediction positive fraction: {_fmt(metrics.get('prediction_positive_fraction'))}",
            "",
            "## Medical Boundary",
            "",
            payload["medical_boundary"],
            "ICG mainly reflects perfusion, vascular permeability, and tissue-activity differences. Model outputs are candidate-region prompts for physician review and prohibit automatic diagnosis claims.",
            "",
            "## Data Gap And Next Step",
            "",
            "There is still no real target-domain intraoperative ICG jaw osteomyelitis MP4/JPEG dataset with pixel-level physician labels. This run uses public proxy MP4 data and fluorescence-intensity pseudo masks to keep a runnable model. The next step is to promote accepted/modified `review_manifest_json/csv` samples into higher-weight training data and retain rejected samples for negative/error analysis.",
            "The script supports multiple merged manifests and `sample_weight` weighted loss. These weights encode review confidence or error-analysis priority; target-domain clinical label status requires separate verification.",
        ]
    return "\n".join(lines) + "\n"


def _parse_shape(value: str) -> tuple[int, int]:
    parts = [part for part in value.lower().replace(",", "x").split("x") if part]
    if len(parts) != 2:
        raise ValueError(f"Expected image shape like 96x128, got: {value}")
    height, width = (int(parts[0]), int(parts[1]))
    if height <= 0 or width <= 0:
        raise ValueError(f"Image shape must be positive, got: {value}")
    return height, width


def _manifest_paths(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (str, Path)):
        raw_items: Sequence[Any] = [value]
    else:
        raw_items = list(value)
    paths: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text:
            continue
        paths.extend(part.strip() for part in text.split(";") if part.strip())
    return paths


def _positive_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _numeric_stats_from_rows(rows: list[dict[str, str]], key: str) -> dict[str, Any]:
    values = []
    for row in rows:
        try:
            values.append(float(row.get(key, "")))
        except (TypeError, ValueError):
            continue
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None, "mean": None}
    array = np.asarray(values, dtype=np.float32)
    return {
        "count": int(array.size),
        "min": round(float(array.min()), 8),
        "median": round(float(np.median(array)), 8),
        "max": round(float(array.max()), 8),
        "mean": round(float(array.mean()), 8),
    }


def _value_counts(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unspecified")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _first_summary_value(summaries: list[dict[str, Any]], key: str) -> Any:
    for summary in summaries:
        value = summary.get(key)
        if value not in (None, "", []):
            return value
    return None


def _sum_summary_int(summaries: list[dict[str, Any]], key: str) -> int:
    total = 0
    for summary in summaries:
        try:
            total += int(summary.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a configurable 2D keyframe signal segmentation model.")
    parser.add_argument(
        "--manifest",
        nargs="*",
        default=[],
        help=(
            "Optional CSV manifest(s) with image_path, mask_path, split, and optional sample_weight. "
            "Multiple paths can be passed as separate values or separated by semicolons."
        ),
    )
    parser.add_argument("--registry", default="", help="Layered dataset registry CSV for enforced training admission.")
    parser.add_argument(
        "--quality-report",
        default="",
        help="Quality-gate JSON paired with --registry; required only for registry-driven training.",
    )
    parser.add_argument(
        "--admission-stage",
        choices=("proxy_pretrain", "reviewed_finetune"),
        default="proxy_pretrain",
        help="Evidence tier admitted from the layered registry.",
    )
    parser.add_argument("--output-checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument(
        "--resume-checkpoint",
        default="",
        help="Continue batch accounting from a compatible project checkpoint and load its model weights.",
    )
    parser.add_argument(
        "--pretrained-checkpoint",
        default="",
        help="Initialize model weights from a compatible project checkpoint for a new fine-tuning run.",
    )
    parser.add_argument(
        "--restore-optimizer",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Restore optimizer state from --resume-checkpoint when the source checkpoint contains it.",
    )
    parser.add_argument(
        "--freeze-encoder",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Freeze enc0/down1/enc1/down2/bottleneck while training the decoder and head.",
    )
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--report-stamp", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--model-id", default="convnext2d_keyframe_proxy_segmenter")
    parser.add_argument("--runtime-allowed", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--image-shape", default="96x128", help="Training size as HxW.")
    parser.add_argument("--synthetic-train-size", type=int, default=24)
    parser.add_argument("--synthetic-val-size", type=int, default=6)
    parser.add_argument("--max-train-batches", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument(
        "--architecture",
        default="convnext_unet",
        choices=("convnext_unet", "residual_attention_unet", "multiscale_depthwise_unet"),
    )
    parser.add_argument("--base-channels", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--domain-aware", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--domain-adaptation-config",
        default="",
        help="YAML/JSON path or inline mapping for domain-tier sampling and microscope image augmentation.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    payload = train_keyframe_proxy(parse_args())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
