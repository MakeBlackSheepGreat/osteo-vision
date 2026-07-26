# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext_unet_s20260726_20260726.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.65`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8984; IoU: 0.8158.
- Precision: 0.8982; recall: 0.9007.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.2996 ms; P95: 4.0165 ms; peak GPU memory: 22.1929 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8321 | 0.7130 | 0.7199 | 0.9871 | 0.1441 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8504 | 0.7402 | 0.7514 | 0.9809 | 0.1372 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8628 | 0.7591 | 0.7749 | 0.9747 | 0.1322 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8719 | 0.7732 | 0.7939 | 0.9684 | 0.1282 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8789 | 0.7843 | 0.8103 | 0.9619 | 0.1247 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8844 | 0.7931 | 0.8248 | 0.9550 | 0.1216 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8889 | 0.8004 | 0.8382 | 0.9479 | 0.1188 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8924 | 0.8061 | 0.8509 | 0.9401 | 0.1160 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8953 | 0.8107 | 0.8632 | 0.9319 | 0.1133 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8973 | 0.8141 | 0.8750 | 0.9229 | 0.1107 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8984 | 0.8158 | 0.8866 | 0.9126 | 0.1080 | 0.0000 | 0.0000 |
| 0.65 | True | 0.8984 | 0.8158 | 0.8982 | 0.9007 | 0.1052 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8970 | 0.8136 | 0.9100 | 0.8865 | 0.1022 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8936 | 0.8083 | 0.9221 | 0.8692 | 0.0988 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8879 | 0.7991 | 0.9350 | 0.8476 | 0.0950 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8769 | 0.7817 | 0.9485 | 0.8178 | 0.0903 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8565 | 0.7503 | 0.9635 | 0.7734 | 0.0840 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8078 | 0.6796 | 0.9811 | 0.6893 | 0.0733 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
