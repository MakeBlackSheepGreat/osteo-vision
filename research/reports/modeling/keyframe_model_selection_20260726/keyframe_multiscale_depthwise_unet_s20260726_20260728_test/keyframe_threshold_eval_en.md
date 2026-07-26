# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_s20260726_20260728.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.65`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9129; IoU: 0.8402.
- Precision: 0.9150; recall: 0.9127.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.3483 ms; P95: 3.9822 ms; peak GPU memory: 21.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8668 | 0.7655 | 0.7743 | 0.9858 | 0.1417 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8808 | 0.7874 | 0.8012 | 0.9793 | 0.1360 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8900 | 0.8022 | 0.8208 | 0.9734 | 0.1319 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8964 | 0.8126 | 0.8361 | 0.9675 | 0.1287 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9014 | 0.8208 | 0.8492 | 0.9618 | 0.1259 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9049 | 0.8266 | 0.8604 | 0.9557 | 0.1235 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9079 | 0.8316 | 0.8708 | 0.9498 | 0.1212 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9101 | 0.8354 | 0.8803 | 0.9436 | 0.1191 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9117 | 0.8381 | 0.8893 | 0.9369 | 0.1170 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9128 | 0.8399 | 0.8980 | 0.9297 | 0.1149 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9132 | 0.8407 | 0.9064 | 0.9219 | 0.1129 | 0.0000 | 0.0000 |
| 0.65 | True | 0.9129 | 0.8402 | 0.9150 | 0.9127 | 0.1106 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9118 | 0.8384 | 0.9236 | 0.9022 | 0.1083 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9097 | 0.8351 | 0.9326 | 0.8900 | 0.1057 | 0.0000 | 0.0000 |
| 0.8 | False | 0.9059 | 0.8290 | 0.9422 | 0.8746 | 0.1027 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8989 | 0.8178 | 0.9527 | 0.8535 | 0.0990 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8859 | 0.7972 | 0.9646 | 0.8220 | 0.0941 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8542 | 0.7486 | 0.9795 | 0.7611 | 0.0855 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
