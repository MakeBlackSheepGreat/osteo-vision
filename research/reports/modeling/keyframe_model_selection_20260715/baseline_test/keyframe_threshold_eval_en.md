# 2D Keyframe Segmentation Threshold Sweep

## Summary

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_candidate_20260714.pt`
- Manifests: 1; split: `test`; samples: 24.
- Recommended runtime threshold: `0.55`; reason: `max_dice_with_empty_and_oversegmentation_guards`.
- Recommended Dice: 0.8987; IoU: 0.8164.
- Precision: 0.9084; recall: 0.8908.
- Empty-mask rate: 0.0000; over-segmentation rate: 0.0000.
- Per-frame latency: 3.0934 ms; P95: 3.5660 ms; peak GPU memory: 22.1929 MB.

## Threshold Table

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.55 | True | 0.8987 | 0.8164 | 0.9084 | 0.8908 | 0.1073 | 0.0000 | 0.0000 |

## Medical Boundary

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.
