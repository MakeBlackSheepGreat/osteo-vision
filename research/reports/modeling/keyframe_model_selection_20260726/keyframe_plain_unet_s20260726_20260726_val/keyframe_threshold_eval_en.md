# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_plain_unet_s20260726_20260726.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.5`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9092; IoU: 0.8339.
- Precision: 0.9046; recall: 0.9155.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 1.9586 ms; P95: 2.4316 ms; peak GPU memory: 24.1309 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8774 | 0.7821 | 0.7971 | 0.9771 | 0.1288 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8898 | 0.8019 | 0.8240 | 0.9683 | 0.1234 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8970 | 0.8137 | 0.8428 | 0.9602 | 0.1196 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9017 | 0.8214 | 0.8571 | 0.9527 | 0.1167 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9049 | 0.8267 | 0.8692 | 0.9452 | 0.1141 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9070 | 0.8303 | 0.8794 | 0.9380 | 0.1119 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9084 | 0.8326 | 0.8886 | 0.9307 | 0.1099 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9090 | 0.8336 | 0.8967 | 0.9233 | 0.1080 | 0.0000 | 0.0000 |
| 0.5 | True | 0.9092 | 0.8339 | 0.9046 | 0.9155 | 0.1062 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9089 | 0.8334 | 0.9120 | 0.9074 | 0.1043 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9080 | 0.8321 | 0.9192 | 0.8988 | 0.1025 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9065 | 0.8296 | 0.9264 | 0.8893 | 0.1006 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9042 | 0.8258 | 0.9334 | 0.8786 | 0.0986 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9010 | 0.8204 | 0.9406 | 0.8663 | 0.0965 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8963 | 0.8129 | 0.9484 | 0.8515 | 0.0940 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8890 | 0.8010 | 0.9568 | 0.8320 | 0.0910 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8769 | 0.7820 | 0.9665 | 0.8046 | 0.0871 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8505 | 0.7415 | 0.9788 | 0.7542 | 0.0805 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
