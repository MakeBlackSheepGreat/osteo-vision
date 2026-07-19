# 2D Keyframe 分割阈值扫描报告

## 结论

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_candidate_20260714.pt`
- Manifest：1 个；split：`val`；样本数：56。
- 推荐运行阈值：`0.55`；选择原因：`max_dice_with_empty_and_oversegmentation_guards`。
- 推荐阈值 Dice：0.8932；IoU：0.8073。
- 空 mask 率：0.0000；过分割率：0.0000。

## 阈值表

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.3 | False | 0.8818 | 0.7887 | 0.1192 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8864 | 0.7961 | 0.1161 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8898 | 0.8016 | 0.1132 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8920 | 0.8053 | 0.1106 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8929 | 0.8068 | 0.1079 | 0.0000 | 0.0000 |
| 0.55 | True | 0.8932 | 0.8073 | 0.1053 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8924 | 0.8060 | 0.1026 | 0.0000 | 0.0000 |

## 医学边界

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG 不是颌骨骨髓炎特异性探针，本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。
