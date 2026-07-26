# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260728.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.6`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9156; IoU: 0.8462.
- Precision: 0.9282; recall: 0.9076.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.8310 ms; P95: 5.6090 ms; peak GPU memory: 27.0166 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8733 | 0.7759 | 0.7864 | 0.9849 | 0.1388 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8881 | 0.7995 | 0.8157 | 0.9778 | 0.1328 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8977 | 0.8152 | 0.8372 | 0.9710 | 0.1283 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9042 | 0.8260 | 0.8542 | 0.9640 | 0.1248 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9088 | 0.8339 | 0.8682 | 0.9572 | 0.1219 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9122 | 0.8397 | 0.8803 | 0.9504 | 0.1193 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9145 | 0.8437 | 0.8911 | 0.9430 | 0.1169 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9160 | 0.8463 | 0.9013 | 0.9350 | 0.1145 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9166 | 0.8475 | 0.9106 | 0.9267 | 0.1123 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9166 | 0.8478 | 0.9197 | 0.9177 | 0.1100 | 0.0000 | 0.0000 |
| 0.6 | True | 0.9156 | 0.8462 | 0.9282 | 0.9076 | 0.1078 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9138 | 0.8434 | 0.9364 | 0.8966 | 0.1055 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9108 | 0.8387 | 0.9450 | 0.8835 | 0.1029 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9061 | 0.8311 | 0.9531 | 0.8681 | 0.1002 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8990 | 0.8197 | 0.9613 | 0.8490 | 0.0971 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8883 | 0.8025 | 0.9702 | 0.8239 | 0.0933 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8697 | 0.7731 | 0.9792 | 0.7869 | 0.0882 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8289 | 0.7115 | 0.9894 | 0.7174 | 0.0795 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
