# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_s20260726_20260727.pt`
- Manifests: 1; split: `test`; samples: 72.
- Recommended runtime threshold: `0.5`; reason: `fixed_threshold_from_validation`.
- Recommended Dice: 0.9060; IoU: 0.8285.
- Precision: 0.9082; recall: 0.9056.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.9349 ms; P95: 5.3204 ms; peak GPU memory: 21.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8763 | 0.7805 | 0.7967 | 0.9753 | 0.1362 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8885 | 0.7999 | 0.8241 | 0.9655 | 0.1304 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8954 | 0.8110 | 0.8428 | 0.9566 | 0.1263 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8999 | 0.8184 | 0.8577 | 0.9481 | 0.1230 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9029 | 0.8232 | 0.8700 | 0.9399 | 0.1201 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9048 | 0.8265 | 0.8809 | 0.9317 | 0.1176 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9058 | 0.8281 | 0.8905 | 0.9233 | 0.1152 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9062 | 0.8287 | 0.8997 | 0.9144 | 0.1129 | 0.0000 | 0.0000 |
| 0.5 | True | 0.9060 | 0.8285 | 0.9082 | 0.9056 | 0.1107 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9052 | 0.8271 | 0.9165 | 0.8958 | 0.1085 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9034 | 0.8241 | 0.9241 | 0.8852 | 0.1063 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9007 | 0.8198 | 0.9317 | 0.8734 | 0.1040 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8970 | 0.8137 | 0.9394 | 0.8599 | 0.1015 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8915 | 0.8049 | 0.9474 | 0.8436 | 0.0987 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8837 | 0.7925 | 0.9555 | 0.8238 | 0.0955 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8720 | 0.7741 | 0.9644 | 0.7977 | 0.0915 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8526 | 0.7443 | 0.9745 | 0.7598 | 0.0862 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8093 | 0.6816 | 0.9864 | 0.6884 | 0.0770 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
