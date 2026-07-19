# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_20260715.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.45`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9010; IoU: 0.8199.
- Precision: 0.8997; recall: 0.9035.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.7279 ms; P95: 4.7131 ms; peak GPU memory: 20.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8766 | 0.7807 | 0.8017 | 0.9682 | 0.1260 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8877 | 0.7983 | 0.8287 | 0.9568 | 0.1205 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8937 | 0.8080 | 0.8474 | 0.9465 | 0.1165 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8973 | 0.8139 | 0.8616 | 0.9373 | 0.1135 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8993 | 0.8171 | 0.8730 | 0.9284 | 0.1109 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9005 | 0.8192 | 0.8830 | 0.9200 | 0.1086 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9009 | 0.8199 | 0.8918 | 0.9116 | 0.1065 | 0.0000 | 0.0000 |
| 0.45 | True | 0.9010 | 0.8199 | 0.8997 | 0.9035 | 0.1047 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9002 | 0.8188 | 0.9072 | 0.8948 | 0.1028 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8988 | 0.8164 | 0.9141 | 0.8855 | 0.1009 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8971 | 0.8136 | 0.9207 | 0.8760 | 0.0991 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8946 | 0.8096 | 0.9273 | 0.8656 | 0.0972 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8914 | 0.8045 | 0.9340 | 0.8541 | 0.0952 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8871 | 0.7975 | 0.9407 | 0.8409 | 0.0930 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8813 | 0.7884 | 0.9483 | 0.8249 | 0.0905 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8728 | 0.7750 | 0.9562 | 0.8045 | 0.0875 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8597 | 0.7548 | 0.9651 | 0.7768 | 0.0837 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8331 | 0.7150 | 0.9760 | 0.7285 | 0.0775 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
