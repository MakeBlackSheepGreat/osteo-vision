# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_s20260726_20260726.pt`
- Manifests: 1; split: `val`; samples: 168.
- Recommended runtime threshold: `0.5`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8914; IoU: 0.8044.
- Precision: 0.8851; recall: 0.8999.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.4587 ms; P95: 4.3570 ms; peak GPU memory: 21.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8552 | 0.7474 | 0.7642 | 0.9722 | 0.1341 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8688 | 0.7683 | 0.7935 | 0.9615 | 0.1277 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8768 | 0.7810 | 0.8140 | 0.9519 | 0.1232 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8822 | 0.7895 | 0.8301 | 0.9431 | 0.1196 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8859 | 0.7954 | 0.8434 | 0.9347 | 0.1167 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8884 | 0.7994 | 0.8552 | 0.9261 | 0.1140 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8903 | 0.8025 | 0.8660 | 0.9179 | 0.1115 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8912 | 0.8041 | 0.8759 | 0.9091 | 0.1092 | 0.0000 | 0.0000 |
| 0.5 | True | 0.8914 | 0.8044 | 0.8851 | 0.8999 | 0.1069 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8910 | 0.8037 | 0.8939 | 0.8902 | 0.1047 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8900 | 0.8022 | 0.9025 | 0.8800 | 0.1025 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8881 | 0.7992 | 0.9111 | 0.8685 | 0.1001 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8851 | 0.7944 | 0.9197 | 0.8553 | 0.0976 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8807 | 0.7875 | 0.9285 | 0.8398 | 0.0949 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8742 | 0.7774 | 0.9382 | 0.8208 | 0.0918 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8645 | 0.7623 | 0.9488 | 0.7962 | 0.0880 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8477 | 0.7369 | 0.9610 | 0.7607 | 0.0829 | 0.0000 | 0.0000 |
| 0.95 | False | 0.8100 | 0.6825 | 0.9765 | 0.6945 | 0.0744 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
