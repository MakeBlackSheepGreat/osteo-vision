"""Train independent heads for video-signal masks without replacing the runtime mainline."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

from osteo_vision_core.core.paths import ensure_dir, resolve_path  # noqa: E402
from osteo_vision_core.datasets.group_splits import (  # noqa: E402
    assert_no_group_leakage,
    assign_group_split,
    normalized_source_group,
)
from osteo_vision_core.models.keyframe_segmenter import checkpoint_sha256, select_torch_device  # noqa: E402
from osteo_vision_core.models.video_signal_multimask import (  # noqa: E402
    MASK_TYPE_TO_HEAD,
    VIDEO_SIGNAL_HEADS,
    VideoSignalMultiMask2D,
)
from osteo_vision_core.reports.writers import write_csv, write_json  # noqa: E402

DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
    "derived/video_signal_multimask_round3_20260707/video_signal_multimask_training_manifest.csv"
)
DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/keyframe_video_signal_multimask_v2_grouped.pt"
BOUNDARY_NOTE = (
    "Multi-head checkpoint trained on public proxy fluorescence masks and prompt-assisted bone-gate seeds. "
    "Bone-gate seeds remain review-required and cannot be reported as physician ground truth."
)


class MultiMaskDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]]):
    def __init__(self, samples: list[dict[str, Any]], *, image_shape: tuple[int, int], heads: tuple[str, ...]) -> None:
        self.samples = samples
        self.image_shape = image_shape
        self.heads = heads

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        sample = self.samples[index]
        height, width = self.image_shape
        with Image.open(sample["image_path"]) as image_obj:
            image = np.asarray(image_obj.convert("RGB").resize((width, height)), dtype=np.uint8)
        targets: np.ndarray = np.zeros((len(self.heads), height, width), dtype=np.float32)
        valid: np.ndarray = np.zeros((len(self.heads),), dtype=np.float32)
        weights: np.ndarray = np.ones((len(self.heads),), dtype=np.float32)
        for head_index, head in enumerate(self.heads):
            record = sample["targets"].get(head)
            if not record:
                continue
            with Image.open(record["mask_path"]) as mask_obj:
                mask = np.asarray(
                    mask_obj.convert("L").resize((width, height), Image.Resampling.NEAREST), dtype=np.uint8
                )
            targets[head_index] = mask > 0
            valid[head_index] = 1.0
            weights[head_index] = float(record["sample_weight"])
        return (
            torch.from_numpy(image.transpose(2, 0, 1).astype(np.float32) / 255.0),
            torch.from_numpy(targets),
            torch.from_numpy(valid),
            torch.from_numpy(weights),
        )


def train_multimask_v2(args: argparse.Namespace) -> dict[str, Any]:
    set_seed(args.seed)
    heads = tuple(item.strip() for item in str(args.heads).split(",") if item.strip())
    unsupported = sorted(set(heads) - set(VIDEO_SIGNAL_HEADS))
    if unsupported:
        raise ValueError(f"Unsupported heads: {unsupported}")
    rows = load_grouped_rows(
        args.manifest,
        heads=heads,
        seed=args.seed,
        val_fraction=args.val_fraction,
        test_fraction=args.test_fraction,
    )
    leakage = assert_no_group_leakage(rows, context="multi-mask training rows")
    samples = aggregate_samples(rows, heads=heads)
    split_samples = {split: [item for item in samples if item["split"] == split] for split in ("train", "val", "test")}
    if not split_samples["train"] or not split_samples["val"]:
        raise ValueError("Grouped multi-mask data requires non-empty train and val splits")
    image_shape = parse_shape(args.image_shape)
    device = select_torch_device(args.device)
    in_channels = 3
    base_channels = int(args.base_channels)
    model_config = {"in_channels": in_channels, "heads": list(heads), "base_channels": base_channels}
    overfit_probe = run_overfit_probe(
        split_samples["train"][: min(8, len(split_samples["train"]))],
        heads=heads,
        image_shape=image_shape,
        model_config=model_config,
        device=device,
        batches=args.overfit_probe_batches,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )
    model = VideoSignalMultiMask2D(
        in_channels=in_channels,
        heads=tuple(heads),
        base_channels=base_channels,
    ).to(device)
    resume_checkpoint = str(getattr(args, "resume_checkpoint", "") or "")
    resume_record = (
        load_resume_checkpoint(
            resume_checkpoint,
            model=model,
            expected_model_config=model_config,
            device=device,
        )
        if resume_checkpoint
        else None
    )
    if resume_record:
        model.load_state_dict(resume_record["state_dict"], strict=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    optimizer_state_status = restore_optimizer_state(
        optimizer,
        resume_record=resume_record,
        restore_requested=bool(getattr(args, "restore_optimizer_state", True)),
        learning_rate=float(args.learning_rate),
    )
    started = time.perf_counter()
    losses = train_model(
        model,
        MultiMaskDataset(split_samples["train"], image_shape=image_shape, heads=heads),
        device=device,
        batches=args.max_train_batches,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        optimizer=optimizer,
    )
    validation = evaluate_heads(
        model,
        MultiMaskDataset(split_samples["val"], image_shape=image_shape, heads=heads),
        heads=heads,
        device=device,
        thresholds=parse_thresholds(args.thresholds),
    )
    test_metrics = (
        evaluate_heads(
            model,
            MultiMaskDataset(split_samples["test"], image_shape=image_shape, heads=heads),
            heads=heads,
            device=device,
            thresholds=[float(validation["heads"][head]["recommended_threshold"]) for head in heads],
            fixed_threshold_by_head={head: float(validation["heads"][head]["recommended_threshold"]) for head in heads},
        )
        if split_samples["test"]
        else {"available": False, "reason": "test_split_empty"}
    )
    checkpoint_path = resolve_path(args.output_checkpoint)
    ensure_dir(checkpoint_path.parent)
    source_manifest_records = manifest_sha256_records(args.manifest)
    previous_completed_batches = int(resume_record["previous_completed_train_batches"]) if resume_record else 0
    fine_tuning = {
        "enabled": resume_record is not None,
        "initialization": "resume_checkpoint" if resume_record else "random",
        "source_checkpoint_path": resume_record["checkpoint_path"] if resume_record else None,
        "source_checkpoint_sha256": resume_record["checkpoint_sha256"] if resume_record else None,
        "source_checkpoint_model_id": resume_record["model_id"] if resume_record else None,
        "strict_model_compatibility_checked": resume_record is not None,
        "optimizer_state_available": bool(resume_record and resume_record["optimizer_state_dict"] is not None),
        "optimizer_state_restored": optimizer_state_status == "restored",
        "optimizer_state_status": optimizer_state_status,
        "previous_completed_train_batches": previous_completed_batches,
        "current_completed_train_batches": int(args.max_train_batches),
        "total_completed_train_batches": previous_completed_batches + int(args.max_train_batches),
    }
    payload = {
        "model_id": "convnext2d_video_signal_multimask_v2_grouped",
        "model_family": "convnext2d_video_signal_multimask",
        "model_config": model_config,
        "state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "training": {
            "source_manifests": [str(resolve_path(item)) for item in args.manifest],
            "source_manifest_sha256": source_manifest_records,
            "row_count": len(rows),
            "sample_count": len(samples),
            "split_sample_counts": {key: len(value) for key, value in split_samples.items()},
            "mask_type_counts": dict(Counter(row["mask_type"] for row in rows)),
            "head_supervision_counts": dict(Counter(row["head"] for row in rows)),
            "review_state_counts": dict(Counter(row["review_state"] for row in rows)),
            "source_group_split": leakage,
            "completed_train_batches": int(args.max_train_batches),
            "mean_train_loss": float(np.mean(losses)),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "overfit_probe": overfit_probe,
            "fine_tuning": fine_tuning,
        },
        "validation": validation,
        "test": test_metrics,
        "runtime_allowed": False,
        "clinical_claim_allowed": False,
        "medical_boundary": BOUNDARY_NOTE,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    torch.save(payload, checkpoint_path)
    digest = checkpoint_sha256(checkpoint_path)
    sidecar = {key: value for key, value in payload.items() if key not in {"state_dict", "optimizer_state_dict"}} | {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
    }
    manifest_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_manifest.json")
    model_card_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_model_card.json")
    write_json(manifest_path, sidecar)
    write_json(
        model_card_path,
        {
            "model_id": payload["model_id"],
            "model_family": payload["model_family"],
            "intended_use": "Independent video-signal mask heads for platform engineering validation.",
            "training_data": payload["training"],
            "metrics": {"validation": validation, "test": test_metrics},
            "limitations": [BOUNDARY_NOTE],
            "clinical_claim_allowed": False,
        },
    )
    report_dir = ensure_dir(resolve_path(args.report_dir))
    filtered_manifest = report_dir / f"video_signal_multimask_v2_grouped_{args.report_stamp}.csv"
    write_csv(filtered_manifest, rows, sorted({key for row in rows for key in row}))
    summary_path = report_dir / f"video_signal_multimask_v2_training_{args.report_stamp}.json"
    write_json(summary_path, sidecar | {"filtered_manifest_path": str(filtered_manifest)})
    return {
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        "model_card_path": str(model_card_path),
        "summary_path": str(summary_path),
        "validation": validation,
        "test": test_metrics,
        "overfit_probe": overfit_probe,
        "fine_tuning": fine_tuning,
    }


def load_grouped_rows(
    paths: list[str],
    *,
    heads: tuple[str, ...],
    seed: int,
    val_fraction: float,
    test_fraction: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in paths:
        path = resolve_path(manifest)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                head = MASK_TYPE_TO_HEAD.get(str(raw.get("mask_type") or ""))
                if head not in heads or not raw.get("image_path") or not raw.get("mask_path"):
                    continue
                source_group = str(raw.get("source_video_path") or raw.get("source_group_id") or raw["image_path"])
                review_state = str(raw.get("review_state") or "review_required")
                weight = float(raw.get("sample_weight") or 1.0)
                rows.append(
                    {
                        **raw,
                        "head": head,
                        "source_group_id": normalized_source_group(source_group),
                        "split": assign_group_split(
                            source_group,
                            seed=seed,
                            val_fraction=val_fraction,
                            test_fraction=test_fraction,
                        ),
                        "sample_weight": weight,
                        "review_state": review_state,
                    }
                )
    return rows


def aggregate_samples(rows: list[dict[str, Any]], *, heads: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["image_path"])
        sample = grouped.setdefault(
            key,
            {
                "image_path": key,
                "source_group_id": row["source_group_id"],
                "split": row["split"],
                "targets": {},
            },
        )
        if sample["split"] != row["split"]:
            raise ValueError(f"Image {key} crosses splits")
        sample["targets"][row["head"]] = {
            "mask_path": str(row["mask_path"]),
            "sample_weight": float(row["sample_weight"]),
            "review_state": row["review_state"],
        }
    return [item for item in grouped.values() if any(head in item["targets"] for head in heads)]


def train_model(
    model: VideoSignalMultiMask2D,
    dataset: MultiMaskDataset,
    *,
    device: torch.device,
    batches: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    optimizer: torch.optim.Optimizer | None = None,
) -> list[float]:
    loader = DataLoader(
        dataset,
        batch_size=min(batch_size, len(dataset)),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    optimizer = optimizer or torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    losses: list[float] = []
    model.train()
    completed = 0
    while completed < batches:
        for image, target, valid, weights in loader:
            image = image.to(device=device, dtype=torch.float32)
            target = target.to(device=device, dtype=torch.float32)
            valid = valid.to(device=device, dtype=torch.float32)
            weights = weights.to(device=device, dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            loss = masked_multimask_loss(model(image), target, valid, weights)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            completed += 1
            if completed >= batches:
                break
    return losses


def load_resume_checkpoint(
    checkpoint_value: str | Path,
    *,
    model: VideoSignalMultiMask2D,
    expected_model_config: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    checkpoint_path = resolve_path(checkpoint_value)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing resume checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unsupported resume checkpoint payload: {checkpoint_path}")
    if checkpoint.get("model_family") != "convnext2d_video_signal_multimask":
        raise ValueError(
            "Resume checkpoint model_family mismatch: "
            f"expected convnext2d_video_signal_multimask, got {checkpoint.get('model_family')!r}"
        )
    actual_config = canonical_multimask_model_config(checkpoint.get("model_config"), checkpoint_path=checkpoint_path)
    expected_config = canonical_multimask_model_config(expected_model_config, checkpoint_path=checkpoint_path)
    if actual_config != expected_config:
        raise ValueError(f"Resume checkpoint model_config mismatch: expected {expected_config}, got {actual_config}")
    state_dict = checkpoint.get("state_dict")
    validate_state_dict_structure(model, state_dict, checkpoint_path=checkpoint_path)
    training = checkpoint.get("training") if isinstance(checkpoint.get("training"), dict) else {}
    fine_tuning = training.get("fine_tuning") if isinstance(training.get("fine_tuning"), dict) else {}
    optimizer_state = checkpoint.get("optimizer_state_dict")
    if optimizer_state is not None and not isinstance(optimizer_state, dict):
        raise ValueError(f"Resume checkpoint optimizer_state_dict must be a mapping: {checkpoint_path}")
    return {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256(checkpoint_path),
        "model_id": checkpoint.get("model_id"),
        "state_dict": state_dict,
        "optimizer_state_dict": optimizer_state,
        "previous_completed_train_batches": int(
            training.get("total_completed_train_batches")
            or fine_tuning.get("total_completed_train_batches")
            or training.get("completed_train_batches")
            or 0
        ),
    }


def canonical_multimask_model_config(value: Any, *, checkpoint_path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Resume checkpoint missing model_config: {checkpoint_path}")
    required = {"in_channels", "heads", "base_channels"}
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"Resume checkpoint model_config missing fields {missing}: {checkpoint_path}")
    heads = value["heads"]
    if not isinstance(heads, (list, tuple)) or not heads:
        raise ValueError(f"Resume checkpoint model_config heads must be a non-empty sequence: {checkpoint_path}")
    return {
        "in_channels": int(value["in_channels"]),
        "heads": [str(head) for head in heads],
        "base_channels": int(value["base_channels"]),
    }


def validate_state_dict_structure(
    model: VideoSignalMultiMask2D,
    state_dict: Any,
    *,
    checkpoint_path: Path,
) -> None:
    if not isinstance(state_dict, dict):
        raise ValueError(f"Resume checkpoint missing state_dict: {checkpoint_path}")
    expected = model.state_dict()
    missing = sorted(set(expected) - set(state_dict))
    unexpected = sorted(set(state_dict) - set(expected))
    shape_mismatches: list[str] = []
    for key in sorted(set(expected) & set(state_dict)):
        value = state_dict[key]
        actual_shape = tuple(value.shape) if isinstance(value, torch.Tensor) else "non_tensor"
        if actual_shape != tuple(expected[key].shape):
            shape_mismatches.append(f"{key}: expected {tuple(expected[key].shape)}, got {actual_shape}")
    if missing or unexpected or shape_mismatches:
        raise ValueError(
            "Resume checkpoint state_dict is incompatible: "
            f"missing={missing}, unexpected={unexpected}, shape_mismatches={shape_mismatches}"
        )


def restore_optimizer_state(
    optimizer: torch.optim.Optimizer,
    *,
    resume_record: dict[str, Any] | None,
    restore_requested: bool,
    learning_rate: float,
) -> str:
    if resume_record is None:
        return "not_applicable_random_initialization"
    optimizer_state = resume_record.get("optimizer_state_dict")
    if optimizer_state is None:
        return "missing_in_source_checkpoint"
    if not restore_requested:
        return "available_not_restored"
    try:
        optimizer.load_state_dict(optimizer_state)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Resume checkpoint optimizer state is incompatible: {exc}") from exc
    for parameter_group in optimizer.param_groups:
        parameter_group["lr"] = learning_rate
    return "restored"


def manifest_sha256_records(paths: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for value in paths:
        path = resolve_path(value)
        records.append({"path": str(path), "sha256": checkpoint_sha256(path)})
    return records


def masked_multimask_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    valid: torch.Tensor,
    weights: torch.Tensor,
) -> torch.Tensor:
    bce = F.binary_cross_entropy_with_logits(logits, target, reduction="none").mean(dim=(2, 3))
    probability = torch.sigmoid(logits)
    intersection = (probability * target).sum(dim=(2, 3))
    denominator = probability.sum(dim=(2, 3)) + target.sum(dim=(2, 3))
    dice = 1.0 - (2.0 * intersection + 1e-5) / (denominator + 1e-5)
    effective = torch.clamp(valid * weights, min=0.0)
    loss = (0.5 * bce + 0.5 * dice) * effective
    return loss.sum() / torch.clamp(effective.sum(), min=1.0)


def evaluate_heads(
    model: VideoSignalMultiMask2D,
    dataset: MultiMaskDataset,
    *,
    heads: tuple[str, ...],
    device: torch.device,
    thresholds: list[float],
    fixed_threshold_by_head: dict[str, float] | None = None,
) -> dict[str, Any]:
    records: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {head: [] for head in heads}
    model.eval()
    with torch.no_grad():
        for image, target, valid, _weights in DataLoader(dataset, batch_size=1, shuffle=False):
            logits = model(image.to(device=device, dtype=torch.float32))
            probability = torch.sigmoid(logits)[0].cpu().numpy()
            for index, head in enumerate(heads):
                if float(valid[0, index]) > 0:
                    records[head].append((probability[index], target[0, index].numpy() > 0))
    result: dict[str, Any] = {"available": True, "sample_count": len(dataset), "heads": {}}
    for head in heads:
        scan_thresholds = [fixed_threshold_by_head[head]] if fixed_threshold_by_head else thresholds
        rows = [head_metrics(records[head], threshold=value) for value in scan_thresholds]
        recommended = max(rows, key=lambda item: (item["non_empty"], item["dice"], -item["over_segmentation_rate"]))
        result["heads"][head] = {
            "supervised_sample_count": len(records[head]),
            "recommended_threshold": recommended["threshold"],
            "recommended_metrics": recommended,
            "threshold_scan": rows,
        }
    result["all_heads_non_empty"] = all(
        bool(item["recommended_metrics"]["non_empty"]) for item in result["heads"].values()
    )
    return result


def head_metrics(records: list[tuple[np.ndarray, np.ndarray]], *, threshold: float) -> dict[str, Any]:
    dice_values: list[float] = []
    iou_values: list[float] = []
    positive_values: list[float] = []
    empty_count = 0
    over_count = 0
    for probability, target in records:
        prediction = probability >= threshold
        intersection = float(np.logical_and(prediction, target).sum())
        pred_area = float(prediction.sum())
        true_area = float(target.sum())
        union = float(np.logical_or(prediction, target).sum())
        dice_values.append(2.0 * intersection / max(1.0, pred_area + true_area))
        iou_values.append(intersection / max(1.0, union))
        fraction = float(prediction.mean())
        positive_values.append(fraction)
        empty_count += int(fraction == 0.0)
        over_count += int(fraction > 0.8)
    count = max(1, len(records))
    mean_positive = float(np.mean(positive_values)) if positive_values else 0.0
    return {
        "threshold": float(threshold),
        "dice": float(np.mean(dice_values)) if dice_values else 0.0,
        "iou": float(np.mean(iou_values)) if iou_values else 0.0,
        "prediction_positive_fraction": mean_positive,
        "empty_mask_rate": empty_count / count,
        "over_segmentation_rate": over_count / count,
        "non_empty": mean_positive > 0.0,
    }


def run_overfit_probe(
    samples: list[dict[str, Any]],
    *,
    heads: tuple[str, ...],
    image_shape: tuple[int, int],
    model_config: dict[str, Any],
    device: torch.device,
    batches: int,
    learning_rate: float,
    seed: int,
) -> dict[str, Any]:
    model = VideoSignalMultiMask2D(**{**model_config, "heads": tuple(heads)}).to(device)
    dataset = MultiMaskDataset(samples, image_shape=image_shape, heads=heads)
    losses = train_model(
        model,
        dataset,
        device=device,
        batches=batches,
        batch_size=min(4, len(dataset)),
        learning_rate=learning_rate,
        seed=seed,
    )
    metrics = evaluate_heads(model, dataset, heads=heads, device=device, thresholds=[0.2, 0.3, 0.4, 0.5])
    return {
        "sample_count": len(dataset),
        "completed_batches": batches,
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "loss_decreased": losses[-1] < losses[0],
        "metrics": metrics,
    }


def parse_thresholds(value: str) -> list[float]:
    parsed = sorted({float(item) for item in value.replace(";", ",").split(",") if item.strip()})
    if not parsed or any(item <= 0 or item >= 1 for item in parsed):
        raise ValueError("Thresholds must be within (0, 1)")
    return parsed


def parse_shape(value: str) -> tuple[int, int]:
    parts = value.lower().replace(",", "x").split("x")
    if len(parts) != 2:
        raise ValueError(f"Expected HxW, got {value}")
    return int(parts[0]), int(parts[1])


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", nargs="+", default=[DEFAULT_MANIFEST])
    parser.add_argument("--heads", default=",".join(VIDEO_SIGNAL_HEADS))
    parser.add_argument("--output-checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument(
        "--resume-checkpoint",
        default="",
        help="Strictly compatible multi-mask checkpoint used to initialize weights and continue training.",
    )
    parser.add_argument(
        "--restore-optimizer-state",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restore optimizer moments when the resume checkpoint contains optimizer_state_dict.",
    )
    parser.add_argument("--report-dir", default="research/reports/modeling")
    parser.add_argument("--report-stamp", default=datetime.now().strftime("%Y%m%d_multimask_v2_grouped"))
    parser.add_argument("--image-shape", default="128x176")
    parser.add_argument("--max-train-batches", type=int, default=320)
    parser.add_argument("--overfit-probe-batches", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--base-channels", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=7e-4)
    parser.add_argument("--thresholds", default="0.2,0.3,0.4,0.5,0.6,0.7")
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    print(json.dumps(train_multimask_v2(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
