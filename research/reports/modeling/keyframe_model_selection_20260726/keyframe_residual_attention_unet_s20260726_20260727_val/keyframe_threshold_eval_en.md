# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260727.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.35`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9174; IoU: 0.8477.
- Precision: 0.9141; recall: 0.9229.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.4626 ms; P95: 5.1770 ms; peak GPU memory: 27.0166 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8949 | 0.8102 | 0.8279 | 0.9755 | 0.1240 | 0.0000 | 0.0000 |
| 0.15 | False | 0.9063 | 0.8291 | 0.8565 | 0.9642 | 0.1185 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9123 | 0.8390 | 0.8761 | 0.9536 | 0.1145 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9155 | 0.8444 | 0.8911 | 0.9433 | 0.1113 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9170 | 0.8470 | 0.9035 | 0.9330 | 0.1086 | 0.0000 | 0.0000 |
| 0.35 | True | 0.9174 | 0.8477 | 0.9141 | 0.9229 | 0.1061 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9167 | 0.8466 | 0.9234 | 0.9124 | 0.1038 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9152 | 0.8440 | 0.9314 | 0.9017 | 0.1017 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9129 | 0.8403 | 0.9388 | 0.8907 | 0.0996 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9098 | 0.8352 | 0.9454 | 0.8792 | 0.0976 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9060 | 0.8288 | 0.9518 | 0.8667 | 0.0955 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9011 | 0.8209 | 0.9580 | 0.8530 | 0.0934 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8950 | 0.8110 | 0.9638 | 0.8378 | 0.0911 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8871 | 0.7983 | 0.9696 | 0.8200 | 0.0886 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8766 | 0.7816 | 0.9753 | 0.7984 | 0.0858 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8617 | 0.7585 | 0.9812 | 0.7705 | 0.0822 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8379 | 0.7229 | 0.9870 | 0.7304 | 0.0774 | 0.0000 | 0.0000 |
| 0.95 | False | 0.7884 | 0.6529 | 0.9936 | 0.6559 | 0.0689 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
