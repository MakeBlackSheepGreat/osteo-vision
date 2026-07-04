# Model Checkpoint Manifest

## Summary

- Config: `C:\Users\876762330\Desktop\projects\osteo-vision\configs\inference\osteo_vision.yml`
- Model version: `osteo-vision-convnext3d-proxy-v0`
- Total models: 7; available now: 4.
- Fixture fallback: True; selection policy: `fixture_fallback`.

## Available Models

- `convnext3d_d025_proxy_segmenter` / `convnext3d_segmenter`: checkpoint exists=True; clinical claim=False; reasons: none.
- `fluorescence_hotspot_2d_segmenter` / `fluorescence_hotspot_segmenter`: checkpoint exists=False; clinical claim=False; reasons: none.
- `d025_lesion_smoke_segmenter` / `d025_lesion_segmenter`: checkpoint exists=True; clinical claim=False; reasons: none.
- `fixture_default` / `fixture`: checkpoint exists=False; clinical claim=False; reasons: none.

## Unavailable Or Pending Models

- `nnunet_v2_osteo_baseline` / `nnunet_v2`: checkpoint exists=False; clinical claim=False; reasons: adapter inference not implemented; missing checkpoint: artifacts/checkpoints/osteo_vision/nnunet_v2.
- `medsam2_osteo_promptable` / `medsam_like`: checkpoint exists=False; clinical claim=False; reasons: adapter inference not implemented; missing checkpoint: artifacts/checkpoints/osteo_vision/medsam2.pt.
- `biomedclip_osteo_screening` / `vlm_encoder`: checkpoint exists=False; clinical claim=False; reasons: adapter inference not implemented; missing dependency: open_clip; missing checkpoint: artifacts/checkpoints/osteo_vision/biomedclip.pt.

## Boundary

The currently available models are CBCT ROI proxy and 2D fluorescence hotspot heuristic baselines. They must not be reported as real intraoperative ICG jaw osteomyelitis clinical performance. This manifest documents engineering readiness, checkpoint provenance, availability, and gaps.
