# D025 代理分割模型对比结论

## 结论

当前不建议把主线 checkpoint 从 ConvNeXt-style 3D 代理分割模型切换到 MONAI SegResNetDS。本轮已在原 ConvNeXt-style checkpoint 上继续训练 1500 batch，并把更优的续训候选提升为本地 `d025_lesion_smoke.pt` 主线 checkpoint。

主要原因是：在同样使用 D025 CBCT lesion ROI 64³ 缓存、209 例训练和 53 例验证的设置下，SegResNetDS 的 Mean Dice 和 Mean IoU 低于当前 ConvNeXt-style baseline。续训后的 ConvNeXt-style 主线进一步提升到 Mean Dice 0.6567、Mean IoU 0.5553，并且 Mean HD95 降至 15.2370；平台演示阶段应继续保留 ConvNeXt-style 路线。

## 对比表

| 模型 | 参数量 | 训练 batch | 最优阈值 | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision | 建议 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt-style 3D U-Net proxy continued | 198,698 | 4500 | 0.20 | 0.6567 | 0.5553 | 15.2370 | 0.4797 | 0.6900 | 0.7238 | 已提升为本地主线 |
| ConvNeXt-style 3D U-Net proxy previous | 198,698 | 3000 | 0.20 | 0.6266 | 0.5183 | 17.6413 | 0.4227 | 0.6756 | 0.6932 | 旧主线备份 |
| MONAI SegResNetDS | 3,154,514 | 3000 | 0.20 | 0.5741 | 0.4766 | 13.8795 | 0.4101 | 0.5721 | 0.7128 | 保留为对照 baseline |

## 产物

- ConvNeXt-style 续训评估：`research/reports/modeling/d025_continue_1500_eval_20260704/d025_proxy_model_evaluation_20260704_zh.md`
- ConvNeXt-style 主线报告：`research/reports/modeling/d025_lesion_smoke_model_20260704_zh.md`
- SegResNetDS 训练报告：`research/reports/modeling/d025_monai_segresnetds_training_20260704_zh.md`
- SegResNetDS checkpoint：`artifacts/checkpoints/osteo_vision/d025_monai_segresnetds.pt`
- SegResNetDS 失败样本预览：`research/reports/modeling/assets/d025_monai_segresnetds_20260704T094021Z/`

## 下一步

1. 主线继续使用已续训提升的 `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`。
2. SegResNetDS 暂不接入 `configs/inference/osteo_vision.yml`，只作为建模报告中的对照证据。
3. 下一轮模型训练应优先做 nnU-Net v2/DynUNet 高分辨率或 patch 级路线，而不是继续在 64³ 代理缓存上堆更多轻量模型。
4. 报告中必须继续标明：D025 是 CBCT lesion-mask 代理数据，不是术中 ICG 颌骨骨髓炎目标域数据。
