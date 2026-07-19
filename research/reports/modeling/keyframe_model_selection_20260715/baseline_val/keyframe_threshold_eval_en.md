# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_candidate_20260714.pt`
- Manifests: 1; split: `val`; samples: 56.
- Recommended runtime threshold: `0.55`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8932; IoU: 0.8073.
- Precision: 0.8907; recall: 0.8977.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.4199 ms; P95: 4.2003 ms; peak GPU memory: 22.1929 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.8403 | 0.7251 | 0.7380 | 0.9774 | 0.1386 | 0.0000 | 0.0000 |
| 0.15 | False | 0.8573 | 0.7507 | 0.7700 | 0.9688 | 0.1316 | 0.0000 | 0.0000 |
| 0.2 | False | 0.8680 | 0.7671 | 0.7930 | 0.9606 | 0.1267 | 0.0000 | 0.0000 |
| 0.25 | False | 0.8759 | 0.7795 | 0.8122 | 0.9524 | 0.1226 | 0.0000 | 0.0000 |
| 0.3 | False | 0.8818 | 0.7887 | 0.8286 | 0.9442 | 0.1192 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8864 | 0.7961 | 0.8433 | 0.9361 | 0.1161 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8898 | 0.8016 | 0.8565 | 0.9277 | 0.1132 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8920 | 0.8053 | 0.8686 | 0.9188 | 0.1106 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8929 | 0.8068 | 0.8797 | 0.9086 | 0.1079 | 0.0000 | 0.0000 |
| 0.55 | True | 0.8932 | 0.8073 | 0.8907 | 0.8977 | 0.1053 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8924 | 0.8060 | 0.9013 | 0.8857 | 0.1026 | 0.0000 | 0.0000 |
| 0.65 | False | 0.8903 | 0.8027 | 0.9123 | 0.8715 | 0.0998 | 0.0000 | 0.0000 |
| 0.7 | False | 0.8866 | 0.7967 | 0.9228 | 0.8552 | 0.0967 | 0.0000 | 0.0000 |
| 0.75 | False | 0.8811 | 0.7882 | 0.9336 | 0.8365 | 0.0935 | 0.0000 | 0.0000 |
| 0.8 | False | 0.8724 | 0.7746 | 0.9450 | 0.8124 | 0.0896 | 0.0000 | 0.0000 |
| 0.85 | False | 0.8580 | 0.7524 | 0.9569 | 0.7799 | 0.0849 | 0.0000 | 0.0000 |
| 0.9 | False | 0.8323 | 0.7143 | 0.9704 | 0.7309 | 0.0783 | 0.0000 | 0.0000 |
| 0.95 | False | 0.7754 | 0.6352 | 0.9852 | 0.6416 | 0.0676 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
