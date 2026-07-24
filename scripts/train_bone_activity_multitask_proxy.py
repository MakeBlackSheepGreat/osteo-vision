"""Train a fail-closed bone-activity multitask model on deterministic proxy data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections.abc import Sized
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import DataLoader, Dataset, Subset  # noqa: E402

from osteo_vision_core.core.config import config_hash, load_yaml  # noqa: E402
from osteo_vision_core.core.paths import ensure_dir, resolve_path  # noqa: E402
from osteo_vision_core.models.bone_activity_multitask import (  # noqa: E402
    BONE_ACTIVITY_CLASSES,
    IGNORE_INDEX,
    MODEL_OUTPUTS,
    BoneActivityMultiTask2D,
    apply_bone_activity_safety_gate,
    bone_activity_multitask_loss,
    bone_activity_probabilities,
)
from osteo_vision_core.models.keyframe_segmenter import checkpoint_sha256, select_torch_device  # noqa: E402
from osteo_vision_core.models.three_priority_promotion import evaluate_three_priority_model_promotion  # noqa: E402
from osteo_vision_core.reports.writers import write_json  # noqa: E402


@dataclass(frozen=True)
class ProxySplit:
    train: list[int]
    val: list[int]
    test: list[int]
    patient_group_split: dict[str, Any]


class SyntheticBoneActivityDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, *, sample_count: int, image_shape: tuple[int, int], seed: int) -> None:
        self.sample_count = int(sample_count)
        self.height, self.width = image_shape
        self.seed = int(seed)
        if self.sample_count < 5:
            raise ValueError("Proxy smoke requires at least five samples")
        if self.height < 24 or self.width < 24:
            raise ValueError("Proxy image dimensions must be at least 24 pixels")

    def __len__(self) -> int:
        return self.sample_count

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        generator = np.random.default_rng(self.seed + index)
        y, x = np.mgrid[-1.0 : 1.0 : complex(self.height), -1.0 : 1.0 : complex(self.width)]
        center_x = float(generator.uniform(-0.12, 0.12))
        center_y = float(generator.uniform(-0.12, 0.12))
        radius_x = float(generator.uniform(0.7, 0.88))
        radius_y = float(generator.uniform(0.62, 0.82))
        gate = ((x - center_x) / radius_x) ** 2 + ((y - center_y) / radius_y) ** 2 <= 1.0
        score = np.clip(0.55 + 0.34 * x - 0.20 * y + generator.normal(0, 0.025, x.shape), 0, 1)
        score = score * gate
        classes = np.full(x.shape, IGNORE_INDEX, dtype=np.int64)
        classes[gate & (score < 0.38)] = 0
        classes[gate & (score >= 0.38) & (score < 0.66)] = 1
        classes[gate & (score >= 0.66)] = 2
        boundary_uncertainty = np.maximum(
            np.exp(-np.square(score - 0.38) / 0.006),
            np.exp(-np.square(score - 0.66) / 0.006),
        )
        uncertainty = np.clip(boundary_uncertainty * gate + (~gate) * 0.8, 0, 1)
        fluorescence = np.clip(score + generator.normal(0, 0.035, score.shape), 0, 1)
        texture = np.clip(0.30 + 0.30 * gate + 0.25 * score + generator.normal(0, 0.03, score.shape), 0, 1)
        white = np.stack(
            [np.clip(texture * 1.10, 0, 1), np.clip(texture * 0.96 + 0.03, 0, 1), np.clip(texture * 0.86 + 0.05, 0, 1)],
            axis=0,
        )
        return {
            "white": torch.from_numpy(white.astype(np.float32)),
            "fluorescence": torch.from_numpy(fluorescence[None].astype(np.float32)),
            "bone_gate": torch.from_numpy(gate[None].astype(np.float32)),
            "activity_score": torch.from_numpy(score[None].astype(np.float32)),
            "class_target": torch.from_numpy(classes),
            "uncertainty": torch.from_numpy(uncertainty[None].astype(np.float32)),
        }


class ManifestBoneActivityDataset(Dataset[dict[str, torch.Tensor]]):
    REQUIRED_FILE_FIELDS = {
        "white": ("white_path", "white_sha256"),
        "fluorescence": ("fluorescence_path", "fluorescence_sha256"),
        "bone_gate": ("bone_gate_path", "bone_gate_sha256"),
        "activity_score": ("activity_score_path", "activity_score_sha256"),
        "class_target": ("class_target_path", "class_target_sha256"),
        "uncertainty": ("uncertainty_path", "uncertainty_sha256"),
    }

    def __init__(
        self,
        rows: list[dict[str, str]],
        *,
        manifest_path: Path,
        image_shape: tuple[int, int],
    ) -> None:
        self.rows = rows
        self.manifest_path = manifest_path
        self.height, self.width = image_shape
        self.paths: list[dict[str, Path]] = []
        for row in rows:
            files: dict[str, Path] = {}
            for role, (path_field, sha_field) in self.REQUIRED_FILE_FIELDS.items():
                path = Path(str(row.get(path_field) or "")).expanduser()
                if not path.is_absolute():
                    path = manifest_path.parent / path
                path = path.resolve()
                expected = str(row.get(sha_field) or "").strip().lower()
                if not path.is_file():
                    raise FileNotFoundError(f"Bone-activity {role} file is missing: {path}")
                if len(expected) != 64 or _sha256_file(path) != expected:
                    raise ValueError(f"Bone-activity {role} SHA256 mismatch: {path}")
                files[role] = path
            self.paths.append(files)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        paths = self.paths[index]
        size = (self.width, self.height)
        with Image.open(paths["white"]) as image:
            white = np.asarray(image.convert("RGB").resize(size, Image.Resampling.BILINEAR), dtype=np.float32)
        with Image.open(paths["fluorescence"]) as image:
            fluorescence = np.asarray(image.convert("L").resize(size, Image.Resampling.BILINEAR), dtype=np.float32)
        with Image.open(paths["bone_gate"]) as image:
            gate = np.asarray(image.convert("L").resize(size, Image.Resampling.NEAREST), dtype=np.uint8) > 0
        with Image.open(paths["activity_score"]) as image:
            score = np.asarray(image.convert("L").resize(size, Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
        with Image.open(paths["class_target"]) as image:
            classes = np.asarray(image.convert("L").resize(size, Image.Resampling.NEAREST), dtype=np.uint8)
        with Image.open(paths["uncertainty"]) as image:
            uncertainty = (
                np.asarray(image.convert("L").resize(size, Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
            )
        if not gate.any():
            raise ValueError(f"Bone-activity proxy gate is empty: {self.rows[index].get('sample_id')}")
        if not set(np.unique(classes)).issubset({0, 1, 2, IGNORE_INDEX}):
            raise ValueError("Bone-activity class target contains unsupported values")
        if np.any((classes != IGNORE_INDEX) & ~gate):
            raise ValueError("Bone-activity class target extends outside its review-gate proxy")
        if not np.isfinite(score).all() or not np.isfinite(uncertainty).all():
            raise ValueError("Bone-activity continuous proxy targets must be finite")
        score[~gate] = 0.0
        uncertainty[~gate] = 1.0
        return {
            "white": torch.from_numpy(np.transpose(white / 255.0, (2, 0, 1)).copy()),
            "fluorescence": torch.from_numpy(fluorescence[None].copy() / 255.0),
            "bone_gate": torch.from_numpy(gate[None].astype(np.float32)),
            "activity_score": torch.from_numpy(score[None].astype(np.float32)),
            "class_target": torch.from_numpy(classes.astype(np.int64)),
            "uncertainty": torch.from_numpy(uncertainty[None].astype(np.float32)),
        }


def train_bone_activity_multitask(config_path: str | Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    seed = int(_mapping(config.get("training")).get("seed", 20260718))
    _set_seed(seed)
    torch.set_num_threads(max(1, min(torch.get_num_threads(), 4)))
    data_config = _mapping(config.get("data"))
    training_config = _mapping(config.get("training"))
    model_config = _mapping(config.get("model"))
    output_config = _mapping(config.get("outputs"))
    image_shape = _image_shape(data_config.get("image_shape"))
    data_mode = str(data_config.get("mode") or "synthetic").strip().lower()
    source_manifest_path: Path | None = None
    source_manifest_sha256: str | None = None
    if data_mode == "synthetic":
        sample_count = int(data_config.get("sample_count", 15))
        group_count = int(data_config.get("patient_group_count", 5))
        dataset: Dataset[dict[str, torch.Tensor]] = SyntheticBoneActivityDataset(
            sample_count=sample_count,
            image_shape=image_shape,
            seed=seed,
        )
        split = _group_split(sample_count, group_count)
        data_provenance = {
            "mode": "synthetic",
            "training_scope": "engineering_smoke_only",
            "domain_tier": str(data_config.get("domain") or "synthetic_proxy"),
            "channel_semantics": "procedural_dual_channel_proxy",
            "source_manifest_path": None,
            "source_manifest_sha256": None,
        }
    elif data_mode == "manifest":
        source_manifest_path, rows, split, data_provenance = _load_manifest_training_data(
            data_config,
            image_shape=image_shape,
        )
        source_manifest_sha256 = _sha256_file(source_manifest_path)
        dataset = ManifestBoneActivityDataset(
            rows,
            manifest_path=source_manifest_path,
            image_shape=image_shape,
        )
        sample_count = len(dataset)
    else:
        raise ValueError("data.mode must be synthetic or manifest")
    device = select_torch_device(str(training_config.get("device") or "cpu"))
    model = BoneActivityMultiTask2D(base_channels=int(model_config.get("base_channels", 4))).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training_config.get("learning_rate", 1e-3)),
        weight_decay=1e-4,
    )
    train_losses = _train(
        model,
        Subset(dataset, split.train),
        optimizer=optimizer,
        device=device,
        batch_size=int(training_config.get("batch_size", 3)),
        max_batches=int(training_config.get("max_train_batches", 4)),
        loss_weights=_mapping(training_config.get("loss_weights")),
        seed=seed,
    )
    safety_config = _mapping(config.get("safety"))
    gate_threshold, abstention_threshold, validation_metrics, threshold_selection = _select_validation_thresholds(
        model,
        Subset(dataset, split.val),
        device=device,
        safety_config=safety_config,
    )
    test_metrics = _evaluate(
        model,
        Subset(dataset, split.test),
        device=device,
        gate_threshold=gate_threshold,
        abstention_threshold=abstention_threshold,
    )
    threshold_selection["frozen_test_evaluation"] = {
        "test_set_used_for_selection": False,
        "thresholds_reused_without_test_tuning": True,
        "minimum_coverage_rate_passed": test_metrics["abstention_coverage_rate"]
        >= threshold_selection["selection_constraints"]["minimum_coverage_rate"],
        "maximum_selective_error_rate_passed": test_metrics["selective_error_rate"]
        <= threshold_selection["selection_constraints"]["maximum_selective_error_rate"],
    }
    threshold_selection["frozen_test_evaluation"]["constraints_passed"] = bool(
        threshold_selection["frozen_test_evaluation"]["minimum_coverage_rate_passed"]
        and threshold_selection["frozen_test_evaluation"]["maximum_selective_error_rate_passed"]
    )
    engineering_utility_ready = bool(
        threshold_selection["validation_constraints_passed"]
        and threshold_selection["frozen_test_evaluation"]["constraints_passed"]
    )
    safety = _run_fail_closed_smoke(model, dataset[0], device=device)
    checkpoint_path = resolve_path(str(output_config["checkpoint_path"]))
    ensure_dir(checkpoint_path.parent)
    checkpoint_payload = {
        "model_id": str(model_config.get("model_id") or "bone_activity_multitask_proxy_v1"),
        "model_family": str(model_config.get("model_family") or "dual_channel_bone_activity_multitask"),
        "model_config": {"base_channels": int(model_config.get("base_channels", 4))},
        "state_dict": model.state_dict(),
        "training_domain": {
            "target_domain": False,
            "domain": str(data_config.get("domain") or "proxy"),
            "domain_tier": data_provenance["domain_tier"],
            "data_mode": data_mode,
            "training_scope": data_provenance["training_scope"],
            "channel_semantics": data_provenance["channel_semantics"],
        },
        "training": {
            "completed": True,
            "sample_count": sample_count,
            "completed_train_batches": int(training_config.get("max_train_batches", 4)),
            "mean_train_loss": float(np.mean(train_losses)),
            "patient_group_split": split.patient_group_split,
            "source_manifest_path": str(source_manifest_path) if source_manifest_path else None,
            "source_manifest_sha256": source_manifest_sha256,
        },
        "outputs": list(MODEL_OUTPUTS),
        "inference_thresholds": {
            "bone_gate_threshold": gate_threshold,
            "abstention_threshold": abstention_threshold,
            "selection_source": "validation_split",
            "runtime_authorized": False,
        },
        "engineering_utility": {
            "ready": engineering_utility_ready,
            "validation_threshold_constraints_passed": threshold_selection["validation_constraints_passed"],
            "frozen_test_constraints_passed": threshold_selection["frozen_test_evaluation"]["constraints_passed"],
            "runtime_authorized": False,
        },
        "safety": safety,
        "labels": {
            "class_set": [*BONE_ACTIVITY_CLASSES, "ignore"],
            "physician_reviewed_bone_gate": False,
            "multi_physician_arbitration": False,
            "label_semantics": (
                "procedural_rule_proxy" if data_mode == "synthetic" else "rule_derived_non_target_fluorescence_proxy"
            ),
        },
        "validation": {
            "independent_test_set": False,
            "calibrated": False,
            "patient_leakage_recomputed": False,
            "independent_institution_split": False,
            "independent_time_split": False,
            "metrics": test_metrics,
            "proxy_validation_metrics": validation_metrics,
            "threshold_selection": threshold_selection,
            "promotion_metrics_eligible": False,
        },
        "review": {"physician_reviewed": False},
        "runtime_allowed": False,
        "clinical_claim_allowed": False,
        "medical_boundary": _medical_boundary(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    torch.save(checkpoint_payload, checkpoint_path)
    digest = checkpoint_sha256(checkpoint_path)
    manifest: dict[str, Any] = {
        "schema_version": "osteo-vision-bone-activity-multitask-checkpoint-v1",
        "capability": "bone_activity_multitask",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "config_path": str(resolve_path(config_path)),
        "config_hash": config_hash(config_path),
        **{key: value for key, value in checkpoint_payload.items() if key != "state_dict"},
    }
    promotion_policy_path = str(config.get("promotion_policy_path") or "").strip()
    promotion_policy = load_yaml(promotion_policy_path) if promotion_policy_path else None
    promotion = evaluate_three_priority_model_promotion(manifest, policy=promotion_policy)
    manifest["engineering_ready"] = promotion["engineering_ready"]
    manifest["target_domain_promotion_ready"] = promotion["target_domain_promotion_ready"]
    manifest["runtime_replacement_allowed"] = promotion["runtime_replacement_allowed"]
    manifest["promotion"] = promotion
    if manifest["engineering_ready"] is not True or manifest["target_domain_promotion_ready"] is not False:
        raise RuntimeError("Proxy bone-activity manifest did not preserve the required engineering-only gate")
    manifest_path = resolve_path(str(output_config["manifest_path"]))
    summary_path = resolve_path(str(output_config["summary_path"]))
    write_json(manifest_path, manifest)
    write_json(summary_path, manifest)
    return {
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        "summary_path": str(summary_path),
        "checkpoint_sha256": digest,
        "engineering_ready": True,
        "target_domain_promotion_ready": False,
        "metrics": test_metrics,
        "engineering_utility_ready": engineering_utility_ready,
        "safety": safety,
    }


def _train(
    model: BoneActivityMultiTask2D,
    dataset: Dataset[dict[str, torch.Tensor]],
    *,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    batch_size: int,
    max_batches: int,
    loss_weights: Mapping[str, Any],
    seed: int,
) -> list[float]:
    loader = DataLoader(
        dataset,
        batch_size=min(batch_size, len(cast(Sized, dataset))),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    losses: list[float] = []
    model.train()
    completed = 0
    while completed < max_batches:
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            outputs = model(batch["white"].to(device), batch["fluorescence"].to(device))
            loss, _ = bone_activity_multitask_loss(
                outputs,
                {key: value.to(device) for key, value in batch.items() if key not in {"white", "fluorescence"}},
                weights={key: float(value) for key, value in loss_weights.items()},
            )
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            completed += 1
            if completed >= max_batches:
                break
    return losses


def _evaluate(
    model: BoneActivityMultiTask2D,
    dataset: Dataset[dict[str, torch.Tensor]],
    *,
    device: torch.device,
    gate_threshold: float,
    abstention_threshold: float,
) -> dict[str, float]:
    if not 0.0 < float(gate_threshold) < 1.0:
        raise ValueError("gate_threshold must be within (0, 1)")
    if not 0.0 < float(abstention_threshold) < 1.0:
        raise ValueError("abstention_threshold must be within (0, 1)")
    loader = DataLoader(dataset, batch_size=1, shuffle=False)
    dice_values: list[float] = []
    gate_true_positive = 0.0
    gate_false_positive = 0.0
    gate_false_negative = 0.0
    mae_values: list[float] = []
    accuracy_values: list[float] = []
    uncertainty_values: list[float] = []
    class_counts = {class_index: [0.0, 0.0, 0.0] for class_index in range(len(BONE_ACTIVITY_CLASSES))}
    class_support_samples = {class_index: 0.0 for class_index in range(len(BONE_ACTIVITY_CLASSES))}
    transition_true_positive = 0.0
    transition_false_negative = 0.0
    ece_confidence: list[np.ndarray] = []
    ece_correct: list[np.ndarray] = []
    non_abstained_errors = 0.0
    non_abstained_pixel_count = 0.0
    valid_pixel_count = 0.0
    contained_prediction_count = 0.0
    prediction_count = 0.0
    model.eval()
    with torch.no_grad():
        for batch in loader:
            raw_output = model(batch["white"].to(device), batch["fluorescence"].to(device))
            output = bone_activity_probabilities(raw_output)
            target_gate = batch["bone_gate"].to(device) > 0.5
            predicted_gate = output["bone_gate_probability"] >= gate_threshold
            intersection = (predicted_gate & target_gate).sum().item()
            denominator = predicted_gate.sum().item() + target_gate.sum().item()
            dice_values.append(float((2 * intersection) / max(1, denominator)))
            gate_true_positive += float((predicted_gate & target_gate).sum())
            gate_false_positive += float((predicted_gate & ~target_gate).sum())
            gate_false_negative += float((~predicted_gate & target_gate).sum())
            mae_values.append(
                float(
                    torch.abs(
                        output["activity_score"][target_gate] - batch["activity_score"].to(device)[target_gate]
                    ).mean()
                )
            )
            class_prediction = torch.argmax(output["class_probabilities"], dim=1)
            target_class = batch["class_target"].to(device)
            valid = target_class != IGNORE_INDEX
            correct = class_prediction[valid] == target_class[valid]
            accuracy_values.append(float(correct.float().mean()))
            for class_index in class_counts:
                prediction_mask = class_prediction == class_index
                truth_mask = target_class == class_index
                class_counts[class_index][0] += float(torch.logical_and(prediction_mask, truth_mask).sum())
                class_counts[class_index][1] += float(torch.logical_and(prediction_mask, valid & ~truth_mask).sum())
                class_counts[class_index][2] += float(torch.logical_and(~prediction_mask, truth_mask).sum())
                class_support_samples[class_index] += float(bool(truth_mask.any()))
            transition_true_positive += class_counts_for_batch(class_prediction, target_class, class_index=1)[0]
            transition_false_negative += class_counts_for_batch(class_prediction, target_class, class_index=1)[2]
            confidence = output["class_probabilities"].max(dim=1).values[valid]
            ece_confidence.append(confidence.detach().cpu().numpy())
            ece_correct.append(correct.float().detach().cpu().numpy())
            abstention = output["uncertainty"][:, 0] >= abstention_threshold
            non_abstained_errors += float((~abstention[valid] & ~correct).sum())
            non_abstained_pixel_count += float((~abstention & valid).sum())
            valid_pixel_count += float(valid.sum())
            safe_output = apply_bone_activity_safety_gate(
                raw_output,
                reviewed_bone_gate=target_gate,
                physician_reviewed_bone_gate=True,
                target_domain=True,
                model_promotion_ready=True,
                abstention_threshold=abstention_threshold,
            )
            safe_predictions = safe_output["class_prediction"] != IGNORE_INDEX
            contained_prediction_count += float((safe_predictions & target_gate[:, 0]).sum())
            prediction_count += float(safe_predictions.sum())
            uncertainty_values.append(float(output["uncertainty"].mean()))
    per_class_dice = {
        BONE_ACTIVITY_CLASSES[class_index]: _dice_from_counts((counts[0], counts[1], counts[2]))
        for class_index, counts in class_counts.items()
    }
    class_support = {
        f"{BONE_ACTIVITY_CLASSES[class_index]}_support_pixels": counts[0] + counts[2]
        for class_index, counts in class_counts.items()
    }
    class_support.update(
        {
            f"{BONE_ACTIVITY_CLASSES[class_index]}_support_samples": class_support_samples[class_index]
            for class_index in class_counts
        }
    )
    ece = _expected_calibration_error(
        np.concatenate(ece_confidence) if ece_confidence else np.asarray([], dtype=np.float32),
        np.concatenate(ece_correct) if ece_correct else np.asarray([], dtype=np.float32),
    )
    selective_error_rate = non_abstained_errors / max(1.0, non_abstained_pixel_count)
    abstention_coverage_rate = non_abstained_pixel_count / max(1.0, valid_pixel_count)
    return {
        "bone_gate_threshold": float(gate_threshold),
        "abstention_threshold": float(abstention_threshold),
        "bone_gate_dice": float(np.mean(dice_values)),
        "bone_gate_precision": gate_true_positive / max(1.0, gate_true_positive + gate_false_positive),
        "bone_gate_recall": gate_true_positive / max(1.0, gate_true_positive + gate_false_negative),
        "bone_gate_oversegmentation_rate": gate_false_positive / max(1.0, gate_true_positive + gate_false_positive),
        "activity_score_mae": float(np.mean(mae_values)),
        "activity_mae": float(np.mean(mae_values)),
        "macro_dice": float(np.mean(list(per_class_dice.values()))),
        "low_activity_dice": per_class_dice["low_activity"],
        "transition_dice": per_class_dice["transition"],
        "high_activity_dice": per_class_dice["high_activity"],
        **class_support,
        "transition_recall": transition_true_positive / max(1.0, transition_true_positive + transition_false_negative),
        "ece": ece,
        "abstention_error_rate": non_abstained_errors / max(1.0, valid_pixel_count),
        "selective_error_rate": selective_error_rate,
        "abstention_coverage_rate": abstention_coverage_rate,
        "abstention_rate": 1.0 - abstention_coverage_rate,
        "non_abstained_pixel_count": non_abstained_pixel_count,
        "valid_pixel_count": valid_pixel_count,
        "bone_gate_containment_rate": contained_prediction_count / max(1.0, prediction_count),
        "class_accuracy": float(np.mean(accuracy_values)),
        "mean_uncertainty": float(np.mean(uncertainty_values)),
        "sample_count": float(len(cast(Sized, dataset))),
    }


def _select_validation_thresholds(
    model: BoneActivityMultiTask2D,
    dataset: Dataset[dict[str, torch.Tensor]],
    *,
    device: torch.device,
    safety_config: Mapping[str, Any],
) -> tuple[float, float, dict[str, float], dict[str, Any]]:
    default_gate_threshold = float(safety_config.get("bone_gate_threshold", 0.5))
    default_abstention_threshold = float(safety_config.get("abstention_threshold", 0.5))
    selection_config = _mapping(safety_config.get("threshold_selection"))
    enabled = _explicit_true(selection_config.get("enabled"))
    minimum_coverage_rate = float(selection_config.get("minimum_coverage_rate", 0.0))
    maximum_selective_error_rate = float(selection_config.get("maximum_selective_error_rate", 1.0))
    if not 0.0 <= minimum_coverage_rate <= 1.0:
        raise ValueError("minimum_coverage_rate must be within [0, 1]")
    if not 0.0 <= maximum_selective_error_rate <= 1.0:
        raise ValueError("maximum_selective_error_rate must be within [0, 1]")
    gate_candidates = _threshold_candidates(
        selection_config.get("bone_gate_candidates") if enabled else None,
        fallback=default_gate_threshold,
        field="bone_gate_candidates",
    )
    abstention_candidates = _threshold_candidates(
        selection_config.get("abstention_candidates") if enabled else None,
        fallback=default_abstention_threshold,
        field="abstention_candidates",
    )

    gate_scan: list[dict[str, float]] = []
    for threshold in gate_candidates:
        metrics = _evaluate(
            model,
            dataset,
            device=device,
            gate_threshold=threshold,
            abstention_threshold=default_abstention_threshold,
        )
        gate_scan.append(
            {
                "threshold": threshold,
                "bone_gate_dice": metrics["bone_gate_dice"],
                "bone_gate_precision": metrics["bone_gate_precision"],
                "bone_gate_recall": metrics["bone_gate_recall"],
                "bone_gate_oversegmentation_rate": metrics["bone_gate_oversegmentation_rate"],
            }
        )
    selected_gate = max(
        gate_scan,
        key=lambda item: (
            item["bone_gate_dice"],
            item["bone_gate_precision"],
            -abs(item["threshold"] - default_gate_threshold),
        ),
    )["threshold"]

    abstention_scan: list[dict[str, float]] = []
    metrics_by_abstention: dict[float, dict[str, float]] = {}
    for threshold in abstention_candidates:
        metrics = _evaluate(
            model,
            dataset,
            device=device,
            gate_threshold=selected_gate,
            abstention_threshold=threshold,
        )
        metrics_by_abstention[threshold] = metrics
        abstention_scan.append(
            {
                "threshold": threshold,
                "coverage_rate": metrics["abstention_coverage_rate"],
                "selective_error_rate": metrics["selective_error_rate"],
                "joint_non_abstained_error_rate": metrics["abstention_error_rate"],
            }
        )
    eligible = [
        item
        for item in abstention_scan
        if item["coverage_rate"] >= minimum_coverage_rate
        and item["selective_error_rate"] <= maximum_selective_error_rate
    ]
    if eligible:
        selected_abstention_entry = min(
            eligible,
            key=lambda item: (
                item["selective_error_rate"],
                -item["coverage_rate"],
                item["threshold"],
            ),
        )
        validation_constraints_passed = True
    else:
        selected_abstention_entry = min(abstention_scan, key=lambda item: item["threshold"])
        validation_constraints_passed = False
    selected_abstention = selected_abstention_entry["threshold"]
    validation_metrics = metrics_by_abstention[selected_abstention]
    evidence = {
        "enabled": enabled,
        "selection_split": "validation",
        "test_set_used_for_selection": False,
        "selection_rules": {
            "bone_gate": "maximize_dice_then_precision_then_default_proximity",
            "abstention": ("minimize_selective_error_subject_to_coverage_and_error_constraints_then_maximize_coverage"),
            "no_eligible_abstention_fallback": "lowest_threshold_most_conservative",
        },
        "selection_constraints": {
            "minimum_coverage_rate": minimum_coverage_rate,
            "maximum_selective_error_rate": maximum_selective_error_rate,
        },
        "defaults": {
            "bone_gate_threshold": default_gate_threshold,
            "abstention_threshold": default_abstention_threshold,
        },
        "validation_constraints_passed": validation_constraints_passed,
        "selected": {
            "bone_gate_threshold": selected_gate,
            "abstention_threshold": selected_abstention,
        },
        "bone_gate_scan": gate_scan,
        "abstention_scan": abstention_scan,
    }
    return selected_gate, selected_abstention, validation_metrics, evidence


def _threshold_candidates(value: Any, *, fallback: float, field: str) -> list[float]:
    raw_values = [fallback] if value is None else value
    if not isinstance(raw_values, list) or not raw_values:
        raise ValueError(f"{field} must be a non-empty list")
    candidates = sorted({float(item) for item in raw_values})
    if not all(np.isfinite(item) and 0.0 < item < 1.0 for item in candidates):
        raise ValueError(f"{field} values must be finite and within (0, 1)")
    return candidates


def _run_fail_closed_smoke(
    model: BoneActivityMultiTask2D,
    sample: dict[str, torch.Tensor],
    *,
    device: torch.device,
) -> dict[str, bool]:
    model.eval()
    with torch.no_grad():
        outputs = model(sample["white"][None].to(device), sample["fluorescence"][None].to(device))
    unreviewed = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=None,
        physician_reviewed_bone_gate=False,
        target_domain=True,
    )
    proxy = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=sample["bone_gate"][None].to(device),
        physician_reviewed_bone_gate=True,
        target_domain=False,
    )
    return {
        "bone_gate_fail_closed_passed": bool(unreviewed["abstention_mask"].all())
        and unreviewed["spatial_candidates_available"] is False,
        "abstention_passed": bool(proxy["abstention_mask"].all()) and proxy["spatial_candidates_available"] is False,
    }


def _load_manifest_training_data(
    data_config: Mapping[str, Any],
    *,
    image_shape: tuple[int, int],
) -> tuple[Path, list[dict[str, str]], ProxySplit, dict[str, Any]]:
    del image_shape
    manifest_value = str(data_config.get("manifest_path") or "").strip()
    if not manifest_value:
        raise ValueError("data.manifest_path is required when data.mode=manifest")
    manifest_path = resolve_path(manifest_value)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    expected_manifest_sha = str(data_config.get("manifest_sha256") or "").strip().lower()
    if len(expected_manifest_sha) != 64:
        raise ValueError("data.manifest_sha256 is required when data.mode=manifest")
    if _sha256_file(manifest_path) != expected_manifest_sha:
        raise ValueError("Bone-activity training manifest SHA256 mismatch")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [{str(key): str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]
    if not rows:
        raise ValueError("Bone-activity training manifest has no rows")
    expected = {
        "training_scope": str(data_config.get("expected_training_scope") or "").strip(),
        "domain_tier": str(data_config.get("expected_domain_tier") or "").strip(),
        "channel_semantics": str(data_config.get("expected_channel_semantics") or "").strip(),
    }
    if any(not value for value in expected.values()):
        raise ValueError("Manifest mode requires expected training scope, domain tier, and channel semantics")
    required = {
        "sample_id",
        "patient_group_id",
        "case_id",
        "split",
        "target_domain",
        "training_eligible",
        "physician_reviewed_bone_gate",
        "runtime_replacement_allowed",
        "source_case_id",
        "source_sequence_id",
        "source_frame_id",
        "source_image_member",
        "source_mask_member",
        "source_asset_sha256",
        "source_mask_asset_sha256",
        *ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS["white"],
        *ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS["fluorescence"],
        *ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS["bone_gate"],
        *ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS["activity_score"],
        *ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS["class_target"],
        *ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS["uncertainty"],
    }
    missing_columns = sorted(required - set(rows[0]))
    if missing_columns:
        raise ValueError(f"Bone-activity training manifest columns missing: {missing_columns}")
    seen_samples: set[str] = set()
    for row in rows:
        sample_id = row["sample_id"].strip()
        if not sample_id or sample_id in seen_samples:
            raise ValueError(f"Duplicate or missing bone-activity sample_id: {sample_id or 'missing'}")
        seen_samples.add(sample_id)
        if row["split"] not in {"train", "val", "test"}:
            raise ValueError(f"Invalid bone-activity split: {row['split']}")
        if not row["patient_group_id"].strip():
            raise ValueError("Bone-activity patient_group_id is required")
        if not row["case_id"].strip():
            raise ValueError("Bone-activity case_id is required")
        if not _explicit_true(row["training_eligible"]):
            raise ValueError(f"Bone-activity proxy row is not training eligible: {sample_id}")
        if not _explicit_false(row["target_domain"]):
            raise ValueError("Proxy trainer only accepts rows explicitly marked target_domain=false")
        if not _explicit_false(row["physician_reviewed_bone_gate"]):
            raise ValueError("Proxy trainer requires physician_reviewed_bone_gate=false")
        if not _explicit_false(row["runtime_replacement_allowed"]):
            raise ValueError("Proxy trainer requires runtime_replacement_allowed=false")
        for field, expected_value in expected.items():
            if row.get(field) != expected_value:
                raise ValueError(
                    f"Bone-activity manifest {field} mismatch for {sample_id}: "
                    f"{row.get(field)!r} != {expected_value!r}"
                )
    split_indices = {
        split_name: [index for index, row in enumerate(rows) if row["split"] == split_name]
        for split_name in ("train", "val", "test")
    }
    if any(not indices for indices in split_indices.values()):
        raise ValueError("Bone-activity manifest requires non-empty train, val, and test splits")
    groups = {
        split_name: sorted({rows[index]["patient_group_id"] for index in indices})
        for split_name, indices in split_indices.items()
    }
    leakage = bool(
        set(groups["train"]) & set(groups["val"])
        or set(groups["train"]) & set(groups["test"])
        or set(groups["val"]) & set(groups["test"])
    )
    if leakage:
        raise ValueError("Bone-activity manifest patient-group leakage detected")
    _reject_cross_split_identity_overlap(
        rows,
        fields=(
            "case_id",
            "source_case_id",
            "source_sequence_id",
            "source_frame_id",
            "source_image_member",
            "source_mask_member",
            "source_asset_sha256",
            "source_mask_asset_sha256",
            *(sha_field for _, sha_field in ManifestBoneActivityDataset.REQUIRED_FILE_FIELDS.values()),
        ),
    )
    split = ProxySplit(
        train=split_indices["train"],
        val=split_indices["val"],
        test=split_indices["test"],
        patient_group_split={
            "leakage_detected": False,
            "case_overlap_detected": False,
            "asset_sha256_overlap_detected": False,
            "source_identity_overlap_detected": False,
            "strategy": "source_declared_patient_group_split",
            "groups": groups,
            "sample_counts": {name: len(indices) for name, indices in split_indices.items()},
        },
    )
    return manifest_path, rows, split, {"mode": "manifest", **expected}


def _group_split(sample_count: int, group_count: int) -> ProxySplit:
    if group_count < 5 or group_count > sample_count:
        raise ValueError("patient_group_count must be between 5 and sample_count")
    group_by_index = [min(group_count - 1, index * group_count // sample_count) for index in range(sample_count)]
    split_by_group = {
        group: "train" if group % 5 in {0, 1, 2} else "val" if group % 5 == 3 else "test"
        for group in range(group_count)
    }
    split_indices = {
        name: [index for index, group in enumerate(group_by_index) if split_by_group[group] == name]
        for name in ("train", "val", "test")
    }
    groups = {name: sorted({group_by_index[index] for index in indices}) for name, indices in split_indices.items()}
    leakage = bool(
        (set(groups["train"]) & set(groups["val"]))
        or (set(groups["train"]) & set(groups["test"]))
        or (set(groups["val"]) & set(groups["test"]))
    )
    if leakage or any(not split_indices[name] for name in split_indices):
        raise ValueError("Proxy patient-group split must be non-empty and leakage-free")
    return ProxySplit(
        train=split_indices["train"],
        val=split_indices["val"],
        test=split_indices["test"],
        patient_group_split={
            "leakage_detected": leakage,
            "strategy": "deterministic_proxy_patient_group_split",
            "groups": groups,
            "sample_counts": {name: len(indices) for name, indices in split_indices.items()},
        },
    )


def _image_shape(value: Any) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("data.image_shape must contain [height, width]")
    return int(value[0]), int(value[1])


def class_counts_for_batch(
    prediction: torch.Tensor,
    target: torch.Tensor,
    *,
    class_index: int,
) -> tuple[float, float, float]:
    valid = target != IGNORE_INDEX
    predicted = prediction == class_index
    truth = target == class_index
    return (
        float(torch.logical_and(predicted, truth).sum().item()),
        float(torch.logical_and(predicted, valid & ~truth).sum().item()),
        float(torch.logical_and(~predicted, truth).sum().item()),
    )


def _dice_from_counts(counts: tuple[float, float, float]) -> float:
    true_positive, false_positive, false_negative = counts
    denominator = 2.0 * true_positive + false_positive + false_negative
    return 0.0 if denominator == 0 else (2.0 * true_positive) / denominator


def _reject_cross_split_identity_overlap(
    rows: list[dict[str, str]],
    *,
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        splits_by_value: dict[str, set[str]] = {}
        for row in rows:
            value = str(row.get(field) or "").strip().lower()
            if not value:
                raise ValueError(f"Bone-activity manifest {field} is required")
            splits_by_value.setdefault(value, set()).add(row["split"])
        if any(len(splits) > 1 for splits in splits_by_value.values()):
            raise ValueError(f"Bone-activity manifest cross-split leakage detected for {field}")


def _expected_calibration_error(
    confidence: np.ndarray,
    correct: np.ndarray,
    *,
    bins: int = 10,
) -> float:
    if confidence.size == 0 or confidence.shape != correct.shape:
        return 1.0
    if not np.isfinite(confidence).all() or not np.isfinite(correct).all():
        return 1.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    value = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        selected = (confidence >= lower) & (confidence < upper if index < bins - 1 else confidence <= upper)
        if not np.any(selected):
            continue
        value += float(np.mean(selected)) * abs(
            float(np.mean(confidence[selected])) - float(np.mean(correct[selected]))
        )
    return float(value)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _explicit_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _explicit_false(value: Any) -> bool:
    return str(value).strip().lower() == "false"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _medical_boundary() -> str:
    return (
        "Synthetic non-target-domain proxy training only. The checkpoint cannot replace the competition mainline, "
        "cannot establish jaw-osteomyelitis clinical performance, and requires physician-reviewed bone gates."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/training/bone_activity_multitask_proxy_smoke.yml")
    return parser.parse_args()


def main() -> int:
    print(json.dumps(train_bone_activity_multitask(parse_args().config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
