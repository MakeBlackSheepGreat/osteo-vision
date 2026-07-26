# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_nested_skip_unet_s20260726_20260727.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.4`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9196; IoU: 0.8515.
- Precision: 0.9289; recall: 0.9120.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 2.1622 ms; P95: 2.8211 ms; peak GPU memory: 27.0381 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.9081 | 0.8320 | 0.8573 | 0.9667 | 0.1254 | 0.0000 | 0.0000 |
| 0.15 | False | 0.9151 | 0.8438 | 0.8797 | 0.9551 | 0.1207 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9184 | 0.8493 | 0.8945 | 0.9451 | 0.1174 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9199 | 0.8519 | 0.9056 | 0.9362 | 0.1149 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9205 | 0.8529 | 0.9147 | 0.9279 | 0.1127 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9203 | 0.8527 | 0.9224 | 0.9198 | 0.1107 | 0.0000 | 0.0000 |
| 0.4 | True | 0.9196 | 0.8515 | 0.9289 | 0.9120 | 0.1090 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9183 | 0.8494 | 0.9348 | 0.9041 | 0.1073 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9168 | 0.8468 | 0.9404 | 0.8960 | 0.1057 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9146 | 0.8433 | 0.9455 | 0.8875 | 0.1041 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9120 | 0.8389 | 0.9506 | 0.8781 | 0.1024 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9088 | 0.8337 | 0.9554 | 0.8684 | 0.1007 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9052 | 0.8277 | 0.9604 | 0.8579 | 0.0989 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9003 | 0.8198 | 0.9655 | 0.8454 | 0.0969 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8940 | 0.8096 | 0.9704 | 0.8309 | 0.0947 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8852 | 0.7956 | 0.9756 | 0.8124 | 0.0920 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8713 | 0.7737 | 0.9817 | 0.7855 | 0.0884 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8432 | 0.7311 | 0.9889 | 0.7374 | 0.0822 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
