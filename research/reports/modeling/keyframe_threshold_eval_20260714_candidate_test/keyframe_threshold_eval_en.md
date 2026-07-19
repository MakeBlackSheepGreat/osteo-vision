# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_candidate_20260714.pt`
- Manifests: 1; split: `test`; samples: 24.
- Recommended runtime threshold: `0.55`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8987; IoU: 0.8164.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.55 | True | 0.8987 | 0.8164 | 0.1073 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG is not a jaw-osteomyelitis-specific probe. This report is for MP4/JPEG keyframe segmentation stability tuning only.
