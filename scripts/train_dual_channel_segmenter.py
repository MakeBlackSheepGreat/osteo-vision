"""Train white/fluorescence dual-channel proxy segmentation with four ablation modes."""

from __future__ import annotations

import argparse
import json
import random
import sys
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

from scripts.train_keyframe_segmentation_proxy import load_manifest_rows  # noqa: E402
from src.core.paths import ensure_dir, resolve_path  # noqa: E402
from src.datasets.group_splits import assert_no_group_leakage  # noqa: E402
from src.models.dual_channel_segmenter import DUAL_CHANNEL_MODES, TinyDualChannelSegmenter2D  # noqa: E402
from src.models.keyframe_segmenter import checkpoint_sha256, select_torch_device  # noqa: E402
from src.reports.writers import write_json  # noqa: E402


class DualChannelProxyDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, str]], *, image_shape: tuple[int, int]) -> None:
        self.rows = rows
        self.image_shape = image_shape

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        row = self.rows[index]
        height, width = self.image_shape
        with Image.open(row["image_path"]) as image_obj:
            rgb = np.asarray(image_obj.convert("RGB").resize((width, height)), dtype=np.uint8)
        with Image.open(row["mask_path"]) as mask_obj:
            mask = np.asarray(mask_obj.convert("L").resize((width, height), Image.Resampling.NEAREST), dtype=np.uint8)
        fluorescence = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.uint8)
        white = synthetic_white_light(rgb)
        return (
            torch.from_numpy(white.transpose(2, 0, 1).astype(np.float32) / 255.0),
            torch.from_numpy(fluorescence[None].astype(np.float32) / 255.0),
            torch.from_numpy((mask > 0).astype(np.float32)),
        )


def synthetic_white_light(rgb: np.ndarray) -> np.ndarray:
    gray = np.mean(rgb.astype(np.float32), axis=2)
    white = np.stack(
        [np.clip(gray * 1.08 + 12, 0, 255), np.clip(gray * 0.96 + 18, 0, 255), np.clip(gray * 0.88 + 20, 0, 255)],
        axis=-1,
    )
    return white.astype(np.uint8)


def train_dual_channel(args: argparse.Namespace) -> dict[str, Any]:
    set_seed(args.seed)
    rows = load_manifest_rows(args.manifest)
    leakage = assert_no_group_leakage(rows, context="dual-channel training manifest")
    train_rows = [row for row in rows if row.get("split") == "train"]
    val_rows = [row for row in rows if row.get("split") == "val"]
    test_rows = [row for row in rows if row.get("split") == "test"]
    image_shape = parse_shape(args.image_shape)
    device = select_torch_device(args.device)
    model_config = {"base_channels": int(args.base_channels)}
    model = TinyDualChannelSegmenter2D(**model_config).to(device)
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
    loader = DataLoader(
        DualChannelProxyDataset(train_rows, image_shape=image_shape),
        batch_size=args.batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(args.seed),
    )
    modes = list(DUAL_CHANNEL_MODES)
    completed = 0
    model.train()
    while completed < args.max_train_batches:
        for white, fluorescence, target in loader:
            white = white.to(device=device, dtype=torch.float32)
            fluorescence = fluorescence.to(device=device, dtype=torch.float32)
            target = target.to(device=device, dtype=torch.float32)
            mode = modes[completed % len(modes)]
            optimizer.zero_grad(set_to_none=True)
            logits = model(white, fluorescence, mode=mode)[:, 0]
            probability = torch.sigmoid(logits)
            bce = F.binary_cross_entropy_with_logits(logits, target)
            intersection = (probability * target).sum(dim=(1, 2))
            denominator = probability.sum(dim=(1, 2)) + target.sum(dim=(1, 2))
            dice = 1.0 - ((2 * intersection + 1e-5) / (denominator + 1e-5)).mean()
            loss = 0.5 * bce + 0.5 * dice
            loss.backward()
            optimizer.step()
            completed += 1
            if completed >= args.max_train_batches:
                break
    validation = evaluate_ablation(model, val_rows, image_shape=image_shape, device=device, threshold=args.threshold)
    test = evaluate_ablation(model, test_rows, image_shape=image_shape, device=device, threshold=args.threshold)
    selected_mode = select_ablation_mode(validation)
    checkpoint_path = resolve_path(args.output_checkpoint)
    ensure_dir(checkpoint_path.parent)
    manifest_path_resolved = resolve_path(args.manifest)
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
        "current_completed_train_batches": completed,
        "total_completed_train_batches": previous_completed_batches + completed,
    }
    payload = {
        "model_id": "dual_channel_proxy_ablation_segmenter",
        "model_family": "dual_channel_segmenter",
        "model_config": model_config,
        "state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "threshold": args.threshold,
        "training": {
            "manifest_path": str(manifest_path_resolved),
            "manifest_sha256": checkpoint_sha256(manifest_path_resolved),
            "train_samples": len(train_rows),
            "val_samples": len(val_rows),
            "test_samples": len(test_rows),
            "completed_train_batches": completed,
            "source_group_split": leakage,
            "channel_construction": "white-light proxy from luminance; fluorescence proxy from source intensity",
            "fine_tuning": fine_tuning,
        },
        "ablation_validation": validation,
        "ablation_test": test,
        "selected_mode": selected_mode,
        "runtime_allowed": False,
        "clinical_claim_allowed": False,
        "medical_boundary": "Public proxy data only; no target-domain clinical performance claim.",
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    torch.save(payload, checkpoint_path)
    digest = checkpoint_sha256(checkpoint_path)
    sidecar = {key: value for key, value in payload.items() if key not in {"state_dict", "optimizer_state_dict"}} | {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "runtime_allowed": False,
        "metrics": {"validation": validation, "test": test},
    }
    manifest_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_manifest.json")
    model_card_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_model_card.json")
    write_json(manifest_path, sidecar)
    write_json(model_card_path, sidecar)
    report_dir = ensure_dir(resolve_path(args.report_dir))
    summary_path = report_dir / f"dual_channel_ablation_{args.report_stamp}.json"
    write_json(summary_path, sidecar)
    return {
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        "model_card_path": str(model_card_path),
        "summary_path": str(summary_path),
        "validation": validation,
        "test": test,
        "selected_mode": selected_mode,
        "fine_tuning": fine_tuning,
    }


def evaluate_ablation(
    model: TinyDualChannelSegmenter2D,
    rows: list[dict[str, str]],
    *,
    image_shape: tuple[int, int],
    device: torch.device,
    threshold: float,
) -> dict[str, Any]:
    if not rows:
        return {"available": False, "reason": "split_empty"}
    dataset = DualChannelProxyDataset(rows, image_shape=image_shape)
    metrics: dict[str, Any] = {}
    model.eval()
    for mode in DUAL_CHANNEL_MODES:
        dice_values: list[float] = []
        iou_values: list[float] = []
        positive_values: list[float] = []
        with torch.no_grad():
            for white, fluorescence, target in DataLoader(dataset, batch_size=1, shuffle=False):
                probability = (
                    torch.sigmoid(model(white.to(device), fluorescence.to(device), mode=mode))[0, 0].cpu().numpy()
                )
                prediction = probability >= threshold
                true = target[0].numpy() > 0
                intersection = float(np.logical_and(prediction, true).sum())
                pred_area = float(prediction.sum())
                true_area = float(true.sum())
                union = float(np.logical_or(prediction, true).sum())
                dice_values.append(2 * intersection / max(1.0, pred_area + true_area))
                iou_values.append(intersection / max(1.0, union))
                positive_values.append(float(prediction.mean()))
        metrics[mode] = {
            "dice": float(np.mean(dice_values)),
            "iou": float(np.mean(iou_values)),
            "prediction_positive_fraction": float(np.mean(positive_values)),
            "empty_mask_rate": float(np.mean([value == 0 for value in positive_values])),
        }
    return {"available": True, "sample_count": len(rows), "modes": metrics}


def select_ablation_mode(validation: dict[str, Any]) -> str:
    modes = validation.get("modes") if isinstance(validation.get("modes"), dict) else {}
    if not modes:
        return "early_fusion"
    return max(modes, key=lambda mode: float((modes.get(mode) or {}).get("dice", 0.0)))


def load_resume_checkpoint(
    checkpoint_value: str | Path,
    *,
    model: TinyDualChannelSegmenter2D,
    expected_model_config: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    checkpoint_path = resolve_path(checkpoint_value)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing resume checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unsupported resume checkpoint payload: {checkpoint_path}")
    if checkpoint.get("model_family") != "dual_channel_segmenter":
        raise ValueError(
            "Resume checkpoint model_family mismatch: "
            f"expected dual_channel_segmenter, got {checkpoint.get('model_family')!r}"
        )
    actual_config = canonical_dual_channel_model_config(checkpoint.get("model_config"), checkpoint_path=checkpoint_path)
    expected_config = canonical_dual_channel_model_config(expected_model_config, checkpoint_path=checkpoint_path)
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


def canonical_dual_channel_model_config(value: Any, *, checkpoint_path: Path) -> dict[str, int]:
    if not isinstance(value, dict) or "base_channels" not in value:
        raise ValueError(f"Resume checkpoint model_config missing base_channels: {checkpoint_path}")
    return {"base_channels": int(value["base_channels"])}


def validate_state_dict_structure(
    model: TinyDualChannelSegmenter2D,
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


def parse_shape(value: str) -> tuple[int, int]:
    height, width = value.lower().replace(",", "x").split("x")
    return int(height), int(width)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-checkpoint", default="artifacts/checkpoints/osteo_vision/dual_channel_proxy.pt")
    parser.add_argument(
        "--resume-checkpoint",
        default="",
        help="Strictly compatible dual-channel checkpoint used to initialize weights and continue training.",
    )
    parser.add_argument(
        "--restore-optimizer-state",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restore optimizer moments when the resume checkpoint contains optimizer_state_dict.",
    )
    parser.add_argument("--report-dir", default="research/reports/modeling")
    parser.add_argument("--report-stamp", default=datetime.now().strftime("%Y%m%d_dual_channel"))
    parser.add_argument("--image-shape", default="128x176")
    parser.add_argument("--max-train-batches", type=int, default=360)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--base-channels", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=7e-4)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    print(json.dumps(train_dual_channel(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
