# Model Checkpoint Manifest

## Summary

- Config: `C:\Users\876762330\Desktop\projects\osteo-vision\configs\inference\osteo_vision.yml`
- Model version: `osteo-vision-convnext3d-proxy-v0`
- Total models: 8; available now: 6.
- Fixture fallback: True; selection policy: `fixture_fallback`.

## Available Models

- `convnext3d_d025_proxy_segmenter` / `convnext3d_segmenter`: checkpoint exists=True; runtime threshold=0.2; metric threshold=0.2; threshold aligned=True; clinical claim=False; reasons: none; warnings: none.
- `fluorescence_hotspot_2d_segmenter` / `fluorescence_hotspot_segmenter`: checkpoint exists=False; threshold=not recorded; clinical claim=False; reasons: none; warnings: none.
- `convnext2d_keyframe_proxy_segmenter` / `convnext2d_keyframe_segmenter`: checkpoint exists=True; runtime threshold=0.15; metric threshold=0.15; threshold aligned=True; clinical claim=False; reasons: none; warnings: none.
- `d025_lesion_smoke_segmenter` / `d025_lesion_segmenter`: checkpoint exists=True; runtime threshold=0.2; metric threshold=0.2; threshold aligned=True; clinical claim=False; reasons: none; warnings: none.
- `medsam2_osteo_promptable` / `medsam_like`: checkpoint exists=False; threshold=not recorded; clinical claim=False; reasons: none; warnings: medsam_checkpoint_missing_prompt_fallback.
- `fixture_default` / `fixture`: checkpoint exists=False; threshold=not recorded; clinical claim=False; reasons: none; warnings: none.

## Unavailable Or Pending Models

- `nnunet_v2_osteo_baseline` / `nnunet_v2`: checkpoint exists=False; threshold=not recorded; clinical claim=False; reasons: adapter inference not implemented; missing checkpoint: artifacts/checkpoints/osteo_vision/nnunet_v2; warnings: checkpoint_missing.
- `biomedclip_osteo_screening` / `vlm_encoder`: checkpoint exists=False; threshold=not recorded; clinical claim=False; reasons: adapter inference not implemented; missing dependency: open_clip; missing checkpoint: artifacts/checkpoints/osteo_vision/biomedclip.pt; warnings: checkpoint_missing.

## Boundary

The currently available models include a CBCT ROI proxy, trainable 2D keyframe proxy segmentation, 2D fluorescence hotspot fallback, and MedSAM-like prompt fallback. All 2D/3D segmentation results are still synthetic, pseudo-labeled, or non-target-domain engineering evidence. They must not be reported as real intraoperative ICG jaw osteomyelitis clinical performance or real MedSAM2 checkpoint inference. This manifest documents engineering readiness, checkpoint provenance, availability, and gaps.
