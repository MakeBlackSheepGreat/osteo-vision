# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_plain_unet_s20260726_20260728.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.5`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9076; IoU: 0.8327.
- Precision: 0.9194; recall: 0.9004.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 2.1521 ms; P95: 2.9311 ms; peak GPU memory: 24.1309 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8849 | 0.7945 | 0.8165 | 0.9700 | 0.1313 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8952 | 0.8114 | 0.8422 | 0.9598 | 0.1259 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9009 | 0.8209 | 0.8600 | 0.9504 | 0.1220 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9045 | 0.8270 | 0.8738 | 0.9418 | 0.1190 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9067 | 0.8307 | 0.8853 | 0.9335 | 0.1164 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9077 | 0.8326 | 0.8947 | 0.9254 | 0.1141 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9082 | 0.8334 | 0.9035 | 0.9173 | 0.1119 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9081 | 0.8335 | 0.9117 | 0.9090 | 0.1099 | 0.0000 | 0.0000 |
| 0.5 | True | 0.9076 | 0.8327 | 0.9194 | 0.9004 | 0.1079 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9061 | 0.8303 | 0.9264 | 0.8910 | 0.1059 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9042 | 0.8274 | 0.9334 | 0.8812 | 0.1039 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9015 | 0.8231 | 0.9402 | 0.8703 | 0.1019 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8980 | 0.8175 | 0.9469 | 0.8584 | 0.0997 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8930 | 0.8095 | 0.9536 | 0.8441 | 0.0974 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8858 | 0.7979 | 0.9606 | 0.8262 | 0.0945 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8752 | 0.7812 | 0.9683 | 0.8028 | 0.0911 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8571 | 0.7533 | 0.9769 | 0.7678 | 0.0863 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8142 | 0.6902 | 0.9863 | 0.6975 | 0.0775 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
