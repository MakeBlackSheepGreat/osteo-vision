# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260727.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.35`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9198; IoU: 0.8520.
- Precision: 0.9323; recall: 0.9092.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.4599 ms; P95: 5.6721 ms; peak GPU memory: 27.0166 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.9061 | 0.8289 | 0.8505 | 0.9712 | 0.1273 | 0.0000 | 0.0000 |
| 0.15 | False | 0.9158 | 0.8451 | 0.8786 | 0.9579 | 0.1215 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9198 | 0.8518 | 0.8974 | 0.9448 | 0.1172 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9213 | 0.8544 | 0.9117 | 0.9326 | 0.1138 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9211 | 0.8542 | 0.9230 | 0.9209 | 0.1109 | 0.0000 | 0.0000 |
| 0.35 | True | 0.9198 | 0.8520 | 0.9323 | 0.9092 | 0.1083 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9178 | 0.8486 | 0.9406 | 0.8977 | 0.1060 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9144 | 0.8431 | 0.9472 | 0.8856 | 0.1037 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9106 | 0.8366 | 0.9533 | 0.8733 | 0.1016 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9060 | 0.8292 | 0.9590 | 0.8606 | 0.0994 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9007 | 0.8204 | 0.9640 | 0.8471 | 0.0973 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8944 | 0.8102 | 0.9688 | 0.8327 | 0.0952 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8868 | 0.7980 | 0.9732 | 0.8166 | 0.0928 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8774 | 0.7831 | 0.9778 | 0.7979 | 0.0902 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8652 | 0.7643 | 0.9820 | 0.7757 | 0.0873 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8483 | 0.7386 | 0.9863 | 0.7466 | 0.0835 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8225 | 0.7011 | 0.9908 | 0.7059 | 0.0785 | 0.0000 | 0.0000 |
| 0.95 | False | 0.7710 | 0.6300 | 0.9956 | 0.6319 | 0.0698 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
