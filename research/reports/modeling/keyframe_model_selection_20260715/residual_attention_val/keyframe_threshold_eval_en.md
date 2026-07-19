# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_20260715.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.4`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9040; IoU: 0.8249.
- Precision: 0.8928; recall: 0.9179.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.7901 ms; P95: 5.4597 ms; peak GPU memory: 26.0317 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8705 | 0.7714 | 0.7857 | 0.9780 | 0.1297 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8848 | 0.7938 | 0.8169 | 0.9671 | 0.1233 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8931 | 0.8073 | 0.8389 | 0.9571 | 0.1188 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8984 | 0.8157 | 0.8560 | 0.9474 | 0.1153 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9014 | 0.8207 | 0.8700 | 0.9375 | 0.1122 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9032 | 0.8236 | 0.8821 | 0.9277 | 0.1095 | 0.0000 | 0.0000 |
| 0.4 | True | 0.9040 | 0.8249 | 0.8928 | 0.9179 | 0.1070 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9038 | 0.8247 | 0.9025 | 0.9077 | 0.1046 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9032 | 0.8237 | 0.9118 | 0.8975 | 0.1023 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9014 | 0.8209 | 0.9200 | 0.8864 | 0.1001 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8991 | 0.8171 | 0.9280 | 0.8748 | 0.0979 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8959 | 0.8119 | 0.9361 | 0.8619 | 0.0956 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8912 | 0.8044 | 0.9437 | 0.8473 | 0.0932 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8850 | 0.7946 | 0.9512 | 0.8305 | 0.0906 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8772 | 0.7824 | 0.9589 | 0.8115 | 0.0877 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8657 | 0.7647 | 0.9669 | 0.7870 | 0.0843 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8468 | 0.7364 | 0.9754 | 0.7517 | 0.0797 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8102 | 0.6838 | 0.9848 | 0.6920 | 0.0725 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
