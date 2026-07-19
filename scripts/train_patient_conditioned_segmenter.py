"""Train the bounded patient-conditioned dual-channel segmentation engineering model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
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
import yaml  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

from src.metrics.calibration import (  # noqa: E402
    binary_brier_score,
    expected_calibration_error,
    fit_binary_temperature,
    sigmoid_with_temperature,
)
from src.models.clinical_feature_vector import (  # noqa: E402
    build_clinical_feature_encoder_contract,
    unsupported_clinical_feature_names,
)
from src.models.patient_conditioned_segmenter import (  # noqa: E402
    TinyPatientConditionedSegmenter2D,
    apply_patient_conditioning_safety_gate,
)
from src.models.three_priority_promotion import evaluate_three_priority_model_promotion  # noqa: E402

MANIFEST_REQUIRED_COLUMNS = {
    "sample_id",
    "patient_group_id",
    "split",
    "white_path",
    "white_sha256",
    "white_size_bytes",
    "fluorescence_path",
    "fluorescence_sha256",
    "fluorescence_size_bytes",
    "mask_path",
    "mask_sha256",
    "mask_size_bytes",
    "source_ct_affine_json",
    "source_ct_affine_sha256",
    "canonical_ct_affine_json",
    "canonical_ct_affine_sha256",
    "canonical_axis0_spacing_mm",
    "canonical_axis1_spacing_mm",
    "spacing_unit",
    "spacing_axis_contract",
    "clinical_values_json",
    "clinical_present_json",
    "clinical_mapping_json",
    "context_trusted",
    "target_domain",
    "training_eligible",
    "training_scope",
    "runtime_replacement_allowed",
    "domain_tier",
    "channel_semantics",
}
DEFAULT_MANIFEST_TRAINING_SCOPE = "non_target_proxy_pretraining"
DEFAULT_MANIFEST_DOMAIN_TIER = "kits23_abdominal_ct_public_proxy"
DEFAULT_MANIFEST_CHANNEL_SEMANTICS = "non_fluorescence_ct_proxy"


class PatientConditionedProxyDataset(
    Dataset[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ]
):
    def __init__(
        self,
        rows: list[dict[str, str]],
        *,
        feature_names: list[str],
        image_shape: tuple[int, int],
    ) -> None:
        self.rows = rows
        self.feature_names = feature_names
        self.image_shape = image_shape

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(
        self,
        index: int,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]:
        row = self.rows[index]
        height, width = self.image_shape
        with Image.open(row["white_path"]) as image:
            white = np.asarray(image.convert("RGB").resize((width, height)), dtype=np.uint8).copy()
        with Image.open(row["fluorescence_path"]) as image:
            fluorescence = np.asarray(image.convert("L").resize((width, height)), dtype=np.uint8).copy()
        with Image.open(row["mask_path"]) as image:
            mask = np.asarray(
                image.convert("L").resize((width, height), Image.Resampling.NEAREST),
                dtype=np.uint8,
            ).copy()
        values_by_name = json.loads(row["clinical_values_json"])
        present_by_name = json.loads(row["clinical_present_json"])
        values = np.asarray(
            [float(values_by_name.get(name, 0.0)) for name in self.feature_names],
            dtype=np.float32,
        )
        present = np.asarray(
            [bool(present_by_name.get(name, False)) for name in self.feature_names],
            dtype=np.bool_,
        )
        return (
            torch.from_numpy(white.transpose(2, 0, 1).astype(np.float32) / 255.0),
            torch.from_numpy(fluorescence[None].astype(np.float32) / 255.0),
            torch.from_numpy((mask > 0).astype(np.float32))[None],
            torch.from_numpy(values),
            torch.from_numpy(present),
            torch.tensor(row.get("context_trusted", "false").lower() == "true"),
        )


def train_patient_conditioned(
    config_path: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    config_file = Path(config_path).expanduser().resolve()
    config = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    if config.get("capability") != "patient_conditioned_segmentation":
        raise ValueError("Training config capability must be patient_conditioned_segmentation")
    _promotion_policy_path, promotion_policy, promotion_policy_evidence = _load_promotion_policy(
        config,
    )
    seed = int(config.get("seed", 20260718))
    _set_seed(seed)
    destination = Path(output_dir or config["output"]["directory"])
    if not destination.is_absolute():
        destination = ROOT / destination
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)

    feature_config = config["clinical_features"]
    feature_names = [str(value) for value in feature_config["names"]]
    unsupported_features = unsupported_clinical_feature_names(feature_names)
    if unsupported_features:
        raise ValueError(
            "Training config declares clinical features unsupported by the runtime vector contract: "
            + ", ".join(unsupported_features)
        )
    if len(feature_config["mean"]) != len(feature_names) or len(feature_config["scale"]) != len(feature_names):
        raise ValueError("Clinical feature names, mean, and scale must have equal lengths")
    feature_encoder_contract = build_clinical_feature_encoder_contract(feature_names)
    image_shape = tuple(int(value) for value in config.get("image_shape", [64, 64]))
    if len(image_shape) != 2:
        raise ValueError("image_shape must contain height and width")
    data_manifest_path, rows, data_source = _prepare_training_data(
        config,
        destination=destination,
        feature_names=feature_names,
        image_shape=(image_shape[0], image_shape[1]),
        seed=seed,
    )
    split_report = _patient_group_split_report(rows)
    split_rows = {split: [row for row in rows if row["split"] == split] for split in ("train", "val", "test")}
    if any(not split_rows[split] for split in split_rows):
        raise ValueError("Training requires non-empty train, val, and test splits")
    data_profile = _training_data_profile(rows)
    clinical_feature_source_evidence = _build_clinical_feature_source_evidence(
        rows,
        feature_names=feature_names,
        source_manifest_sha256=data_source["source_manifest_sha256"],
    )

    model_config = {
        "clinical_feature_count": len(feature_names),
        **dict(config.get("model") or {}),
        "clinical_mean": [float(value) for value in feature_config["mean"]],
        "clinical_scale": [float(value) for value in feature_config["scale"]],
    }
    device = torch.device(str(config.get("device", "cpu")))
    model = TinyPatientConditionedSegmenter2D(**model_config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config.get("learning_rate", 1e-3)),
        weight_decay=1e-4,
    )
    loss_config = _loss_configuration(config)
    dataset = PatientConditionedProxyDataset(
        split_rows["train"],
        feature_names=feature_names,
        image_shape=(image_shape[0], image_shape[1]),
    )
    loader = DataLoader(
        dataset,
        batch_size=int(config.get("batch_size", 4)),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    completed_batches, loss_history = _train_batches(
        model,
        optimizer,
        loader,
        device=device,
        max_batches=int(config.get("max_train_batches", 8)),
        loss_config=loss_config,
    )
    threshold_candidates = [
        float(value) for value in config.get("threshold_candidates", [config.get("threshold", 0.5)])
    ]
    threshold_selection = {
        str(candidate): evaluate_model(
            model,
            split_rows["val"],
            feature_names=feature_names,
            image_shape=(image_shape[0], image_shape[1]),
            device=device,
            threshold=candidate,
        )
        for candidate in threshold_candidates
    }
    threshold = max(
        threshold_candidates,
        key=lambda candidate: (
            threshold_selection[str(candidate)]["conditioned_dice"],
            threshold_selection[str(candidate)]["conditioned_iou"],
            -threshold_selection[str(candidate)]["oversegmentation"],
        ),
    )
    validation_metrics = threshold_selection[str(threshold)]
    test_metrics = evaluate_model(
        model,
        split_rows["test"],
        feature_names=feature_names,
        image_shape=(image_shape[0], image_shape[1]),
        device=device,
        threshold=threshold,
    )
    safety = evaluate_safety_gates(
        model,
        split_rows["test"],
        feature_names=feature_names,
        image_shape=(image_shape[0], image_shape[1]),
        device=device,
    )

    artifact_stem = (
        "patient_conditioned_manifest_proxy" if data_source["mode"] == "manifest" else "patient_conditioned_proxy_smoke"
    )
    checkpoint_path = destination / f"{artifact_stem}.pt"
    generated_at = datetime.now(UTC).isoformat()
    training_domain = {
        "target_domain": False,
        "domain": data_source["domain"],
        "domain_tier": data_source["domain_tier"],
        "data_mode": data_source["mode"],
        "training_eligible_source": data_source["training_eligible_source"],
        "training_scope": data_source["training_scope"],
        "channel_semantics": data_source["channel_semantics"],
    }
    medical_boundary = (
        "Non-target-domain proxy pretraining only; the auxiliary image channel is not fluorescence, "
        "physician review is required, and this checkpoint cannot replace the competition mainline model."
        if data_source["mode"] == "manifest"
        else (
            "Procedural non-target-domain engineering training only; physician review is required and "
            "the checkpoint cannot replace the competition mainline model."
        )
    )
    checkpoint_payload = {
        "capability": "patient_conditioned_segmentation",
        "model_id": "tiny_patient_conditioned_dual_channel_v1",
        "model_family": "patient_conditioned_segmenter",
        "model_config": model.model_config(),
        "clinical_feature_names": feature_names,
        "feature_encoder_contract": feature_encoder_contract,
        "state_dict": model.state_dict(),
        "threshold": threshold,
        "training_domain": training_domain,
        "training_data": {
            "mode": data_source["mode"],
            "source_manifest_path": str(data_manifest_path),
            "source_manifest_sha256": data_source["source_manifest_sha256"],
            "patient_group_split": split_report,
            "paired_image_mask_context": data_source["paired_image_mask_context"],
            "channel_semantics": data_source["channel_semantics"],
            "data_profile": data_profile,
        },
        "loss_config": loss_config,
        "clinical_data": {
            "paired_image_mask_context": data_source["paired_image_mask_context"],
            "feature_names": feature_names,
            "channel_semantics": data_source["channel_semantics"],
            "feature_encoder_contract": feature_encoder_contract,
            "clinical_feature_source_evidence": clinical_feature_source_evidence,
        },
        "validation": {"independent_test_set": False},
        "promotion_policy": promotion_policy_evidence,
        "runtime_allowed": False,
        "runtime_replacement_allowed": False,
        "engineering_ready": bool(all(safety.values())),
        "target_domain_promotion_ready": False,
        "medical_boundary": medical_boundary,
        "generated_at_utc": generated_at,
    }
    torch.save(checkpoint_payload, checkpoint_path)
    checkpoint_digest = _sha256(checkpoint_path)
    evidence_bundle = _write_patient_conditioned_evidence(
        destination / "promotion_evidence",
        model=model,
        all_rows=rows,
        validation_rows=split_rows["val"],
        test_rows=split_rows["test"],
        feature_names=feature_names,
        image_shape=(image_shape[0], image_shape[1]),
        device=device,
        threshold=threshold,
        checkpoint_sha256=checkpoint_digest,
        safety=safety,
        test_metrics=test_metrics,
        generated_at=generated_at,
        max_calibration_pixels=int(dict(config.get("calibration") or {}).get("max_pixels", 250_000)),
        seed=seed,
    )
    manifest = {
        "schema_version": "osteo-vision-patient-conditioned-training-v1",
        "capability": "patient_conditioned_segmentation",
        "model_id": checkpoint_payload["model_id"],
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_digest,
        "training_domain": checkpoint_payload["training_domain"],
        "training": {
            "completed": completed_batches == int(config.get("max_train_batches", 8)),
            "sample_count": len(rows),
            "train_sample_count": len(split_rows["train"]),
            "validation_sample_count": len(split_rows["val"]),
            "test_sample_count": len(split_rows["test"]),
            "completed_batches": completed_batches,
            "loss_history": loss_history,
            "patient_group_split": split_report,
            "data_manifest_path": str(data_manifest_path),
            "data_manifest_sha256": data_source["source_manifest_sha256"],
            "source_manifest_path": str(data_manifest_path),
            "source_manifest_sha256": data_source["source_manifest_sha256"],
            "data_mode": data_source["mode"],
            "domain_tier": data_source["domain_tier"],
            "training_scope": data_source["training_scope"],
            "channel_semantics": data_source["channel_semantics"],
            "loss_config": loss_config,
            "data_profile": data_profile,
        },
        "outputs": [
            "image_only_logits",
            "conditioned_logits",
            "delta_map",
            "uncertainty",
        ],
        "safety": {
            "zero_spatial_effect_fallback_passed": safety["zero_spatial_effect_fallback_passed"],
            "bounded_modulation_passed": safety["bounded_modulation_passed"],
            "restricted_spatial_effect_passed": safety["restricted_spatial_effect_passed"],
            "max_logit_delta": model.max_logit_delta,
            "missing_or_untrusted_context_policy": "force_delta_map_zero",
        },
        "validation": {
            "independent_test_set": False,
            "calibrated": False,
            "metrics": evidence_bundle["proxy_metrics"],
            "proxy_validation_metrics": validation_metrics,
            "proxy_test_metrics": test_metrics,
            "promotion_metrics_eligible": False,
            "selected_threshold": threshold,
            "threshold_selection_proxy": threshold_selection,
        },
        "review": {"physician_reviewed": False},
        "clinical_data": {
            "paired_image_mask_context": data_source["paired_image_mask_context"],
            "feature_names": feature_names,
            "channel_semantics": data_source["channel_semantics"],
            "feature_encoder_contract": feature_encoder_contract,
            "clinical_feature_source_evidence": clinical_feature_source_evidence,
        },
        "subgroup_audit": {
            "passed": False,
            "report_path": evidence_bundle["evidence"]["subgroup_report"]["path"],
            "reason_codes": evidence_bundle["subgroup_reason_codes"],
        },
        "evidence": evidence_bundle["evidence"],
        "engineering_ready": bool(
            completed_batches == int(config.get("max_train_batches", 8)) and all(safety.values())
        ),
        "target_domain_promotion_ready": False,
        "runtime_allowed": False,
        "clinical_claim_allowed": False,
        "generated_at_utc": generated_at,
        "medical_boundary": checkpoint_payload["medical_boundary"],
        "promotion_policy": promotion_policy_evidence,
    }
    promotion = evaluate_three_priority_model_promotion(manifest, policy=promotion_policy)
    manifest["promotion_policy"]["normalized_content_sha256"] = promotion["policy_sha256"]
    manifest["engineering_ready"] = promotion["engineering_ready"]
    manifest["target_domain_promotion_ready"] = promotion["target_domain_promotion_ready"]
    manifest["runtime_replacement_allowed"] = promotion["runtime_replacement_allowed"]
    manifest["promotion"] = promotion
    if manifest["engineering_ready"] is not True or manifest["target_domain_promotion_ready"] is not False:
        raise RuntimeError("Proxy patient-conditioned manifest violated the engineering-only promotion gate")
    manifest_path = destination / f"{artifact_stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        **manifest,
    }


def _load_promotion_policy(
    config: dict[str, Any],
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    value = str(config.get("promotion_policy_path") or "").strip()
    if not value:
        raise ValueError("promotion_policy_path is required")
    policy_path = Path(value).expanduser()
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    policy_path = policy_path.resolve()
    if not policy_path.is_file():
        raise FileNotFoundError(f"Promotion policy not found: {policy_path}")
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise ValueError("Promotion policy must be a YAML mapping")
    schema_version = str(policy.get("schema_version") or "").strip()
    status = str(policy.get("status") or "").strip()
    if not schema_version or not status:
        raise ValueError("Promotion policy requires schema_version and status")
    evidence = {
        "path": str(policy_path),
        "sha256": _sha256(policy_path),
        "schema_version": schema_version,
        "status": status,
    }
    return policy_path, policy, evidence


def _prepare_training_data(
    config: dict[str, Any],
    *,
    destination: Path,
    feature_names: list[str],
    image_shape: tuple[int, int],
    seed: int,
) -> tuple[Path, list[dict[str, str]], dict[str, Any]]:
    data_config = dict(config.get("data") or {})
    mode = str(data_config.get("mode") or "synthetic").strip().lower()
    if mode == "synthetic":
        proxy_config = dict(config.get("proxy_smoke") or {})
        data_manifest_path = generate_proxy_smoke_dataset(
            destination / "proxy_data",
            feature_names=feature_names,
            image_shape=image_shape,
            group_counts=dict(proxy_config["group_counts"]),
            samples_per_group=int(proxy_config.get("samples_per_group", 2)),
            seed=seed,
        )
        rows = _read_rows(data_manifest_path)
        source = {
            "mode": mode,
            "domain": "procedural_dual_channel_clinical_proxy",
            "domain_tier": "synthetic_proxy",
            "training_eligible_source": False,
            "training_scope": "engineering_smoke_only",
            "channel_semantics": "procedural_fluorescence_proxy",
            "paired_image_mask_context": False,
            "source_manifest_sha256": _sha256(data_manifest_path),
        }
        return data_manifest_path, rows, source
    if mode != "manifest":
        raise ValueError("data.mode must be synthetic or manifest")

    manifest_value = str(data_config.get("manifest_path") or "").strip()
    if not manifest_value:
        raise ValueError("data.manifest_path is required when data.mode=manifest")
    data_manifest_path = Path(manifest_value).expanduser()
    if not data_manifest_path.is_absolute():
        data_manifest_path = ROOT / data_manifest_path
    data_manifest_path = data_manifest_path.resolve()
    if not data_manifest_path.is_file():
        raise FileNotFoundError(f"Training data manifest not found: {data_manifest_path}")

    expected = {
        "training_scope": str(data_config.get("expected_training_scope") or DEFAULT_MANIFEST_TRAINING_SCOPE),
        "domain_tier": str(data_config.get("expected_domain_tier") or DEFAULT_MANIFEST_DOMAIN_TIER),
        "channel_semantics": str(data_config.get("expected_channel_semantics") or DEFAULT_MANIFEST_CHANNEL_SEMANTICS),
    }
    rows = _read_rows(data_manifest_path)
    normalized_rows = _validate_manifest_rows(
        data_manifest_path,
        rows,
        feature_names=feature_names,
        expected=expected,
    )
    source = {
        "mode": mode,
        "domain": expected["domain_tier"],
        "domain_tier": expected["domain_tier"],
        "training_eligible_source": True,
        "training_scope": expected["training_scope"],
        "channel_semantics": expected["channel_semantics"],
        "paired_image_mask_context": True,
        "source_manifest_sha256": _sha256(data_manifest_path),
    }
    return data_manifest_path, normalized_rows, source


def _validate_manifest_rows(
    manifest_path: Path,
    rows: list[dict[str, str]],
    *,
    feature_names: list[str],
    expected: dict[str, str],
) -> list[dict[str, str]]:
    if not rows:
        raise ValueError("Manifest training CSV contains no samples")
    missing_columns = MANIFEST_REQUIRED_COLUMNS - set(rows[0])
    if missing_columns:
        raise ValueError(f"Manifest training CSV is missing columns: {sorted(missing_columns)}")

    normalized: list[dict[str, str]] = []
    sample_ids: set[str] = set()
    for row_number, source_row in enumerate(rows, start=2):
        row = dict(source_row)
        sample_id = str(row.get("sample_id") or "").strip()
        patient_group_id = str(row.get("patient_group_id") or "").strip()
        if not sample_id or not patient_group_id:
            raise ValueError(f"Manifest row {row_number} requires sample_id and patient_group_id")
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate sample_id in manifest: {sample_id}")
        sample_ids.add(sample_id)
        split = str(row.get("split") or "").strip().lower()
        if split not in {"train", "val", "test"}:
            raise ValueError(f"Manifest row {row_number} has unsupported split: {split!r}")
        row["sample_id"] = sample_id
        row["patient_group_id"] = patient_group_id
        row["split"] = split

        if _strict_bool(row.get("target_domain"), field="target_domain"):
            raise ValueError(f"Manifest row {row_number} must remain target_domain=false")
        if not _strict_bool(row.get("training_eligible"), field="training_eligible"):
            raise ValueError(f"Manifest row {row_number} must set training_eligible=true")
        if _strict_bool(
            row.get("runtime_replacement_allowed"),
            field="runtime_replacement_allowed",
        ):
            raise ValueError(f"Manifest row {row_number} must keep runtime_replacement_allowed=false")
        _strict_bool(row.get("context_trusted"), field="context_trusted")
        for field, required_value in expected.items():
            actual = str(row.get(field) or "").strip()
            if actual != required_value:
                raise ValueError(f"Manifest row {row_number} requires {field}={required_value!r}, got {actual!r}")

        values = _json_mapping(
            row.get("clinical_values_json"),
            field="clinical_values_json",
            row_number=row_number,
        )
        present = _json_mapping(
            row.get("clinical_present_json"),
            field="clinical_present_json",
            row_number=row_number,
        )
        mapping = _json_mapping(
            row.get("clinical_mapping_json"),
            field="clinical_mapping_json",
            row_number=row_number,
        )
        for name in feature_names:
            if name not in present or not isinstance(present[name], bool):
                raise ValueError(f"Manifest row {row_number} requires boolean presence for clinical feature {name!r}")
            source_description = mapping.get(name)
            if not isinstance(source_description, str) or not source_description.strip():
                raise ValueError(
                    f"Manifest row {row_number} requires a non-empty source description "
                    f"for clinical feature {name!r}"
                )
            if present[name]:
                try:
                    value = float(values[name])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Manifest row {row_number} requires a numeric value for present feature {name!r}"
                    ) from exc
                if not math.isfinite(value):
                    raise ValueError(f"Manifest row {row_number} has a non-finite value for feature {name!r}")
        row["clinical_values_json"] = _compact_json(values)
        row["clinical_present_json"] = _compact_json(present)
        row["clinical_mapping_json"] = _compact_json({name: str(mapping[name]).strip() for name in feature_names})

        resolved_paths: dict[str, Path] = {}
        for role in ("white", "fluorescence", "mask"):
            field = f"{role}_path"
            path = Path(str(row.get(field) or "").strip()).expanduser()
            if not path.is_absolute():
                path = manifest_path.parent / path
            path = path.resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Manifest row {row_number} {field} does not exist: {path}")
            expected_size = _strict_positive_integer(
                row.get(f"{role}_size_bytes"),
                field=f"{role}_size_bytes",
                row_number=row_number,
            )
            actual_size = path.stat().st_size
            if actual_size != expected_size:
                raise ValueError(
                    f"Manifest row {row_number} {role} size mismatch: " f"expected {expected_size}, got {actual_size}"
                )
            expected_sha256 = _strict_sha256(
                row.get(f"{role}_sha256"),
                field=f"{role}_sha256",
                row_number=row_number,
            )
            actual_sha256 = _sha256(path)
            if actual_sha256 != expected_sha256:
                raise ValueError(
                    f"Manifest row {row_number} {role} SHA256 mismatch: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            row[field] = str(path)
            row[f"{role}_sha256"] = expected_sha256
            row[f"{role}_size_bytes"] = str(expected_size)
            resolved_paths[role] = path
        _validate_manifest_images(resolved_paths, row_number=row_number)
        _validate_spatial_provenance(row, row_number=row_number)
        normalized.append(row)
    return normalized


def _validate_manifest_images(paths: dict[str, Path], *, row_number: int) -> None:
    try:
        with Image.open(paths["white"]) as image:
            image.load()
            white_size = image.size
        with Image.open(paths["fluorescence"]) as image:
            image.load()
            fluorescence_size = image.size
        with Image.open(paths["mask"]) as image:
            mask = np.asarray(image.convert("L"), dtype=np.uint8)
            mask_size = image.size
    except (OSError, ValueError) as exc:
        raise ValueError(f"Manifest row {row_number} contains an unreadable image") from exc
    if white_size != fluorescence_size or white_size != mask_size:
        raise ValueError(
            f"Manifest row {row_number} image dimensions mismatch: "
            f"white={white_size}, fluorescence={fluorescence_size}, mask={mask_size}"
        )
    values = set(int(value) for value in np.unique(mask))
    if not (values.issubset({0, 1}) or values.issubset({0, 255})):
        raise ValueError(f"Manifest row {row_number} mask must be binary 0/1 or 0/255, got {sorted(values)}")


def _strict_positive_integer(value: Any, *, field: str, row_number: int) -> int:
    token = str(value or "").strip()
    try:
        parsed = int(token)
    except ValueError as exc:
        raise ValueError(f"Manifest row {row_number} {field} must be a positive integer") from exc
    if parsed <= 0 or str(parsed) != token:
        raise ValueError(f"Manifest row {row_number} {field} must be a positive integer")
    return parsed


def _strict_sha256(value: Any, *, field: str, row_number: int) -> str:
    token = str(value or "").strip().lower()
    if len(token) != 64 or any(character not in "0123456789abcdef" for character in token):
        raise ValueError(f"Manifest row {row_number} {field} must be a 64-character SHA256")
    return token


def _validate_spatial_provenance(row: dict[str, str], *, row_number: int) -> None:
    affines: dict[str, np.ndarray] = {}
    for prefix in ("source_ct", "canonical_ct"):
        field = f"{prefix}_affine_json"
        try:
            payload = json.loads(str(row.get(field) or ""))
            affine = np.asarray(payload, dtype=np.float64)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"Manifest row {row_number} {field} must contain a finite 4x4 affine") from exc
        if affine.shape != (4, 4) or not np.isfinite(affine).all():
            raise ValueError(f"Manifest row {row_number} {field} must contain a finite 4x4 affine")
        if not np.allclose(affine[3], np.asarray([0.0, 0.0, 0.0, 1.0]), rtol=0.0, atol=1e-9):
            raise ValueError(f"Manifest row {row_number} {field} must be a homogeneous affine")
        canonical_json = json.dumps(
            affine.tolist(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        expected_sha256 = _strict_sha256(
            row.get(f"{prefix}_affine_sha256"),
            field=f"{prefix}_affine_sha256",
            row_number=row_number,
        )
        actual_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"Manifest row {row_number} {prefix} affine SHA256 mismatch: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        row[field] = canonical_json
        row[f"{prefix}_affine_sha256"] = expected_sha256
        affines[prefix] = affine

    for axis in (0, 1):
        field = f"canonical_axis{axis}_spacing_mm"
        try:
            value = float(row.get(field) or "")
        except ValueError as exc:
            raise ValueError(f"Manifest row {row_number} {field} must be finite and positive") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Manifest row {row_number} {field} must be finite and positive")
        affine_spacing = float(np.linalg.norm(affines["canonical_ct"][:3, axis]))
        if not math.isclose(value, affine_spacing, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(
                f"Manifest row {row_number} {field} does not match canonical affine: "
                f"declared {value}, affine {affine_spacing}"
            )
        row[field] = format(value, ".17g")
    if str(row.get("spacing_unit") or "").strip() != "mm":
        raise ValueError(f"Manifest row {row_number} spacing_unit must be 'mm'")
    if str(row.get("spacing_axis_contract") or "").strip() != "array_axis0_rows;array_axis1_columns":
        raise ValueError(f"Manifest row {row_number} spacing_axis_contract is unsupported")


def _json_mapping(value: Any, *, field: str, row_number: int) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Manifest row {row_number} has invalid {field} JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest row {row_number} {field} must be a JSON object")
    return payload


def _build_clinical_feature_source_evidence(
    rows: list[dict[str, str]],
    *,
    feature_names: list[str],
    source_manifest_sha256: str,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Clinical feature source evidence requires at least one training row")
    source_manifest_digest = str(source_manifest_sha256).strip().lower()
    if len(source_manifest_digest) != 64 or any(
        character not in "0123456789abcdef" for character in source_manifest_digest
    ):
        raise ValueError("Clinical feature source evidence requires a valid source manifest SHA256")

    feature_sources: list[dict[str, Any]] = []
    for feature_name in feature_names:
        descriptions: set[str] = set()
        present_sample_count = 0
        present_patient_groups: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            mapping = _json_mapping(
                row.get("clinical_mapping_json"),
                field="clinical_mapping_json",
                row_number=row_number,
            )
            present = _json_mapping(
                row.get("clinical_present_json"),
                field="clinical_present_json",
                row_number=row_number,
            )
            source_description = mapping.get(feature_name)
            if not isinstance(source_description, str) or not source_description.strip():
                raise ValueError(
                    f"Manifest row {row_number} requires a non-empty source description "
                    f"for clinical feature {feature_name!r}"
                )
            descriptions.add(source_description.strip())
            present_value = present.get(feature_name)
            if not isinstance(present_value, bool):
                raise ValueError(
                    f"Manifest row {row_number} requires boolean presence for clinical feature {feature_name!r}"
                )
            if present_value:
                present_sample_count += 1
                patient_group_id = str(row.get("patient_group_id") or "").strip()
                if not patient_group_id:
                    raise ValueError(f"Manifest row {row_number} requires patient_group_id")
                present_patient_groups.add(patient_group_id)
        if len(descriptions) != 1:
            raise ValueError(
                f"Clinical feature {feature_name!r} has inconsistent source descriptions: {sorted(descriptions)}"
            )
        source_description = next(iter(descriptions))
        feature_sources.append(
            {
                "feature_name": feature_name,
                "source_description": source_description,
                "source_description_sha256": hashlib.sha256(source_description.encode("utf-8")).hexdigest(),
                "present_sample_count": present_sample_count,
                "missing_sample_count": len(rows) - present_sample_count,
                "present_patient_group_count": len(present_patient_groups),
            }
        )

    evidence: dict[str, Any] = {
        "schema_version": "osteo-vision-clinical-feature-source-evidence-v1",
        "source_manifest_sha256": source_manifest_digest,
        "feature_names": list(feature_names),
        "source_fields": [
            "clinical_values_json",
            "clinical_present_json",
            "clinical_mapping_json",
        ],
        "feature_sources": feature_sources,
    }
    evidence["evidence_sha256"] = _canonical_json_sha256(evidence)
    return evidence


def _strict_bool(value: Any, *, field: str) -> bool:
    token = str(value or "").strip().lower()
    if token not in {"true", "false"}:
        raise ValueError(f"Manifest field {field} must be true or false, got {value!r}")
    return token == "true"


def generate_proxy_smoke_dataset(
    output_dir: str | Path,
    *,
    feature_names: list[str],
    image_shape: tuple[int, int],
    group_counts: dict[str, Any],
    samples_per_group: int,
    seed: int,
) -> Path:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, str]] = []
    group_number = 0
    for split in ("train", "val", "test"):
        for _ in range(int(group_counts.get(split, 0))):
            group_number += 1
            group_id = f"proxy-patient-{group_number:03d}"
            clinical = _proxy_clinical_values(rng, feature_names)
            for sample_index in range(samples_per_group):
                sample_id = f"{group_id}-{sample_index:02d}"
                white, fluorescence, mask = _proxy_images(
                    rng,
                    clinical,
                    height=image_shape[0],
                    width=image_shape[1],
                )
                white_path = root / f"{sample_id}_white.png"
                fluorescence_path = root / f"{sample_id}_fluorescence.png"
                mask_path = root / f"{sample_id}_mask.png"
                Image.fromarray(white).save(white_path)
                Image.fromarray(fluorescence).save(fluorescence_path)
                Image.fromarray(mask * 255).save(mask_path)
                rows.append(
                    {
                        "sample_id": sample_id,
                        "patient_group_id": group_id,
                        "group_id": group_id,
                        "split": split,
                        "white_path": str(white_path),
                        "fluorescence_path": str(fluorescence_path),
                        "mask_path": str(mask_path),
                        "clinical_values_json": json.dumps(clinical, ensure_ascii=False, sort_keys=True),
                        "clinical_present_json": json.dumps(
                            {name: True for name in feature_names},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "clinical_mapping_json": json.dumps(
                            {name: f"synthetic_proxy.generated.{name}" for name in feature_names},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "context_trusted": "true",
                        "target_domain": "false",
                        "physician_reviewed": "false",
                        "training_eligible": "false",
                        "domain_tier": "synthetic_proxy",
                    }
                )
    manifest_path = root / "patient_conditioned_proxy_samples.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest_path


def evaluate_model(
    model: TinyPatientConditionedSegmenter2D,
    rows: list[dict[str, str]],
    *,
    feature_names: list[str],
    image_shape: tuple[int, int],
    device: torch.device,
    threshold: float,
) -> dict[str, float]:
    dataset = PatientConditionedProxyDataset(rows, feature_names=feature_names, image_shape=image_shape)
    aggregates: dict[str, list[float]] = {
        "conditioned_dice": [],
        "conditioned_iou": [],
        "conditioned_recall": [],
        "conditioned_precision": [],
        "image_only_dice": [],
        "empty_mask": [],
        "oversegmentation": [],
        "uncertainty_mean": [],
        "delta_abs_mean": [],
        "conditioned_foreground_dice": [],
        "image_only_foreground_dice": [],
        "context_eligible": [],
        "clinical_effect_nonzero": [],
    }
    conditioned_global_counts = [0.0, 0.0, 0.0]
    image_global_counts = [0.0, 0.0, 0.0]
    model.eval()
    with torch.no_grad():
        for white, fluorescence, target, values, present, trusted in DataLoader(dataset, batch_size=1):
            output = model(
                white.to(device),
                fluorescence.to(device),
                values.to(device),
                present.to(device),
                context_trusted=trusted.to(device),
                conditioning_authorized=True,
            )
            truth = target.to(device) > 0.5
            conditioned = torch.sigmoid(output.conditioned_logits) >= threshold
            image_only = torch.sigmoid(output.image_only_logits) >= threshold
            conditioned_counts = _binary_counts(conditioned, truth)
            image_counts = _binary_counts(image_only, truth)
            for index, count in enumerate(conditioned_counts):
                conditioned_global_counts[index] += count
            for index, count in enumerate(image_counts):
                image_global_counts[index] += count
            aggregates["conditioned_dice"].append(_dice(conditioned_counts))
            aggregates["conditioned_iou"].append(_iou(conditioned_counts))
            aggregates["conditioned_recall"].append(
                conditioned_counts[0] / max(1.0, conditioned_counts[0] + conditioned_counts[2])
            )
            aggregates["conditioned_precision"].append(
                conditioned_counts[0] / max(1.0, conditioned_counts[0] + conditioned_counts[1])
            )
            aggregates["image_only_dice"].append(_dice(image_counts))
            predicted_fraction = float(conditioned.float().mean().item())
            true_fraction = float(truth.float().mean().item())
            aggregates["empty_mask"].append(float(predicted_fraction == 0.0))
            aggregates["oversegmentation"].append(float(predicted_fraction > max(0.05, true_fraction * 2.0)))
            aggregates["uncertainty_mean"].append(float(output.uncertainty.mean().item()))
            aggregates["delta_abs_mean"].append(float(output.delta_map.abs().mean().item()))
            aggregates["context_eligible"].append(float(output.context_eligible.float().mean().item()))
            aggregates["clinical_effect_nonzero"].append(float(torch.count_nonzero(output.delta_map).item() > 0))
            if true_fraction > 0:
                aggregates["conditioned_foreground_dice"].append(_dice(conditioned_counts))
                aggregates["image_only_foreground_dice"].append(_dice(image_counts))
    metrics = {key: float(np.mean(values)) if values else 0.0 for key, values in aggregates.items()}
    metrics["conditioned_global_dice"] = _dice(
        (conditioned_global_counts[0], conditioned_global_counts[1], conditioned_global_counts[2])
    )
    metrics["image_only_global_dice"] = _dice((image_global_counts[0], image_global_counts[1], image_global_counts[2]))
    metrics["conditioned_minus_image_only_dice"] = metrics["conditioned_dice"] - metrics["image_only_dice"]
    return metrics


def evaluate_safety_gates(
    model: TinyPatientConditionedSegmenter2D,
    rows: list[dict[str, str]],
    *,
    feature_names: list[str],
    image_shape: tuple[int, int],
    device: torch.device,
) -> dict[str, bool]:
    batch = next(
        iter(
            DataLoader(
                PatientConditionedProxyDataset(rows, feature_names=feature_names, image_shape=image_shape),
                batch_size=min(2, len(rows)),
            )
        )
    )
    white, fluorescence, target, values, present, _ = [item.to(device) for item in batch]
    model.eval()
    with torch.no_grad():
        untrusted = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=False,
            conditioning_authorized=True,
        )
        missing = model(
            white,
            fluorescence,
            values,
            torch.zeros_like(present),
            context_trusted=True,
            conditioning_authorized=True,
        )
        trusted = model(
            white,
            fluorescence,
            values,
            present,
            context_trusted=True,
            conditioning_authorized=True,
        )
        unpromoted = model(white, fluorescence, values, present, context_trusted=True)
        restricted = apply_patient_conditioning_safety_gate(
            trusted,
            reviewed_bone_gate=target,
            physician_reviewed_bone_gate=True,
            clinical_context_verified=True,
            target_domain=True,
            model_promotion_ready=True,
            uncertainty_threshold=0.01,
        )
        unreviewed_runtime = apply_patient_conditioning_safety_gate(
            trusted,
            reviewed_bone_gate=target,
            physician_reviewed_bone_gate=False,
            clinical_context_verified=True,
            target_domain=True,
            model_promotion_ready=True,
            uncertainty_threshold=0.01,
        )
    zero_effect = bool(
        torch.count_nonzero(untrusted.delta_map).item() == 0
        and torch.equal(untrusted.image_only_logits, untrusted.conditioned_logits)
        and torch.count_nonzero(missing.delta_map).item() == 0
        and torch.equal(missing.image_only_logits, missing.conditioned_logits)
        and torch.count_nonzero(unpromoted.delta_map).item() == 0
        and torch.equal(unpromoted.image_only_logits, unpromoted.conditioned_logits)
    )
    bounded = bool(float(trusted.delta_map.abs().max().item()) <= model.max_logit_delta + 1e-6)
    reviewed_gate = target > 0.5
    restricted_spatial_effect = bool(
        torch.count_nonzero(restricted["delta_map"][~reviewed_gate]).item() == 0
        and torch.equal(
            restricted["conditioned_logits"][~reviewed_gate],
            restricted["image_only_logits"][~reviewed_gate],
        )
        and torch.count_nonzero(restricted["difference_mask"][~reviewed_gate]).item() == 0
        and torch.count_nonzero(unreviewed_runtime["delta_map"]).item() == 0
        and unreviewed_runtime["available"] is False
    )
    return {
        "zero_spatial_effect_fallback_passed": zero_effect,
        "bounded_modulation_passed": bounded,
        "restricted_spatial_effect_passed": restricted_spatial_effect,
    }


def _write_patient_conditioned_evidence(
    output_dir: Path,
    *,
    model: TinyPatientConditionedSegmenter2D,
    all_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    test_rows: list[dict[str, str]],
    feature_names: list[str],
    image_shape: tuple[int, int],
    device: torch.device,
    threshold: float,
    checkpoint_sha256: str,
    safety: dict[str, bool],
    test_metrics: dict[str, float],
    generated_at: str,
    max_calibration_pixels: int,
    seed: int,
) -> dict[str, Any]:
    if max_calibration_pixels <= 0:
        raise ValueError("calibration.max_pixels must be positive")
    validation = _collect_prediction_evidence(
        model,
        validation_rows,
        feature_names=feature_names,
        image_shape=image_shape,
        device=device,
        threshold=threshold,
    )
    test = _collect_prediction_evidence(
        model,
        test_rows,
        feature_names=feature_names,
        image_shape=image_shape,
        device=device,
        threshold=threshold,
    )
    if not validation["all_outputs_finite"] or not test["all_outputs_finite"]:
        raise RuntimeError("Patient-conditioned promotion evidence contains non-finite outputs")

    validation_logits, validation_targets = _sample_calibration_pixels(
        validation["logits"],
        validation["targets"],
        max_pixels=max_calibration_pixels,
        seed=seed,
    )
    test_logits, test_targets = _sample_calibration_pixels(
        test["logits"],
        test["targets"],
        max_pixels=max_calibration_pixels,
        seed=seed + 1,
    )
    temperature_fit = fit_binary_temperature(
        validation_logits,
        validation_targets,
        max_samples=max_calibration_pixels,
        seed=seed,
    )
    temperature = float(temperature_fit["temperature"])
    test_uncalibrated = sigmoid_with_temperature(test_logits, 1.0)
    test_calibrated = sigmoid_with_temperature(test_logits, temperature)
    test_ece_before = expected_calibration_error(test_targets, test_uncalibrated)
    test_ece_after = expected_calibration_error(test_targets, test_calibrated)
    subgroup_report = _build_proxy_subgroup_report(
        test["records"],
        checkpoint_sha256=checkpoint_sha256,
        generated_at=generated_at,
    )
    split_manifest = _build_proxy_split_manifest(
        all_rows,
        checkpoint_sha256=checkpoint_sha256,
        generated_at=generated_at,
    )
    proxy_metrics = {
        "dice": float(test_metrics["conditioned_dice"]),
        "iou": float(test_metrics["conditioned_iou"]),
        "recall": float(test_metrics["conditioned_recall"]),
        "precision": float(test_metrics["conditioned_precision"]),
        "ece": float(test_ece_after["ece"]),
        "empty_mask_rate": float(test_metrics["empty_mask"]),
        "over_segmentation_rate": float(test_metrics["oversegmentation"]),
        "conditioned_minus_image_only_dice": float(test_metrics["conditioned_minus_image_only_dice"]),
        "worst_subgroup_dice_delta": float(subgroup_report["worst_subgroup_dice_delta"]),
        "context_fallback_success_rate": float(safety["zero_spatial_effect_fallback_passed"]),
    }
    boundary_values = [
        float(record["boundary_shift_mm"]) for record in test["records"] if record.get("boundary_shift_mm") is not None
    ]
    boundary_shift_available = len(boundary_values) == len(test["records"])
    if boundary_shift_available:
        proxy_metrics["max_boundary_shift_mm"] = max(boundary_values, default=0.0)
    payloads: dict[str, dict[str, Any]] = {
        "split_manifest": split_manifest,
        "prediction_manifest": {
            "schema_version": "osteo-vision-patient-conditioned-predictions-v1",
            "checkpoint_sha256": checkpoint_sha256,
            "generated_at_utc": generated_at,
            "split": "test",
            "record_count": len(test["records"]),
            "all_outputs_finite": test["all_outputs_finite"],
            "metrics": proxy_metrics,
            "physical_boundary_shift": {
                "available_for_all_records": boundary_shift_available,
                "metric": "symmetric_2d_boundary_hausdorff_distance",
                "unit": "mm",
                "empty_mask_policy": {
                    "both_empty": "zero_identical_boundaries",
                    "one_empty": "unavailable_fail_closed",
                },
            },
            "records": test["records"],
            "medical_boundary": (
                "Non-target-domain proxy predictions for output-integrity and evidence-contract validation only."
            ),
        },
        "calibration_report": {
            "schema_version": "osteo-vision-patient-conditioned-calibration-v1",
            "checkpoint_sha256": checkpoint_sha256,
            "generated_at_utc": generated_at,
            "calibrated": False,
            "ece": proxy_metrics["ece"],
            "proxy_calibration_computed": True,
            "target_domain_calibration_available": False,
            "fit_split": "validation_proxy",
            "test_split": "test_proxy",
            "fit": temperature_fit,
            "test": {
                "sampled_pixel_count": int(test_targets.size),
                "ece_before": float(test_ece_before["ece"]),
                "ece_after": float(test_ece_after["ece"]),
                "brier_before": binary_brier_score(test_targets, test_uncalibrated),
                "brier_after": binary_brier_score(test_targets, test_calibrated),
                "bins_before": test_ece_before["bins"],
                "bins_after": test_ece_after["bins"],
            },
            "failure_reasons": [
                "non_target_domain_proxy",
                "independent_target_domain_calibration_missing",
            ],
            "medical_boundary": (
                "Temperature scaling is computed on public proxy pixels and cannot authorize target-domain runtime use."
            ),
        },
        "subgroup_report": subgroup_report,
        "safety_report": {
            "schema_version": "osteo-vision-patient-conditioned-safety-v1",
            "checkpoint_sha256": checkpoint_sha256,
            "generated_at_utc": generated_at,
            "output_contract_passed": bool(test["all_outputs_finite"]),
            **safety,
            "test_record_count": len(test["records"]),
            "physical_boundary_shift_available": boundary_shift_available,
            "target_domain_safety_evidence_available": False,
            "medical_boundary": (
                "Engineering fail-closed checks passed on proxy data; target-domain physician-reviewed safety evidence remains required."
            ),
        },
        "physician_review": {
            "schema_version": "osteo-vision-patient-conditioned-physician-review-v1",
            "checkpoint_sha256": checkpoint_sha256,
            "generated_at_utc": generated_at,
            "role": "unavailable",
            "auth_source": "unavailable",
            "actor_id": None,
            "institution": None,
            "decision": "review_required",
            "trusted_physician_review_available": False,
            "medical_boundary": "No trusted physician acceptance is available for this proxy checkpoint.",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, dict[str, str]] = {}
    for name, payload in payloads.items():
        path = (output_dir / f"{name}.json").resolve()
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        evidence[name] = {"path": str(path), "sha256": _sha256(path)}
    return {
        "evidence": evidence,
        "proxy_metrics": proxy_metrics,
        "subgroup_reason_codes": list(subgroup_report["reason_codes"]),
    }


def _collect_prediction_evidence(
    model: TinyPatientConditionedSegmenter2D,
    rows: list[dict[str, str]],
    *,
    feature_names: list[str],
    image_shape: tuple[int, int],
    device: torch.device,
    threshold: float,
) -> dict[str, Any]:
    dataset = PatientConditionedProxyDataset(rows, feature_names=feature_names, image_shape=image_shape)
    records: list[dict[str, Any]] = []
    logits: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for row, batch in zip(rows, DataLoader(dataset, batch_size=1), strict=True):
            white, fluorescence, target, values, present, trusted = batch
            output = model(
                white.to(device),
                fluorescence.to(device),
                values.to(device),
                present.to(device),
                context_trusted=trusted.to(device),
                conditioning_authorized=True,
            )
            tensors = (
                output.image_only_logits,
                output.conditioned_logits,
                output.delta_map,
                output.uncertainty,
            )
            finite_outputs = bool(all(torch.isfinite(value).all().item() for value in tensors))
            record: dict[str, Any] = {
                "sample_id": row["sample_id"],
                "patient_group_id": row["patient_group_id"],
                "split": row["split"],
                "finite_outputs": finite_outputs,
                "target_domain": False,
                "physician_reviewed": False,
                "input_sha256": {role: _row_asset_sha256(row, role) for role in ("white", "fluorescence", "mask")},
                "subgroup_labels": _proxy_subgroup_labels(row, feature_names),
            }
            if finite_outputs:
                truth = target.to(device) > 0.5
                conditioned = torch.sigmoid(output.conditioned_logits) >= threshold
                image_only = torch.sigmoid(output.image_only_logits) >= threshold
                conditioned_counts = _binary_counts(conditioned, truth)
                image_counts = _binary_counts(image_only, truth)
                record.update(
                    {
                        "conditioned_dice": _dice(conditioned_counts),
                        "image_only_dice": _dice(image_counts),
                        "conditioned_minus_image_only_dice": _dice(conditioned_counts) - _dice(image_counts),
                        "predicted_foreground_fraction": float(conditioned.float().mean().item()),
                        "target_foreground_fraction": float(truth.float().mean().item()),
                        "uncertainty_mean": float(output.uncertainty.mean().item()),
                        "max_abs_delta": float(output.delta_map.abs().max().item()),
                    }
                )
                record.update(
                    _physical_boundary_shift_evidence(
                        row,
                        conditioned[0, 0].detach().cpu().numpy(),
                        image_only[0, 0].detach().cpu().numpy(),
                        image_shape=image_shape,
                    )
                )
                logits.append(output.conditioned_logits.detach().cpu().numpy().astype(np.float32).reshape(-1))
                targets.append(truth.detach().cpu().numpy().astype(np.float32).reshape(-1))
            records.append(record)
    return {
        "records": records,
        "all_outputs_finite": bool(records and all(record["finite_outputs"] for record in records)),
        "logits": np.concatenate(logits) if logits else np.asarray([], dtype=np.float32),
        "targets": np.concatenate(targets) if targets else np.asarray([], dtype=np.float32),
    }


def _sample_calibration_pixels(
    logits: np.ndarray,
    targets: np.ndarray,
    *,
    max_pixels: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    flat_logits = np.asarray(logits, dtype=np.float32).reshape(-1)
    flat_targets = np.asarray(targets, dtype=np.float32).reshape(-1)
    if flat_logits.size == 0 or flat_logits.size != flat_targets.size:
        raise RuntimeError("Calibration evidence requires finite paired logits and targets")
    if flat_logits.size <= max_pixels:
        return flat_logits, flat_targets
    indexes = np.random.default_rng(seed).choice(flat_logits.size, size=max_pixels, replace=False)
    return flat_logits[indexes], flat_targets[indexes]


def _physical_boundary_shift_evidence(
    row: dict[str, str],
    conditioned_mask: np.ndarray,
    image_only_mask: np.ndarray,
    *,
    image_shape: tuple[int, int],
) -> dict[str, Any]:
    required = ("canonical_axis0_spacing_mm", "canonical_axis1_spacing_mm")
    if any(not str(row.get(field) or "").strip() for field in required):
        return {
            "boundary_shift_mm": None,
            "boundary_shift_status": "spacing_unavailable",
            "model_pixel_spacing_mm": None,
        }
    with Image.open(row["white_path"]) as image:
        source_width, source_height = image.size
    model_height, model_width = image_shape
    row_spacing = float(row["canonical_axis0_spacing_mm"]) * source_height / model_height
    column_spacing = float(row["canonical_axis1_spacing_mm"]) * source_width / model_width
    distance, status = _symmetric_boundary_hausdorff_mm(
        np.asarray(conditioned_mask, dtype=np.bool_),
        np.asarray(image_only_mask, dtype=np.bool_),
        row_spacing_mm=row_spacing,
        column_spacing_mm=column_spacing,
    )
    return {
        "boundary_shift_mm": distance,
        "boundary_shift_status": status,
        "model_pixel_spacing_mm": {
            "row_axis0": row_spacing,
            "column_axis1": column_spacing,
        },
        "source_affine_sha256": row.get("source_ct_affine_sha256"),
        "canonical_affine_sha256": row.get("canonical_ct_affine_sha256"),
    }


def _symmetric_boundary_hausdorff_mm(
    first: np.ndarray,
    second: np.ndarray,
    *,
    row_spacing_mm: float,
    column_spacing_mm: float,
) -> tuple[float | None, str]:
    if first.shape != second.shape or first.ndim != 2:
        raise ValueError("Boundary-shift masks must be paired two-dimensional arrays")
    first_positive = bool(np.any(first))
    second_positive = bool(np.any(second))
    if not first_positive and not second_positive:
        return 0.0, "both_empty_identical"
    if first_positive != second_positive:
        return None, "one_mask_empty_unavailable"
    spacing = np.asarray([row_spacing_mm, column_spacing_mm], dtype=np.float64)
    if not np.isfinite(spacing).all() or np.any(spacing <= 0):
        raise ValueError("Boundary-shift spacing must be finite and positive")
    first_points = np.argwhere(_binary_boundary(first)).astype(np.float64) * spacing
    second_points = np.argwhere(_binary_boundary(second)).astype(np.float64) * spacing
    if first_points.size == 0 or second_points.size == 0:
        return None, "boundary_extraction_unavailable"
    forward = _directed_boundary_distance_mm(first_points, second_points)
    reverse = _directed_boundary_distance_mm(second_points, first_points)
    return float(max(forward, reverse)), "available"


def _binary_boundary(mask: np.ndarray) -> np.ndarray:
    value = np.asarray(mask, dtype=np.bool_)
    padded = np.pad(value, 1, mode="constant", constant_values=False)
    height, width = value.shape
    neighborhoods = [
        padded[1 + row_offset : 1 + row_offset + height, 1 + column_offset : 1 + column_offset + width]
        for row_offset in (-1, 0, 1)
        for column_offset in (-1, 0, 1)
    ]
    eroded = np.logical_and.reduce(neighborhoods)
    return np.logical_and(value, np.logical_not(eroded))


def _directed_boundary_distance_mm(source: np.ndarray, target: np.ndarray) -> float:
    maximum_nearest_squared = 0.0
    for start in range(0, len(source), 128):
        difference = source[start : start + 128, None, :] - target[None, :, :]
        nearest_squared = np.min(np.sum(np.square(difference), axis=2), axis=1)
        maximum_nearest_squared = max(maximum_nearest_squared, float(np.max(nearest_squared)))
    return math.sqrt(maximum_nearest_squared)


def _build_proxy_subgroup_report(
    records: list[dict[str, Any]],
    *,
    checkpoint_sha256: str,
    generated_at: str,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for feature, label in dict(record.get("subgroup_labels") or {}).items():
            groups.setdefault(f"{feature}:{label}", []).append(record)
    subgroup_rows: list[dict[str, Any]] = []
    for name, members in sorted(groups.items()):
        conditioned = [float(member["conditioned_dice"]) for member in members]
        image_only = [float(member["image_only_dice"]) for member in members]
        subgroup_rows.append(
            {
                "subgroup": name,
                "sample_count": len(members),
                "patient_group_count": len({str(member["patient_group_id"]) for member in members}),
                "conditioned_dice": float(np.mean(conditioned)),
                "image_only_dice": float(np.mean(image_only)),
                "conditioned_minus_image_only_dice": float(np.mean(conditioned) - np.mean(image_only)),
            }
        )
    if not subgroup_rows:
        raise RuntimeError("Subgroup evidence requires at least one declared proxy subgroup")
    patient_group_count = len({str(record["patient_group_id"]) for record in records})
    reason_codes = ["non_target_domain_proxy", "institution_and_time_independence_missing"]
    if patient_group_count < 2:
        reason_codes.append("insufficient_distinct_test_patient_groups")
    return {
        "schema_version": "osteo-vision-patient-conditioned-subgroup-v1",
        "checkpoint_sha256": checkpoint_sha256,
        "generated_at_utc": generated_at,
        "passed": False,
        "proxy_audit_computed": True,
        "patient_group_count": patient_group_count,
        "subgroups": subgroup_rows,
        "worst_subgroup_dice_delta": min(float(row["conditioned_minus_image_only_dice"]) for row in subgroup_rows),
        "reason_codes": reason_codes,
        "medical_boundary": (
            "Proxy subgroup statistics cannot establish no-harm across target-domain clinical subgroups."
        ),
    }


def _build_proxy_split_manifest(
    rows: list[dict[str, str]],
    *,
    checkpoint_sha256: str,
    generated_at: str,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for row in rows:
        patient_group_id = str(row["patient_group_id"])
        dataset_id = str(row.get("source_dataset_id") or "procedural_proxy")
        split = "validation" if row["split"] == "val" else row["split"]
        records.append(
            {
                "sample_id": row["sample_id"],
                "split": split,
                "patient_id": patient_group_id,
                "case_id": str(row.get("source_case_id") or patient_group_id),
                "source_asset_sha256": _row_asset_sha256(row, "white"),
                "institution_id": str(row.get("institution_id") or f"public_source_{dataset_id}"),
                "acquisition_period": str(row.get("acquisition_period") or "public_release_unverified"),
                "target_domain": False,
                "admitted": _row_bool(row, "training_eligible"),
                "physician_reviewed": _row_bool(row, "physician_reviewed"),
            }
        )
    return {
        "schema_version": "osteo-vision-patient-conditioned-split-v1",
        "checkpoint_sha256": checkpoint_sha256,
        "generated_at_utc": generated_at,
        "records": records,
        "patient_group_leakage_detected": False,
        "institution_independent": False,
        "time_independent": False,
        "medical_boundary": (
            "Public proxy records retain their single-source and unverified-acquisition-period limitations."
        ),
    }


def _proxy_subgroup_labels(row: dict[str, str], feature_names: list[str]) -> dict[str, str]:
    values = _json_mapping(
        row.get("clinical_values_json"),
        field="clinical_values_json",
        row_number=0,
    )
    present = _json_mapping(
        row.get("clinical_present_json"),
        field="clinical_present_json",
        row_number=0,
    )
    labels: dict[str, str] = {}
    for name in feature_names:
        if present.get(name) is not True or name not in values:
            labels[name] = "missing"
            continue
        value = float(values[name])
        if name == "age_years":
            labels[name] = "under_45" if value < 45 else "45_to_64" if value < 65 else "65_plus"
        elif name == "sex_at_birth_female":
            labels[name] = "female" if value >= 0.5 else "male"
        elif "egfr" in name.lower():
            labels[name] = "below_60" if value < 60 else "60_or_higher"
        elif value in {0.0, 1.0}:
            labels[name] = "present" if value >= 0.5 else "absent"
        else:
            labels[name] = "available_numeric"
    return labels


def _row_asset_sha256(row: dict[str, str], role: str) -> str:
    declared = str(row.get(f"{role}_sha256") or "").strip().lower()
    if declared:
        return declared
    return _sha256(Path(row[f"{role}_path"]).resolve())


def _row_bool(row: dict[str, str], field: str) -> bool:
    return str(row.get(field) or "false").strip().lower() == "true"


def _train_batches(
    model: TinyPatientConditionedSegmenter2D,
    optimizer: torch.optim.Optimizer,
    loader: DataLoader[Any],
    *,
    device: torch.device,
    max_batches: int,
    loss_config: dict[str, float | int | bool] | None = None,
) -> tuple[int, list[float]]:
    resolved_loss = _loss_configuration({"loss": loss_config or {}})
    completed = 0
    losses: list[float] = []
    model.train()
    while completed < max_batches:
        for white, fluorescence, target, values, present, trusted in loader:
            if bool(resolved_loss["freeze_image_after_warmup"]) and completed == int(
                resolved_loss["conditioning_warmup_batches"]
            ):
                _set_image_branch_trainable(model, trainable=False)
            optimizer.zero_grad(set_to_none=True)
            output = model(
                white.to(device),
                fluorescence.to(device),
                values.to(device),
                present.to(device),
                context_trusted=trusted.to(device),
                conditioning_authorized=(completed >= int(resolved_loss["conditioning_warmup_batches"])),
            )
            target = target.to(device)
            conditioned_loss = _segmentation_loss(
                output.conditioned_logits,
                target,
                positive_class_weight=float(resolved_loss["positive_class_weight"]),
                bce_weight=float(resolved_loss["bce_weight"]),
                dice_weight=float(resolved_loss["dice_weight"]),
            )
            image_loss = _segmentation_loss(
                output.image_only_logits,
                target,
                positive_class_weight=float(resolved_loss["positive_class_weight"]),
                bce_weight=float(resolved_loss["bce_weight"]),
                dice_weight=float(resolved_loss["dice_weight"]),
            )
            loss = (
                float(resolved_loss["conditioned_weight"]) * conditioned_loss
                + float(resolved_loss["image_only_weight"]) * image_loss
                + float(resolved_loss["delta_l1_weight"]) * output.delta_map.abs().mean()
            )
            loss.backward()
            optimizer.step()
            completed += 1
            losses.append(float(loss.detach().cpu().item()))
            if completed >= max_batches:
                break
    return completed, losses


def _segmentation_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    *,
    positive_class_weight: float = 1.0,
    bce_weight: float = 0.5,
    dice_weight: float = 0.5,
) -> torch.Tensor:
    probability = torch.sigmoid(logits)
    intersection = (probability * target).sum(dim=(1, 2, 3))
    denominator = probability.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    dice_loss = 1.0 - ((2.0 * intersection + 1e-5) / (denominator + 1e-5)).mean()
    positive_weight = torch.tensor(positive_class_weight, device=logits.device, dtype=logits.dtype)
    binary_cross_entropy = F.binary_cross_entropy_with_logits(logits, target, pos_weight=positive_weight)
    return bce_weight * binary_cross_entropy + dice_weight * dice_loss


def _loss_configuration(config: dict[str, Any]) -> dict[str, float | int | bool]:
    configured = dict(config.get("loss") or {})
    resolved: dict[str, float | int | bool] = {
        "positive_class_weight": float(configured.get("positive_class_weight", 1.0)),
        "bce_weight": float(configured.get("bce_weight", 0.5)),
        "dice_weight": float(configured.get("dice_weight", 0.5)),
        "conditioned_weight": float(configured.get("conditioned_weight", 1.0)),
        "image_only_weight": float(configured.get("image_only_weight", 0.35)),
        "delta_l1_weight": float(configured.get("delta_l1_weight", 0.01)),
        "conditioning_warmup_batches": int(configured.get("conditioning_warmup_batches", 0)),
        "freeze_image_after_warmup": bool(configured.get("freeze_image_after_warmup", False)),
    }
    for field in (
        "positive_class_weight",
        "bce_weight",
        "dice_weight",
        "conditioned_weight",
        "image_only_weight",
        "delta_l1_weight",
    ):
        if float(resolved[field]) < 0:
            raise ValueError(f"loss.{field} must be non-negative")
    if float(resolved["positive_class_weight"]) == 0:
        raise ValueError("loss.positive_class_weight must be positive")
    if int(resolved["conditioning_warmup_batches"]) < 0:
        raise ValueError("loss.conditioning_warmup_batches must be non-negative")
    if float(resolved["bce_weight"]) + float(resolved["dice_weight"]) <= 0:
        raise ValueError("At least one segmentation loss component must be enabled")
    return resolved


def _set_image_branch_trainable(model: TinyPatientConditionedSegmenter2D, *, trainable: bool) -> None:
    for module in (model.image_encoder, model.image_only_head):
        for parameter in module.parameters():
            parameter.requires_grad_(trainable)


def _proxy_clinical_values(rng: np.random.Generator, names: list[str]) -> dict[str, float]:
    defaults = {
        "age_years": float(rng.integers(18, 86)),
        "sex_at_birth_female": float(rng.integers(0, 2)),
        "diabetes": float(rng.random() < 0.25),
        "hypertension": float(rng.random() < 0.35),
        "renal_disease": float(rng.random() < 0.12),
        "immunosuppression": float(rng.random() < 0.12),
        "antiresorptive_medication": float(rng.random() < 0.15),
        "wbc_10e9_l": float(rng.uniform(3.5, 15.0)),
        "neutrophil_percent": float(rng.uniform(40.0, 88.0)),
        "crp_mg_l": float(rng.uniform(0.0, 80.0)),
        "esr_mm_h": float(rng.uniform(2.0, 85.0)),
        "hemoglobin_g_l": float(rng.uniform(90.0, 165.0)),
    }
    return {name: float(defaults.get(name, rng.normal())) for name in names}


def _proxy_images(
    rng: np.random.Generator,
    clinical: dict[str, float],
    *,
    height: int,
    width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[:height, :width]
    center_x = float(rng.uniform(width * 0.35, width * 0.65))
    center_y = float(rng.uniform(height * 0.35, height * 0.65))
    image_radius = float(rng.uniform(min(height, width) * 0.12, min(height, width) * 0.2))
    risk = (
        0.012 * (clinical.get("age_years", 50.0) - 50.0)
        + 0.5 * clinical.get("diabetes", 0.0)
        + 0.4 * clinical.get("immunosuppression", 0.0)
        + 0.006 * clinical.get("crp_mg_l", 10.0)
    )
    target_radius = np.clip(image_radius + risk * 2.0, image_radius - 3.0, image_radius + 4.0)
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    signal = np.exp(-np.square(distance / max(1.0, image_radius)))
    fluorescence = np.clip(25.0 + 205.0 * signal + rng.normal(0, 7, (height, width)), 0, 255).astype(np.uint8)
    base = np.clip(105.0 + 55.0 * signal + rng.normal(0, 10, (height, width)), 0, 255)
    white = np.stack(
        [
            np.clip(base * 1.08, 0, 255),
            np.clip(base * 0.98, 0, 255),
            np.clip(base * 0.9, 0, 255),
        ],
        axis=-1,
    ).astype(np.uint8)
    mask = (distance <= target_radius).astype(np.uint8)
    return white, fluorescence, mask


def _patient_group_split_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    groups: dict[str, set[str]] = {}
    for row in rows:
        groups.setdefault(row["patient_group_id"], set()).add(row["split"])
    leaking = {group: sorted(splits) for group, splits in groups.items() if len(splits) != 1}
    if leaking:
        raise ValueError(f"Patient groups cross dataset splits: {leaking}")
    return {
        "group_field": "patient_group_id",
        "leakage_detected": False,
        "group_count": len(groups),
        "split_group_counts": {
            split: len({row["patient_group_id"] for row in rows if row["split"] == split})
            for split in ("train", "val", "test")
        },
    }


def _training_data_profile(rows: list[dict[str, str]]) -> dict[str, Any]:
    mask_fraction_by_split: dict[str, list[float]] = {split: [] for split in ("train", "val", "test")}
    duplicate_auxiliary_count = 0
    clinical_contexts: set[str] = set()
    for row in rows:
        split = row["split"]
        with Image.open(row["mask_path"]) as image:
            mask = np.asarray(image.convert("L"), dtype=np.uint8)
        mask_fraction_by_split[split].append(float(np.mean(mask > 0)))
        with Image.open(row["white_path"]) as image:
            white_red = np.asarray(image.convert("RGB"), dtype=np.uint8)[:, :, 0]
        with Image.open(row["fluorescence_path"]) as image:
            auxiliary = np.asarray(image.convert("L"), dtype=np.uint8)
        if white_red.shape == auxiliary.shape and np.array_equal(white_red, auxiliary):
            duplicate_auxiliary_count += 1
        clinical_contexts.add(
            json.dumps(
                {
                    "values": json.loads(row["clinical_values_json"]),
                    "present": json.loads(row["clinical_present_json"]),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return {
        "mask_foreground_fraction_by_split": {
            split: {
                "mean": float(np.mean(values)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
            }
            for split, values in mask_fraction_by_split.items()
        },
        "empty_mask_rate_by_split": {
            split: float(np.mean(np.asarray(values) == 0.0)) for split, values in mask_fraction_by_split.items()
        },
        "unique_clinical_context_count": len(clinical_contexts),
        "auxiliary_equals_white_red_sample_rate": (float(duplicate_auxiliary_count / len(rows))),
        "input_channel_redundancy_detected": duplicate_auxiliary_count == len(rows),
    }


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _binary_counts(prediction: torch.Tensor, truth: torch.Tensor) -> tuple[float, float, float]:
    true_positive = float(torch.logical_and(prediction, truth).sum().item())
    false_positive = float(torch.logical_and(prediction, ~truth).sum().item())
    false_negative = float(torch.logical_and(~prediction, truth).sum().item())
    return true_positive, false_positive, false_negative


def _dice(counts: tuple[float, float, float]) -> float:
    true_positive, false_positive, false_negative = counts
    return 2.0 * true_positive / max(1.0, 2.0 * true_positive + false_positive + false_negative)


def _iou(counts: tuple[float, float, float]) -> float:
    true_positive, false_positive, false_negative = counts
    return true_positive / max(1.0, true_positive + false_positive + false_negative)


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(_compact_json(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/training/patient_conditioned_segmentation_proxy.yml",
    )
    parser.add_argument("--output-dir", default="")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = train_patient_conditioned(args.config, output_dir=args.output_dir or None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
