# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_s20260716_20260715.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.45`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8970; IoU: 0.8135.
- Precision: 0.8905; recall: 0.9056.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.2373 ms; P95: 3.8134 ms; peak GPU memory: 20.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8700 | 0.7702 | 0.7898 | 0.9697 | 0.1281 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8814 | 0.7882 | 0.8168 | 0.9586 | 0.1224 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8878 | 0.7984 | 0.8356 | 0.9485 | 0.1183 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8919 | 0.8050 | 0.8501 | 0.9396 | 0.1152 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8947 | 0.8096 | 0.8623 | 0.9314 | 0.1126 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8961 | 0.8119 | 0.8727 | 0.9226 | 0.1102 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8969 | 0.8132 | 0.8819 | 0.9142 | 0.1080 | 0.0000 | 0.0000 |
| 0.45 | True | 0.8970 | 0.8135 | 0.8905 | 0.9056 | 0.1059 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8967 | 0.8129 | 0.8986 | 0.8968 | 0.1039 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8958 | 0.8115 | 0.9066 | 0.8872 | 0.1019 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8944 | 0.8092 | 0.9143 | 0.8773 | 0.0999 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8919 | 0.8052 | 0.9214 | 0.8664 | 0.0978 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8890 | 0.8007 | 0.9294 | 0.8542 | 0.0956 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8848 | 0.7939 | 0.9372 | 0.8402 | 0.0932 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8787 | 0.7844 | 0.9453 | 0.8232 | 0.0905 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8696 | 0.7703 | 0.9543 | 0.8012 | 0.0872 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8548 | 0.7476 | 0.9644 | 0.7700 | 0.0829 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8234 | 0.7014 | 0.9770 | 0.7141 | 0.0757 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
