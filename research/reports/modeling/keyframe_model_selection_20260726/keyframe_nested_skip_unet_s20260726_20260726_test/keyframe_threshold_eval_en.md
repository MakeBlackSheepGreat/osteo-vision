# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_nested_skip_unet_s20260726_20260726.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.6`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9112; IoU: 0.8382.
- Precision: 0.9235; recall: 0.9025.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 2.1461 ms; P95: 2.5208 ms; peak GPU memory: 27.0381 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8811 | 0.7882 | 0.8041 | 0.9773 | 0.1347 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8929 | 0.8072 | 0.8301 | 0.9690 | 0.1293 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8997 | 0.8184 | 0.8478 | 0.9613 | 0.1255 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9042 | 0.8258 | 0.8616 | 0.9541 | 0.1225 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9074 | 0.8313 | 0.8734 | 0.9473 | 0.1200 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9095 | 0.8348 | 0.8833 | 0.9403 | 0.1177 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9110 | 0.8374 | 0.8923 | 0.9336 | 0.1157 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9119 | 0.8391 | 0.9009 | 0.9264 | 0.1136 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9122 | 0.8397 | 0.9087 | 0.9190 | 0.1117 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9120 | 0.8394 | 0.9162 | 0.9111 | 0.1098 | 0.0000 | 0.0000 |
| 0.6 | True | 0.9112 | 0.8382 | 0.9235 | 0.9025 | 0.1079 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9098 | 0.8360 | 0.9308 | 0.8931 | 0.1059 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9076 | 0.8325 | 0.9379 | 0.8826 | 0.1038 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9044 | 0.8273 | 0.9454 | 0.8703 | 0.1015 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8998 | 0.8199 | 0.9533 | 0.8555 | 0.0989 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8920 | 0.8072 | 0.9620 | 0.8349 | 0.0956 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8784 | 0.7857 | 0.9716 | 0.8050 | 0.0912 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8469 | 0.7376 | 0.9842 | 0.7470 | 0.0834 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
