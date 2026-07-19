# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260715_20260715.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.4`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.9117; IoU: 0.8379.
- Precision: 0.9045; recall: 0.9210.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 4.3780 ms; P95: 5.2114 ms; peak GPU memory: 26.0317 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8808 | 0.7875 | 0.8018 | 0.9786 | 0.1275 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8944 | 0.8093 | 0.8318 | 0.9688 | 0.1216 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9021 | 0.8219 | 0.8528 | 0.9590 | 0.1173 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9069 | 0.8299 | 0.8693 | 0.9496 | 0.1139 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9095 | 0.8343 | 0.8826 | 0.9399 | 0.1111 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9111 | 0.8370 | 0.8943 | 0.9305 | 0.1085 | 0.0000 | 0.0000 |
| 0.4 | True | 0.9117 | 0.8379 | 0.9045 | 0.9210 | 0.1061 | 0.0000 | 0.0000 |
| 0.45 | False | 0.9115 | 0.8376 | 0.9138 | 0.9112 | 0.1039 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9102 | 0.8356 | 0.9220 | 0.9008 | 0.1018 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9083 | 0.8324 | 0.9300 | 0.8898 | 0.0996 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9051 | 0.8272 | 0.9374 | 0.8772 | 0.0974 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9008 | 0.8201 | 0.9444 | 0.8633 | 0.0951 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8952 | 0.8110 | 0.9514 | 0.8475 | 0.0926 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8879 | 0.7994 | 0.9585 | 0.8294 | 0.0900 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8779 | 0.7835 | 0.9655 | 0.8073 | 0.0869 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8635 | 0.7613 | 0.9728 | 0.7788 | 0.0831 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8411 | 0.7278 | 0.9810 | 0.7389 | 0.0782 | 0.0000 | 0.0000 |
| 0.95 | False | 0.7955 | 0.6631 | 0.9895 | 0.6682 | 0.0699 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
