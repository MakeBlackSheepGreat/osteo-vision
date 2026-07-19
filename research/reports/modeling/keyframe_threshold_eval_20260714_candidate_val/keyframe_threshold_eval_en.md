# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_candidate_20260714.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.55`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8932; IoU: 0.8073.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.3 | False | 0.8818 | 0.7887 | 0.1192 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8864 | 0.7961 | 0.1161 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8898 | 0.8016 | 0.1132 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8920 | 0.8053 | 0.1106 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8929 | 0.8068 | 0.1079 | 0.0000 | 0.0000 |
| 0.55 | True | 0.8932 | 0.8073 | 0.1053 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8924 | 0.8060 | 0.1026 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG is not a jaw-osteomyelitis-specific probe. This report is for MP4/JPEG keyframe segmentation stability tuning only.
