# 2D Keyframe 分割阈值扫描报告

## 结论

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_multiscale_depthwise_unet_s20260715_20260715.pt`
- Manifest：1 个；split：`test`；样本数：24。
- 推荐运行阈值：`0.4`；选择原因：`max_dice_with_empty_and_oversegmentation_guards`。
- 推荐阈值 Dice：0.8848；IoU：0.7938。
- 精确率：0.8804；召回率：0.8908。
- 空 mask 率：0.0000；过分割率：0.0000。
- 单帧延迟：3.2836 ms；P95：4.0082 ms；峰值显存：20.1387 MB。

## 阈值表

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.4 | True | 0.8848 | 0.7938 | 0.8804 | 0.8908 | 0.1109 | 0.0000 | 0.0000 |

## 医学边界

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG 主要反映灌注与组织活性差异；本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。
