# 2D Keyframe 分割阈值扫描报告

## 结论

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt`
- Manifest：1 个；split：`val`；样本数：37。
- 推荐运行阈值：`0.15`；选择原因：`max_dice_with_empty_and_oversegmentation_guards`。
- 推荐阈值 Dice：0.9093；IoU：0.8340。
- 空 mask 率：0.0000；过分割率：0.0000。

## 阈值表

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.9089 | 0.8332 | 0.1932 | 0.0000 | 0.0000 |
| 0.15 | True | 0.9093 | 0.8340 | 0.1860 | 0.0000 | 0.0000 |
| 0.2 | False | 0.9080 | 0.8320 | 0.1807 | 0.0000 | 0.0000 |
| 0.25 | False | 0.9058 | 0.8282 | 0.1764 | 0.0000 | 0.0000 |
| 0.3 | False | 0.9030 | 0.8237 | 0.1728 | 0.0000 | 0.0000 |
| 0.35 | False | 0.8999 | 0.8187 | 0.1695 | 0.0000 | 0.0000 |
| 0.4 | False | 0.8962 | 0.8128 | 0.1664 | 0.0000 | 0.0000 |
| 0.45 | False | 0.8925 | 0.8067 | 0.1635 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8883 | 0.7999 | 0.1608 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8833 | 0.7920 | 0.1579 | 0.0000 | 0.0000 |
| 0.6 | False | 0.8778 | 0.7833 | 0.1550 | 0.0000 | 0.0000 |

## 医学边界

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG 不是颌骨骨髓炎特异性探针，本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。
