# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext_unet_s20260726_20260726.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.65`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.8987; IoU: 0.8176.
- Precision: 0.9138; recall: 0.8881.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 2.7369 ms; P95: 3.3251 ms; peak GPU memory: 22.1929 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8430 | 0.7297 | 0.7380 | 0.9854 | 0.1483 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8612 | 0.7571 | 0.7707 | 0.9781 | 0.1409 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8730 | 0.7753 | 0.7944 | 0.9711 | 0.1357 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8814 | 0.7885 | 0.8134 | 0.9640 | 0.1315 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8880 | 0.7991 | 0.8303 | 0.9567 | 0.1278 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8929 | 0.8069 | 0.8447 | 0.9493 | 0.1245 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8963 | 0.8126 | 0.8575 | 0.9414 | 0.1216 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8987 | 0.8165 | 0.8697 | 0.9325 | 0.1187 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9002 | 0.8191 | 0.8812 | 0.9230 | 0.1158 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9006 | 0.8201 | 0.8921 | 0.9127 | 0.1130 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9003 | 0.8198 | 0.9030 | 0.9012 | 0.1102 | 0.0000 | 0.0000 |
| 0.65 | True | 0.8987 | 0.8176 | 0.9138 | 0.8881 | 0.1072 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8959 | 0.8133 | 0.9249 | 0.8729 | 0.1040 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8910 | 0.8056 | 0.9360 | 0.8545 | 0.1005 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8836 | 0.7942 | 0.9476 | 0.8324 | 0.0966 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8708 | 0.7745 | 0.9594 | 0.8021 | 0.0918 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8483 | 0.7403 | 0.9726 | 0.7569 | 0.0854 | 0.0000 | 0.0000 |
| 0.95 | False | 0.7964 | 0.6656 | 0.9864 | 0.6722 | 0.0747 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
