# JPEG/MP4 Keyframe Hotspot Segmentation Bridge Report

Date: 2026-07-04

## Conclusion

This update closes a practical gap between official JPEG/MP4 inputs and AI-assisted review. Fluorescence-like JPEG images and MP4 keyframes can now enter a 2D fluorescence hotspot segmentation baseline that produces binary masks, candidate regions, quantitative summaries, and evidence images.

This remains a heuristic baseline, not a trained clinical model. Its role is to provide a runnable, exportable, physician-reviewable minimum loop for track 2 on official-style JPEG/MP4 inputs.

## Files

- 2D hotspot implementation: `src/models/hotspot_segmenter.py`
- Adapter: `src/models/adapters.py`
- Runtime config: `configs/inference/osteo_vision.yml`
- Task recommendation config: `configs/tasks/osteo_vision.yml`
- MP4 analysis integration: `backend/src/services/analysis_service.py`
- Frontend labels: `frontend/src/utils/caseDisplay.ts`
- Tests: `tests/unit/test_model_adapters.py`, `tests/unit/test_inference_pipelines.py`, `backend/tests/contract/test_case_inputs_api.py`

## Current Capability

### JPEG / 2D Image

New model:

- model_id: `fluorescence_hotspot_2d_segmenter`
- family: `fluorescence_hotspot_segmenter`
- input_type: `2d_image`
- outputs: `png_binary_mask`, pseudo-color image, overlay, connected candidates, positive area fraction

Verified under the real config:

```json
{
  "status": "completed",
  "model_id": "fluorescence_hotspot_2d_segmenter",
  "model_family": "fluorescence_hotspot_segmenter",
  "mask_format": "png_binary_mask",
  "positive_area_px": 250,
  "warning_codes": [
    "heuristic_hotspot_segmenter_non_diagnostic"
  ]
}
```

### MP4 / Keyframes

MP4 analysis now extracts keyframes and runs hotspot segmentation on each keyframe. The result is recorded in:

- `fused_outputs.hotspot_outputs`
- `quantitative_summary.hotspot_frame_count`
- `quantitative_summary.hotspot_candidate_count`
- `quantitative_summary.hotspot_max_positive_area_fraction`
- `candidate_regions` as `video_keyframe_hotspot`
- ROI mask / heatmap / overlay artifacts

## Medical Boundary

This bridge uses intensity enhancement, thresholding, and connected-component analysis. It is a rule-based heuristic baseline for candidate review and engineering evidence, not a replacement for physician judgement and not diagnostic performance for jaw osteomyelitis.

## Next Steps

1. Use the OFDVDnet baseline manifest to generate more JPEG/frame-sequence inputs and analyze threshold stability.
2. Use hotspot candidates as prompts for MedSAM or a more formal 2D segmentation adapter.
3. Upgrade the frontend MP4 result panel from keyframes only to keyframes plus masks, candidates, and quantification.
