# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_s20260715_20260715.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.4`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8761; IoU: 0.7798.
- Precision: 0.8606; recall: 0.8941.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.1845 ms; P95: 3.7051 ms; peak GPU memory: 20.1387 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8467 | 0.7344 | 0.7571 | 0.9615 | 0.1326 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8599 | 0.7544 | 0.7875 | 0.9482 | 0.1257 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8668 | 0.7651 | 0.8081 | 0.9360 | 0.1209 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8713 | 0.7722 | 0.8245 | 0.9253 | 0.1172 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8741 | 0.7765 | 0.8382 | 0.9147 | 0.1139 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8758 | 0.7792 | 0.8503 | 0.9044 | 0.1110 | 0.0000 | 0.0000 |
| 0.4 | True | 0.8761 | 0.7798 | 0.8606 | 0.8941 | 0.1084 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8760 | 0.7795 | 0.8702 | 0.8836 | 0.1060 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8751 | 0.7783 | 0.8796 | 0.8726 | 0.1035 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8734 | 0.7756 | 0.8886 | 0.8607 | 0.1010 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8710 | 0.7719 | 0.8974 | 0.8482 | 0.0986 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8671 | 0.7659 | 0.9058 | 0.8337 | 0.0960 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8623 | 0.7587 | 0.9146 | 0.8180 | 0.0933 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8558 | 0.7488 | 0.9241 | 0.7994 | 0.0902 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8468 | 0.7354 | 0.9336 | 0.7773 | 0.0868 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8338 | 0.7164 | 0.9447 | 0.7489 | 0.0826 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8118 | 0.6850 | 0.9575 | 0.7074 | 0.0770 | 0.0000 | 0.0000 |
| 0.95 | False | 0.7648 | 0.6215 | 0.9733 | 0.6328 | 0.0677 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
