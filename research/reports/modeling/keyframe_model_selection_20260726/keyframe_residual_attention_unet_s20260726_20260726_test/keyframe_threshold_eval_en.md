# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260726.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.55`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9147; IoU: 0.8446.
- Precision: 0.9309; recall: 0.9028.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 6.6376 ms; P95: 9.1966 ms; peak GPU memory: 27.0166 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8848 | 0.7941 | 0.8092 | 0.9790 | 0.1339 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8979 | 0.8155 | 0.8384 | 0.9697 | 0.1280 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9055 | 0.8282 | 0.8586 | 0.9612 | 0.1238 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9104 | 0.8366 | 0.8743 | 0.9531 | 0.1205 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9132 | 0.8415 | 0.8869 | 0.9448 | 0.1177 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9152 | 0.8449 | 0.8977 | 0.9369 | 0.1153 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9160 | 0.8464 | 0.9073 | 0.9286 | 0.1130 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9162 | 0.8469 | 0.9158 | 0.9204 | 0.1109 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9158 | 0.8463 | 0.9236 | 0.9119 | 0.1089 | 0.0000 | 0.0000 |
| 0.55 | True | 0.9147 | 0.8446 | 0.9309 | 0.9028 | 0.1069 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9127 | 0.8412 | 0.9379 | 0.8926 | 0.1049 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9099 | 0.8367 | 0.9447 | 0.8814 | 0.1028 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9061 | 0.8305 | 0.9513 | 0.8689 | 0.1006 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9011 | 0.8225 | 0.9581 | 0.8545 | 0.0982 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8941 | 0.8112 | 0.9649 | 0.8370 | 0.0954 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8839 | 0.7950 | 0.9720 | 0.8146 | 0.0922 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8675 | 0.7693 | 0.9794 | 0.7827 | 0.0878 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8341 | 0.7189 | 0.9885 | 0.7254 | 0.0805 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
