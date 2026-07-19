# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_20260715.pt`
- Manifests: 1; split: `test`; samples: 24.
- Recommended runtime threshold: `0.45`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9045; IoU: 0.8259.
- Precision: 0.9209; recall: 0.8902.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.6519 ms; P95: 4.0450 ms; peak GPU memory: 20.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.45 | True | 0.9045 | 0.8259 | 0.9209 | 0.8902 | 0.1056 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
