# 关键帧分割模型多随机种子选型报告

## 结论

- 推荐候选族：`residual_attention_unet_keyframe_segmenter`。
- 验证集选定 checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260727.pt`。
- 锁定阈值：`0.35`。
- 当前保持 `runtime_replacement_allowed=false`，进入严格 4K tiled 与平台闭环门控。

## 独立测试集比较

| 模型 | 随机种子数 | Dice 均值 +/- SD | IoU 均值 +/- SD | 召回率 | P95 ms | 峰值显存 MB | 门控 |
|---|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt U-Net baseline | 1 | 0.8987 +/- 0.0000 | 0.8176 +/- 0.0000 | 0.8881 | 3.33 | 22.19 | baseline |
| multiscale_depthwise_unet_keyframe_segmenter | 3 | 0.9041 +/- 0.0099 | 0.8258 +/- 0.0160 | 0.9017 | 4.53 | 21.14 | hold |
| nested_skip_unet_keyframe_segmenter | 3 | 0.9147 +/- 0.0044 | 0.8438 +/- 0.0068 | 0.9064 | 2.78 | 27.04 | pass |
| plain_unet_keyframe_segmenter | 3 | 0.9121 +/- 0.0051 | 0.8395 +/- 0.0078 | 0.9028 | 2.71 | 24.13 | pass |
| residual_attention_unet_keyframe_segmenter | 3 | 0.9167 +/- 0.0027 | 0.8476 +/- 0.0039 | 0.9066 | 6.83 | 27.02 | pass |

## 4K Tiled 模型选型对比

以下表格采用验证集选定 checkpoint 的锁定测试结果，并在同一台 RTX 5060 Laptop GPU 上执行官方尺寸 `3840 x 2160` 合成关键帧的 4K tiled 推理。所有模型使用 `512` 像素切片、`64` 像素重叠、批量 `4`、全证据输出，重复运行 3 次；每次均生成 mask、probability map、uncertainty、伪彩、overlay、risk mask 与 uncertain mask。

| 模型 | 参数量 | 平均训练损失 | 锁定测试集 Dice | 锁定测试集 IoU | 召回率 | 4K 模型 P95 (ms) | 4K 显存 (MB) | 4K 门控 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt U-Net 基线 | 77,258 | 0.166815 | 0.898735 | 0.817590 | 0.888125 | 853.29 | 656.32 | 通过 |
| 多尺度深度可分离 U-Net | 29,414 | 0.218038 | 0.912923 | 0.840246 | 0.912711 | 883.16 | 608.14 | 通过 |
| Plain U-Net | 92,846 | 0.229228 | 0.917576 | 0.847995 | 0.905498 | **566.39** | 704.38 | 通过 |
| Nested Skip U-Net | 99,374 | 0.229071 | 0.919556 | 0.851456 | **0.912017** | 712.62 | 752.41 | 通过 |
| Residual Attention U-Net（主选） | 403,785 | **0.146409** | **0.919809** | **0.852008** | 0.909238 | 761.85 | 723.58 | 通过 |

4K 门控要求为：官方 4K 尺寸、CUDA 执行、tiled 模式、45 个切片、输出尺寸一致、确定性掩膜、模型 P95 不高于 3000 ms、峰值显存不高于 2048 MB，以及候选区面积位于预设安全范围。五个模型均满足上述检查。

Residual Attention U-Net 在多随机种子均值和验证集选定 checkpoint 的锁定测试中均为最高 Dice/IoU。它仍需完成生产配置绑定与 MP4 平台流门控，才可替换当前生产运行配置。

## 证据边界

全部指标均基于公开、非目标域的荧光代理掩膜，不能用于衡量颌骨骨髓炎术中 ICG 场景的临床性能，也不能支持自动诊断结论。
