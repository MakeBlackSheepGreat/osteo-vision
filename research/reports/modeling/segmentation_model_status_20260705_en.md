# Segmentation Model Status And Threshold Alignment

## Conclusion

The platform software now has a runnable segmentation loop, but the evidence has two different levels. The D025 CBCT lesion ROI proxy model has reproducible validation metrics. The JPEG/MP4 keyframe model has a trainable checkpoint and pseudo-label validation metrics, but it still lacks real intraoperative ICG jaw osteomyelitis pixel-level physician labels.

This update aligns the D025 mainline runtime threshold from `0.6` to the threshold-sweep optimum `0.2`, and completes threshold sweep, continued training, and runtime-threshold alignment for the 2D MP4/JPEG keyframe mainline. After continued training, `convnext2d_keyframe_proxy_segmenter` uses threshold `0.15`; on the D046 proxy validation split it reaches Dice `0.9093` and IoU `0.8340`, with empty-mask and over-segmentation rates both at `0`. These changes update engineering runtime thresholds and pseudo-label validation evidence only; the medical boundary is unchanged.

## Current Mainline Metrics

| Model | Input | Data boundary | Threshold | Dice | IoU | HD95 | Sensitivity | Precision | Current use |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `convnext3d_d025_proxy_segmenter` | `npz_roi` / CBCT ROI | D025 CBCT lesion ROI proxy data | 0.20 | 0.6567 | 0.5553 | 15.2370 | 0.6900 | 0.7238 | 3D proxy segmentation mainline |
| `convnext2d_keyframe_proxy_segmenter` | JPEG / MP4 keyframe | D046 public/proxy MP4 keyframe pseudo-labels | 0.15 | 0.9093 | 0.8340 | N/A | N/A | N/A | 2D video keyframe segmentation mainline |
| `fluorescence_hotspot_2d_segmenter` | JPEG / MP4 keyframe | Heuristic fluorescence hotspot | 0.60 | N/A | N/A | N/A | N/A | N/A | Stable fallback and visual candidate regions |

## Completed Alignment

- The D025 3D segmentation runtime threshold in `configs/inference/osteo_vision.yml` is now `0.2`.
- `artifacts/checkpoints/osteo_vision/d025_lesion_smoke_manifest.json` and the local model card are aligned to the best threshold-sweep metrics.
- `scripts/generate_model_checkpoint_manifest.py` now records `runtime_threshold`, `sidecar_metric_threshold`, and `threshold_alignment` to prevent runtime/report threshold drift.
- `research/reports/modeling/d025_mainline_eval_20260705/` stores the current mainline checkpoint re-evaluation and failure previews.
- Added `tools/run_keyframe_tiling_smoke.py` to call `convnext2d_keyframe_proxy_segmenter` directly on an official-resolution 4K keyframe with tiled inference. The local 2026-07-05 3840x2160 synthetic proxy keyframe check passed with `tile_count=45`, and mask/probability/overlay dimensions matched the input under `.pytest_tmp/keyframe_tiling_4k_smoke/`.
- Added an empty-mask fallback in MP4 keyframe analysis: if the trainable keyframe model writes an empty mask, the platform records `keyframe_segmenter_empty_mask_fallback` and falls back to `fluorescence_hotspot_2d_segmenter` so physician-review candidates are not lost.
- Added `scripts/evaluate_keyframe_segmentation_proxy.py` to sweep `0.10-0.60` thresholds for the 2D keyframe checkpoint and report Dice, IoU, empty-mask rate, positive-area fraction, and over-segmentation rate. The post-training evaluation is stored under `research/reports/modeling/keyframe_threshold_eval_20260705/`.
- Continued `convnext2d_keyframe_proxy_segmenter` training for 160 batches on the D046 proxy manifest. The checkpoint sidecar, model card, and `configs/inference/osteo_vision.yml` runtime threshold are aligned to `0.15`.

## Claims Not Allowed

- Do not claim real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
- Do not treat D025 CBCT lesion ROI metrics as microscope 4K MP4/JPEG metrics.
- Do not treat 2D keyframe pseudo-label Dice as physician-labeled lesion-boundary Dice.

## Next Steps

1. Use `tools/build_keyframe_training_manifest_from_review.py` to convert physician-reviewed accepted/modified/rejected samples into weighted training manifests.
2. Add `run_keyframe_tiling_smoke.py` and `evaluate_keyframe_segmentation_proxy.py` to routine regression and keep tracking empty-mask and fallback rates on real or public proxy MP4 keyframes.
3. For the next training round, prioritize merged physician-review manifests instead of repeating D046 pseudo-label-only training.
4. Keep nnU-Net/DynUNet high-resolution work as the next-stage CBCT/anatomical-prior enhancement without blocking the current JPEG/MP4 software loop.
