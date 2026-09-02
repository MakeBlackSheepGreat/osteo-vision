# 关键帧分割模型多随机种子选型报告

## 结论

- 推荐候选族：`residual_attention_unet_keyframe_segmenter`。
- 验证集选定 checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260715_20260715.pt`。
- 锁定阈值：`0.4`。
- 当前保持 `runtime_replacement_allowed=false`，进入严格 4K tiled 与平台闭环门控。

## 独立测试集比较

| 模型 | 随机种子数 | Dice 均值 +/- SD | IoU 均值 +/- SD | 召回率 | P95 ms | 峰值显存 MB | 门控 |
|---|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt U-Net baseline | 1 | 0.8987 +/- 0.0000 | 0.8164 +/- 0.0000 | 0.8908 | 3.57 | 22.19 | baseline |
| multiscale_depthwise_unet_keyframe_segmenter | 3 | 0.8978 +/- 0.0113 | 0.8149 +/- 0.0183 | 0.8933 | 4.25 | 20.14 | hold |
| residual_attention_unet_keyframe_segmenter | 3 | 0.9149 +/- 0.0041 | 0.8435 +/- 0.0071 | 0.9099 | 5.13 | 26.03 | pass |

## 证据边界

全部指标均基于公开、非目标域的荧光代理掩膜，不能用于衡量颌骨骨髓炎术中 ICG 场景的临床性能，也不能支持自动诊断结论。
