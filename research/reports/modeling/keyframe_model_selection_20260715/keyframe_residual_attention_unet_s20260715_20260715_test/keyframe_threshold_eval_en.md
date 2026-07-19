# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260715_20260715.pt`
- Manifests: 1; split: `test`; samples: 24.
- Recommended runtime threshold: `0.4`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9177; IoU: 0.8483.
- Precision: 0.9231; recall: 0.9135.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.2062 ms; P95: 4.8362 ms; peak GPU memory: 26.0317 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.4 | True | 0.9177 | 0.8483 | 0.9231 | 0.9135 | 0.1084 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
