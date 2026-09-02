# MedSAM-like Prompt Segmentation Contract

Date: 2026-07-04

## Summary

This update turns `MedSAMLikeAdapter` from an empty adapter into a runnable 2D prompt segmentation contract. The current implementation is a **prompt contract fallback**: it accepts clinician ROIs, candidate bounding boxes, or point prompts, then writes a reviewable binary mask and overlay. This supports clinician review and future replacement with a real MedSAM/SAM2 checkpoint.

It is not MedSAM2 weight inference and it does not represent target-domain intraoperative ICG jaw osteomyelitis segmentation performance. The model inventory reports a `medsam_checkpoint_missing_prompt_fallback` warning.

## Files

- Prompt fallback implementation: `src/models/prompt_segmenter.py`
- Adapter integration: `src/models/adapters.py`
- Runtime config: `configs/inference/osteo_vision.yml`
- Unit test: `tests/unit/test_model_adapters.py`

## Input Contract

The minimal implementation supports `2d_image` inputs. Prompts are read from `AdapterRequest.metadata`:

- `roi_hints`: normalized rectangular ROIs from the clinician ROI tool.
- `prompts[].bbox_xyxy`: pixel-space rectangle.
- `prompts[].bbox_normalized`: normalized rectangle.
- `prompts[].geometry`: normalized rectangle geometry.
- `prompts[].point`: point prompt in normalized or pixel coordinates.

## Output Contract

Outputs follow the existing segmentation adapter shape:

- `segmentation_mask.format = png_binary_mask`
- `segmentation_mask.path`
- `lesion_evidence.overlay_path`
- `lesion_evidence.candidates`
- `quantification.positive_area_px`
- `quantification.positive_area_fraction`
- warning: `medsam_like_prompt_fallback_non_diagnostic`

## Value for the Platform Loop

1. Provides a runnable "clinician ROI/bbox -> promptable segmentation -> mask/overlay -> clinician review" interface.
2. Preserves a stable output contract for later real MedSAM/SAM2 checkpoint integration.
3. Can reuse current MP4 hotspot candidate boxes and ROI canvas outputs as prompts.

## Boundary

- No real MedSAM2 checkpoint is available.
- Current scope is 2D prompt fallback only, with no video propagation, 3D CBCT prompting, or learned mask refinement.
- Masks are generated from prompt geometry, not learned lesion boundaries.
- Outputs are research validation platform evidence and require physician review.

## Verification

- `conda run -n osteo-vision python -m pytest tests/unit/test_model_adapters.py -q`
- `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml`
