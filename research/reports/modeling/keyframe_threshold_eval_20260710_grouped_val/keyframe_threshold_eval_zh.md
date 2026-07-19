# 2D Keyframe 分割阈值扫描报告

## 结论

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_grouped_20260710.pt`
- Manifest：1 个；split：`val`；样本数：56。
- 推荐运行阈值：`0.45`；选择原因：`max_dice_with_empty_and_oversegmentation_guards`。
- 推荐阈值 Dice：0.9160；IoU：0.8452。
- 空 mask 率：0.0000；过分割率：0.0000。

## 阈值表

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2 | False | 0.9048 | 0.8265 | 0.1899 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9094 | 0.8342 | 0.1848 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9123 | 0.8391 | 0.1807 | 0.0000 | 0.0000 |
| 0.35 | False | 0.9145 | 0.8428 | 0.1769 | 0.0000 | 0.0000 |
| 0.4 | False | 0.9156 | 0.8446 | 0.1734 | 0.0000 | 0.0000 |
| 0.45 | True | 0.9160 | 0.8452 | 0.1701 | 0.0000 | 0.0000 |
| 0.5 | False | 0.9156 | 0.8445 | 0.1670 | 0.0000 | 0.0000 |
| 0.55 | False | 0.9145 | 0.8427 | 0.1638 | 0.0000 | 0.0000 |
| 0.6 | False | 0.9126 | 0.8395 | 0.1605 | 0.0000 | 0.0000 |
| 0.65 | False | 0.9096 | 0.8344 | 0.1572 | 0.0000 | 0.0000 |
| 0.7 | False | 0.9054 | 0.8275 | 0.1537 | 0.0000 | 0.0000 |

## 医学边界

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG 不是颌骨骨髓炎特异性探针，本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。
