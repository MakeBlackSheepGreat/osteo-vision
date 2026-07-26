# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260726.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.55`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9154; IoU: 0.8444.
- Precision: 0.9102; recall: 0.9227.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.8566 ms; P95: 5.8950 ms; peak GPU memory: 27.0166 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8702 | 0.7707 | 0.7797 | 0.9859 | 0.1329 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8854 | 0.7948 | 0.8090 | 0.9792 | 0.1272 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8949 | 0.8102 | 0.8298 | 0.9727 | 0.1232 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9016 | 0.8212 | 0.8462 | 0.9662 | 0.1200 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9064 | 0.8292 | 0.8600 | 0.9597 | 0.1172 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9098 | 0.8349 | 0.8719 | 0.9530 | 0.1148 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9124 | 0.8392 | 0.8825 | 0.9461 | 0.1126 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9141 | 0.8420 | 0.8923 | 0.9388 | 0.1104 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9152 | 0.8439 | 0.9016 | 0.9310 | 0.1084 | 0.0000 | 0.0000 |
| 0.55 | True | 0.9154 | 0.8444 | 0.9102 | 0.9227 | 0.1064 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9150 | 0.8436 | 0.9184 | 0.9135 | 0.1043 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9137 | 0.8416 | 0.9264 | 0.9035 | 0.1023 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9117 | 0.8381 | 0.9344 | 0.8921 | 0.1001 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9085 | 0.8328 | 0.9426 | 0.8789 | 0.0977 | 0.0000 | 0.0000 |
| 0.8 | False | 0.9034 | 0.8244 | 0.9511 | 0.8623 | 0.0950 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8953 | 0.8112 | 0.9601 | 0.8408 | 0.0917 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8815 | 0.7892 | 0.9703 | 0.8099 | 0.0873 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8512 | 0.7425 | 0.9828 | 0.7530 | 0.0800 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
