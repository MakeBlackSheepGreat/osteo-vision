from __future__ import annotations

import pytest
import torch

from osteo_vision_core.models.bone_activity_multitask import (
    IGNORE_INDEX,
    BoneActivityMultiTask2D,
    apply_bone_activity_safety_gate,
    bone_activity_multitask_loss,
    bone_activity_probabilities,
)


def test_bone_activity_model_emits_all_multitask_outputs() -> None:
    model = BoneActivityMultiTask2D(base_channels=4)
    outputs = model(torch.rand(2, 3, 32, 40), torch.rand(2, 1, 32, 40))
    probabilities = bone_activity_probabilities(outputs)

    assert outputs["bone_gate_logits"].shape == (2, 1, 32, 40)
    assert outputs["activity_score_logits"].shape == (2, 1, 32, 40)
    assert outputs["class_logits"].shape == (2, 3, 32, 40)
    assert outputs["uncertainty_logits"].shape == (2, 1, 32, 40)
    assert probabilities["class_probabilities"].sum(dim=1).allclose(torch.ones(2, 32, 40), atol=1e-5)


def test_bone_activity_safety_gate_fails_closed_for_unreviewed_or_proxy_data() -> None:
    model = BoneActivityMultiTask2D(base_channels=4)
    outputs = model(torch.rand(1, 3, 24, 24), torch.rand(1, 1, 24, 24))
    reviewed_gate = torch.ones(1, 1, 24, 24)

    unreviewed = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=None,
        physician_reviewed_bone_gate=False,
        target_domain=True,
    )
    proxy = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=reviewed_gate,
        physician_reviewed_bone_gate=True,
        target_domain=False,
    )
    unpromoted = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=reviewed_gate,
        physician_reviewed_bone_gate=True,
        target_domain=True,
    )

    for result in (unreviewed, proxy, unpromoted):
        assert result["available"] is False
        assert result["spatial_candidates_available"] is False
        assert bool(result["abstention_mask"].all()) is True
        assert bool((result["class_prediction"] == IGNORE_INDEX).all()) is True
        assert result["target_domain_promotion_ready"] is False


def test_bone_activity_loss_is_finite_and_backpropagates() -> None:
    model = BoneActivityMultiTask2D(base_channels=4)
    outputs = model(torch.rand(2, 3, 24, 24), torch.rand(2, 1, 24, 24))
    gate = torch.zeros(2, 1, 24, 24)
    gate[:, :, 4:20, 4:20] = 1
    classes = torch.full((2, 24, 24), IGNORE_INDEX, dtype=torch.long)
    classes[:, 4:12, 4:20] = 0
    classes[:, 12:16, 4:20] = 1
    classes[:, 16:20, 4:20] = 2
    loss, components = bone_activity_multitask_loss(
        outputs,
        {
            "bone_gate": gate,
            "activity_score": torch.rand(2, 1, 24, 24) * gate,
            "class_target": classes,
            "uncertainty": torch.zeros(2, 1, 24, 24),
        },
    )
    loss.backward()

    assert torch.isfinite(loss)
    assert set(components) == {
        "bone_gate",
        "activity_score",
        "class_logits",
        "uncertainty",
    }
    assert any(parameter.grad is not None for parameter in model.parameters())


def test_bone_activity_loss_handles_empty_bone_gate_without_nan() -> None:
    model = BoneActivityMultiTask2D(base_channels=2)
    outputs = model(torch.rand(1, 3, 24, 24), torch.rand(1, 1, 24, 24))
    loss, _ = bone_activity_multitask_loss(
        outputs,
        {
            "bone_gate": torch.zeros(1, 1, 24, 24),
            "activity_score": torch.zeros(1, 1, 24, 24),
            "class_target": torch.full((1, 24, 24), IGNORE_INDEX, dtype=torch.long),
            "uncertainty": torch.ones(1, 1, 24, 24),
        },
    )

    assert torch.isfinite(loss)


def test_bone_activity_safety_gate_hides_abstained_scores_and_probabilities() -> None:
    outputs = {
        "bone_gate_logits": torch.zeros(1, 1, 1, 2),
        "activity_score_logits": torch.zeros(1, 1, 1, 2),
        "class_logits": torch.zeros(1, 3, 1, 2),
        "uncertainty_logits": torch.tensor([[[[-10.0, 10.0]]]]),
    }
    result = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=torch.ones(1, 1, 1, 2),
        physician_reviewed_bone_gate=True,
        target_domain=True,
        model_promotion_ready=True,
        abstention_threshold=0.5,
    )

    assert result["available"] is True
    assert result["target_domain_promotion_ready"] is True
    assert result["activity_score_available_mask"].tolist() == [[[[True, False]]]]
    assert float(result["activity_score"][0, 0, 0, 0]) > 0.0
    assert float(result["activity_score"][0, 0, 0, 1]) == 0.0
    assert float(result["class_probabilities"][0, :, 0, 0].sum()) == pytest.approx(1.0)
    assert float(result["class_probabilities"][0, :, 0, 1].sum()) == 0.0
    assert int(result["class_prediction"][0, 0, 1]) == IGNORE_INDEX


def test_bone_activity_safety_gate_fails_closed_on_non_finite_output() -> None:
    outputs = {
        "bone_gate_logits": torch.zeros(1, 1, 1, 1),
        "activity_score_logits": torch.full((1, 1, 1, 1), float("nan")),
        "class_logits": torch.zeros(1, 3, 1, 1),
        "uncertainty_logits": torch.full((1, 1, 1, 1), float("nan")),
    }
    result = apply_bone_activity_safety_gate(
        outputs,
        reviewed_bone_gate=torch.ones(1, 1, 1, 1),
        physician_reviewed_bone_gate=True,
        target_domain=True,
        model_promotion_ready=True,
    )

    assert result["available"] is False
    assert "non_finite_model_output" in result["failure_reasons"]
    assert bool(result["abstention_mask"].all()) is True
    assert torch.count_nonzero(result["activity_score"]).item() == 0
    assert torch.isfinite(result["uncertainty"]).all()
    assert bool((result["uncertainty"] == 1).all()) is True
