from __future__ import annotations

import numpy as np

from src.datasets.domain_adaptation import (
    augment_microscope_image,
    canonical_domain_tier,
    load_domain_adaptation_config,
    row_sampling_weights,
    sampled_indices,
    sampling_report,
)


def test_registry_domain_tier_aliases_use_configured_sampling_weights() -> None:
    rows = [
        {"domain_tier": "near_domain", "review_state": "review_required", "source_group_id": "a"},
        {"domain_tier": "derived_proxy", "review_state": "review_required", "source_group_id": "b"},
    ]
    config = load_domain_adaptation_config({"enabled": True, "sampling": {"balance_source_groups": False}})
    weights = row_sampling_weights(rows, config)
    assert canonical_domain_tier("target_domain") == "target"
    assert canonical_domain_tier("fluorescence_proxy") == "proxy"
    assert weights[0] == 2.0 * 0.75
    assert weights[1] == 1.0 * 0.75


def test_domain_sampling_prefers_reviewed_near_target_and_reports_groups() -> None:
    rows = [
        {"domain_tier": "near_target", "review_state": "modified", "source_group_id": "a"},
        {"domain_tier": "synthetic", "review_state": "review_required", "source_group_id": "b"},
    ]
    config = load_domain_adaptation_config({"enabled": True})
    indices = sampled_indices(rows, config=config, sample_count=200, seed=7)
    report = sampling_report(rows, indices)
    assert report["domain_tier_counts"]["near_target"] > report["domain_tier_counts"]["synthetic"]
    assert set(report["source_group_counts"]) == {"a", "b"}


def test_microscope_augmentation_is_deterministic_and_keeps_geometry() -> None:
    image = np.full((32, 48, 3), 96, dtype=np.uint8)
    config = load_domain_adaptation_config(
        {
            "enabled": True,
            "augmentation": {
                "probability": 1.0,
                "specular_probability": 1.0,
                "occlusion_probability": 1.0,
                "jpeg_probability": 1.0,
            },
        }
    )
    first = augment_microscope_image(image, config=config, rng=np.random.default_rng(11))
    second = augment_microscope_image(image, config=config, rng=np.random.default_rng(11))
    assert first.shape == image.shape
    assert first.dtype == np.uint8
    assert np.array_equal(first, second)
    assert not np.array_equal(first, image)
