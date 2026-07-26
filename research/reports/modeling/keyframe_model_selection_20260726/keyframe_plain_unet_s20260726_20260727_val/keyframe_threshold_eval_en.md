# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_plain_unet_s20260726_20260727.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.4`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9170; IoU: 0.8468.
- Precision: 0.9126; recall: 0.9229.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 1.9366 ms; P95: 2.4144 ms; peak GPU memory: 24.1309 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8953 | 0.8109 | 0.8297 | 0.9735 | 0.1232 | 0.0000 | 0.0000 |
| 0.15 | False | 0.9053 | 0.8272 | 0.8549 | 0.9633 | 0.1183 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9108 | 0.8364 | 0.8721 | 0.9544 | 0.1149 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9139 | 0.8416 | 0.8850 | 0.9461 | 0.1122 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9158 | 0.8448 | 0.8956 | 0.9382 | 0.1099 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9168 | 0.8465 | 0.9047 | 0.9307 | 0.1079 | 0.0000 | 0.0000 |
| 0.4 | True | 0.9170 | 0.8468 | 0.9126 | 0.9229 | 0.1061 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9167 | 0.8465 | 0.9196 | 0.9155 | 0.1044 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9160 | 0.8452 | 0.9261 | 0.9077 | 0.1028 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9148 | 0.8431 | 0.9323 | 0.8995 | 0.1011 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9131 | 0.8404 | 0.9386 | 0.8907 | 0.0995 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9109 | 0.8367 | 0.9444 | 0.8814 | 0.0978 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9078 | 0.8317 | 0.9501 | 0.8710 | 0.0960 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9039 | 0.8253 | 0.9559 | 0.8592 | 0.0941 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8985 | 0.8164 | 0.9619 | 0.8448 | 0.0919 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8907 | 0.8037 | 0.9682 | 0.8266 | 0.0893 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8783 | 0.7841 | 0.9754 | 0.8009 | 0.0858 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8536 | 0.7462 | 0.9841 | 0.7560 | 0.0802 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
