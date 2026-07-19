# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260716_20260715.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.5`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9108; IoU: 0.8364.
- Precision: 0.9035; recall: 0.9200.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.5002 ms; P95: 5.2572 ms; peak GPU memory: 26.0317 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8685 | 0.7681 | 0.7784 | 0.9834 | 0.1319 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8838 | 0.7922 | 0.8089 | 0.9753 | 0.1259 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8935 | 0.8078 | 0.8308 | 0.9678 | 0.1216 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9000 | 0.8184 | 0.8481 | 0.9600 | 0.1181 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9042 | 0.8254 | 0.8622 | 0.9521 | 0.1152 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9071 | 0.8303 | 0.8740 | 0.9445 | 0.1127 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9092 | 0.8337 | 0.8847 | 0.9367 | 0.1104 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9105 | 0.8359 | 0.8948 | 0.9285 | 0.1082 | 0.0000 | 0.0000 |
| 0.5 | True | 0.9108 | 0.8364 | 0.9035 | 0.9200 | 0.1061 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9103 | 0.8355 | 0.9116 | 0.9108 | 0.1041 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9095 | 0.8342 | 0.9199 | 0.9012 | 0.1021 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9075 | 0.8310 | 0.9278 | 0.8901 | 0.0999 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9046 | 0.8263 | 0.9354 | 0.8779 | 0.0977 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9002 | 0.8190 | 0.9430 | 0.8633 | 0.0953 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8942 | 0.8094 | 0.9514 | 0.8457 | 0.0924 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8853 | 0.7951 | 0.9603 | 0.8235 | 0.0891 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8705 | 0.7719 | 0.9699 | 0.7920 | 0.0848 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8410 | 0.7274 | 0.9817 | 0.7382 | 0.0779 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
