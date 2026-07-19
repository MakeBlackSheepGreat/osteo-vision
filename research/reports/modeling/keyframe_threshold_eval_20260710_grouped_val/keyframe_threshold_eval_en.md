# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_grouped_20260710.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.45`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9160; IoU: 0.8452.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2 | False | 0.9048 | 0.8265 | 0.1899 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9094 | 0.8342 | 0.1848 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9123 | 0.8391 | 0.1807 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9145 | 0.8428 | 0.1769 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9156 | 0.8446 | 0.1734 | 0.0000 | 0.0000 |
| 0.45 | True | 0.9160 | 0.8452 | 0.1701 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9156 | 0.8445 | 0.1670 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9145 | 0.8427 | 0.1638 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9126 | 0.8395 | 0.1605 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9096 | 0.8344 | 0.1572 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9054 | 0.8275 | 0.1537 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG is not a jaw-osteomyelitis-specific probe. This report is for MP4/JPEG keyframe segmentation stability tuning only.
