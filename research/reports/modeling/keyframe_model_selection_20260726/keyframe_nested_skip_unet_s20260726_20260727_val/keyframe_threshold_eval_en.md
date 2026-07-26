# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_nested_skip_unet_s20260726_20260727.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.4`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9168; IoU: 0.8466.
- Precision: 0.9144; recall: 0.9209.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 2.3962 ms; P95: 3.2707 ms; peak GPU memory: 27.0381 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8990 | 0.8169 | 0.8382 | 0.9706 | 0.1217 | 0.0000 | 0.0000 |
| 0.15 | False | 0.9074 | 0.8307 | 0.8610 | 0.9604 | 0.1172 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9117 | 0.8381 | 0.8765 | 0.9515 | 0.1141 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9143 | 0.8424 | 0.8884 | 0.9433 | 0.1115 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9159 | 0.8451 | 0.8984 | 0.9357 | 0.1094 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9167 | 0.8465 | 0.9070 | 0.9283 | 0.1075 | 0.0000 | 0.0000 |
| 0.4 | True | 0.9168 | 0.8466 | 0.9144 | 0.9209 | 0.1057 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9164 | 0.8460 | 0.9212 | 0.9134 | 0.1041 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9155 | 0.8446 | 0.9274 | 0.9058 | 0.1025 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9142 | 0.8424 | 0.9333 | 0.8978 | 0.1009 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9123 | 0.8392 | 0.9389 | 0.8891 | 0.0994 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9100 | 0.8354 | 0.9443 | 0.8800 | 0.0978 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9070 | 0.8303 | 0.9499 | 0.8696 | 0.0960 | 0.0000 | 0.0000 |
| 0.75 | False | 0.9031 | 0.8240 | 0.9556 | 0.8579 | 0.0941 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8978 | 0.8153 | 0.9615 | 0.8439 | 0.0920 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8902 | 0.8031 | 0.9681 | 0.8259 | 0.0894 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8777 | 0.7832 | 0.9753 | 0.7999 | 0.0859 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8516 | 0.7430 | 0.9843 | 0.7525 | 0.0800 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
