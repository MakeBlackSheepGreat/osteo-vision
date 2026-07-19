# 2D Keyframe 分割阈值扫描报告

## 结论

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260716_20260715.pt`
- Manifest：1 个；split：`test`；样本数：24。
- 推荐运行阈值：`0.5`；选择原因：`max_dice_with_empty_and_oversegmentation_guards`。
- 推荐阈值 Dice：0.9169；IoU：0.8467。
- 精确率：0.9256；召回率：0.9096。
- 空 mask 率：0.0000；过分割率：0.0000。
- 单帧延迟：4.1280 ms；P95：4.8247 ms；峰值显存：26.0317 MB。

## 阈值表

| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | True | 0.9169 | 0.8467 | 0.9256 | 0.9096 | 0.1076 | 0.0000 | 0.0000 |

## 医学边界

Threshold metrics are computed against pseudo masks from public/proxy keyframes only. Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured.
ICG 主要反映灌注与组织活性差异；本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。
