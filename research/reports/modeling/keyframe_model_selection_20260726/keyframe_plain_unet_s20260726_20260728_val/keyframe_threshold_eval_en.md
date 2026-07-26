# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_plain_unet_s20260726_20260728.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.5`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8977; IoU: 0.8162.
- Precision: 0.8927; recall: 0.9051.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 1.9753 ms; P95: 2.6694 ms; peak GPU memory: 24.1309 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8688 | 0.7688 | 0.7852 | 0.9744 | 0.1305 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8790 | 0.7851 | 0.8104 | 0.9622 | 0.1248 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8853 | 0.7954 | 0.8285 | 0.9525 | 0.1208 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8897 | 0.8027 | 0.8430 | 0.9440 | 0.1176 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8928 | 0.8078 | 0.8550 | 0.9362 | 0.1150 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8949 | 0.8114 | 0.8656 | 0.9285 | 0.1126 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8963 | 0.8137 | 0.8751 | 0.9208 | 0.1105 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8973 | 0.8155 | 0.8841 | 0.9132 | 0.1084 | 0.0000 | 0.0000 |
| 0.5 | True | 0.8977 | 0.8162 | 0.8927 | 0.9051 | 0.1064 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8974 | 0.8157 | 0.9007 | 0.8965 | 0.1044 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8967 | 0.8146 | 0.9089 | 0.8872 | 0.1024 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8952 | 0.8123 | 0.9170 | 0.8769 | 0.1003 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8927 | 0.8081 | 0.9251 | 0.8649 | 0.0980 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8889 | 0.8021 | 0.9333 | 0.8510 | 0.0955 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8834 | 0.7932 | 0.9423 | 0.8339 | 0.0927 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8747 | 0.7795 | 0.9523 | 0.8112 | 0.0892 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8589 | 0.7548 | 0.9637 | 0.7770 | 0.0844 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8208 | 0.6980 | 0.9776 | 0.7095 | 0.0759 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
