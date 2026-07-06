# 2D Keyframe 分割阈值扫描报告

## 结论

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt`
- Manifest：1 个；split：`val`；样本数：37。
- 推荐运行阈值：`0.6`；选择原因：`max_dice_with_empty_and_oversegmentation_guards`。
- 推荐阈值 Dice：0.8682；IoU：0.7677。
- 空 mask 率：0.0000；过分割率：0.0000。

## 阈值表

| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | False | 0.7896 | 0.6531 | 0.2742 | 0.0000 | 0.0270 |
| 0.15 | False | 0.8179 | 0.6926 | 0.2536 | 0.0000 | 0.0270 |
| 0.2 | False | 0.8321 | 0.7132 | 0.2417 | 0.0000 | 0.0270 |
| 0.25 | False | 0.8423 | 0.7282 | 0.2326 | 0.0000 | 0.0270 |
| 0.3 | False | 0.8498 | 0.7395 | 0.2248 | 0.0000 | 0.0270 |
| 0.35 | False | 0.8559 | 0.7488 | 0.2180 | 0.0000 | 0.0270 |
| 0.4 | False | 0.8603 | 0.7556 | 0.2120 | 0.0000 | 0.0270 |
| 0.45 | False | 0.8635 | 0.7603 | 0.2062 | 0.0000 | 0.0000 |
| 0.5 | False | 0.8658 | 0.7640 | 0.2008 | 0.0000 | 0.0000 |
| 0.55 | False | 0.8674 | 0.7665 | 0.1954 | 0.0000 | 0.0000 |
| 0.6 | True | 0.8682 | 0.7677 | 0.1900 | 0.0000 | 0.0000 |

## 医学边界

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance.
ICG 不是颌骨骨髓炎特异性探针，本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。
